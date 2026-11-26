import Foundation
import Security

enum TMDbKeyring {
    private static var query: [String: Any] {
        [kSecClass as String: kSecClassGenericPassword,
         kSecAttrService as String: "org.innersanctum.bijou.discovery",
         kSecAttrAccount as String: "tmdb-read-token"]
    }

    static func read() throws -> String? {
        var q = query
        q[kSecReturnData as String] = true
        var result: CFTypeRef?
        let status = SecItemCopyMatching(q as CFDictionary, &result)
        if status == errSecItemNotFound { return nil }
        guard status == errSecSuccess, let data = result as? Data,
              let token = String(data: data, encoding: .utf8), !token.isEmpty
        else { throw BijouError("Could not read the TMDb token from Keychain.") }
        return token
    }

    static func store(_ token: String?) throws {
        guard let token else {
            let status = SecItemDelete(query as CFDictionary)
            guard status == errSecSuccess || status == errSecItemNotFound else { throw BijouError("Could not remove the TMDb token.") }
            return
        }
        let value: [String: Any] = [kSecValueData as String: Data(token.utf8),
                                    kSecAttrAccessible as String: kSecAttrAccessibleWhenUnlockedThisDeviceOnly]
        var status = SecItemUpdate(query as CFDictionary, value as CFDictionary)
        if status == errSecItemNotFound {
            status = SecItemAdd(query.merging(value) { _, new in new } as CFDictionary, nil)
        }
        guard status == errSecSuccess else { throw BijouError("Could not save the TMDb token in Keychain.") }
    }
}

enum TMDbDiscovery {
    private struct Page: Decodable {
        struct Hit: Decodable {
            let id: Int
            let title: String
            let release_date, overview, poster_path: String?
        }
        let results: [Hit]
        let total_pages: Int
    }
    static func search(_ title: String, page: Int, token: String) async throws -> HomeClient.MoviePage {
        var url = URLComponents(string: "https://api.themoviedb.org/3/search/movie")!
        url.queryItems = [URLQueryItem(name: "query", value: title), URLQueryItem(name: "page", value: String(page))]
        var request = URLRequest(url: url.url!, timeoutInterval: 20)
        request.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")
        let session = URLSession(configuration: .ephemeral)
        defer { session.finishTasksAndInvalidate() }
        let (data, response) = try await session.data(for: request)
        switch (response as? HTTPURLResponse)?.statusCode {
        case 200: break
        case 401, 403: throw BijouError("TMDb rejected this device’s read token. Replace it in Settings → Movie discovery.")
        case 429: throw BijouError("TMDb is receiving too many searches. Try again shortly.")
        default: throw BijouError("TMDb could not complete the search. Try again later.")
        }
        return try decode(data)
    }

    static func decode(_ data: Data) throws -> HomeClient.MoviePage {
        let page = try JSONDecoder().decode(Page.self, from: data)
        return HomeClient.MoviePage(results: page.results.map { hit in
            HomeClient.MovieHit(id: hit.id, title: hit.title, year: String((hit.release_date ?? "").prefix(4)),
                                overview: hit.overview ?? "", poster: hit.poster_path.flatMap {
                URL(string: "https://image.tmdb.org/t/p/w185")?.appendingPathComponent($0)
            })
        }, pages: min(page.total_pages, 500))
    }
}
