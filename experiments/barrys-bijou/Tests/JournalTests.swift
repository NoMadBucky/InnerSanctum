import Foundation
import XCTest
@testable import BijouCore

final class JournalTests: XCTestCase {
    func testWatchedSortKeepsUnrankedFilmsAndUnknownDatesLast() {
        func film(_ title: String, _ date: String?) -> Film {
            Film(ref: FilmRef(path: title, personalID: nil), title: title, watched: date,
                 year: nil, description: nil, body: "", sources: [], posterKey: nil)
        }
        let a = film("A", "2026-01-01"), b = film("B", nil), c = film("C", "2026-03-03")
        let d = film("D", nil), e = film("E", "2026-02-02")
        let films = [e, d, c, b, a], ranks = [b.ref: 1, a.ref: 2]
        XCTAssertEqual(WatchedSort.viewed.films(films, ranks: ranks).map(\.title), ["C", "E", "A", "B", "D"])
        XCTAssertEqual(WatchedSort.ranked.films(films, ranks: ranks).map(\.title), ["B", "A", "C", "E", "D"])
    }

    func testOfflineRelaunchAndConflictRetainLaterMoves() throws {
        let tmp = FileManager.default.temporaryDirectory.appendingPathComponent(UUID().uuidString)
        defer { try? FileManager.default.removeItem(at: tmp) }
        let refs = (0..<4).map { FilmRef(path: "Resources/videos/\(8100000 + $0).md", personalID: "bho:\(8100000 + $0)") }
        let (a, b, c, d) = (refs[0], refs[1], refs[2], refs[3])
        let films = refs.map { Film(ref: $0, title: $0.path, watched: nil, year: nil, description: nil, body: "", sources: [], posterKey: nil) }
        let base = Catalog(library: "fixture", revision: String(repeating: "a", count: 64), films: films, order: [a, b], labels: [:], issues: [])
        var j = Journal(base)
        try j.confirm(b, gap: Gap(above: a, below: nil))
        XCTAssertTrue(j.pending.isEmpty, "Confirming the current gap must not enqueue a write")
        try j.confirm(a, gap: Gap(above: b, below: nil))
        try j.confirm(c, gap: Gap(above: a, below: nil))
        let request = try XCTUnwrap(j.outgoing())
        try Storage(directory: tmp).save(j)
        j = try XCTUnwrap(Storage(directory: tmp).load(base.library))
        XCTAssertEqual(j.order, [b, a, c]); XCTAssertEqual(j.outgoing(), request)
        var latest = base; latest.order = [a, d, b]; latest.revision = String(repeating: "b", count: 64)
        XCTAssertThrowsError(try j.receive(latest), "An uncertain request must retain its original ID")
        try j.receive(latest, rejected: request.requestID)
        XCTAssertEqual(j.order, [b, a, c]); XCTAssertEqual(j.pending.count, 2)
        XCTAssertThrowsError(try j.resolve(on: base.revision, gap: Gap(above: b, below: nil)))
        try j.resolve(on: latest.revision, gap: Gap(above: b, below: nil))
        let reviewed = try XCTUnwrap(j.outgoing())
        XCTAssertNotEqual(request.requestID, reviewed.requestID)
        try j.acknowledge(Receipt(requestID: reviewed.requestID, revision: String(repeating: "c", count: 64)))
        XCTAssertEqual(j.order, [d, b, a, c])
        let later = try XCTUnwrap(j.outgoing())
        XCTAssertEqual(later.film, c); XCTAssertEqual(later.revision, j.base.revision)
        try j.acknowledge(Receipt(requestID: later.requestID, revision: String(repeating: "d", count: 64)))
        XCTAssertEqual(j.order, j.base.order); XCTAssertTrue(j.pending.isEmpty)
    }

    func testSecondGapNeedsSeparateReviewRatherThanGuessing() throws {
        let refs = ["a", "b", "c", "d"].map { FilmRef(path: $0, personalID: nil) }
        let (a, b, c, d) = (refs[0], refs[1], refs[2], refs[3])
        let films = refs.map { Film(ref: $0, title: $0.path, watched: nil, year: nil, description: nil, body: "", sources: [], posterKey: nil) }
        var cat = Catalog(library: "x", revision: "initial", films: films, order: [a], labels: [:], issues: [])
        var local = Journal(cat)
        try local.confirm(b, gap: Gap(above: a, below: nil))
        try local.confirm(c, gap: Gap(above: a, below: b))
        let req = try XCTUnwrap(local.outgoing())
        cat.order = [a, d]; cat.revision = String(repeating: "b", count: 64)
        try local.receive(cat, rejected: req.requestID)
        try local.resolve(on: cat.revision, gap: Gap(above: d, below: nil))
        let sent = try XCTUnwrap(local.outgoing())
        try local.acknowledge(Receipt(requestID: sent.requestID, revision: String(repeating: "c", count: 64)))
        XCTAssertEqual(local.pending.first?.film, c); XCTAssertTrue(local.needsReview)
        XCTAssertEqual(local.review?.order, [a, d, b]); XCTAssertNil(local.outgoing())
    }
}
