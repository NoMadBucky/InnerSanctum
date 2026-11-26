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

struct Round {
    static let guesses = 10
    struct Reveal {
        let chosen, actual: Int
        var correct: Bool { chosen == actual }
    }

    private let hand: [Event]
    private(set) var table: [Event]
    private(set) var turn = 1
    private(set) var reveal: Reveal?
    var finished: Bool { turn > Self.guesses }
    var drawn: Event? { finished ? nil : hand[turn] }
    var score: Int { table.count - 1 }

    init(deck: [Event], shuffle: Bool = true) throws {
        guard deck.count > Self.guesses else { throw DeckError.insufficientCards }
        guard Set(deck.map(\.year)).count == deck.count else { throw DeckError.duplicateYear }
        guard Set(deck.map(\.id)).count == deck.count else { throw DeckError.duplicateID }
        hand = Array((shuffle ? deck.shuffled() : deck).prefix(Self.guesses + 1))
        table = [hand[0]]
    }

    mutating func place(at gap: Int) {
        guard reveal == nil, let drawn, (0...table.count).contains(gap) else { return }
        let actual = table.firstIndex { $0.year > drawn.year } ?? table.count
        reveal = Reveal(chosen: gap, actual: actual)
        if gap == actual { table.insert(drawn, at: gap) }
    }

    mutating func advance() {
        guard reveal != nil else { return }
        reveal = nil
        turn += 1
    }
}
