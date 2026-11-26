import Foundation

struct ScoreEntry: Codable, Identifiable {
    let id: UUID
    let score: Int
    let date: Date
    var initials: String? // Scores saved by earlier versions have no initials.
}

enum ScoreHistory {
    static func entries(_ data: Data) -> [ScoreEntry] {
        (try? JSONDecoder().decode([ScoreEntry].self, from: data)) ?? []
    }

    static func record(_ entry: ScoreEntry, in data: Data) -> Data? {
        let ranked = ([entry] + entries(data))
            .sorted { ($0.score, $0.date) > ($1.score, $1.date) }.prefix(10)
        guard ranked.contains(where: { $0.id == entry.id }) else { return nil }
        return try? JSONEncoder().encode(Array(ranked))
    }

    static func letters(_ text: String) -> String {
        String(text.filter { $0.isASCII && $0.isLetter }.prefix(3)).uppercased()
    }

    static func sign(_ id: UUID, with text: String, in data: Data) -> Data {
        var board = entries(data)
        let initials = letters(text)
        guard initials.count == 3, let index = board.firstIndex(where: { $0.id == id }) else { return data }
        board[index].initials = initials
        return (try? JSONEncoder().encode(board)) ?? data
    }
}
