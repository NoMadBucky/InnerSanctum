// Render the original Bijou streetcar rag with the macOS General MIDI acoustic piano.
// swift Tools/render_reel_piano.swift <temporary.wav>
// afconvert -f m4af -d aac -b 128000 <temporary.wav> Bijou/ReelPiano.m4a
import AVFoundation
import Foundation

let rate = 44100.0
struct Event { let frame: Int; let key, velocity: UInt8 }
var notes: [Event] = []
func strike(_ time: Double, _ pitch: Int, _ duration: Double, _ velocity: Int) {
    notes.append(Event(frame: Int(time * rate), key: UInt8(pitch), velocity: UInt8(velocity)))
    notes.append(Event(frame: Int((time + duration) * rate), key: UInt8(pitch), velocity: 0))
}
func chord(_ time: Double, _ pitches: [Int], _ duration: Double, _ velocity: Int) {
    for (i, key) in pitches.enumerated() { strike(time + Double(i) * 0.008, key, duration, velocity) }
}
chord(0.05, [48, 67, 72], 0.55, 55)
chord(1.05, [52, 67, 76], 0.55, 58)
chord(2.05, [43, 65, 71], 0.66, 60)

// Two beats to the bar; alternate bass and backbeat beneath the syncopated tune.
let beat = 0.5
let bass = [48, 52, 53, 42, 43, 45, 50, 43]
let voicings = [[64, 67, 69], [62, 67, 71], [60, 65, 69], [60, 63, 69],
                [60, 64, 67], [61, 64, 67], [60, 65, 69], [59, 65, 67]]
let tune = [[76, 79, 81], [79, 76, 74], [77, 81, 84], [81, 78, 75],
            [76, 79, 84], [85, 82, 79], [81, 77, 74], [71, 74, 77]]
for bar in 0..<8 {
    let t = Double(3 + bar)
    strike(t, bass[bar], 0.31, 61)
    chord(t + beat, voicings[bar], 0.23, 53)
    strike(t, tune[bar][0], 0.29, 76)
    strike(t + 0.36, tune[bar][1], 0.27, 70)
    strike(t + 0.76, tune[bar][2], 0.19, 67)
}
chord(11.0, [48, 55, 64, 69, 72, 84], 0.53, 67)
notes.sort { $0.frame < $1.frame }

let engine = AVAudioEngine(), piano = AVAudioUnitSampler()
let format = AVAudioFormat(standardFormatWithSampleRate: rate, channels: 2)!
engine.attach(piano)
piano.masterGain = 8  // Leave headroom for the final two-handed chord.
engine.connect(piano, to: engine.mainMixerNode, format: format)
let bank = URL(fileURLWithPath: "/System/Library/Components/CoreAudio.component/Contents/Resources/gs_instruments.dls")
try piano.loadSoundBankInstrument(at: bank, program: 0, bankMSB: UInt8(kAUSampler_DefaultMelodicBankMSB), bankLSB: 0)
try engine.enableManualRenderingMode(.offline, format: format, maximumFrameCount: 1024)
try engine.start()
let file = try AVAudioFile(forWriting: URL(fileURLWithPath: CommandLine.arguments[1]), settings: format.settings)
let buffer = AVAudioPCMBuffer(pcmFormat: format, frameCapacity: 1024)!
let end = Int(12 * rate)
var index = 0, frame = 0
while frame < end {
    while index < notes.count && notes[index].frame == frame {
        let e = notes[index]
        if e.velocity == 0 { piano.stopNote(e.key, onChannel: 0) }
        else { piano.startNote(e.key, withVelocity: e.velocity, onChannel: 0) }
        index += 1
    }
    let next = index < notes.count ? notes[index].frame : end
    let count = min(1024, next - frame)
    guard try engine.renderOffline(AVAudioFrameCount(count), to: buffer) == .success else { fatalError("Piano render failed") }
    for i in 0..<count where end - frame - i < 11025 {
        for channel in 0..<2 { buffer.floatChannelData![channel][i] *= Float(end - frame - i) / 11025 }
    }
    try file.write(from: buffer)
    frame += count
}
file.close()
engine.stop()
