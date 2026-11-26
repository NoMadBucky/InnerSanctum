import Foundation

struct Event: Codable, Identifiable, Equatable {
    let id: String // Stable English Wikipedia article key
    let year: Int
    let date, title, note: String
    let source: URL?
    let attribution: String?
    var article: URL { URL(string: "https://en.wikipedia.org/wiki/")!.appendingPathComponent(id) }
}

enum DeckError: Error { case insufficientCards, duplicateYear, duplicateID }

enum GameMode: String, CaseIterable {
    case standard = "Standard"
    case longPlay = "Long Play"

    var scoresKey: String {
        self == .standard ? "chronology.scores.v1" : "chronology.longPlay.scores.v1"
    }
}

struct Round {
    static let guesses = 10
    static let missLimit = 3
    let mode: GameMode
    struct Reveal {
        let chosen, actual, yearsOutsideGap: Int
        var correct: Bool { chosen == actual }
        var gapsOff: Int { abs(chosen - actual) }
        var verdict: String {
            if correct { return "Correct!" }
            if gapsOff > 4 || yearsOutsideGap > 500 {
                return "Your time machine has been repossessed."
            }
            switch gapsOff {
            case 1: return "Almost!"
            case 2...3: return "History begs to differ."
            default: return "Did you shuffle the centuries?"
            }
        }
    }

    private let hand: [Event]
    private(set) var table: [Event]
    private(set) var turn = 1
    private(set) var reveal: Reveal?
    private(set) var misses = 0
    private(set) var finished = false
    var isFinalReveal: Bool {
        reveal != nil && (turn == hand.count - 1 || (mode == .longPlay && misses == Self.missLimit))
    }
    var drawn: Event? { finished ? nil : hand[turn] }
    var score: Int { table.count - 1 }

    init(deck: [Event], mode: GameMode = .standard, shuffle: Bool = true) throws {
        guard deck.count >= (mode == .standard ? Self.guesses + 1 : 2) else { throw DeckError.insufficientCards }
        guard Set(deck.map(\.year)).count == deck.count else { throw DeckError.duplicateYear }
        guard Set(deck.map(\.id)).count == deck.count else { throw DeckError.duplicateID }
        self.mode = mode
        let ordered = shuffle ? deck.shuffled() : deck
        hand = mode == .longPlay ? ordered : Array(ordered.prefix(Self.guesses + 1))
        table = [hand[0]]
    }

    mutating func place(at gap: Int) {
        guard reveal == nil, let drawn, (0...table.count).contains(gap) else { return }
        let actual = table.firstIndex { $0.year > drawn.year } ?? table.count
        // A guess is an interval, not a year. Measure to its nearest crossed boundary.
        let yearsOutside: Int
        if gap < actual { yearsOutside = drawn.year - table[gap].year }
        else if gap > actual { yearsOutside = table[gap - 1].year - drawn.year }
        else { yearsOutside = 0 }
        reveal = Reveal(chosen: gap, actual: actual, yearsOutsideGap: yearsOutside)
        if gap == actual { table.insert(drawn, at: gap) } else { misses += 1 }
    }

    mutating func advance() {
        guard reveal != nil else { return }
        finished = isFinalReveal
        reveal = nil
        turn += 1
    }
}
