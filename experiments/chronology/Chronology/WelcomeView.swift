import SwiftUI

struct WelcomeView: View {
    let start, scores: () -> Void
    @State private var spread = false
    @Environment(\.accessibilityReduceMotion) private var reduceMotion

    var body: some View {
        VStack(spacing: 18) {
            Spacer()
            ZStack {
                ForEach(0..<3) { index in
                    RoundedRectangle(cornerRadius: 15)
                        .fill([Color.teal, .mint, .yellow][index].gradient)
                        .frame(width: 82, height: 112)
                        .overlay { Image(systemName: ["globe", "sparkles", "hourglass"][index]).font(.largeTitle).foregroundStyle(.black) }
                        .rotationEffect(.degrees(spread ? Double(index - 1) * 16 : 0))
                        .offset(x: spread ? CGFloat(index - 1) * 42 : 0)
                }
            }.accessibilityHidden(true).padding(.bottom)
            Text("Chronology").font(.system(.largeTitle, design: .serif).bold())
            Text("Where in history does your card belong?").multilineTextAlignment(.center)
            Spacer()
            Button("New Game", action: start).buttonStyle(.borderedProminent).controlSize(.large)
            Button("High Scores", action: scores)
        }
        .padding()
        .onAppear { withAnimation(reduceMotion ? nil : .spring(duration: 0.8)) { spread = true } }
    }
}

struct ScoreEntry: Codable, Identifiable {
    let id: UUID
    let score: Int
    let date: Date
}

enum ScoreHistory {
    static func entries(_ data: Data) -> [ScoreEntry] {
        (try? JSONDecoder().decode([ScoreEntry].self, from: data)) ?? []
    }

    static func record(_ score: Int, in data: Data) -> Data {
        let ranked = (entries(data) + [ScoreEntry(id: UUID(), score: score, date: Date())])
            .sorted { ($0.score, $0.date) > ($1.score, $1.date) }
        return (try? JSONEncoder().encode(Array(ranked.prefix(10)))) ?? data
    }
}

struct ScoreBoard: View {
    @AppStorage("chronology.scores.v1") private var data = Data()
    @Environment(\.dismiss) private var dismiss
    var body: some View {
        NavigationStack {
            let entries = ScoreHistory.entries(data)
            List {
                if entries.isEmpty {
                    ContentUnavailableView("No scores yet", systemImage: "rosette",
                                           description: Text("Finish a round to record your first score."))
                } else {
                    Section("Your best ten rounds on this device") {
                        ForEach(Array(entries.enumerated()), id: \.element.id) { index, entry in
                            HStack {
                                Text("#\(index + 1)").foregroundStyle(.secondary)
                                Text(entry.date, style: .date)
                                Spacer()
                                Text("\(entry.score)/\(Round.guesses)").bold()
                            }
                        }
                    }
                }
            }.navigationTitle("High Scores")
                .toolbar { Button("Done") { dismiss() } }
        }
    }
}
