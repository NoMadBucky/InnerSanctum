// The Bijou streetcar rag, performed on the macOS General MIDI acoustic piano.
// Built with the animator and its cue sheet by Tools/render_opening_reel.sh.
import AVFoundation
import Foundation

func renderPiano(to url: URL) throws {
    let rate = 44100.0, beat = ReelCue.beat
    struct Event { let frame: Int; let key, velocity: UInt8 }
    var notes: [Event] = []
    func strike(_ time: Double, _ pitch: Int, _ duration: Double, _ velocity: Int) {
        notes.append(Event(frame: Int((time*rate).rounded()), key: UInt8(pitch), velocity: UInt8(velocity)))
        notes.append(Event(frame: Int(((time+duration)*rate).rounded()), key: UInt8(pitch), velocity: 0))
    }
    func chord(_ time: Double, _ pitches: [Int], _ duration: Double, _ velocity: Int) {
        for (i, key) in pitches.enumerated() { strike(time+Double(i)*0.008, key, duration, velocity) }
    }
    chord(0.015, [48,67,72], 0.55, 55)
    chord(2*beat+0.015, [52,67,76], 0.55, 58)
    chord(4*beat+0.015, [43,65,71], 0.62, 60)

    let bass = [48,52,53,42,43,45,50,43]
    let voicings = [[64,67,69],[62,67,71],[60,65,69],[60,63,69],
                    [60,64,67],[61,64,67],[60,65,69],[59,65,67]]
    let tune = [[76,79,81],[79,76,74],[77,81,84],[81,78,75],
                [76,79,84],[85,82,79],[81,77,74],[71,74,77]]
    for bar in bass.indices {
        let t = ReelCue.streetCut + Double(2*bar)*beat
        if bar == 2 {
            // Brake to a clipped F; leave the sliding doors a breath of silence.
            chord(ReelCue.carStop, [41,60,65,69], 0.19, 65)
            chord(ReelCue.doorsOpen, [60,65,69,81], 0.13, 74)
            strike(ReelCue.doorsOpen+beat/2, 84, 0.15, 70)
            continue
        }
        if bar == 6 {
            // Hand the high-stepping tune to the departing car for a beat.
            strike(ReelCue.departure, 50, 0.35, 68)
            for (j, key) in [74,77,81,84].enumerated() {
                strike(t+Double(j)*beat/2, key, 0.17, 64+j*3)
            }
            chord(t+beat, [60,65,69], 0.18, 54)
            continue
        }
        if bar == 7 {
            // A clipped dominant seventh and a B pickup leave space for the tonic.
            chord(ReelCue.title, [43,55,65,71,79], 0.27, 70)
            chord(ReelCue.title+beat, [55,65,71,86], 0.17, 73)
            strike(ReelCue.title+1.5*beat, 83, 0.13, 78)
            continue
        }
        strike(t, bass[bar], 0.31, 61)
        chord(t+beat, voicings[bar], 0.23, 53)
        strike(t, tune[bar][0], 0.29, 76)
        strike(t+0.36, tune[bar][1], 0.27, 70)
        strike(t+0.76, tune[bar][2], 0.19, 67)
    }
    // Bass octaves and a rolled C-major triad; let the high C ring into black.
    chord(ReelCue.lastChord, [36,48,55,64,67,72,84], 0.76, 80)
    notes.sort { $0.frame < $1.frame }

    let engine = AVAudioEngine(), piano = AVAudioUnitSampler()
    let format = AVAudioFormat(standardFormatWithSampleRate: rate, channels: 2)!
    engine.attach(piano)
    piano.overallGain = 8
    if #available(macOS 27, *) { try engine.connectNode(piano, to: engine.mainMixerNode, format: format) }
    else { engine.connect(piano, to: engine.mainMixerNode, format: format) }
    let bank = URL(fileURLWithPath: "/System/Library/Components/CoreAudio.component/Contents/Resources/gs_instruments.dls")
    try piano.loadSoundBankInstrument(at: bank, program: 0, bankMSB: UInt8(kAUSampler_DefaultMelodicBankMSB), bankLSB: 0)
    try engine.enableManualRenderingMode(.offline, format: format, maximumFrameCount: 1024)
    try engine.start()
    var settings = format.settings
    settings[AVLinearPCMIsNonInterleaved] = false
    let file = try AVAudioFile(forWriting: url, settings: settings)
    defer { file.close(); engine.stop() }
    let buffer = AVAudioPCMBuffer(pcmFormat: format, frameCapacity: 1024)!
    let end = Int(ReelCue.end*rate)
    var index = 0, frame = 0
    while frame < end {
        while index < notes.count && notes[index].frame == frame {
            let e = notes[index]
            if e.velocity == 0 { piano.stopNote(e.key, onChannel: 0) }
            else { piano.startNote(e.key, withVelocity: e.velocity, onChannel: 0) }
            index += 1
        }
        let next = index < notes.count ? notes[index].frame : end
        let count = min(1024, next-frame)
        guard try engine.renderOffline(AVAudioFrameCount(count), to: buffer) == .success else { fatalError("Piano render failed") }
        for i in 0..<count where end-frame-i < 11025 {
            for channel in 0..<2 { buffer.floatChannelData![channel][i] *= Float(end-frame-i)/11025 }
        }
        try file.write(from: buffer)
        frame += count
    }
}
