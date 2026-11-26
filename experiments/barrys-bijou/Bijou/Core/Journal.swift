import Foundation

struct BijouError: LocalizedError {
    let message: String
    init(_ message: String) { self.message = message }
    var errorDescription: String? { message }
}

struct FilmRef: Codable, Hashable, Identifiable {
    let path: String
    let personalID: String?
    var id: String { path }
}

struct Film: Codable, Identifiable {
    struct Source: Codable, Hashable { let title: String; let address: String }
    let ref: FilmRef
    let title: String
    let watched: String?
    let year: String?
    let description: String?
    let body: String
    let sources: [Source]
    let posterKey: String?
    var metadata: [String: String]? = nil
    var viewed: Bool? = nil
    var watchlist: Bool? = nil
    var inLibrary: Bool? = nil
    var tmdb: String? = nil
    var plex: String? = nil
    var plexMovieLinks: (app: URL, web: URL)? {
        // Existing synced catalogs store the older preplay link; reuse its exact match.
        guard let plex, let parts = URLComponents(string: plex),
              parts.scheme == "plex", parts.host == "preplay",
              let server = parts.queryItems?.first(where: { $0.name == "server" })?.value,
              server.range(of: #"^[A-Za-z0-9-]{8,128}\z"#, options: .regularExpression) != nil,
              let key = parts.queryItems?.first(where: { $0.name == "metadataKey" })?.value,
              key.range(of: #"^/library/metadata/[1-9][0-9]*\z"#, options: .regularExpression) != nil else { return nil }
        let segment = key.replacingOccurrences(of: "/", with: "%2F")
        guard let app = URL(string: "plex://libraries/\(server)/unmatched/\(segment)"),
              let web = URL(string: "https://app.plex.tv/desktop/#!/server/\(server)/details?key=\(segment)") else { return nil }
        return (app, web)
    }
    var tmdbEntry: URL? {
        for text in [tmdb].compactMap({ $0 }) + sources.map(\.address) {
            if let u = URL(string: text), ["https", "http"].contains(u.scheme?.lowercased() ?? ""),
               ["www.themoviedb.org", "themoviedb.org", "tmdb.org"].contains(u.host?.lowercased() ?? ""),
               let range = u.path.range(of: #"^/movie/[1-9][0-9]*(?=[-/]|$)"#, options: .regularExpression) {
                return URL(string: "https://www.themoviedb.org" + u.path[range])
            }
        }
        return nil
    }
    var tmdbSearch: URL? {
        var parts = URLComponents(string: "https://www.themoviedb.org/search/movie")
        parts?.queryItems = [URLQueryItem(name: "query", value: title)]
        return parts?.url
    }
    // Catalogs from before these fields existed contained watched movies only.
    var isViewed: Bool { viewed ?? true }
    var isInLibrary: Bool { inLibrary ?? (metadata?["in_library"]?.lowercased() == "true") }
    var viewingLabel: String {
        if let watched { return "Watched \(watched)" }
        if isViewed { return "Watch date unknown" }
        return watchlist == true ? "Watchlist" : "Not marked watched"
    }
    var id: String { ref.path }

    static func viewingOrder(_ a: Film, _ b: Film) -> Bool {
        if a.watched != b.watched { return (a.watched ?? "") > (b.watched ?? "") }
        let comparison = a.title.localizedStandardCompare(b.title)
        return comparison == .orderedSame ? a.id < b.id : comparison == .orderedAscending
    }
}

enum WatchedSort {
    case viewed, ranked

    func films(_ films: [Film], ranks: [FilmRef: Int]) -> [Film] {
        films.sorted { a, b in
            if self == .ranked {
                let first = ranks[a.ref] ?? Int.max
                let second = ranks[b.ref] ?? Int.max
                if first != second { return first < second }
            }
            return Film.viewingOrder(a, b)
        }
    }
}

enum MovieShelf: String, CaseIterable {
    case watched = "Watched", watchlist = "Watchlist", library = "Library", all = "All Movies"
    func includes(_ film: Film) -> Bool {
        switch self {
        case .watched: return film.isViewed
        case .watchlist: return film.watchlist ?? (film.metadata?["video_status"] == "watchlist")
        case .library: return film.isInLibrary
        case .all: return true
        }
    }
}

struct Catalog: Codable {
    let library: String
    var revision: String
    var films: [Film]
    var order: [FilmRef]
    var labels: [String: String]
    var issues: [String]
    var origin: String? = nil
    var fixtureReactionFiling: Bool? = nil
    var personalReactionFiling: Bool? = nil

    func title(_ ref: FilmRef) -> String {
        films.first { $0.ref == ref }?.title ?? labels[ref.path] ?? ref.path
    }
}

struct Gap: Codable, Equatable {
    let above: FilmRef?
    let below: FilmRef?

    static func choices(for film: FilmRef, in order: [FilmRef]) -> [Gap] {
        let other = order.filter { $0 != film }
        return (0...other.count).map {
            Gap(above: $0 == 0 ? nil : other[$0 - 1], below: $0 == other.count ? nil : other[$0])
        }
    }

    func placing(_ film: FilmRef, in order: [FilmRef]) throws -> [FilmRef] {
        guard !order.contains(where: { $0.path == film.path && $0 != film }),
              let i = Self.choices(for: film, in: order).firstIndex(of: self) else {
            throw BijouError("These neighbors changed. Choose a placement in the current list.")
        }
        var result = order.filter { $0 != film }
        result.insert(film, at: i)
        return result
    }
}

struct Intent: Codable {
    var id = UUID().uuidString
    let film: FilmRef
    let gap: Gap
}

struct Placement: Codable, Equatable {
    let library: String
    let revision: String
    let requestID: String
    let film: FilmRef
    let gap: Gap
}

struct Receipt: Codable {
    let requestID: String
    let revision: String
    enum CodingKeys: String, CodingKey { case requestID = "request_id", revision }
}

/// One SQLite commit stores the entire transition, including the immutable in-flight request.
struct Journal: Codable {
    var base: Catalog
    var order: [FilmRef]
    var pending: [Intent] = []
    var frozen: Placement?
    var review: Catalog?
    init(_ snapshot: Catalog) { base = snapshot; order = snapshot.order }

    var needsReview: Bool { review != nil || !base.issues.isEmpty }

    mutating func confirm(_ film: FilmRef, gap: Gap) throws {
        guard !needsReview, base.films.contains(where: { $0.ref == film && $0.isViewed }) else {
            throw BijouError("Review the catalog before changing this film.")
        }
        let next = try gap.placing(film, in: order)
        guard next != order else { return }
        pending.append(Intent(film: film, gap: gap))
        order = next
    }

    mutating func outgoing() -> Placement? {
        if let frozen { return frozen }
        guard !needsReview, let move = pending.first else { return nil }
        let request = Placement(library: base.library, revision: base.revision, requestID: move.id,
                                film: move.film, gap: move.gap)
        frozen = request
        return request
    }

    mutating func acknowledge(_ receipt: Receipt) throws {
        guard let sent = frozen, sent.requestID == receipt.requestID,
              sent.requestID == pending.first?.id, receipt.revision.count == 64 else {
            throw BijouError("Unrecognized receipt. The original request is still saved.")
        }
        base.order = try sent.gap.placing(sent.film, in: base.order)
        base.labels[sent.film.path] = base.title(sent.film)
        base.revision = receipt.revision
        pending.removeFirst()
        frozen = nil
        projectPending()
    }

    mutating func receive(_ fresh: Catalog, rejected: String? = nil) throws {
        guard fresh.library == base.library else { throw BijouError("This is a different library.") }
        if let rejected {
            guard frozen?.requestID == rejected else { throw BijouError("Unexpected conflict response.") }
            frozen = nil  // Server explicitly refused this ID; no uncertain write is discarded.
        } else if frozen != nil {
            throw BijouError("Reconcile the original request before refreshing.")
        }
        if !pending.isEmpty && (fresh.revision != base.revision || rejected != nil || !fresh.issues.isEmpty || review != nil) {
            review = fresh
        } else {
            base = fresh
            if pending.isEmpty { order = fresh.order }
        }
    }

    mutating func resolve(on revision: String, gap: Gap?) throws {
        guard let latest = review, latest.revision == revision, latest.issues.isEmpty, let first = pending.first,
              latest.films.contains(where: { $0.ref == first.film }) else {
            throw BijouError("The library changed or a film needs repair. Your local ranking is saved.")
        }
        if let gap {
            let proposed = try gap.placing(first.film, in: latest.order)
            pending.removeFirst()
            if proposed != latest.order { pending.insert(Intent(film: first.film, gap: gap), at: 0) }
        } else {
            guard latest.order.contains(first.film) else { throw BijouError("Choose a gap for this unranked film.") }
            pending.removeFirst()
        }
        base = latest
        review = nil
        projectPending()
    }

    private mutating func projectPending() {
        var result = base.order
        for (i, move) in pending.enumerated() {
            guard base.films.contains(where: { $0.ref == move.film }),
                  let next = try? move.gap.placing(move.film, in: result), next != result else {
                // Don't invent a replacement gap or throw away the original local projection.
                if i == 0 { review = base }
                return
            }
            result = next
        }
        order = result
    }

    var markdown: String {
        let lines = order.enumerated().map { offset, ref in
            let title = base.title(ref).replacingOccurrences(of: "\\", with: "\\\\")
                .replacingOccurrences(of: "[", with: "\\[").replacingOccurrences(of: "]", with: "\\]")
            return "\(offset + 1). [\(title)](/\(ref.path))"
        }
        return (["# Bijou", "", "## Ranking", ""] + lines).joined(separator: "\n") + "\n"
    }
}
