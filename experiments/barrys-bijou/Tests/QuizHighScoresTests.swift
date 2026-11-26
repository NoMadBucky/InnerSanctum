import XCTest
@testable import BijouCore

final class QuizHighScoresTests: XCTestCase {
    func testAdmissionTiesAndPersistedBoard() throws {
        var board = QuizHighScores()
        XCTAssertEqual(QuizHighScores.initials("a-1bcD"), "ABC")
        XCTAssertFalse(board.submit(round: UUID(), initials: "AB", score: 10))
        let first = UUID()
        XCTAssertTrue(board.submit(round: first, initials: "ACE", score: 7))
        XCTAssertFalse(board.submit(round: first, initials: "ACE", score: 7))
        for _ in 1..<10 { XCTAssertTrue(board.submit(round: UUID(), initials: "TIE", score: 7)) }
        XCTAssertFalse(board.qualifies(7))
        XCTAssertTrue(board.submit(round: UUID(), initials: "TOP", score: 10))
        let loaded = try JSONDecoder().decode(QuizHighScores.self, from: JSONEncoder().encode(board))
        XCTAssertEqual(loaded.entries.count, 10)
        XCTAssertEqual(loaded.entries.first?.score, 10)
        XCTAssertEqual(loaded.entries[1].id, first)
    }
}
