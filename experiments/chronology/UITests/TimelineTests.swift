import XCTest

final class TimelineTests: XCTestCase {
    func testMissAcrossFullTable() {
        let app = XCUIApplication()
        app.launchArguments = ["-lastGuessFixture"]
        app.launch()
        XCTAssertTrue(app.staticTexts["Guess 10 of 10  ·  9 correct"].waitForExistence(timeout: 5))
        let timeline = app.scrollViews["timeline"]
        timeline.swipeLeft()
        XCTAssertTrue(app.buttons["First"].isEnabled)
        app.buttons["Last"].tap()
        XCTAssertTrue(app.staticTexts["Gap 11 of 11"].isHittable)
        app.buttons["Place Here"].tap()
        let ghost = app.staticTexts["ghost"]
        XCTAssertTrue(ghost.waitForExistence(timeout: 4))
        expectation(for: NSPredicate(format: "hittable == true"), evaluatedWith: ghost)
        waitForExpectations(timeout: 4)
        XCTAssertTrue(ghost.label.contains("1215"))
        XCTAssertTrue(app.staticTexts["Beginning"].isHittable)
        app.buttons["See Results"].tap()
        XCTAssertTrue(app.staticTexts["9 of 10 placed correctly"].exists)
    }
}
