import AVFoundation
import XCTest
@testable import BijouCore

final class ReactionStoreTests: XCTestCase {
    func testOfflineRelaunchKeepsTwoPlayableTakesAndIsolatesLibraries() throws {
        let root = FileManager.default.temporaryDirectory.appendingPathComponent(UUID().uuidString)
        defer { try? FileManager.default.removeItem(at: root) }
        let film = FilmRef(path: "Resources/videos/8100001.md", personalID: "bho:8100001")
        func open(_ library: String = "fixture") -> ReactionStore { ReactionStore(root: root, library: library, film: film) }
        let store = open()
        let format = try XCTUnwrap(AVAudioFormat(standardFormatWithSampleRate: 44100, channels: 1))
        let buffer = try XCTUnwrap(AVAudioPCMBuffer(pcmFormat: format, frameCapacity: 4410))
        buffer.frameLength = 4410
        for n in 0..<4410 { buffer.floatChannelData![0][n] = Float(sin(Double(n) * 0.1) * 0.1) }
        var ids: [UUID] = []
        for i in 0..<3 {
            let id = UUID()
            try store.begin(id)
            do {
                let audio = try AVAudioFile(forWriting: store.audio(id, draft: true),
                                            settings: [AVFormatIDKey: kAudioFormatMPEG4AAC, AVSampleRateKey: 44100, AVNumberOfChannelsKey: 1])
                try audio.write(from: buffer)
            }
            XCTAssertEqual(try open().list().count, ids.count)
            if i == 2 {
                try store.discard(id)
                XCTAssertFalse(FileManager.default.fileExists(atPath: store.audio(id, draft: true).path))
            } else {
                let duration = try AVAudioPlayer(contentsOf: store.audio(id, draft: true)).duration
                try store.keep(AudioReaction(id: id, recordedAt: Date(timeIntervalSince1970: Double(i)),
                                             viewingDate: "2026-01-01", seconds: duration))
                ids.append(id)
            }
        }
        let reopened = open()
        let takes = try reopened.list()
        XCTAssertEqual(takes.map(\.id), ids.reversed())
        for take in takes {
            XCTAssertEqual(take.viewingDate, "2026-01-01")
            XCTAssertEqual(try AVAudioPlayer(contentsOf: reopened.audio(take.id)).duration, take.seconds, accuracy: 0.001)
        }
        XCTAssertTrue(try open("personal").list().isEmpty)
        XCTAssertTrue(try ReactionStore(root: root, library: "fixture", film: FilmRef(path: "other", personalID: nil)).list().isEmpty)
    }
}
