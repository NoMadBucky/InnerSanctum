import XCTest

final class ScreeningRoomTests: XCTestCase {
    func testCancelRankAndReopen() throws {
        continueAfterFailure = false
        let app = XCUIApplication()
        let session = UUID()
        app.launchArguments = ["--sample-ui-test", session.uuidString, "-ApplePersistenceIgnoreState", "YES"]
        defer {
            app.terminate()
            #if os(macOS)
            try? FileManager.default.removeItem(at: FileManager.default.temporaryDirectory
                .appendingPathComponent("bijou-ui-\(session.uuidString)"))
            #endif
        }
        func openFilm() {
            let enter = app.buttons["enter-theater"]
            XCTAssertTrue(enter.waitForExistence(timeout: 8))
            enter.tap()
            let film = app.buttons["film-Resources/videos/8100001.md"]
            XCTAssertTrue(film.waitForExistence(timeout: 8))
            film.tap()
        }
        app.launch(); openFilm()
        app.buttons["rank-action"].tap()
        app.buttons["cancel-placement"].tap()
        XCTAssertFalse(app.staticTexts["rank-position"].exists)
        app.buttons["rank-action"].tap()
        app.buttons["confirm-placement"].tap()
        XCTAssertTrue(app.staticTexts["rank-position"].waitForExistence(timeout: 5))
        app.terminate(); app.launch(); openFilm()
        XCTAssertTrue(app.staticTexts["rank-position"].waitForExistence(timeout: 5))
        XCTAssertEqual(app.buttons["rank-action"].label, "Rerank")
    }
}
