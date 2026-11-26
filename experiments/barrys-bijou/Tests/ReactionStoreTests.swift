import AVFoundation
import XCTest
@testable import BijouCore

final class ReactionStoreTests: XCTestCase {
    func testSilentAndAudibleSamplesWithIdenticalDurations() throws {
        let format = try XCTUnwrap(AVAudioFormat(standardFormatWithSampleRate: 48000, channels: 1))
        let buffer = try XCTUnwrap(AVAudioPCMBuffer(pcmFormat: format, frameCapacity: 4800))
        buffer.frameLength = 4800
        for amplitude: Float in [0, 0.0005, 0.2] {
            let url = FileManager.default.temporaryDirectory.appendingPathComponent("\(UUID()).wav")
            defer { try? FileManager.default.removeItem(at: url) }
            let track = try MicrophoneTrack(url: url, format: format)
            for n in 0..<4800 { buffer.floatChannelData![0][n] = amplitude * sin(Float(n) * 0.1) }
            for _ in 0..<10 { track.append(buffer) }
            track.close()
            XCTAssertEqual(track.progress.seconds, 1)
            XCTAssertEqual(track.progress.peak, amplitude, accuracy: 0.0001)
            XCTAssertEqual(try ReactionSignal.quietMessage(at: url) == nil, amplitude == 0.2)
        }
    }
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
                let track = try MicrophoneTrack(url: store.audio(id, draft: true), format: format)
                for _ in 0..<(i == 2 ? 1 : 30) { track.append(buffer) }
                XCTAssertNil(track.progress.error)
                XCTAssertEqual(track.progress.seconds, i == 2 ? 0.1 : 3, accuracy: 0.001)
                track.close()
            }
            XCTAssertEqual(try open().list().count, ids.count)
            if i == 2 {
                XCTAssertThrowsError(try store.recordedSeconds(id, expected: 3))
                XCTAssertThrowsError(try store.keep(AudioReaction(id: id, recordedAt: Date(), viewingDate: nil, seconds: 0.1)))
                try store.discard(id)
                XCTAssertFalse(FileManager.default.fileExists(atPath: store.audio(id, draft: true).path))
            } else {
                let duration = try store.recordedSeconds(id, expected: 3)
                XCTAssertEqual(duration, 3, accuracy: 0.001)
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
        try reopened.delete(ids[0])
        XCTAssertEqual(try open().list().map(\.id), [ids[1]])
        XCTAssertFalse(FileManager.default.fileExists(atPath: store.audio(ids[0]).path))
        XCTAssertTrue(try ReactionStore(root: root, library: "fixture", film: FilmRef(path: "other", personalID: nil)).list().isEmpty)
    }
}
