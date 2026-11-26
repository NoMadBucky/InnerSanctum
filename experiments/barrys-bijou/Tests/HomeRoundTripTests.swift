import Combine
import Foundation
import XCTest
@testable import BijouCore

final class HomeRoundTripTests: XCTestCase {
    @MainActor
    func testLocalBonjourAdvertisement() async throws {
        guard let locator = ProcessInfo.processInfo.environment["BIJOU_TEST_HOME"] else {
            throw XCTSkip("Run adapter/rehearse.py to advertise the fixture on the local Mac.")
        }
        let discovery = HomeDiscovery()
        let found = expectation(description: "The fixture appeared in the Home Sync picker")
        let subscription = discovery.$macs.first { $0.contains(where: { $0.id == locator }) }.sink { _ in found.fulfill() }
        defer { subscription.cancel(); discovery.stop() }
        discovery.start()
        await fulfillment(of: [found], timeout: 10)
    }

    func testHumanEntryAndAuthenticatedServerReceipt() throws {
        let code = try PairCode.parse(" 7km-4v3q\n")
        XCTAssertEqual(code.value, "7KM4V3Q")
        for invalid in ["", "7KM4V3", "7KM4V3QX", "7KM4V3O", "7ΚM4V3Q"] {
            XCTAssertThrowsError(try PairCode.parse(invalid))
        }
        XCTAssertEqual(try HomeAddress.parse("192.168.1.20").absoluteString, "https://192.168.1.20:8765")
        XCTAssertThrowsError(try HomeAddress.parse("http://127.0.0.1"))
        XCTAssertThrowsError(try HomeAddress.parse("https://someone@mac.local/pair"))
        let keys = try PairingProof(code: code, salt: String(repeating: "ab", count: 16),
                                    certificate: String(repeating: "01", count: 32))
        let receipt = "abcd0ae3f77fec0dbea80e9a525932d55306e13d9396615a7e6c32dc1fec3a97"
        XCTAssertTrue(keys.verifies(receipt, device: "abc", token: "def", library: "123"))
        XCTAssertFalse(keys.verifies(receipt, device: "abc", token: "changed", library: "123"))
        XCTAssertFalse(keys.verifies(keys.claim, device: "abc", token: "def", library: "123"))
    }

    func testValidCodeWithoutDiscoveryCanPairByAddress() throws {
        let url = try HomeAddress.parse("192.168.1.20")
        var draft = PairingDraft()
        draft.code = "7km-4v3q"
        guard case .incomplete(.address, _) = draft.check(nearby: []) else {
            return XCTFail("A valid code without a discovered Mac must prompt for its address.")
        }
        draft.address = "192.168.1.20"
        guard case .ready(_, let fallback) = draft.check(nearby: []), fallback == url else {
            return XCTFail("The address shown for an empty list must work without an extra mode switch.")
        }
        draft.manual = true
        draft.address = "not a host"
        guard case .incomplete(.address, _) = draft.check(nearby: [url]) else {
            return XCTFail("Do not silently substitute a discovered Mac for an invalid manual address.")
        }
        draft.address = "192.168.1.20:8765"
        guard case .ready(let code, let dest) = draft.check(nearby: []) else {
            return XCTFail("Manual pairing must work with no Bonjour results and retain the code.")
        }
        XCTAssertEqual(code.value, "7KM4V3Q")
        XCTAssertEqual(dest, url)
        draft.code = "7km4"
        guard case .incomplete(.code, _) = draft.check(nearby: []) else { return XCTFail("An incomplete code must not pair.") }
    }

    func testMultipleDiscoveredMacsRequireACurrentSelection() throws {
        let mac = try HomeAddress.parse("studio.local"), other = try HomeAddress.parse("mini.local")
        var draft = PairingDraft()
        draft.code = "7KM4V3Q"
        draft.selectedMac = "https://departed.local:8765"
        guard case .incomplete(.mac, _) = draft.check(nearby: [mac, other]) else { return XCTFail("Select a current Mac.") }
        draft.selectedMac = other.absoluteString
        guard case .ready(_, let dest) = draft.check(nearby: [mac, other]) else { return XCTFail("Selection should enable pairing.") }
        XCTAssertEqual(dest, other)
        guard case .ready(_, let only) = draft.check(nearby: [mac]) else { return XCTFail("One Mac needs no picker.") }
        XCTAssertEqual(only, mac)
    }
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
        let address = try HomeAddress.parse(XCTUnwrap(env["BIJOU_TEST_HOME"]))
        let code = try PairCode.parse(phoneCode.lowercased())
        let wrong = HomeClient(url: address, fingerprint: String(repeating: "0", count: 64))
        do { _ = try await wrong.catalog(); XCTFail("Unpinned server was accepted") }
        catch { XCTAssertFalse(error is HomeResponse, "TLS must fail before an HTTP response") }

        let enrolled = try await HomeClient.pair(code, at: address)
        XCTAssertEqual(enrolled.fingerprint, env["BIJOU_TEST_PIN"])
        let phone = HomeClient(enrolled)
        do { _ = try await HomeClient.pair(code, at: address); XCTFail("A used code paired a second device.") }
        catch let e as HomeResponse { XCTAssertEqual(e.status, 403) }
        let mac = HomeClient(try await HomeClient.pair(PairCode.parse(macCode), at: address))
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
