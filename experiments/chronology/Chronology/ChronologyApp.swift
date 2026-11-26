import SwiftUI

@main
struct ChronologyApp: App {
    @State private var session = UUID()

    var body: some Scene {
        WindowGroup {
            GameLoader { session = UUID() }.id(session)
        }
    }
}

private struct GameLoader: View {
    let restart: () -> Void
    @State private var round: Round?
    @State private var failed = false

    var body: some View {
        if let round {
            GameView(round: round, restart: restart)
        } else if failed {
            ContentUnavailableView("Deck unavailable", systemImage: "rectangle.stack.badge.minus",
                                   description: Text("The bundled history deck could not be read."))
        } else {
            ProgressView().task {
                do {
                    guard let url = Bundle.main.url(forResource: "events", withExtension: "json")
                    else { throw CocoaError(.fileNoSuchFile) }
                    let deck = try JSONDecoder().decode([Event].self, from: Data(contentsOf: url))
                    #if DEBUG
                    if ProcessInfo.processInfo.arguments.contains("-lastGuessFixture") {
                        let sorted = deck.sorted { $0.year < $1.year }
                        // Make the final draw earlier than all ten dated table cards.
                        var fixture = try Round(deck: Array(sorted[1...10]) + [sorted[0]], shuffle: false)
                        for _ in 1..<Round.guesses { fixture.place(at: fixture.table.count); fixture.advance() }
                        round = fixture
                        return
                    }
                    #endif
                    round = try Round(deck: deck)
                } catch { failed = true }
            }
        }
    }
}

private struct GameView: View {
    @State var round: Round
    let restart: () -> Void
    @State private var gap: Int? = 0
    @State private var scrolling = false
    @State private var showingAnswer = false
    @State private var reading: Event?
    @Environment(\.accessibilityReduceMotion) private var reduceMotion
    private var motion: Animation? { reduceMotion ? nil : .easeInOut(duration: 0.35) }

    var body: some View {
        VStack(spacing: 12) {
            Text("Chronology").font(.system(.largeTitle, design: .serif).bold())
            if let event = round.drawn {
                Text("Guess \(round.turn) of \(Round.guesses)  ·  \(round.score) correct")
                    .font(.subheadline.monospacedDigit())
                Spacer(minLength: 0)
                ViewThatFits(in: .vertical) {
                    drawCard(event)
                    ScrollView { drawCard(event) }
                }
                Spacer(minLength: 0)
                timeline(event)
                if round.reveal == nil {
                    HStack {
                        jump("First", 0)
                        jump("Earlier", (gap ?? 0) - 1)
                        jump("Later", (gap ?? 0) + 1)
                        jump("Last", round.table.count)
                    }.buttonStyle(.bordered)
                    Button("Place Here") {
                        guard !scrolling, let gap else { return }
                        withAnimation(motion) { round.place(at: gap) }
                    }.disabled(scrolling || gap == nil)
                        .accessibilityValue(gapDescription)
                        .buttonStyle(.borderedProminent)
                } else {
                    Button(round.turn == Round.guesses ? "See Results" : "Draw Next") {
                        showingAnswer = false
                        round.advance()
                    }.buttonStyle(.borderedProminent).disabled(!showingAnswer || scrolling)
                }
            } else {
                Spacer()
                Image(systemName: "rosette").font(.largeTitle)
                Text("\(round.score) of \(Round.guesses) placed correctly").font(.title2.bold())
                Button("Play Again", action: restart).buttonStyle(.borderedProminent)
                Spacer()
            }
        }
        .padding(.vertical)
        .sheet(item: $reading) { EventReader(event: $0) }
        .task(id: round.reveal != nil) {
            guard let reveal = round.reveal else { return }
            if !reveal.correct && !reduceMotion {
                do { try await Task.sleep(for: .milliseconds(650)) } catch { return }
            }
            withAnimation(motion) { gap = reveal.actual; showingAnswer = true }
        }
    }

    private var gapDescription: String {
        guard let gap, (0...round.table.count).contains(gap) else { return "" }
        let left = gap > 0 ? "After \(round.table[gap - 1].title)" : "Beginning of timeline"
        let right = gap < round.table.count ? "before \(round.table[gap].title)" : "end of timeline"
        return "\(left), \(right)"
    }

    private func drawCard(_ event: Event) -> some View {
                VStack(spacing: 8) {
                    if let reveal = round.reveal {
                        Label(reveal.correct ? "Correct!" : "Not quite",
                              systemImage: reveal.correct ? "sparkles" : "arrow.uturn.left.circle")
                            .foregroundStyle(reveal.correct ? Color.green : .orange)
                            .transition(.scale.combined(with: .opacity))
                    } else {
                        Text("YOUR DRAW").font(.caption.bold()).foregroundStyle(.secondary)
                    }
                    Text(event.title).font(.system(.title2, design: .serif).bold())
                    if round.reveal != nil {
                        Text(event.date).bold()
                        Text(event.note).font(.subheadline)
                        Button("Learn More") { reading = event }
                    }
                }
                .multilineTextAlignment(.center).padding()
                .frame(maxWidth: .infinity)
                .background(.thinMaterial, in: RoundedRectangle(cornerRadius: 18))
                .padding(.horizontal)
    }

    private func jump(_ title: String, _ index: Int) -> some View {
        Button(title) { withAnimation(motion) { gap = index } }
            .disabled(!(0...round.table.count).contains(index) || gap == index)
    }

    private func timeline(_ event: Event) -> some View {
        // Each snap target is a gap framed by its two dated neighbors.
        ScrollView(.horizontal) {
            HStack(spacing: 0) {
                ForEach(0...round.table.count, id: \.self) { index in
                    VStack(spacing: 10) {
                        if let r = round.reveal, !r.correct, showingAnswer, index == r.actual {
                            Text("Belongs here: \(event.title) · \(event.date)")
                                .padding(8).overlay(RoundedRectangle(cornerRadius: 8).stroke(style: StrokeStyle(dash: [4])))
                                .accessibilityIdentifier("ghost")
                        } else if let r = round.reveal, r.correct, index == r.actual {
                            Label("Added to the table", systemImage: "checkmark.seal.fill")
                                .foregroundStyle(.green)
                        } else if let r = round.reveal, !r.correct, index == r.chosen {
                            Text("Your guess").bold()
                        } else {
                            Text("Gap \(index + 1) of \(round.table.count + 1)").font(.caption)
                        }
                        HStack {
                            neighbor(index - 1, edge: "Beginning")
                            Image(systemName: "arrow.down").accessibilityHidden(true)
                            neighbor(index, edge: "End")
                        }
                    }
                    .padding(.horizontal, 12)
                    .containerRelativeFrame(.horizontal)
                    .id(index)
                }
            }.scrollTargetLayout()
        }
        .accessibilityIdentifier("timeline")
        .scrollIndicators(.hidden)
        .scrollTargetBehavior(.viewAligned(limitBehavior: .never))
        .scrollPosition(id: $gap, anchor: .center)
        .onScrollPhaseChange { _, phase in scrolling = phase != .idle }
        .scrollDisabled(round.reveal != nil)
        .fixedSize(horizontal: false, vertical: true)
    }

    @ViewBuilder private func neighbor(_ index: Int, edge: String) -> some View {
        if round.table.indices.contains(index) {
            let event = round.table[index]
            VStack {
                Text(event.date).bold().foregroundStyle(.teal)
                Text(event.title).font(.subheadline)
            }.multilineTextAlignment(.center)
                .padding(8).frame(maxWidth: .infinity, minHeight: 95)
                .background(.teal.opacity(0.1), in: RoundedRectangle(cornerRadius: 12))
                .accessibilityElement(children: .combine)
        } else {
            Text(edge).foregroundStyle(.secondary).frame(maxWidth: .infinity)
        }
    }
}
