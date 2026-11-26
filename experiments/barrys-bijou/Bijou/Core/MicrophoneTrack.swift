import AVFoundation
import Accelerate
import Foundation

enum ReactionSignal {
    static func peak(_ buffer: AVAudioPCMBuffer) -> Float {
        guard let channels = buffer.floatChannelData, buffer.frameLength > 0 else { return 0 }
        let count = Int(buffer.format.channelCount)
        var peak: Float = 0
        for c in 0..<count {
            let ptr = buffer.format.isInterleaved ? channels[0] + c : channels[c]
            var value: Float = 0
            vDSP_maxmgv(ptr, vDSP_Stride(buffer.stride), &value, vDSP_Length(buffer.frameLength))
            peak = max(peak, value)
        }
        return peak
    }

    /// Check decoded samples, including legacy AAC files. Stop early once there is clear signal.
    static func quietMessage(at url: URL) throws -> String? {
        let file = try AVAudioFile(forReading: url, commonFormat: .pcmFormatFloat32, interleaved: false)
        guard let buffer = AVAudioPCMBuffer(pcmFormat: file.processingFormat, frameCapacity: 8192) else {
            throw BijouError("Could not inspect the recorded audio.")
        }
        var maximum: Float = 0
        while file.framePosition < file.length {
            try file.read(into: buffer, frameCount: min(8192, AVAudioFrameCount(file.length - file.framePosition)))
            if buffer.frameLength == 0 { break }
            maximum = max(maximum, peak(buffer))
            if maximum >= 0.0032 { return nil } // About −50 dBFS.
        }
        return maximum == 0 ? "This recording contains silence. Check the microphone input and record a new take."
            : "This recording has a very weak signal. Check the microphone input and speak closer to it."
    }
}

/// The input tap writes on the audio thread; the UI reads progress and closes the file.
final class MicrophoneTrack: @unchecked Sendable {
    private let lock = NSLock()
    private var file: AVAudioFile?
    private var frames: AVAudioFramePosition = 0
    private let rate: Double
    private let cap: AVAudioFramePosition
    private var failure: String?
    private var recentPeak: Float = 0

    init(url: URL, format: AVAudioFormat) throws {
        rate = format.sampleRate
        guard rate > 0, format.channelCount > 0 else { throw BijouError("No microphone input is available.") }
        cap = AVAudioFramePosition(rate * ReactionStore.limit)
        var settings = ReactionStore.recordingSettings
        settings[AVSampleRateKey] = rate
        settings[AVNumberOfChannelsKey] = format.channelCount
        file = try AVAudioFile(forWriting: url, settings: settings, commonFormat: format.commonFormat,
                               interleaved: format.isInterleaved)
    }

    func append(_ buffer: AVAudioPCMBuffer) {
        lock.lock(); defer { lock.unlock() }
        guard let file, failure == nil, frames < cap else { return }
        let original = buffer.frameLength
        guard original > 0 else { return }
        buffer.frameLength = min(original, AVAudioFrameCount(cap - frames))
        defer { buffer.frameLength = original }
        do { try file.write(from: buffer); frames += AVAudioFramePosition(buffer.frameLength)
            recentPeak = max(recentPeak * 0.85, ReactionSignal.peak(buffer))
        }
        catch { failure = "Could not write microphone samples: \(error.localizedDescription)" }
    }
    var progress: (seconds: Double, error: String?, peak: Float) {
        lock.lock(); defer { lock.unlock() }
        return (Double(frames) / rate, failure, recentPeak)
    }
    func close() {
        lock.lock(); defer { lock.unlock() }
        file = nil
    }
}
