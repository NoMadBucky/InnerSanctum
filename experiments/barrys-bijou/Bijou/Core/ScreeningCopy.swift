import Foundation

/// A portable, read-only input for device acceptance; it carries no home credentials.
struct ScreeningCopy: Decodable {
    let format: String
    let catalog: Catalog
    let covers: [String: Data]

    static func read(_ url: URL) throws -> ScreeningCopy {
        let props = try url.resourceValues(forKeys: [.isRegularFileKey, .fileSizeKey])
        guard props.isRegularFile == true, let size = props.fileSize, size <= 40 * 1024 * 1024 else {
            throw BijouError("Choose a screening copy of 40 MB or less.")
        }
        let copy = try JSONDecoder().decode(Self.self, from: Data(contentsOf: url, options: .mappedIfSafe))
        let c = copy.catalog
        let safePath = { (path: String) in path.range(of: "^Resources/videos/[0-9]{7}\\.md$", options: .regularExpression) != nil }
        let safeKey = { (key: String) in key.range(of: "^[0-9a-f]{64}$", options: .regularExpression) != nil }
        let keys = Set(c.films.compactMap(\.posterKey))
        guard copy.format == "bijou-screening-1", c.library.hasPrefix("snapshot-"),
              safeKey(String(c.library.dropFirst("snapshot-".count))), safeKey(c.revision),
              c.films.count <= 10_000, Set(c.films.map(\.id)).count == c.films.count,
              c.films.allSatisfy({ safePath($0.id) }), c.order.allSatisfy({ safePath($0.path) }),
              Set(c.order.map(\.path)).count == c.order.count, keys.allSatisfy(safeKey),
              copy.covers.allSatisfy({ keys.contains($0.key) && $0.value.count <= 1024 * 1024 && $0.value.starts(with: [0xff, 0xd8]) }) else {
            throw BijouError("This is not a valid Bijou screening copy.")
        }
        return copy
    }
}
