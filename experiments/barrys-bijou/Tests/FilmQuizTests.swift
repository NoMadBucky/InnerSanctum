import XCTest
@testable import BijouCore

final class FilmQuizTests: XCTestCase {
    func testRoundUsesTenDistinctSafeCluesAndFourDistinctWatchedOptions() {
        var films = (0..<10).map { n in
            Film(ref: FilmRef(path: "\(n)", personalID: nil), title: "Feature \(n)", watched: nil, year: "1990",
                 description: nil, body: "", sources: [], posterKey: nil, viewed: true,
                 quizClue: "A projectionist uncovers a secret during screening number \(n) at the old theatre.")
        }
        XCTAssertTrue(FilmQuiz(films: Array(films.dropLast())).round().isEmpty)
        var unsafe = films[0]
        unsafe.quizClue = "The film FEATURE—0 is named directly in this synopsis and must not be used."
        XCTAssertTrue(FilmQuiz(films: [unsafe]).eligible.isEmpty)
        var unseen = films[1]; unseen.viewed = false
        XCTAssertTrue(FilmQuiz(films: [unseen]).choices.isEmpty)
        films.append(films[1])
        let round = FilmQuiz(films: films).round()
        XCTAssertEqual(round.count, 10)
        XCTAssertEqual(Set(round.map(\.film.id)).count, 10)
        for q in round {
            XCTAssertEqual(q.options.count, 4)
            XCTAssertEqual(Set(q.options.map(FilmQuiz.label)).count, 4)
            XCTAssertEqual(q.options.filter { $0.id == q.film.id }.count, 1)
        }
    }
}
