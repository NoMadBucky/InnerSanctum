import SwiftUI

struct WelcomeView: View {
    @Binding var mode: GameMode
    let start, scores: () -> Void
    var showingScores = false
    @State private var credits = false

    var body: some View {
        VStack(spacing: 18) {
            Spacer()
            VStack(spacing: 4) {
                Text("Periodical").font(.system(.largeTitle, design: .serif).bold())
                Text("A Snap History Game").font(.subheadline).foregroundStyle(.secondary)
            }.accessibilityElement(children: .combine)
            Text("Can you find your place in history?").bold().multilineTextAlignment(.center)
            Spacer()
            ModePicker(mode: $mode)
            Text(mode == .standard ? "Ten guesses to build your timeline." :
                    "Draw without repeats until three misses or the deck runs out.")
                .font(.subheadline).multilineTextAlignment(.center)
            Button("New Game", action: start).buttonStyle(.borderedProminent).controlSize(.large)
            Button("High Scores", action: scores)
        }
        .padding()
        .frame(maxWidth: .infinity, maxHeight: .infinity)
        .background { IntroBackdrop(visible: !showingScores && !credits) }
        .overlay(alignment: .topTrailing) {
            Button { credits = true } label: {
                Image(systemName: "info.circle").frame(width: 44, height: 44)
                    .background(.black.opacity(0.5), in: Circle())
            }.foregroundStyle(.white).accessibilityLabel("Montage credits").padding(.horizontal)
        }
        .sheet(isPresented: $credits) {
            NavigationStack {
                List {
                    Text("Diamond Sutra frontispiece · International Dunhuang Project\nThe Great Wave · Katsushika Hokusai\nFirst flight · John T. Daniels\nEarthrise · William Anders / NASA")
                    Link("Mandela voting in 1994 · Paul Weinberg", destination: URL(string: "https://commons.wikimedia.org/wiki/File:Mandela_voting_in_1994.jpg")!)
                    Text("Images cropped, panned and crossfaded for Periodical.")
                    Link("Montage license: CC BY-SA 3.0", destination: URL(string: "https://creativecommons.org/licenses/by-sa/3.0/")!)
                }.navigationTitle("Montage credits")
                    .toolbar { Button("Done") { credits = false } }
            }
        }
        .environment(\.colorScheme, .dark)
    }
}

private struct ModePicker: View {
    @Binding var mode: GameMode
    var body: some View {
        Picker("Game mode", selection: $mode) {
            ForEach(GameMode.allCases, id: \.self) { Text($0.rawValue).tag($0) }
        }.pickerStyle(.segmented)
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
    @State var mode: GameMode
    @AppStorage(GameMode.standard.scoresKey) private var standardScores = Data()
    @AppStorage(GameMode.longPlay.scoresKey) private var longScores = Data()
    @Environment(\.dismiss) private var dismiss
    var body: some View {
        NavigationStack {
            let entries = ScoreHistory.entries(mode == .standard ? standardScores : longScores)
            List {
                ModePicker(mode: $mode)
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
                                Text(mode == .standard ? "\(entry.score)/\(Round.guesses)" : "\(entry.score) correct").bold()
                            }
                        }
                    }
                }
            }.navigationTitle("High Scores")
                .toolbar { Button("Done") { dismiss() } }
        }
    }
}
