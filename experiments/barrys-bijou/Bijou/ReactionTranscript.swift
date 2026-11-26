import AVFoundation
import Speech
import SwiftUI

private enum LocalSpeech {
    static func transcribe(_ url: URL) async throws -> String {
        guard SpeechTranscriber.isAvailable,
              let locale = await SpeechTranscriber.supportedLocale(equivalentTo: .current) else {
            throw BijouError("On-device transcription is unavailable for this device or language.")
        }
        let module = SpeechTranscriber(locale: locale, preset: .transcription)
        if let assets = try await AssetInventory.assetInstallationRequest(supporting: [module]) {
            try await assets.downloadAndInstall()
        }
        try Task.checkCancellation()
        let analyzer = SpeechAnalyzer(modules: [module])
        let file = try AVAudioFile(forReading: url)
        return try await withTaskCancellationHandler {
            let reader = Task {
                var parts: [String] = []
                for try await result in module.results {
                    try Task.checkCancellation()
                    let part = String(result.text.characters).trimmingCharacters(in: .whitespacesAndNewlines)
                    if !part.isEmpty { parts.append(part) }
                }
                return parts.joined(separator: " ")
            }
            defer { reader.cancel() }
            try await analyzer.start(inputAudioFile: file, finishAfterFile: true)
            let text = try await reader.value
            guard !text.isEmpty else { throw BijouError("No speech was recognized. Your recording is still available.") }
            return text
        } onCancel: { Task { await analyzer.cancelAndFinishNow() } }
    }
}

struct ReactionTranscript: View {
    let take: AudioReaction
    let store: ReactionStore
    let remote: ArchivedReaction?
    @EnvironmentObject private var studio: Studio
    @Environment(\.dismiss) private var dismiss
    @State private var text = ""
    @State private var revision: String?
    @State private var notice: String?
    @State private var job: Task<Void, Never>?
    @State private var saving = false
    @State private var loaded = false
    private var local: Bool { FileManager.default.fileExists(atPath: store.audio(take.id).path) }
    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack {
                Text("Reaction transcript").font(.system(.title, design: .serif))
                Spacer()
                Button("Done") { dismiss() }.disabled(saving)
            }
            Text("Review the draft against your recording. Speech recognition runs on this device; the first use may download a language model.")
                .font(.callout)
            if job != nil {
                ProgressView("Preparing or transcribing…")
                Button("Cancel transcription") { job?.cancel() }
            } else if local && text.isEmpty {
                Button("Transcribe on this device") { generate() }.buttonStyle(AdmissionStyle())
            } else if !local && text.isEmpty {
                Text("Download the recording from the film card to transcribe it.")
            }
            TextEditor(text: $text).frame(minHeight: 110)
                .accessibilityLabel("Editable transcript").disabled(job != nil || saving || !local)
            if let notice { Text(notice).font(.callout) }
            if local {
                Text("Draft edits are saved on this device.").font(.caption)
                if let remote, let revision, let creds = studio.credentials, creds.library == studio.journal?.base.library {
                    let personal = studio.journal?.base.origin == "personal"
                    Button(personal ? "Save reviewed text to Personal" : "Save reviewed text to practice library") {
                        let reviewed = text.trimmingCharacters(in: .whitespacesAndNewlines)
                        saving = true
                        Task {
                            defer { saving = false }
                            do {
                                self.revision = try await HomeClient(creds).saveTranscript(reviewed, record: remote,
                                                                                          library: creds.library, revision: revision)
                                notice = "Reviewed transcript saved to the reaction."
                                await studio.sync(manual: true)
                            } catch { notice = error.localizedDescription }
                        }
                    }.disabled(text.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty || job != nil || saving)
                } else { Text("File the recording and sync to save reviewed text to its reaction concept.").font(.caption) }
            }
        }.padding(20)
        .onAppear {
            revision = remote?.revision
            do { text = try store.draftTranscript(take.id) ?? remote?.transcript ?? "" }
            catch { notice = error.localizedDescription }
            loaded = true
        }
        .onChange(of: text) { _, new in
            if loaded && local {
                do { try store.saveTranscript(new, for: take.id) } catch { notice = error.localizedDescription }
            }
        }
        .onDisappear { job?.cancel() }
        .interactiveDismissDisabled(saving)
        #if os(macOS)
        .frame(minWidth: 440, minHeight: 380)
        #endif
    }
    private func generate() {
        notice = nil
        job = Task {
            defer { job = nil }
            do {
                let draft = try await LocalSpeech.transcribe(store.audio(take.id))
                try Task.checkCancellation()
                try store.saveTranscript(draft, for: take.id)
                text = draft
            } catch { if !Task.isCancelled { notice = error.localizedDescription } }
        }
    }
}
