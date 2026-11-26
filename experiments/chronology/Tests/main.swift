import Foundation

// Run against the actual bundle input, independently of the simulator.
let deck = try JSONDecoder().decode([Event].self, from: Data(contentsOf:
    URL(fileURLWithPath: CommandLine.arguments[1])))
let sorted = deck.sorted { $0.year < $1.year }
var round = try Round(deck: Array(sorted[1...10]) + [sorted[0]], shuffle: false)
for turn in 1...9 {
    round.place(at: round.table.count)
    round.place(at: 0)
    precondition(round.score == turn && round.table.count == turn + 1)
    round.advance()
}
round.place(at: 10)
precondition(round.reveal?.chosen == 10 && round.reveal?.actual == 0)
precondition(round.score == 9 && !round.finished && round.table.count == 10)
round.advance()
precondition(round.finished && round.drawn == nil)
var perfect = try Round(deck: deck)
var seen = Set([perfect.table[0].id])
while let card = perfect.drawn {
    precondition(seen.insert(card.id).inserted)
    perfect.place(at: perfect.table.filter { $0.year < card.year }.count)
    precondition(perfect.table.map(\.year) == perfect.table.map(\.year).sorted())
    perfect.advance()
}
precondition(perfect.score == 10 && seen.count == 11)
do {
    _ = try Round(deck: deck + [deck[0]])
    fatalError("Duplicate year accepted")
} catch DeckError.duplicateYear {}
print("Validated \(deck.count) cards, perfect round, and final opposite-end miss.")
