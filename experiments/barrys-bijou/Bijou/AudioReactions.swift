import AVFoundation
import SwiftUI

#if os(iOS)
@MainActor
private enum ReactionSession {
    static var tail: Task<Void, Never>?
    static func enqueue(_ operation: @escaping @Sendable () async throws -> Void) -> Task<Void, Error> {
        let previous = tail
        let next = Task.detached {
            await previous?.value
            try await operation()
        }
        tail = Task { _ = await next.result }
        return next
    }
    static func activate(recording: Bool) -> Task<Void, Error> {
        enqueue {
            let session = AVAudioSession.sharedInstance()
            try session.setCategory(recording ? .record : .playback, mode: recording ? .measurement : .spokenAudio)
            if #available(iOS 27, *) {
                guard try await session.activate(options: []) else { throw BijouError("Audio session could not start.") }
            } else { try session.setActive(true) }
        }
    }
    static func release() {
        _ = enqueue {
            let session = AVAudioSession.sharedInstance()
            if #available(iOS 27, *) {
                _ = try await session.deactivate(options: .notifyOthersOnDeactivation)
            } else { try session.setActive(false, options: .notifyOthersOnDeactivation) }
        }
    }
}
#endif

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
    private var playbackRequest: UUID?
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
        defer { if permissionRequest == request { requesting = false; permissionRequest = nil } }
        guard permitted else { notice = "Allow Bijou to use the microphone in Settings → Privacy & Security → Microphone."; return }
        do {
            #if os(iOS)
            let session = AVAudioSession.sharedInstance()
            // A reaction uses only input. Playback sets its own category when requested.
            sessionActive = true
            try await ReactionSession.activate(recording: true).value
            guard permissionRequest == request else { return }
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
        } catch { if permissionRequest == request { discard(); notice = error.localizedDescription } }
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
    func play(_ take: AudioReaction) async {
        guard !recording, !requesting else { return }
        let wasPlaying = playing == take.id
        stopPlayback()
        guard !wasPlaying else { return }
        let request = UUID()
        playbackRequest = request
        do {
            #if os(iOS)
            let session = AVAudioSession.sharedInstance()
            sessionActive = true
            try await ReactionSession.activate(recording: false).value
            guard playbackRequest == request else { return }
            output = session.currentRoute.outputs.map(\.portName).joined(separator: ", ")
            if session.outputVolume == 0 { output += " · Media volume is zero" }
            #else
            output = "system sound output"
            #endif
            let url = store.audio(take.id, draft: take.id == draftID)
            let (p, warning) = try await Task.detached {
                let warning = try ReactionSignal.quietMessage(at: url)
                let p = try AVAudioPlayer(contentsOf: url)
                guard p.prepareToPlay() else { throw BijouError("Cannot prepare this recording.") }
                return (p, warning)
            }.value
            guard playbackRequest == request else { return }
            player = p; playing = take.id; p.delegate = self
            let started = await Task.detached { p.play() }.value
            guard playbackRequest == request else { p.stop(); return }
            guard started else { throw BijouError("Cannot play this recording.") }
            notice = warning
        } catch { if playbackRequest == request { stopPlayback(); notice = error.localizedDescription } }
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
    func stopPlayback() { playbackRequest = nil; player?.stop(); player = nil; playing = nil; releaseSession() }
    private func releaseSession() {
        #if os(iOS)
        guard sessionActive else { return }
        ReactionSession.release()
        sessionActive = false
        #endif
    }
}

struct AudioReactions: View {
    @StateObject private var room: ReactionRoom
    @Environment(\.scenePhase) private var phase
    @State private var deleting: AudioReaction?
    @State private var transcribing: AudioReaction?
    @EnvironmentObject private var studio: Studio
    @State private var filing: UUID?
    @State private var download: Task<Void, Never>?
    @State private var downloading: UUID?
    let archived: [ArchivedReaction]
    let film: FilmRef
    let viewed: String?
    let focusedTake: UUID?
    @Binding private var recordRequest: UUID?
    init(store: ReactionStore, viewed: String?, film: FilmRef, archived: [ArchivedReaction], focusedTake: UUID? = nil,
         recordRequest: Binding<UUID?> = .constant(nil)) {
        _recordRequest = recordRequest
        self.focusedTake = focusedTake
        self.archived = archived
        _room = StateObject(wrappedValue: ReactionRoom(store: store)); self.viewed = viewed; self.film = film
    }
    private func clock(_ t: Double) -> String {
        if t > 0 && t < 1 { return "<1s" }
        return String(format: "%d:%02d", Int(t) / 60, Int(t) % 60)
    }
    private var takes: [AudioReaction] {
        var merged = Dictionary(room.takes.map { ($0.id, $0) }, uniquingKeysWith: { first, _ in first })
        for record in archived { merged[record.id] = record.take }
        return merged.values.filter { focusedTake == nil || $0.id == focusedTake }.sorted { $0.recordedAt > $1.recordedAt }
    }
    private func downloadAndPlay(_ take: AudioReaction, remote: ArchivedReaction?) {
        guard downloading == nil else { return }
        guard let creds = studio.credentials, creds.library == studio.journal?.base.library else {
            room.notice = "Connect to the paired Mac to download this recording."; return
        }
        downloading = take.id
        download = Task {
            defer { downloading = nil }
            do {
                let receipt = try remote?.receipt ?? room.store.receipt(take.id)
                let data = try await HomeClient(creds).archivedAudio(take.id)
                try Task.checkCancellation()
                let store = room.store
                try await Task.detached { try store.cache(data, take: take, receipt: receipt) }.value
                room.reload()
                if !Task.isCancelled { await room.play(take) }
            } catch {
                if !Task.isCancelled { room.notice = "Could not download from the paired Mac: \(error.localizedDescription)" }
            }
        }
    }
    @ViewBuilder private var recordingControls: some View {
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
            }.buttonStyle(JournalActionStyle()).disabled(room.requesting)
        }
    }

    private func takeRow(_ take: AudioReaction) -> some View {
        let remote = archived.first { $0.id == take.id }
        let filed = remote != nil || room.store.filed(take.id)
        let local = FileManager.default.fileExists(atPath: room.store.audio(take.id).path)
        return VStack(alignment: .leading, spacing: 3) {
            Text(take.recordedAt.formatted(date: .abbreviated, time: .shortened)).font(.subheadline.bold())
            if let day = take.viewingDate { Text("Viewing: \(day)").font(.caption) }
            if focusedTake != nil {
                transcriptSummary(take, reviewed: remote?.transcript)
                if !filed { Label("Only on this device", systemImage: "internaldrive") }
            }
            if local {
                Button(room.playing == take.id ? "Stop playback" : "Play · \(clock(take.seconds))") { Task { await room.play(take) } }
                    .disabled(room.recording || room.requesting)
            } else if filed {
                Button(downloading == take.id ? "Downloading…" : "Download and play · \(clock(take.seconds))") {
                    downloadAndPlay(take, remote: remote)
                }.disabled(downloading != nil || room.recording || room.requesting)
            }
            filingControls(take, filed: filed)
            if local || remote?.transcript != nil {
                Button(remote?.transcript != nil ? "Read transcript" : "Transcribe / review") {
                    room.stopPlayback(); transcribing = take
                }.disabled(room.recording || room.requesting)
            }
            if local {
                Button(role: .destructive) { deleting = take } label: {
                    Label(filed ? "Remove from this device" : "Delete recording", systemImage: "trash")
                }.disabled(filing == take.id)
            }
        }
    }

    @ViewBuilder private func transcriptSummary(_ take: AudioReaction, reviewed: String?) -> some View {
        if let reviewed {
            Text("Reviewed transcript").font(.headline)
            Text(reviewed).textSelection(.enabled)
        }
        if let draft = try? room.store.draftTranscript(take.id), !draft.isEmpty, draft != reviewed {
            Text("Local draft").font(.headline)
            Text(draft).textSelection(.enabled)
        } else if reviewed == nil { Text("No transcript yet.").foregroundStyle(.secondary) }
    }

    @ViewBuilder private func filingControls(_ take: AudioReaction, filed: Bool) -> some View {
        if filed {
            Label(studio.journal?.base.origin == "personal" ? "Filed in Personal" : "Filed in practice library", systemImage: "checkmark.circle")
        } else if studio.journal?.base.fixtureReactionFiling == true || studio.journal?.base.personalReactionFiling == true,
                  let creds = studio.credentials, creds.library == studio.journal?.base.library {
            let personal = studio.journal?.base.personalReactionFiling == true
            Button(filing == take.id ? "Filing…" : personal ? "File in Personal" : "File in practice library") {
                filing = take.id
                Task {
                    defer { filing = nil }
                    do {
                        let receipt = try await HomeClient(creds).fileReaction(take, url: room.store.audio(take.id),
                                                                              film: film, library: creds.library, personal: personal)
                        try room.store.saveReceipt(receipt); room.notice = nil; room.reload()
                    } catch { room.notice = error.localizedDescription }
                }
            }.disabled(filing != nil)
        }
    }

    private var reactionList: some View {
        VStack(alignment: .leading, spacing: 10) {
            if focusedTake == nil { recordingControls }
            if focusedTake != nil && takes.isEmpty { Text("This recording is no longer on this device.") }
            ForEach(takes) { take in takeRow(take) }
            if room.playing != nil { Label("Playing through \(room.output)", systemImage: "speaker.wave.2").font(.caption) }
            if let message = room.notice { Text(message).font(.callout) }
            if room.needsUnmute { Button("Unmute microphone") { room.unmute() } }
        }
    }

    private var presentedList: some View {
        reactionList.reactionTranscriptSheet(selection: $transcribing, store: room.store, archived: archived)
            .alert("Delete recording?", isPresented: deletePrompt, presenting: deleting) { take in
                Button("Delete", role: .destructive) { room.delete(take) }
                Button("Cancel", role: .cancel) {}
            } message: { take in
                Text("Remove the take recorded \(take.recordedAt.formatted()) from this device?")
            }
    }

    private var deletePrompt: Binding<Bool> {
        Binding(get: { deleting != nil }, set: { if !$0 { deleting = nil } })
    }

    var body: some View {
        presentedList
        .onAppear { room.reload() }
        .onChange(of: recordRequest, initial: true) { _, request in
            guard request != nil else { return }
            recordRequest = nil
            if room.preview != nil {
                room.notice = "Keep or discard your current take before recording another."
            } else {
                Task { await room.record(viewed: viewed) }
            }
        }
        .onDisappear { download?.cancel(); room.discard() }
        .onChange(of: phase) { _, p in if p == .background && room.recording { room.stop() } }
        .task(id: room.recording) {
            while room.recording && !Task.isCancelled {
                room.tick()
                do { try await Task.sleep(for: .milliseconds(200)) } catch { return }
            }
        }
    }
    @ViewBuilder private func previewActions(_ take: AudioReaction) -> some View {
        Button(room.playing == take.id ? "Stop preview" : "Preview") { Task { await room.play(take) } }
        Button("Keep") { room.keep() }.buttonStyle(.borderedProminent)
        Button("Discard", role: .destructive) { room.discard() }
    }
}
