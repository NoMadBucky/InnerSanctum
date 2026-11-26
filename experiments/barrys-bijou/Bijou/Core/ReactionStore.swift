import AVFoundation
import CryptoKit
import Foundation

struct AudioReaction: Codable, Identifiable {
    let id: UUID
    let recordedAt: Date
    let viewingDate: String?
    let seconds: Double
}

struct FilingReceipt: Codable {
    let id, path, sha256: String
    let take: UUID
}

struct ArchivedReaction: Codable, Identifiable {
    let id: UUID
    let recordedAt: Date
    let viewingDate: String?
    let seconds: Double
    let receipt: FilingReceipt
    let revision: String?
    let transcript: String?
    var take: AudioReaction { AudioReaction(id: id, recordedAt: recordedAt, viewingDate: viewingDate, seconds: seconds) }
}

/// A kept take is one directory: the recording and its metadata become visible together.
struct ReactionStore {
    static let limit: TimeInterval = 120
    let directory: URL
    init(root: URL, library: String, film: FilmRef) {
        let scope = [library, film.path, film.personalID ?? ""].map {
            SHA256.hash(data: Data($0.utf8)).map { String(format: "%02x", $0) }.joined()
        }.joined(separator: "-")
        directory = root.appendingPathComponent("Reactions").appendingPathComponent(scope)
    }

    private func folder(_ id: UUID, draft: Bool) -> URL {
        directory.appendingPathComponent((draft ? ".draft-" : "") + id.uuidString)
    }
    func audio(_ id: UUID, draft: Bool = false) -> URL {
        let dir = folder(id, draft: draft)
        let legacy = dir.appendingPathComponent("reaction.m4a")
        if !draft && FileManager.default.fileExists(atPath: legacy.path) { return legacy }
        return dir.appendingPathComponent("reaction.wav")
    }
    static let recordingSettings: [String: Any] = [
        AVFormatIDKey: kAudioFormatLinearPCM, AVSampleRateKey: 44_100,
        AVNumberOfChannelsKey: 1, AVLinearPCMBitDepthKey: 16,
        AVLinearPCMIsFloatKey: false, AVLinearPCMIsBigEndianKey: false
    ]
    func recordedSeconds(_ id: UUID, expected: Double) throws -> Double {
        let file = try AVAudioFile(forReading: audio(id, draft: true))
        let seconds = Double(file.length) / file.processingFormat.sampleRate
        guard seconds.isFinite, seconds >= 0.25, seconds + 0.75 >= expected else {
            throw BijouError("The microphone recording was empty or cut short. No take was saved. Please try again.")
        }
        return min(seconds, Self.limit)
    }
    func begin(_ id: UUID) throws {
        try FileManager.default.createDirectory(at: directory, withIntermediateDirectories: true,
                                                 attributes: [.posixPermissions: 0o700])
        try FileManager.default.createDirectory(at: folder(id, draft: true), withIntermediateDirectories: false,
                                                 attributes: [.posixPermissions: 0o700])
    }
    func discard(_ id: UUID) throws {
        let draft = folder(id, draft: true)
        if FileManager.default.fileExists(atPath: draft.path) { try FileManager.default.removeItem(at: draft) }
    }
    func delete(_ id: UUID) throws {
        try FileManager.default.removeItem(at: filed(id) ? audio(id) : folder(id, draft: false))
    }
    func receipt(_ id: UUID) throws -> FilingReceipt {
        try JSONDecoder().decode(FilingReceipt.self, from: Data(contentsOf: folder(id, draft: false).appendingPathComponent("filed.json")))
    }
    func cache(_ data: Data, take: AudioReaction, receipt: FilingReceipt) throws {
        guard receipt.take == take.id, SHA256.hash(data: data).map({ String(format: "%02x", $0) }).joined() == receipt.sha256
        else { throw BijouError("The downloaded recording did not match its filing receipt.") }
        let dir = folder(take.id, draft: false)
        try FileManager.default.createDirectory(at: dir, withIntermediateDirectories: true, attributes: [.posixPermissions: 0o700])
        try JSONEncoder().encode(take).write(to: dir.appendingPathComponent("take.json"), options: .atomic)
        try saveReceipt(receipt)
        try data.write(to: audio(take.id), options: .atomic)
    }
    func saveReceipt(_ receipt: FilingReceipt) throws {
        try JSONEncoder().encode(receipt).write(to: folder(receipt.take, draft: false).appendingPathComponent("filed.json"), options: .atomic)
    }
    func filed(_ id: UUID) -> Bool {
        FileManager.default.fileExists(atPath: folder(id, draft: false).appendingPathComponent("filed.json").path)
    }
    func draftTranscript(_ id: UUID) throws -> String? {
        let url = folder(id, draft: false).appendingPathComponent("transcript.txt")
        guard FileManager.default.fileExists(atPath: url.path) else { return nil }
        return try String(contentsOf: url, encoding: .utf8)
    }
    func saveTranscript(_ text: String, for id: UUID) throws {
        try text.write(to: folder(id, draft: false).appendingPathComponent("transcript.txt"), atomically: true, encoding: .utf8)
    }
    func keep(_ take: AudioReaction) throws {
        guard take.seconds.isFinite, take.seconds > 0, take.seconds <= Self.limit,
              abs(try recordedSeconds(take.id, expected: take.seconds) - take.seconds) < 0.01
        else { throw BijouError("There is no usable recording to keep.") }
        let draft = folder(take.id, draft: true)
        try JSONEncoder().encode(take).write(to: draft.appendingPathComponent("take.json"), options: .atomic)
        try FileManager.default.moveItem(at: draft, to: folder(take.id, draft: false))
    }
    func list() throws -> [AudioReaction] {
        guard FileManager.default.fileExists(atPath: directory.path) else { return [] }
        let files = try FileManager.default.contentsOfDirectory(at: directory, includingPropertiesForKeys: nil,
                                                               options: .skipsHiddenFiles)
        return try files.compactMap { file -> AudioReaction? in
            guard let id = UUID(uuidString: file.lastPathComponent) else { return nil }
            let take = try JSONDecoder().decode(AudioReaction.self, from: Data(contentsOf: file.appendingPathComponent("take.json")))
            guard take.id == id else { throw BijouError("A saved reaction could not be identified.") }
            return take
        }.sorted { $0.recordedAt > $1.recordedAt }
    }
}
