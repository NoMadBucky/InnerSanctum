import XCTest
@testable import BijouCore

final class TMDbDiscoveryTests: XCTestCase {
    func testDirectResultsUseExistingMovieCardsAndTMDbPageLimit() throws {
        let data = Data(#"{"total_pages":650,"results":[{"id":42,"title":"Film","release_date":"1998-07-04","poster_path":"/poster.jpg"},{"id":43,"title":"Unreleased","poster_path":null}]}"#.utf8)
        let page = try TMDbDiscovery.decode(data)
        XCTAssertEqual(page.pages, 500)
        XCTAssertEqual(page.results.map(\.id), [42, 43])
        XCTAssertEqual(page.results.map(\.year), ["1998", ""])
        XCTAssertEqual(page.results.first?.poster?.absoluteString, "https://image.tmdb.org/t/p/w185/poster.jpg")
        XCTAssertNil(page.results.last?.poster)
    }
}
