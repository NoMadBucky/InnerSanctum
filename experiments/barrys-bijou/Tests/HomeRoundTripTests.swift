import Foundation
import XCTest
@testable import BijouCore

final class HomeRoundTripTests: XCTestCase {
    func testPortableReadOnlyScreeningCopy() throws {
        guard let path = ProcessInfo.processInfo.environment["BIJOU_TEST_SCREENING"] else {
            throw XCTSkip("Run adapter/rehearse.py to include the screening copy.")
        }
        let copy = try ScreeningCopy.read(URL(fileURLWithPath: path))
        XCTAssertEqual(copy.catalog.films.count, 6); XCTAssertEqual(copy.covers.count, 5)
        XCTAssertTrue(copy.catalog.library.hasPrefix("snapshot-"))
        var local = Journal(copy.catalog)
        let film = try XCTUnwrap(local.base.films.first)
        try local.confirm(film.ref, gap: Gap(above: nil, below: nil))
        XCTAssertTrue(local.markdown.contains("](/\(film.ref.path))"))
        XCTAssertTrue(copy.catalog.order.isEmpty)
    }
    /// The rehearsal runner supplies two independent, one-use codes for a fresh loopback fixture.
    func testTwoPairedClientsAndOfflineRelaunch() async throws {
        let env = ProcessInfo.processInfo.environment
        guard let phoneCode = env["BIJOU_TEST_PHONE"], let macCode = env["BIJOU_TEST_MAC"] else {
            throw XCTSkip("Run adapter/rehearse.py for the two-client HTTPS integration test.")
        }
        let code = try PairCode.parse(phoneCode)
        let wrong = HomeClient(url: code.url, fingerprint: String(repeating: "0", count: 64))
        do { _ = try await wrong.catalog(); XCTFail("Unpinned server was accepted") }
        catch { XCTAssertFalse(error is HomeResponse, "TLS must fail before an HTTP response") }

        let phone = HomeClient(try await HomeClient.pair(code))
        let mac = HomeClient(try await HomeClient.pair(PairCode.parse(macCode)))
        let initial = try await phone.catalog()
        XCTAssertEqual(initial.films.count, 6); XCTAssertTrue(initial.order.isEmpty)
        let sorted = initial.films.sorted(by: Film.viewingOrder)
        XCTAssertEqual(sorted.map(\.title).prefix(3), ["The Last Projection", "A Balcony for Two", "Northbound at Midnight"])
        XCTAssertNil(sorted.last?.watched)
        let a = sorted[0].ref, b = sorted[1].ref, c = sorted[2].ref
        let cover = try await phone.cover(XCTUnwrap(sorted[0].posterKey))
        XCTAssertTrue(cover.starts(with: [0xff, 0xd8]))
        let tmp = FileManager.default.temporaryDirectory.appendingPathComponent(UUID().uuidString)
        defer { try? FileManager.default.removeItem(at: tmp) }
        var local = Journal(initial)
        try local.confirm(a, gap: Gap(above: nil, below: nil))
        try Storage(directory: tmp).save(local)
        local = try XCTUnwrap(Storage(directory: tmp).load(initial.library))
        let original = try XCTUnwrap(local.outgoing())
        let first = try await phone.place(original)
        let retry = try await phone.place(original)
        XCTAssertEqual(first.revision, retry.revision)
        try local.acknowledge(retry)
        var desktop = Journal(try await mac.catalog())
        try desktop.confirm(b, gap: Gap(above: a, below: nil))
        let second = try await mac.place(XCTUnwrap(desktop.outgoing()))
        try desktop.acknowledge(second)
        try local.confirm(c, gap: Gap(above: a, below: nil))
        let stale = try XCTUnwrap(local.outgoing())
        do { _ = try await phone.place(stale); XCTFail("Stale placement published") }
        catch let e as HomeResponse { XCTAssertEqual(e.status, 409) }
        let remote = try await phone.catalog()
        try local.receive(remote, rejected: stale.requestID)
        XCTAssertEqual(local.order, [a, c]); XCTAssertEqual(local.review?.order, [a, b])
        try local.resolve(on: remote.revision, gap: Gap(above: b, below: nil))
        let restored = try await phone.place(XCTUnwrap(local.outgoing()))
        try local.acknowledge(restored)
        try local.confirm(a, gap: Gap(above: c, below: nil))
        let rerank = try await phone.place(XCTUnwrap(local.outgoing()))
        try local.acknowledge(rerank)
        let readback = try await mac.catalog()
        XCTAssertEqual(readback.order, [b, c, a]); XCTAssertTrue(readback.issues.isEmpty)
        XCTAssertEqual(local.order, readback.order); XCTAssertTrue(local.pending.isEmpty)
    }
}
