import SwiftUI

struct EventReader: View {
    let event: Event
    @Environment(\.dismiss) private var dismiss
    @State private var description: String?
    @State private var loading = true

    var body: some View {
        NavigationStack {
            List {
                Section(event.date) {
                    Text(event.title).font(.headline)
                    Text(event.note)
                    Link("Historical source", destination: event.source ?? event.article)
                    if let attribution = event.attribution {
                        Text(attribution).font(.caption).foregroundStyle(.secondary)
                        Link("Creative Commons Attribution-ShareAlike 4.0",
                             destination: URL(string: "https://creativecommons.org/licenses/by-sa/4.0/")!)
                    }
                }
                Section("Wikipedia") {
                    if loading { ProgressView() }
                    else { Text(description ?? "Preview unavailable. You can still open the article.") }
                    Link("Read the article", destination: event.article)
                }
            }.navigationTitle("Learn More")
                .toolbar { Button("Done") { dismiss() } }
        }.task(id: event.id) {
            struct Summary: Decodable { let description: String? }
            defer { loading = false }
            let url = URL(string: "https://en.wikipedia.org/api/rest_v1/page/summary/")!
                .appendingPathComponent(event.id)
            do {
                var request = URLRequest(url: url, timeoutInterval: 6)
                request.setValue("ChronologyPrototype/0.1 (iOS educational card game)", forHTTPHeaderField: "User-Agent")
                let (data, response) = try await URLSession.shared.data(for: request)
                if (response as? HTTPURLResponse)?.statusCode == 200 {
                    description = try JSONDecoder().decode(Summary.self, from: data).description
                }
            } catch { description = nil }
        }
    }
}
