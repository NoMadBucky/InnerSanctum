import SwiftUI

struct PlacementEditor: View {
    let film: FilmRef
    // Freeze the visible neighbors when the sheet opens; a refresh cannot move the selected gap.
    @State private var catalog: Catalog
    @State private var order: [FilmRef]
    let review: Bool
    @EnvironmentObject private var studio: Studio
    @Environment(\.dismiss) private var dismiss
    @Environment(\.colorScheme) private var scheme
    @State private var selected: Int
    @State private var issue: String?

    init(film: FilmRef, catalog: Catalog, order: [FilmRef], review: Bool) {
        self.film = film; self.review = review
        _catalog = State(initialValue: catalog); _order = State(initialValue: order)
        _selected = State(initialValue: order.firstIndex(of: film) ?? order.count / 2)
    }

    var body: some View {
        let h = House(scheme)
        let choices = Gap.choices(for: film, in: order)
        let other = order.filter { $0 != film }
        let index = min(selected, choices.count - 1)
        let gap = choices[index]
        VStack(alignment: .leading, spacing: 14) {
            HStack {
                Text(review ? "PLACEMENT REVIEW" : "THE RANKING ROOM").font(.caption.weight(.semibold)).tracking(1.4).foregroundStyle(h.brass)
                Spacer()
                Button("Cancel") { dismiss() }.accessibilityIdentifier("cancel-placement")
            }
            Text(catalog.title(film)).font(.system(.title, design: .serif))
            if other.isEmpty {
                Text(order.contains(film) ? "This film is already first." : "Make this your first ranked film.")
            } else { Text("Choose a gap between the posters, from best to worst.") }
            ScrollViewReader { reader in
                ScrollView(.horizontal) {
                    HStack(spacing: 8) {
                        ForEach(choices.indices, id: \.self) { i in
                            Button { selected = i } label: {
                                VStack(spacing: 7) {
                                    Image(systemName: i == index ? "checkmark.diamond.fill" : "diamond")
                                    Text(i == index ? "Selected" : "Place here").font(.caption.bold())
                                    Text("#\(i + 1)").font(.caption.monospacedDigit())
                                }.frame(minWidth: 72, minHeight: 125)
                                    .overlay(Rectangle().stroke(i == index ? h.brass : h.brass.opacity(0.35), lineWidth: i == index ? 2 : 1))
                            }.buttonStyle(.plain).id(i)
                                .accessibilityLabel("Position \(i + 1)\(i == index ? ", selected" : "")")
                                .accessibilityIdentifier("gap-\(i)")
                            if i < other.count {
                                VStack(spacing: 6) {
                                    Poster(film: catalog.films.first { $0.ref == other[i] }, width: 74)
                                    Text(catalog.title(other[i])).font(.caption).multilineTextAlignment(.center).lineLimit(2)
                                }.frame(width: 84)
                            }
                        }
                    }.padding(.vertical, 5)
                }
                .onAppear { reader.scrollTo(index, anchor: .center) }
                .onChange(of: selected) { _, i in withAnimation { reader.scrollTo(i, anchor: .center) } }
            }
            VStack(alignment: .leading, spacing: 5) {
                Text("Position \(index + 1) of \(choices.count)").font(.headline)
                if let above = gap.above { Text("Worse than \(catalog.title(above))") }
                if let below = gap.below { Text("Better than \(catalog.title(below))") }
            }
            if let issue { Text(issue).foregroundStyle(.red) }
            Button("Confirm placement") {
                do { try studio.confirm(film, gap: gap, reviewing: review ? catalog.revision : nil); dismiss() }
                catch {
                    issue = error.localizedDescription
                    if let j = studio.journal {
                        catalog = review ? (j.review ?? j.base) : j.base
                        order = review ? catalog.order : j.order
                        selected = order.firstIndex(of: film) ?? order.count / 2
                    }
                }
            }.buttonStyle(AdmissionStyle())
                .accessibilityIdentifier("confirm-placement")
                .disabled(!review && order.firstIndex(of: film) == index)
        }
        .padding(22).frame(maxWidth: 720, maxHeight: .infinity, alignment: .topLeading)
        .background(h.paper).foregroundStyle(h.ink)
        #if os(macOS)
        .frame(minWidth: 530, minHeight: 380)
        #endif
    }
}
