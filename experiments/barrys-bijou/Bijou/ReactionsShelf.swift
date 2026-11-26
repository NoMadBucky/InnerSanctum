import SwiftUI

struct ReactionsShelf: View {
    @EnvironmentObject private var studio: Studio
    @Binding var count: Int
    @State private var rows: [ShelfTake] = []
    @State private var query = ""
    @State private var filter = "All"
    @State private var selected: ShelfTake?
    @State private var refresh = 0
    @State private var loading = true
    @State private var issue: String?

    var body: some View {
        let search = query.trimmingCharacters(in: .whitespacesAndNewlines)
        let personal = studio.journal?.base.origin == "personal"
        let visible = rows.filter { $0.matches(search) && (filter == "All" || $0.filed == (filter == "Filed")) }
        VStack(alignment: .leading, spacing: 12) {
            TextField("Find a title or words in a reaction", text: $query).textFieldStyle(.roundedBorder)
            Picker("Filing status", selection: $filter) {
                Text("All").tag("All")
                Text("Device only").tag("Local")
                Text("Filed").tag("Filed")
            }.pickerStyle(.segmented)
            if let issue { Text(issue); Button("Retry") { refresh += 1 } }
            else if loading && rows.isEmpty { ProgressView("Finding reactions…") }
            else if visible.isEmpty {
                Text(rows.isEmpty ? "Keep an audio reaction on a film to see it here." : "No reactions match this search or filter.")
            }
            LazyVStack(alignment: .leading, spacing: 0) {
                ForEach(visible) { row in
                    Button { selected = row } label: {
                        HStack(alignment: .top, spacing: 14) {
                            Poster(film: row.film, width: 64)
                            VStack(alignment: .leading, spacing: 5) {
                                Text(row.film.title).font(.system(.headline, design: .serif))
                                Text("\(row.take.recordedAt.formatted(date: .abbreviated, time: .shortened)) · \(Duration.seconds(row.take.seconds).formatted(.time(pattern: .minuteSecond)))")
                                    .font(.caption).foregroundStyle(.secondary)
                                Text(row.filed ? (personal ? "Filed in Personal" : "Filed in practice library") : "Only on this device")
                                    .font(.caption.bold())
                                if row.filed { Text(row.downloaded ? "Available offline" : "Download to play").font(.caption) }
                                Text(row.excerpt(search) ?? "No transcript yet").font(.subheadline).lineLimit(3)
                            }
                            Spacer()
                        }.padding(.vertical, 10).contentShape(Rectangle())
                    }.buttonStyle(.plain)
                    Divider()
                }
            }
        }
        .onReceive(studio.$journal) { _ in refresh += 1 }
        .task(id: refresh) {
            guard let catalog = studio.journal?.base, let root = studio.reactionShelfRoot else { return }
            loading = true; issue = nil
            let worker = Task.detached(priority: .userInitiated) { try ShelfTake.load(root: root, catalog: catalog) }
            do {
                let result = try await withTaskCancellationHandler { try await worker.value } onCancel: { worker.cancel() }
                try Task.checkCancellation()
                rows = result; count = result.count; loading = false
            } catch { if !Task.isCancelled { issue = error.localizedDescription; loading = false } }
        }
        .sheet(item: $selected, onDismiss: { refresh += 1 }) { row in
            ScrollView {
                VStack(alignment: .leading, spacing: 16) {
                    HStack {
                        Text(row.film.title).font(.system(.title, design: .serif))
                        Spacer()
                        Button("Done") { selected = nil }
                    }
                    if let catalog = studio.journal?.base,
                       let film = catalog.films.first(where: { $0.ref == row.film.ref }),
                       let store = studio.reactionStore(library: catalog.library, film: film.ref) {
                        AudioReactions(store: store, viewed: film.watched, film: film.ref,
                                       archived: film.archivedReactions ?? [], focusedTake: row.take.id)
                    }
                }.padding(22).frame(maxWidth: 620, alignment: .leading)
            }
            #if os(macOS)
            .frame(minWidth: 440, minHeight: 380)
            #endif
        }
    }
}
