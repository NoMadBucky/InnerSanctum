import SwiftUI

struct MovieDiscovery: View {
    let credentials: Credentials
    let known: [Int: FilmRef]
    let open: (FilmRef) -> Void
    @EnvironmentObject private var studio: Studio
    @Environment(\.dismiss) private var dismiss
    @State private var text: String
    @State private var results: HomeClient.MoviePage?
    @State private var issue: String?
    @State private var loading = false
    @State private var page = 1
    @State private var submitted = ""
    @State private var adding: Int?
    @State private var reviewID: Int?
    @State private var candidates: [HomeClient.WatchlistReply.Candidate] = []
    init(credentials: Credentials, catalog: Catalog, initial: String, open: @escaping (FilmRef) -> Void) {
        self.credentials = credentials
        self.open = open
        known = Dictionary(catalog.films.compactMap { film in
            film.tmdbEntry.flatMap { Int($0.lastPathComponent) }.map { ($0, film.ref) }
        }, uniquingKeysWith: { first, _ in first })
        _text = State(initialValue: initial)
    }
    private var query: String { text.trimmingCharacters(in: .whitespacesAndNewlines) }
    private func add(_ id: Int, distinctFrom: [String] = []) {
        guard adding == nil else { return }
        issue = nil; adding = id
        Task {
            defer { adding = nil }
            do {
                let reply = try await studio.addMovie(id, library: credentials.library, distinctFrom: distinctFrom)
                if let ref = reply.film { open(ref) }
                else if let matches = reply.matches { candidates = matches; reviewID = id }
                else { issue = "The Mac did not confirm this movie. Try again." }
            } catch { issue = error.localizedDescription }
        }
    }
    private func search(_ n: Int) {
        guard !loading, !query.isEmpty, query.count <= 200 else { return }
        let title = query
        reviewID = nil; candidates = []
        issue = nil; loading = true
        Task {
            defer { loading = false }
            do {
                results = try await HomeClient(credentials).searchTMDb(title, page: n)
                submitted = title; page = n
            } catch { issue = error.localizedDescription }
        }
    }
    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack {
                Text("Search TMDb").font(.system(.title, design: .serif))
                Spacer()
                Button("Done") { dismiss() }
            }
            HStack {
                TextField("Movie title", text: $text).textFieldStyle(.roundedBorder)
                    .onSubmit { search(1) }.disabled(loading)
                Button("Search") { search(1) }.disabled(loading || query.isEmpty || query.count > 200)
            }
            if loading { ProgressView("Searching TMDb…") }
            if let issue { Text(issue).font(.callout) }
            ScrollView {
                VStack(alignment: .leading, spacing: 12) {
                    if let results {
                        Text(results.results.isEmpty ? "No movies found for “\(submitted)”." : "Results for “\(submitted)” · Page \(page)")
                            .font(.subheadline)
                        ForEach(results.results) { hit in
                            Divider()
                            Link(destination: URL(string: "https://www.themoviedb.org/movie/\(hit.id)")!) {
                                Text(hit.title).font(.system(.headline, design: .serif))
                            }
                            if let poster = hit.poster {
                                AsyncImage(url: poster) { image in image.resizable().scaledToFit() }
                                    placeholder: { Color.clear }.frame(width: 64, height: 96).accessibilityHidden(true)
                            }
                            Text([hit.year, known[hit.id] != nil ? "In Personal OKF" : "No TMDb ID match in Personal"]
                                .filter { !$0.isEmpty }.joined(separator: " · ")).font(.caption)
                            if !hit.overview.isEmpty { Text(hit.overview).font(.subheadline).lineLimit(3) }
                            if let ref = known[hit.id] {
                                Button("Open in Bijou") { open(ref) }
                            } else if reviewID == hit.id {
                                Text("Possible matches in Personal").font(.headline)
                                ForEach(candidates, id: \.ref) { c in
                                    Button("Open \(c.title) · \(c.year ?? "Year unknown")") { open(c.ref) }
                                }
                                Button("Different movie — add to Watchlist") {
                                    add(hit.id, distinctFrom: candidates.map(\.ref.path))
                                }.buttonStyle(JournalActionStyle())
                            } else {
                                Button(adding == hit.id ? "Adding…" : "Add to Watchlist") { add(hit.id) }
                                    .buttonStyle(JournalActionStyle()).disabled(studio.syncing || loading)
                            }
                        }
                        HStack {
                            if page > 1 { Button("Previous") { search(page - 1) } }
                            Spacer()
                            if page < results.pages { Button("Next") { search(page + 1) } }
                        }.disabled(loading || submitted != query)
                    }
                }.frame(maxWidth: .infinity, alignment: .leading)
            }.id("\(submitted)-\(page)")
            Text("This product uses the TMDB API but is not endorsed or certified by TMDB.")
                .font(.caption2).foregroundStyle(.secondary)
        }.padding(20).disabled(adding != nil).interactiveDismissDisabled(adding != nil)
        #if os(macOS)
        .frame(minWidth: 380, minHeight: 420)
        #endif
    }
}
