import Foundation

struct ShelfTake: Identifiable {
    struct Key: Hashable { let film: FilmRef; let take: UUID }
    let film: Film
    let take: AudioReaction
    let filed: Bool
    let downloaded: Bool
    let reviewed: String?
    let draft: String?
    var id: Key { Key(film: film.ref, take: take.id) }

    func matches(_ query: String) -> Bool {
        query.isEmpty || [film.title, reviewed, draft].compactMap { $0 }.contains { $0.localizedCaseInsensitiveContains(query) }
    }
    func excerpt(_ query: String) -> String? {
        let texts = [reviewed, draft].compactMap { $0 }.filter { !$0.isEmpty }
        if !query.isEmpty {
            for text in texts {
                if let range = text.range(of: query, options: [.caseInsensitive, .diacriticInsensitive], locale: .current) {
                    let start = text.index(range.lowerBound, offsetBy: -28, limitedBy: text.startIndex) ?? text.startIndex
                    return (start == text.startIndex ? "" : "…") + text[start...].prefix(180)
                }
            }
        }
        return texts.first.map { String($0.prefix(180)) }
    }
    static func load(root: URL, catalog: Catalog) throws -> [Self] {
        var rows: [Self] = []
        for film in catalog.films {
            try Task.checkCancellation()
            let store = ReactionStore(root: root, library: catalog.library, film: film.ref)
            let remote = Dictionary((film.archivedReactions ?? []).map { ($0.id, $0) }, uniquingKeysWith: { first, _ in first })
            var takes = remote.mapValues(\.take)
            for take in try store.list() { takes[take.id] = take }
            for take in takes.values {
                rows.append(Self(film: film, take: take, filed: remote[take.id] != nil || store.filed(take.id),
                                 downloaded: FileManager.default.fileExists(atPath: store.audio(take.id).path),
                                 reviewed: remote[take.id]?.transcript, draft: try store.draftTranscript(take.id)))
            }
        }
        return rows.sorted { a, b in
            if a.take.recordedAt != b.take.recordedAt { return a.take.recordedAt > b.take.recordedAt }
            return (a.film.id, a.take.id.uuidString) < (b.film.id, b.take.id.uuidString)
        }
    }
}
