import AVFoundation
import CryptoKit
import Foundation

struct AudioReaction: Codable, Identifiable {
    let id: UUID
    let recordedAt: Date
    let viewingDate: String?
    let seconds: Double
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
