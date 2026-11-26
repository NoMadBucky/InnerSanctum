import Foundation

// Run against the actual bundle input, independently of the simulator.
let clock = ContinuousClock()
let start = clock.now
let bytes = try Data(contentsOf: URL(fileURLWithPath: CommandLine.arguments[1]))
let deck = try JSONDecoder().decode([Event].self, from: bytes)
_ = try Round(deck: deck)
print("Read \(bytes.count) bytes, decoded \(deck.count) events and dealt a round in \(start.duration(to: clock.now)).")
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

var long = try Round(deck: sorted, mode: .longPlay, shuffle: false)
for guess in 1...15 {
    let miss = [1, 8, 15].contains(guess)
    long.place(at: miss ? 0 : long.table.count)
    precondition(long.isFinalReveal == (guess == 15))
    long.place(at: 0) // A second tap cannot spend another miss.
    precondition(!long.finished && long.drawn != nil)
    long.advance()
}
precondition(long.finished && long.drawn == nil && long.score == 12 && long.misses == 3)

var marathon = try Round(deck: deck, mode: .longPlay)
var dealt = Set([marathon.table[0].id])
while let card = marathon.drawn {
    precondition(dealt.insert(card.id).inserted)
    marathon.place(at: marathon.table.filter { $0.year < card.year }.count)
    precondition(marathon.isFinalReveal == (dealt.count == deck.count))
    marathon.advance()
}
precondition(dealt.count == deck.count && marathon.score == deck.count - 1 && marathon.misses == 0)
print("Validated Long Play beyond ten guesses, third miss, and full-deck exhaustion.")
