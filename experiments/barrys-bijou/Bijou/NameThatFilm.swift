import AVFoundation
import SwiftUI

@MainActor
private final class QuizVoice: ObservableObject {
    private let synth = AVSpeechSynthesizer()
    @Published private(set) var choices: [AVSpeechSynthesisVoice] = []
    func refresh() {
        choices = AVSpeechSynthesisVoice.speechVoices()
            .filter { $0.language.lowercased().split(separator: "-").first == "en" }
            .sorted { Self.label($0).localizedStandardCompare(Self.label($1)) == .orderedAscending }
    }
    static func label(_ voice: AVSpeechSynthesisVoice) -> String {
        let quality = voice.quality == .premium ? " · Premium" : voice.quality == .enhanced ? " · Enhanced" : ""
        return "\(voice.name) · \(voice.language)\(quality)"
    }
    func stop() { synth.stopSpeaking(at: .immediate) }
    func read(_ clue: String, using id: String) {
        stop()
        let line = AVSpeechUtterance(string: clue)
        line.voice = choices.first { $0.identifier == id } ?? AVSpeechSynthesisVoice(language: "en-US")
        synth.speak(line)
    }
}

struct NameThatFilm: View {
    @EnvironmentObject private var studio: Studio
    @Environment(\.dismiss) private var dismiss
    @Environment(\.scenePhase) private var phase
    @Environment(\.colorScheme) private var scheme
    @AppStorage("quizMuted") private var muted = false
    @AppStorage("quizVoiceID") private var voiceID = ""
    @StateObject private var voice = QuizVoice()
    @State private var questions: [FilmQuiz.Question] = []
    @State private var answers: [String] = []
    @State private var index = 0
    @State private var roundID = UUID()
    @State private var showingNarration = false
    private var pool: FilmQuiz { FilmQuiz(films: studio.journal?.base.films ?? []) }
    private func start() {
        let round = pool.round()
        questions = round; index = 0; answers = []; roundID = UUID()
        if !muted, let first = round.first { voice.read(first.clue, using: voiceID) }
    }
    var body: some View {
        ScrollViewReader { reader in
        ScrollView {
            VStack(alignment: .leading, spacing: 18) {
                HStack {
                    Text("Name That Film").font(.system(.title, design: .serif)).accessibilityAddTraits(.isHeader)
                    Spacer()
                    Button { showingNarration.toggle() } label: {
                        Label("Narration settings", systemImage: muted ? "speaker.slash" : "speaker.wave.2")
                            .labelStyle(.iconOnly).frame(minWidth: 44, minHeight: 44)
                    }.buttonStyle(.plain)
                    .popover(isPresented: $showingNarration) {
                        ScrollView { narrationControls.padding(20) }
                            .frame(idealWidth: 320, idealHeight: 230)
                            .presentationCompactAdaptation(.sheet)
                    }
                    Button("Done") { voice.stop(); dismiss() }
                }.id("quiz-top")
                if questions.isEmpty {
                    Text("Ten clues from Watched. Four choices each. No timer.")
                    let available = pool.eligible.count
                    Text("\(available) films with eligible clues").font(.caption)
                    if available >= FilmQuiz.length {
                        Button("Start round", action: start).buttonStyle(JournalActionStyle())
                    } else {
                        Text("You need 10 distinct clues. Sync with the updated Personal adapter; the Mac caches missing TMDb overviews in the background.")
                        Button("Sync clues") { Task { await studio.sync(manual: true) } }
                            .disabled(studio.syncing || studio.isSample || studio.isSnapshot)
                    }
                    QuizScoreboard(score: nil, round: roundID)
                } else if questions.indices.contains(index) {
                    questionView(questions[index])
                } else {
                    let missed = questions.indices.filter { answers[$0] != questions[$0].film.id }
                    Text("Final score").font(.headline)
                    Text("\(questions.count - missed.count) / \(questions.count)").font(.largeTitle.bold())
                    QuizScoreboard(score: questions.count - missed.count, round: roundID).id(roundID)
                    if missed.isEmpty { Text("A perfect round!") }
                    else {
                        Text("Films you missed").font(.headline)
                        ForEach(missed, id: \.self) { i in Text("\(i + 1). \(FilmQuiz.label(questions[i].film))") }
                    }
                    Button("Play again", action: start).buttonStyle(JournalActionStyle())
                }
            }.frame(maxWidth: 600, alignment: .leading).padding(24).frame(maxWidth: .infinity)
        }
        .safeAreaInset(edge: .bottom, spacing: 0) {
            if questions.indices.contains(index), answers.count == index + 1 {
                nextAction(for: questions[index])
            }
        }
        .onChange(of: index) { _, _ in reader.scrollTo("quiz-top", anchor: .top) }
        .onChange(of: roundID) { _, _ in reader.scrollTo("quiz-top", anchor: .top) }
        }.background(House(scheme).paper).foregroundStyle(House(scheme).ink)
        .onAppear { voice.refresh() }
        .onChange(of: voiceID) { _, id in
            if !muted, questions.indices.contains(index), answers.count == index { voice.read(questions[index].clue, using: id) }
            else { voice.stop() }
        }
        .onDisappear { voice.stop() }
        .onChange(of: phase) { _, value in if value == .active { voice.refresh() } else { voice.stop() } }
        #if os(macOS)
        .frame(minWidth: 440, minHeight: 520)
        #endif
    }
    private var narrationControls: some View {
        VStack(alignment: .leading, spacing: 16) {
            HStack { Text("Narration").font(.headline); Spacer(); Button("Done") { showingNarration = false } }
            Toggle("Read clues aloud", isOn: Binding(get: { !muted }, set: { enabled in
                muted = !enabled
                if enabled, questions.indices.contains(index), answers.count == index { voice.read(questions[index].clue, using: voiceID) }
                else { voice.stop() }
            }))
            if !muted {
                Picker("Narrator", selection: $voiceID) {
                    Text("Default English voice").tag("")
                    if !voiceID.isEmpty && !voice.choices.contains(where: { $0.identifier == voiceID }) {
                        Text("Unavailable · using default").tag(voiceID)
                    }
                    ForEach(voice.choices, id: \.identifier) { item in Text(QuizVoice.label(item)).tag(item.identifier) }
                }.pickerStyle(.menu)
                Button("Preview voice") { voice.read("Welcome to Bijou. Can you name that film?", using: voiceID) }
            }
        }
    }
    private func nextAction(for question: FilmQuiz.Question) -> some View {
        VStack(spacing: 0) {
            Divider()
            HStack(spacing: 12) {
                Poster(film: question.film, width: 32)
                VStack(alignment: .leading, spacing: 2) {
                    Text(answers[index] == question.film.id ? "Correct!" : "The answer was").font(.caption.weight(.semibold))
                    Text(FilmQuiz.label(question.film)).font(.headline).lineLimit(2)
                }
                Spacer()
            }.frame(maxWidth: 600).padding(.horizontal, 24).padding(.top, 8)
            Button {
                guard questions.indices.contains(index), answers.count == index + 1 else { return }
                index += 1
                if !muted, questions.indices.contains(index) { voice.read(questions[index].clue, using: voiceID) }
            } label: {
                HStack {
                    Text(index + 1 == questions.count ? "See score" : "Next question")
                    Spacer()
                    Image(systemName: "arrow.right").accessibilityHidden(true)
                }
            }
            .buttonStyle(JournalActionStyle()).frame(maxWidth: 600)
            .padding(.horizontal, 24).padding(.vertical, 8)
        }.frame(maxWidth: .infinity).background(House(scheme).paper)
    }
    @ViewBuilder private func questionView(_ q: FilmQuiz.Question) -> some View {
        let answered = answers.count > index
        Text("Question \(index + 1) of \(questions.count)").font(.subheadline.weight(.semibold)).foregroundStyle(House(scheme).brass)
        Text(q.clue).font(.system(.title3, design: .serif))
        if !muted && !answered {
            HStack {
                Button("Replay clue") { voice.read(q.clue, using: voiceID) }
                Button("Stop narration") { voice.stop() }
            }
        }
        ForEach(q.options) { film in
            Button {
                guard answers.count == index else { return }
                voice.stop(); answers.append(film.id)
            } label: {
                Text(FilmQuiz.label(film)).frame(maxWidth: .infinity, alignment: .leading).padding(.vertical, 6)
            }.buttonStyle(.bordered).disabled(answered)
        }
    }
}
