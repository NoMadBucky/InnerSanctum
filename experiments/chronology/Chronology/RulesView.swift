import SwiftUI

struct RulesView: View {
    @Environment(\.dismiss) private var dismiss
    private let sand = Color(red: 0.97, green: 0.81, blue: 0.52)

    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(alignment: .leading, spacing: 22) {
                    Label("MILESTONES  /  FIELD GUIDE", systemImage: "hourglass")
                        .font(.caption.bold()).tracking(1).foregroundStyle(sand)
                    Text("Where does your card belong?")
                        .font(.system(.largeTitle, design: .serif).bold())
                    step("01", "Draw", "Your first card is dated. Draw another event with its date hidden.")
                    step("02", "Find the gap", "Slide the timeline until the gold marker sits where the event belongs. It can go before, between, or after the dated cards. Tap Place Here to commit.")
                    step("03", "See the date", "Get it right to keep the card and earn a point. On a miss, see the correct gap before the card is discarded. Tap a dated card to learn more.")
                    Divider()
                    Text("Two ways to play").font(.system(.title2, design: .serif).bold())
                    Text("**Standard** · Ten guesses. How many can you place?")
                    Text("**Long Play** · Keep drawing without repeats until your third miss or the deck runs out.")
                }.padding(24).frame(maxWidth: .infinity, alignment: .leading)
            }
            .background(Color(red: 0.035, green: 0.105, blue: 0.11))
            .navigationTitle("Rules").navigationBarTitleDisplayMode(.inline)
            .toolbar { Button("Done") { dismiss() } }
        }.preferredColorScheme(.dark)
    }

    private func step(_ number: String, _ heading: String, _ text: String) -> some View {
        HStack(alignment: .firstTextBaseline, spacing: 14) {
            Text(number).font(.headline.monospacedDigit()).foregroundStyle(sand)
            VStack(alignment: .leading, spacing: 5) {
                Text(heading).font(.system(.title3, design: .serif).bold())
                Text(text)
            }
        }.accessibilityElement(children: .combine)
    }
}
