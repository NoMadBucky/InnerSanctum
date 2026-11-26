import SwiftUI

struct QuizScoreboard: View {
    let score: Int?
    let round: UUID
    @AppStorage("quizHighScores.v1") private var saved = Data()
    @State private var initials = ""
    @State private var skipped = false

    private var board: QuizHighScores {
        (try? JSONDecoder().decode(QuizHighScores.self, from: saved)) ?? QuizHighScores()
    }

    private func submit() {
        var latest = board
        guard let score, latest.submit(round: round, initials: initials, score: score),
              let data = try? JSONEncoder().encode(latest) else { return }
        saved = data
    }

    var body: some View {
        let scores = board
        VStack(alignment: .leading, spacing: 12) {
            Text("High scores").font(.headline).accessibilityAddTraits(.isHeader)
            if let score, scores.qualifies(score), !skipped, !scores.entries.contains(where: { $0.id == round }) {
                Text("You made the board! Enter three initials.").font(.headline)
                HStack {
                    TextField("AAA", text: Binding(get: { initials }, set: { initials = QuizHighScores.initials($0) }))
                        .font(.system(.title3, design: .monospaced).bold()).textFieldStyle(.roundedBorder)
                        .frame(maxWidth: 80).accessibilityLabel("Three initials, A through Z")
                        .autocorrectionDisabled().onSubmit(submit)
                    Button("Save", action: submit).disabled(initials.count != 3)
                    Button("Skip") { skipped = true }
                }
            }
            if scores.entries.isEmpty {
                Text("The board is open. Be the first to sign it.")
            } else {
                ForEach(Array(scores.entries.enumerated()), id: \.element.id) { i, entry in
                    HStack {
                        Text(String(format: "%02d", i + 1)).foregroundStyle(.secondary)
                        Text(entry.initials).bold().tracking(3)
                        if entry.id == round { Image(systemName: "star.fill").accessibilityLabel("Your new score") }
                        Spacer()
                        Text("\(entry.score) / \(FilmQuiz.length)")
                    }.font(.system(.body, design: .monospaced)).accessibilityElement(children: .combine)
                }
            }
            Text("Top \(QuizHighScores.capacity) on this device · Earlier scores win ties.").font(.caption).foregroundStyle(.secondary)
        }
    }
}
