import Foundation

struct FilmQuiz {
    struct Question {
        let film: Film
        let clue: String
        let options: [Film]
    }
    static let length = 10
    let eligible: [(Film, String)]
    let choices: [Film]
    static func label(_ film: Film) -> String {
        film.year.map { "\(film.title) (\($0))" } ?? film.title
    }
    private static func words(_ value: String) -> String {
        value.folding(options: [.caseInsensitive, .diacriticInsensitive], locale: Locale(identifier: "en_US_POSIX"))
            .components(separatedBy: CharacterSet.alphanumerics.inverted).filter { !$0.isEmpty }.joined(separator: " ")
    }
    init(films: [Film]) {
        var ids = Set<String>(), labels = Set<String>(), clues = Set<String>()
        var pool: [(Film, String)] = [], options: [Film] = []
        for film in films.filter(\.isViewed) {
            let id = film.tmdbEntry?.absoluteString ?? film.id, label = Self.words(Self.label(film))
            guard !ids.contains(id), !labels.contains(label), !label.isEmpty else { continue }
            ids.insert(id); labels.insert(label); options.append(film)
            guard let clue = film.quizClue, (40...2000).contains(clue.count) else { continue }
            let normalized = Self.words(clue)
            guard !(" " + normalized + " ").contains(" " + Self.words(film.title) + " "),
                  clues.insert(normalized).inserted else { continue }
            pool.append((film, clue))
        }
        eligible = pool; choices = options
    }
    func round() -> [Question] {
        guard eligible.count >= Self.length else { return [] }
        return eligible.shuffled().prefix(Self.length).map { film, clue in
            let others = choices.filter { $0.id != film.id }.shuffled().prefix(3)
            return Question(film: film, clue: clue, options: ([film] + others).shuffled())
        }
    }
}
