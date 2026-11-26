import AVFoundation
import SwiftUI

@MainActor
private final class ReactionRoom: NSObject, ObservableObject, AVAudioPlayerDelegate {
    @Published var takes: [AudioReaction] = []
    @Published var recording = false
    @Published var finishing = false
    @Published var requesting = false
    @Published var elapsed: TimeInterval = 0
    @Published var preview: AudioReaction?
    @Published var playing: UUID?
    @Published var inputLevel = 0.0
    @Published var needsUnmute = false
    @Published var output = ""
    @Published var notice: String?
    let store: ReactionStore
    private var engine: AVAudioEngine?
    private var track: MicrophoneTrack?
    private var lastInput = ContinuousClock.now
    private(set) var inputName = "the selected microphone"
    private var player: AVAudioPlayer?
    private var draftID: UUID?
    private var started = Date()
    private var viewing: String?
    private var permissionRequest: UUID?
    private var sessionActive = false

    init(store: ReactionStore) { self.store = store }

    func reload() { do { takes = try store.list() } catch { notice = error.localizedDescription } }

    func unmute() {
        do {
            try AVAudioApplication.shared.setInputMuted(false)
            needsUnmute = AVAudioApplication.shared.isInputMuted
            if !needsUnmute { notice = nil }
        } catch { notice = error.localizedDescription }
    }

    func record(viewed: String?) async {
        guard !requesting, !recording, draftID == nil else { return }
        stopPlayback()
        let request = UUID()
        permissionRequest = request
        requesting = true; notice = nil
        #if os(iOS)
        let permitted = await AVAudioApplication.requestRecordPermission()
        #else
        let permitted = await AVCaptureDevice.requestAccess(for: .audio)
        #endif
        guard permissionRequest == request else { return }
        requesting = false; permissionRequest = nil
        guard permitted else { notice = "Allow Bijou to use the microphone in Settings → Privacy & Security → Microphone."; return }
        do {
            #if os(iOS)
            let session = AVAudioSession.sharedInstance()
            // A reaction uses only input. Playback sets its own category when requested.
            try session.setCategory(.record, mode: .measurement)
            try session.setActive(true)
            sessionActive = true
            if let builtIn = session.availableInputs?.first(where: { $0.portType == .builtInMic }) {
                try session.setPreferredInput(builtIn)
            }
            guard let port = session.currentRoute.inputs.first else { throw BijouError("iOS has not routed a microphone to Bijou.") }
            inputName = port.portName
            #endif
            needsUnmute = AVAudioApplication.shared.isInputMuted
            guard !needsUnmute else { throw BijouError("Bijou’s microphone input is muted. Unmute it before recording.") }
            let id = UUID()
            try store.begin(id); draftID = id
            let engine = AVAudioEngine()
            let input = engine.inputNode
            let format = input.outputFormat(forBus: 0)
            let track = try MicrophoneTrack(url: store.audio(id, draft: true), format: format)
            try Self.attach(input, track: track)
            self.engine = engine; self.track = track
            engine.prepare()
            try engine.start()
            lastInput = .now; started = Date(); viewing = viewed; elapsed = 0; inputLevel = 0; recording = true
        } catch { discard(); notice = error.localizedDescription }
    }

    nonisolated private static func attach(_ input: AVAudioInputNode, track: MicrophoneTrack) throws {
        if #available(iOS 27, macOS 27, *) {
            try input.installAudioTap(onBus: 0, bufferSize: 2048, format: nil) { buffer, _ in
                track.append(AVAudioPCMBuffer(copying: buffer))
            }
        } else {
            input.installTap(onBus: 0, bufferSize: 2048, format: nil) { buffer, _ in track.append(buffer) }
        }
    }
    func tick() {
        guard let progress = track?.progress else { return }
        inputLevel = min(1, max(0, (20 * log10(Double(max(progress.peak, 0.00001))) + 60) / 60))
        if progress.seconds > elapsed { elapsed = progress.seconds; lastInput = .now }
        if progress.error != nil || elapsed >= ReactionStore.limit { stop() }
        else if lastInput.duration(to: .now) > .seconds(4) {
            stop()
            notice = "Audio stopped arriving from \(inputName). Check your input device and try again."
        }
    }
    private func closeInput() {
        engine?.stop(); engine?.inputNode.removeTap(onBus: 0); engine = nil
        track?.close(); track = nil
    }
    func stop() {
        guard recording, !finishing, let id = draftID, let track else { return }
        finishing = true
        closeInput()
        let captured = track.progress
        recording = false; finishing = false; releaseSession()
        do {
            if let error = captured.error { throw BijouError(error) }
            guard captured.seconds > 0 else { throw BijouError("No audio arrived from \(inputName). Check your input device and try again.") }
            elapsed = try store.recordedSeconds(id, expected: captured.seconds)
            notice = try ReactionSignal.quietMessage(at: store.audio(id, draft: true))
            preview = AudioReaction(id: id, recordedAt: started, viewingDate: viewing, seconds: elapsed)
        } catch { discard(); notice = error.localizedDescription }
    }
    func keep() {
        guard let preview else { return }
        stopPlayback()
        do {
            try store.keep(preview)
            self.preview = nil; draftID = nil; elapsed = 0; notice = nil; reload()
        } catch { notice = "Could not keep this take: \(error.localizedDescription)" }
    }
    func discard() {
        permissionRequest = nil; requesting = false
        closeInput(); recording = false; finishing = false
        stopPlayback()
        if let draftID {
            do { try store.discard(draftID) } catch { notice = error.localizedDescription }
        }
        draftID = nil; preview = nil; elapsed = 0
    }
    func play(_ take: AudioReaction) {
        let wasPlaying = playing == take.id
        stopPlayback()
        guard !wasPlaying, !recording else { return }
        do {
            #if os(iOS)
            let session = AVAudioSession.sharedInstance()
            try session.setCategory(.playback, mode: .spokenAudio); try session.setActive(true)
            sessionActive = true
            output = session.currentRoute.outputs.map(\.portName).joined(separator: ", ")
            if session.outputVolume == 0 { output += " · Media volume is zero" }
            #else
            output = "system sound output"
            #endif
            let url = store.audio(take.id, draft: take.id == draftID)
            let warning = try ReactionSignal.quietMessage(at: url)
            let p = try AVAudioPlayer(contentsOf: url)
            p.delegate = self
            p.volume = 1
            guard p.prepareToPlay(), p.play() else { throw BijouError("Cannot play this recording.") }
            player = p; playing = take.id; notice = warning
        } catch { releaseSession(); notice = error.localizedDescription }
    }
    func delete(_ take: AudioReaction) {
        if playing == take.id { stopPlayback() }
        do { try store.delete(take.id); notice = nil; reload() }
        catch { notice = "Could not delete recording: \(error.localizedDescription)" }
    }
    nonisolated func audioPlayerDidFinishPlaying(_ player: AVAudioPlayer, successfully flag: Bool) {
        Task { @MainActor in if self.player === player {
            self.stopPlayback()
            if !flag { self.notice = "Playback ended before the recording finished." }
        } }
    }
    nonisolated func audioPlayerDecodeErrorDidOccur(_ player: AVAudioPlayer, error: Error?) {
        Task { @MainActor in if self.player === player {
            self.stopPlayback(); self.notice = "The audio file could not be decoded."
        } }
    }
    func stopPlayback() { player?.stop(); player = nil; playing = nil; releaseSession() }
    private func releaseSession() {
        #if os(iOS)
        guard sessionActive else { return }
        try? AVAudioSession.sharedInstance().setActive(false, options: .notifyOthersOnDeactivation)
        sessionActive = false
        #endif
    }
}

struct AudioReactions: View {
    @StateObject private var room: ReactionRoom
    @Environment(\.scenePhase) private var phase
    @State private var deleting: AudioReaction?
    let viewed: String?
    init(store: ReactionStore, viewed: String?) {
        _room = StateObject(wrappedValue: ReactionRoom(store: store)); self.viewed = viewed
    }
    private func clock(_ t: Double) -> String {
        if t > 0 && t < 1 { return "<1s" }
        return String(format: "%d:%02d", Int(t) / 60, Int(t) % 60)
    }
    var body: some View {
        VStack(alignment: .leading, spacing: 10) {
            Text("Audio reactions").font(.headline)
            Text("Up to two minutes per take · Saved on this device").font(.caption).foregroundStyle(.secondary)
            if room.recording {
                Text("Recording \(clock(room.elapsed)) / 2:00").monospacedDigit()
                ProgressView(value: room.inputLevel) { Text("Microphone · \(room.inputName)") }
                Button(room.finishing ? "Finishing recording…" : "Stop recording") { room.stop() }.disabled(room.finishing)
            } else if let take = room.preview {
                Text("New take · \(clock(take.seconds))").font(.subheadline)
                ViewThatFits(in: .horizontal) {
                    HStack { previewActions(take) }
                    VStack(alignment: .leading) { previewActions(take) }
                }
            } else {
                Button { Task { await room.record(viewed: viewed) } } label: {
                    Label(room.requesting ? "Waiting for microphone…" : "Record reaction", systemImage: "mic")
                }.disabled(room.requesting)
            }
            ForEach(room.takes) { take in
                VStack(alignment: .leading, spacing: 3) {
                    Text(take.recordedAt.formatted(date: .abbreviated, time: .shortened)).font(.subheadline.bold())
                    if let day = take.viewingDate { Text("Viewing: \(day)").font(.caption) }
                    Button(room.playing == take.id ? "Stop playback" : "Play · \(clock(take.seconds))") { room.play(take) }
                        .disabled(room.recording || room.requesting)
                    Button(role: .destructive) { deleting = take } label: {
                        Label("Delete recording", systemImage: "trash")
                    }
                }
            }
            if room.playing != nil { Label("Playing through \(room.output)", systemImage: "speaker.wave.2").font(.caption) }
            if let message = room.notice { Text(message).font(.callout) }
            if room.needsUnmute { Button("Unmute microphone") { room.unmute() } }
        }
        .onAppear { room.reload() }
        .alert("Delete recording?", isPresented: Binding(get: { deleting != nil }, set: { if !$0 { deleting = nil } }),
               presenting: deleting) { take in
            Button("Delete", role: .destructive) { room.delete(take) }
            Button("Cancel", role: .cancel) {}
        } message: { take in
            Text("Remove the take recorded \(take.recordedAt.formatted()) from this device?")
        }
        .onDisappear { room.discard() }
        .onChange(of: phase) { _, p in if p == .background && room.recording { room.stop() } }
        .task(id: room.recording) {
            while room.recording && !Task.isCancelled {
                room.tick()
                do { try await Task.sleep(for: .milliseconds(200)) } catch { return }
            }
        }
    }
    @ViewBuilder private func previewActions(_ take: AudioReaction) -> some View {
        Button(room.playing == take.id ? "Stop preview" : "Preview") { room.play(take) }
        Button("Keep") { room.keep() }.buttonStyle(.borderedProminent)
        Button("Discard", role: .destructive) { room.discard() }
    }
}
