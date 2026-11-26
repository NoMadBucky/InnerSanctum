import Foundation

struct QuizHighScores: Codable {
    struct Entry: Codable, Identifiable {
        let id: UUID
        let initials: String
        let score: Int
    }

    static let capacity = 10
    private(set) var entries: [Entry] = []

    static func initials(_ input: String) -> String {
        String(input.filter { $0.isASCII && $0.isLetter }.prefix(3)).uppercased()
    }

    func qualifies(_ score: Int) -> Bool {
        (0...FilmQuiz.length).contains(score) &&
            (entries.count < Self.capacity || score > (entries.last?.score ?? -1))
    }

    mutating func submit(round: UUID, initials: String, score: Int) -> Bool {
        guard qualifies(score), initials.count == 3, initials == Self.initials(initials),
              !entries.contains(where: { $0.id == round }) else { return false }
        let index = entries.firstIndex { $0.score < score } ?? entries.count
        entries.insert(Entry(id: round, initials: initials, score: score), at: index)
        if entries.count > Self.capacity { entries.removeLast() }
        return true
    }
}
