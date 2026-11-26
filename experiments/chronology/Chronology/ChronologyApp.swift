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
                    if ProcessInfo.processInfo.arguments.contains("-firstGuessFixture") {
                        round = try Round(deck: deck.sorted { $0.year > $1.year }, shuffle: false)
                        return
                    }
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
    @State private var gap = 0
    @State private var scrolling = false
    @State private var showingAnswer = false
    @State private var reading: Event?
    @Environment(\.accessibilityReduceMotion) private var reduceMotion
    private var motion: Animation? { reduceMotion ? nil : .easeInOut(duration: 0.35) }

    var body: some View {
        ScrollViewReader { proxy in
            board(proxy)
        }
    }

    private func board(_ proxy: ScrollViewProxy) -> some View {
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
                        jump("First", 0, proxy)
                        jump("Earlier", gap - 1, proxy)
                        jump("Later", gap + 1, proxy)
                        jump("Last", round.table.count, proxy)
                    }.buttonStyle(.bordered)
                    Button("Place Here") {
                        guard !scrolling else { return }
                        withAnimation(motion) { round.place(at: gap) }
                    }.disabled(scrolling)
                        .accessibilityValue(gapDescription)
                        .buttonStyle(.borderedProminent)
                } else {
                    Button(round.turn == Round.guesses ? "See Results" : "Draw Next") {
                        showingAnswer = false
                        scrolling = false
                        round.advance()
                    }.buttonStyle(.borderedProminent)
                        // Only a miss needs the brief "Your guess" preview.
                        // Advancing a scored turn never depends on a scroll-idle callback.
                        .disabled(round.reveal?.correct == false && !showingAnswer)
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
            guard let reveal = round.reveal, !reveal.correct else { return }
            if !reduceMotion {
                do { try await Task.sleep(for: .milliseconds(650)) } catch { return }
            }
            withAnimation(motion) {
                proxy.scrollTo(reveal.actual, anchor: .center)
                showingAnswer = true
            }
        }
    }

    private var gapDescription: String {
        guard (0...round.table.count).contains(gap) else { return "" }
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

    private func jump(_ title: String, _ index: Int, _ proxy: ScrollViewProxy) -> some View {
        Button(title) { withAnimation(motion) { proxy.scrollTo(index, anchor: .center) } }
            .disabled(!(0...round.table.count).contains(index) || gap == index)
    }

    private func timeline(_ event: Event) -> some View {
        let pitch = TimelineSnap.pitch
        let slot: CGFloat = 24
        return VStack(spacing: 4) {
            if let r = round.reveal, !r.correct, showingAnswer {
                Text("Belongs here: \(event.title) · \(event.date)")
                    .padding(8).overlay(RoundedRectangle(cornerRadius: 8).stroke(style: StrokeStyle(dash: [4])))
                    .accessibilityIdentifier("ghost")
            } else if let r = round.reveal {
                Text(r.correct ? "Added to the table" : "Your guess").bold()
            } else {
                Text("Gap \(gap + 1) of \(round.table.count + 1)").font(.caption)
            }
            Image(systemName: "arrowtriangle.down.fill").foregroundStyle(.teal).accessibilityHidden(true)
            ScrollView(.horizontal) {
                HStack(spacing: 0) {
                    ForEach(0...round.table.count, id: \.self) { index in
                        Color.clear.frame(width: slot, height: 1).id(index)
                        if index < round.table.count {
                            card(round.table[index]).frame(width: pitch - slot)
                        }
                    }
                }
                // Half a viewport of breathing room lets both end gaps reach the cursor.
                .containerRelativeFrame(.horizontal, alignment: .center) { width, _ in
                    width + CGFloat(round.table.count) * pitch
                }
            }
            .accessibilityIdentifier("timeline")
            .scrollIndicators(.hidden)
            .scrollTargetBehavior(TimelineSnap())
            .onScrollGeometryChange(for: Int.self) { geometry in
                Int((geometry.contentOffset.x / pitch).rounded())
            } action: { _, nearest in gap = min(max(nearest, 0), round.table.count) }
            .onScrollPhaseChange { _, phase in scrolling = phase != .idle }
            .scrollDisabled(round.reveal != nil)
            .fixedSize(horizontal: false, vertical: true)
            .overlay {
                Capsule().fill(.teal).frame(width: 3)
                    .allowsHitTesting(false).accessibilityHidden(true)
            }
            Text(positionCaption)
                .font(.footnote.bold()).monospacedDigit()
        }
    }

    private var positionCaption: String {
        if gap <= 0 { return "Beginning · Before \(round.table[0].year)" }
        if gap >= round.table.count { return "End · After \(round.table[round.table.count - 1].year)" }
        return "Between \(round.table[gap - 1].year) and \(round.table[gap].year)"
    }

    private func card(_ event: Event) -> some View {
            VStack {
                Text(event.date).bold().foregroundStyle(.teal)
                Text(event.title).font(.subheadline)
            }.multilineTextAlignment(.center)
                .padding(8).frame(maxWidth: .infinity, minHeight: 95)
                .background(.teal.opacity(0.1), in: RoundedRectangle(cornerRadius: 12))
                .accessibilityElement(children: .combine)
    }
}

// Quantize only the projected resting offset. Native drag and momentum remain continuous.
private struct TimelineSnap: ScrollTargetBehavior {
    static let pitch: CGFloat = 156
    func updateTarget(_ target: inout ScrollTarget, context: TargetContext) {
        let projected = (target.rect.minX / Self.pitch).rounded() * Self.pitch
        target.rect.origin.x = min(max(0, projected), max(0, context.contentSize.width - context.containerSize.width))
    }
}
