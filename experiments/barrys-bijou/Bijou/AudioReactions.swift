import AVFoundation
import SwiftUI

@MainActor
private final class ReactionRoom: NSObject, ObservableObject, AVAudioRecorderDelegate, AVAudioPlayerDelegate {
    @Published var takes: [AudioReaction] = []
    @Published var recording = false
    @Published var requesting = false
    @Published var elapsed: TimeInterval = 0
    @Published var preview: AudioReaction?
    @Published var playing: UUID?
    @Published var notice: String?
    let store: ReactionStore
    private var recorder: AVAudioRecorder?
    private var player: AVAudioPlayer?
    private var draftID: UUID?
    private var started = Date()
    private var viewing: String?
    private var permissionRequest: UUID?
    private var sessionActive = false

    init(store: ReactionStore) { self.store = store }

    func reload() { do { takes = try store.list() } catch { notice = error.localizedDescription } }

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
            try session.setCategory(.playAndRecord, mode: .default, options: [.defaultToSpeaker])
            try session.setActive(true)
            sessionActive = true
            #endif
            let id = UUID()
            try store.begin(id); draftID = id
            let r = try AVAudioRecorder(url: store.audio(id, draft: true), settings: [
                AVFormatIDKey: kAudioFormatMPEG4AAC, AVSampleRateKey: 44_100,
                AVNumberOfChannelsKey: 1, AVEncoderBitRateKey: 64_000
            ])
            r.delegate = self
            guard r.record(forDuration: ReactionStore.limit) else { throw BijouError("Could not start recording. Check your microphone.") }
            recorder = r; started = Date(); viewing = viewed; elapsed = 0; recording = true
        } catch { discard(); notice = error.localizedDescription }
    }

    func tick() { if let recorder { elapsed = min(recorder.currentTime, ReactionStore.limit) } }
    func stop() { recorder?.stop(); finish(success: true) }
    nonisolated func audioRecorderDidFinishRecording(_ recorder: AVAudioRecorder, successfully flag: Bool) {
        Task { @MainActor in if self.recorder === recorder { self.finish(success: flag) } }
    }
    nonisolated func audioRecorderEncodeErrorDidOccur(_ recorder: AVAudioRecorder, error: Error?) {
        Task { @MainActor in if self.recorder === recorder { self.finish(success: false) } }
    }
    private func finish(success: Bool) {
        guard let id = draftID, recording else { return }
        recorder?.delegate = nil; recorder = nil; recording = false; releaseSession()
        do {
            guard success else { throw BijouError("Recording was interrupted before it could be saved.") }
            let duration = try AVAudioPlayer(contentsOf: store.audio(id, draft: true)).duration
            guard duration.isFinite, duration > 0 else { throw BijouError("The recording was empty. Please try again.") }
            elapsed = min(duration, ReactionStore.limit)
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
        recorder?.delegate = nil; recorder?.stop(); recorder = nil; recording = false
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
            try session.setCategory(.playback); try session.setActive(true)
            sessionActive = true
            #endif
            let p = try AVAudioPlayer(contentsOf: store.audio(take.id, draft: take.id == draftID))
            p.delegate = self
            guard p.play() else { throw BijouError("Cannot play this recording.") }
            player = p; playing = take.id; notice = nil
        } catch { releaseSession(); notice = error.localizedDescription }
    }
    nonisolated func audioPlayerDidFinishPlaying(_ player: AVAudioPlayer, successfully flag: Bool) {
        Task { @MainActor in if self.player === player { self.stopPlayback() } }
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
    let viewed: String?
    init(store: ReactionStore, viewed: String?) {
        _room = StateObject(wrappedValue: ReactionRoom(store: store)); self.viewed = viewed
    }
    private func clock(_ t: Double) -> String { String(format: "%d:%02d", Int(t) / 60, Int(t) % 60) }
    var body: some View {
        VStack(alignment: .leading, spacing: 10) {
            Text("Audio reactions").font(.headline)
            Text("Up to two minutes per take · Saved on this device").font(.caption).foregroundStyle(.secondary)
            if room.recording {
                Text("Recording \(clock(room.elapsed)) / 2:00").monospacedDigit()
                Button("Stop recording") { room.stop() }
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
                }
            }
            if let message = room.notice { Text(message).font(.callout) }
        }
        .onAppear { room.reload() }
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
