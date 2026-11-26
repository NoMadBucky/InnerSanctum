import AVFoundation
import SwiftUI

@MainActor
private final class QuizVoice: ObservableObject {
    private let synth = AVSpeechSynthesizer()
    func stop() { synth.stopSpeaking(at: .immediate) }
    func read(_ clue: String) {
        stop()
        let line = AVSpeechUtterance(string: clue)
        line.voice = AVSpeechSynthesisVoice(language: "en-US")
        synth.speak(line)
    }
}

struct NameThatFilm: View {
    @EnvironmentObject private var studio: Studio
    @Environment(\.dismiss) private var dismiss
    @Environment(\.scenePhase) private var phase
    @Environment(\.colorScheme) private var scheme
    @AppStorage("quizMuted") private var muted = false
    @StateObject private var voice = QuizVoice()
    @State private var questions: [FilmQuiz.Question] = []
    @State private var answers: [String] = []
    @State private var index = 0
    private var pool: FilmQuiz { FilmQuiz(films: studio.journal?.base.films ?? []) }
    private func start() {
        let round = pool.round()
        questions = round; index = 0; answers = []
        if !muted, let first = round.first { voice.read(first.clue) }
    }
    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 18) {
                HStack {
                    Text("Name That Film").font(.system(.title, design: .serif)).accessibilityAddTraits(.isHeader)
                    Spacer()
                    Button("Done") { voice.stop(); dismiss() }
                }
                Toggle("Read clues aloud", isOn: Binding(get: { !muted }, set: { enabled in
                    muted = !enabled
                    if enabled, questions.indices.contains(index), answers.count == index { voice.read(questions[index].clue) }
                    else { voice.stop() }
                }))
                if questions.isEmpty {
                    Text("Ten clues from Watched. Four choices each. No timer.")
                    let available = pool.eligible.count
                    Text("\(available) films with eligible clues").font(.caption)
                    if available >= FilmQuiz.length {
                        Button("Start round", action: start).buttonStyle(AdmissionStyle())
                    } else {
                        Text("You need 10 distinct clues. Sync with the updated Personal adapter; the Mac caches missing TMDb overviews in the background.")
                        Button("Sync clues") { Task { await studio.sync(manual: true) } }
                            .disabled(studio.syncing || studio.isSample || studio.isSnapshot)
                    }
                } else if questions.indices.contains(index) {
                    questionView(questions[index])
                } else {
                    let missed = questions.indices.filter { answers[$0] != questions[$0].film.id }
                    BillingLine(title: "FINAL SCORE")
                    Text("\(questions.count - missed.count) / \(questions.count)").font(.largeTitle.bold())
                    if missed.isEmpty { Text("A perfect round!") }
                    else {
                        Text("Films you missed").font(.headline)
                        ForEach(missed, id: \.self) { i in Text("\(i + 1). \(FilmQuiz.label(questions[i].film))") }
                    }
                    Button("Play again", action: start).buttonStyle(AdmissionStyle())
                }
            }.frame(maxWidth: 600, alignment: .leading).padding(24).frame(maxWidth: .infinity)
        }.background(House(scheme).paper).foregroundStyle(House(scheme).ink)
        .onDisappear { voice.stop() }
        .onChange(of: phase) { _, value in if value != .active { voice.stop() } }
        #if os(macOS)
        .frame(minWidth: 440, minHeight: 520)
        #endif
    }
    @ViewBuilder private func questionView(_ q: FilmQuiz.Question) -> some View {
        let answered = answers.count > index
        Text("QUESTION \(index + 1) OF \(questions.count)").font(.caption.bold()).tracking(1)
        Text(q.clue).font(.system(.title3, design: .serif))
        if !muted && !answered {
            HStack {
                Button("Replay clue") { voice.read(q.clue) }
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
        if answered {
            HStack {
                Poster(film: q.film, width: 74)
                VStack(alignment: .leading) {
                    Text(answers[index] == q.film.id ? "Correct!" : "The answer was").font(.headline)
                    Text(FilmQuiz.label(q.film))
                }
            }
            Button(index + 1 == questions.count ? "See score" : "Next question") {
                guard answers.count == index + 1 else { return }
                index += 1
                if !muted, questions.indices.contains(index) { voice.read(questions[index].clue) }
            }.buttonStyle(AdmissionStyle())
        }
    }
}
