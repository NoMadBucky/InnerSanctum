import SwiftUI

struct FilmCardShelf: View {
    let films: [Film]
    let ranks: [FilmRef: Int]
    let open: (FilmRef) -> Void
    @State private var position: Film.ID?
    @Environment(\.colorScheme) private var scheme
    @Environment(\.accessibilityReduceMotion) private var reduceMotion

    var body: some View {
        let h = House(scheme)
        let index = films.firstIndex { $0.id == position } ?? 0
        VStack(spacing: 8) {
            HStack {
                stepButton("Previous film", icon: "chevron.left", to: index - 1)
                Spacer()
                Text("Film \(index + 1) of \(films.count)").font(.subheadline.monospacedDigit())
                Spacer()
                stepButton("Next film", icon: "chevron.right", to: index + 1)
            }.foregroundStyle(h.brass)
            ScrollView(.horizontal) {
                LazyHStack(spacing: 0) {
                    ForEach(films) { film in
                        Button { open(film.ref) } label: {
                            card(film, house: h)
                        }
                        .buttonStyle(.plain)
                        .accessibilityHint("Opens film details")
                        .accessibilityIdentifier("film-\(film.id)")
                        .containerRelativeFrame(.horizontal)
                        .id(film.id)
                    }
                }.scrollTargetLayout()
            }
            .scrollIndicators(.hidden)
            .scrollTargetBehavior(.paging)
            .scrollPosition(id: $position)
            .onChange(of: films.map(\.id), initial: true) { _, ids in
                if position.map(ids.contains) != true { position = ids.first }
            }
        }
    }

    private func stepButton(_ name: String, icon: String, to index: Int) -> some View {
        Button {
            guard films.indices.contains(index) else { return }
            withAnimation(reduceMotion ? nil : .easeInOut(duration: 0.22)) { position = films[index].id }
        } label: {
            Image(systemName: icon).frame(minWidth: 44, minHeight: 44)
        }.buttonStyle(.plain).accessibilityLabel(name).disabled(!films.indices.contains(index))
    }

    private func card(_ film: Film, house: House) -> some View {
        VStack(spacing: 10) {
            Poster(film: film, width: 120)
                .overlay { Rectangle().strokeBorder(house.brass.opacity(0.55)) }
            Text(film.title).font(.system(.title2, design: .serif).weight(.semibold)).lineLimit(2)
            Text([film.year, film.viewingLabel].compactMap { $0 }.joined(separator: "  ·  "))
                .font(.subheadline)
            if let rank = ranks[film.ref] { Text("Ranked · #\(rank)").font(.caption.bold()).foregroundStyle(house.brass) }
            Label("Film details", systemImage: "ticket").font(.subheadline.weight(.semibold)).foregroundStyle(house.brass)
        }
        .multilineTextAlignment(.center).padding(16).frame(maxWidth: .infinity)
        .background(house.brass.opacity(0.06))
        .overlay { Rectangle().strokeBorder(house.brass.opacity(0.35)) }
        .contentShape(Rectangle()).padding(.horizontal, 2)
    }
}
