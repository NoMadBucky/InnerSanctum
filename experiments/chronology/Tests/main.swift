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

let legacy = ScoreEntry(id: UUID(), score: 8, date: Date(timeIntervalSince1970: 0))
var board = try JSONEncoder().encode(Array(repeating: legacy, count: 10))
precondition(ScoreHistory.entries(board).count == 5)
let below = ScoreEntry(id: UUID(), score: 7, date: Date())
precondition(ScoreHistory.record(below, in: board) == nil)
let tied = ScoreEntry(id: UUID(), score: 8, date: Date())
board = ScoreHistory.record(tied, in: board)!
precondition(ScoreHistory.sign(tied.id, with: "a1", in: board) == board)
board = ScoreHistory.sign(tied.id, with: "a-c3e!", in: board)
let ranked = ScoreHistory.entries(board)
precondition(ranked.count == 5 && ranked.first?.initials == "ACE" && ranked.last?.initials == nil)
print("Validated legacy boards, initials and the top-five cutoff with ties.")

func verdict(_ years: [Int], guess: Int) throws -> Round.Reveal {
    let cards = years.map { Event(id: "\($0)", year: $0, date: "\($0)", title: "", note: "", source: nil, attribution: nil) }
    var game = try Round(deck: cards, mode: .longPlay, shuffle: false)
    for year in years.dropFirst().dropLast() {
        game.place(at: game.table.filter { $0.year < year }.count)
        game.advance()
    }
    game.place(at: guess)
    return game.reveal!
}
let near = try verdict([1000, 1500], guess: 0)
let far = try verdict([1501, 1000], guess: 1)
precondition(near.yearsOutsideGap == 500 && near.verdict == "Almost!")
precondition(far.yearsOutsideGap == 501 && far.verdict != near.verdict)
let timeline = [1000, 1010, 1020, 1030, 1040, 1050, 1055]
let misses = try (0...6).map { try verdict(timeline, guess: $0) }
precondition(misses[1].verdict == far.verdict && misses[2].verdict != far.verdict)
precondition(misses[3].verdict == misses[4].verdict && misses[2].verdict != misses[3].verdict)
precondition(misses[4].yearsOutsideGap == 15 && misses[5].verdict == near.verdict && misses[6].correct)
