import SwiftUI

struct MovieDiscovery: View {
    let credentials: Credentials
    let known: Set<Int>
    @Environment(\.dismiss) private var dismiss
    @State private var text: String
    @State private var results: HomeClient.MoviePage?
    @State private var issue: String?
    @State private var loading = false
    @State private var page = 1
    @State private var submitted = ""
    init(credentials: Credentials, catalog: Catalog, initial: String) {
        self.credentials = credentials
        known = Set(catalog.films.compactMap { $0.tmdbEntry.flatMap { Int($0.lastPathComponent) } })
        _text = State(initialValue: initial)
    }
    private var query: String { text.trimmingCharacters(in: .whitespacesAndNewlines) }
    private func search(_ n: Int) {
        guard !loading, !query.isEmpty, query.count <= 200 else { return }
        let title = query
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
                            Text([hit.year, known.contains(hit.id) ? "In Personal OKF" : "No TMDb ID match in Personal"]
                                .filter { !$0.isEmpty }.joined(separator: " · ")).font(.caption)
                            if !hit.overview.isEmpty { Text(hit.overview).font(.subheadline).lineLimit(3) }
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
        }.padding(20)
        #if os(macOS)
        .frame(minWidth: 380, minHeight: 420)
        #endif
    }
}
