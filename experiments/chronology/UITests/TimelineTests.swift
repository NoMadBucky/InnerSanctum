import XCTest

final class TimelineTests: XCTestCase {
    func testInteriorMissCentersBetweenVisibleCardEdges() {
        let app = XCUIApplication()
        app.launchArguments = ["-interiorMissFixture"]
        app.launch()
        app.buttons["New Game"].tap()
        app.buttons["Place Here"].tap() // Before both, instead of between them.
        XCTAssertTrue(app.staticTexts["ghost"].waitForExistence(timeout: 5))
        let board = app.scrollViews["timeline"]
        let left = board.buttons["tableCard.Magna_Carta"]
        let right = board.buttons["tableCard.Battle_of_Sekigahara"]
        let centered = NSPredicate { _, _ in
            guard left.isHittable, right.isHittable else { return false }
            let midpoint = (left.frame.maxX + right.frame.minX) / 2
            return abs(midpoint - board.frame.midX) <= 1
        }
        expectation(for: centered, evaluatedWith: board)
        waitForExpectations(timeout: 4)
    }

    func testFirstCorrectPlacementAllowsNextDraw() {
        let app = XCUIApplication()
        app.launchArguments = ["-firstGuessFixture"]
        app.launch()
        app.buttons["New Game"].tap()
        let openingID = app.buttons.matching(NSPredicate(format: "identifier BEGINSWITH 'tableCard.'"))
            .firstMatch.identifier
        app.buttons["Learn More"].tap()
        XCTAssertTrue(app.navigationBars["Learn More"].exists)
        app.buttons["Done"].tap()
        app.buttons["Draw First Card"].tap()
        app.buttons["Place Here"].tap()
        let next = app.buttons["Draw Next"]
        XCTAssertTrue(next.waitForExistence(timeout: 3))
        XCTAssertTrue(next.isEnabled)
        let table = app.scrollViews["timeline"]
        table.swipeLeft()
        let anchor = table.buttons[openingID]
        if !anchor.isHittable { table.swipeLeft() }
        XCTAssertTrue(anchor.isHittable)
        anchor.tap()
        XCTAssertTrue(app.navigationBars["Learn More"].exists)
        app.buttons["Done"].tap()
        next.tap()
        XCTAssertTrue(app.staticTexts["Guess 2 of 10  ·  1 correct"].waitForExistence(timeout: 3))
        XCTAssertTrue(app.buttons["Place Here"].isEnabled)
    }

    func testMissAcrossFullTable() {
        let app = XCUIApplication()
        app.launchArguments = ["-lastGuessFixture"]
        app.launch()
        app.buttons["New Game"].tap()
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
        XCTAssertTrue(app.staticTexts["Beginning · Before 1453"].isHittable)
        app.buttons["See Results"].tap()
        XCTAssertTrue(app.staticTexts["9 of 10 placed correctly"].exists)
        app.buttons["High Scores"].tap()
        XCTAssertTrue(app.staticTexts["9/10"].firstMatch.exists)
        app.terminate()
        app.launch()
        app.buttons["High Scores"].tap()
        XCTAssertTrue(app.staticTexts["9/10"].firstMatch.exists)
    }
}
