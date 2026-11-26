import SwiftUI

struct FilmCardShelf: View {
    let films: [Film]
    let ranks: [FilmRef: Int]
    let open: (FilmRef) -> Void
    @State private var position: Film.ID?
    @State private var viewport: CGFloat = 340
    @Environment(\.colorScheme) private var scheme
    @Environment(\.accessibilityReduceMotion) private var reduceMotion

    var body: some View {
        let h = House(scheme)
        let index = films.firstIndex { $0.id == position } ?? 0
        let width = min(228, viewport * 0.59)
        VStack(spacing: 8) {
            HStack {
                stepButton("Previous film", icon: "chevron.left", to: index - 1)
                Spacer()
                Text("Film \(index + 1) of \(films.count)").font(.subheadline.monospacedDigit())
                Spacer()
                stepButton("Next film", icon: "chevron.right", to: index + 1)
            }.foregroundStyle(h.brass)
            ScrollView(.horizontal) {
                LazyHStack(spacing: 10) {
                    ForEach(films) { film in
                        Button { open(film.ref) } label: {
                            DVDJacket(film: film, width: width, reduceMotion: reduceMotion)
                        }
                        .buttonStyle(.plain)
                        .accessibilityLabel(FilmQuiz.label(film))
                        .accessibilityHint("Opens film details")
                        .accessibilityIdentifier("film-\(film.id)")
                        .visualEffect { [viewport, reduceMotion] content, geometry in
                            let x = geometry.frame(in: .named("film-rack")).midX
                            let offset = max(-1, min(1, (x - viewport / 2) / (width + 10)))
                            return content
                                .rotation3DEffect(.degrees(reduceMotion ? 0 : -22 * offset),
                                                  axis: (x: 0, y: 1, z: 0), perspective: 0.55)
                                .scaleEffect(reduceMotion ? 1 : 1 - abs(offset) * 0.06)
                        }
                        .id(film.id)
                    }
                }.scrollTargetLayout()
            }
            .contentMargins(.horizontal, max(0, (viewport - width) / 2), for: .scrollContent)
            .contentMargins(.vertical, 12, for: .scrollContent)
            .coordinateSpace(name: "film-rack")
            .onGeometryChange(for: CGFloat.self) { $0.size.width } action: { viewport = $0 }
            .scrollIndicators(.hidden)
            .scrollTargetBehavior(.viewAligned(limitBehavior: .alwaysByOne, anchor: .center))
            .scrollPosition(id: $position, anchor: .center)
            .background(h.brass.opacity(0.055), in: RoundedRectangle(cornerRadius: 10))
            .overlay(alignment: .bottom) {
                Rectangle().fill(h.brass.opacity(0.55)).frame(height: 2).accessibilityHidden(true)
            }
            .onChange(of: films.map(\.id), initial: true) { _, ids in
                if position.map(ids.contains) != true { position = ids.first }
            }
            if films.indices.contains(index) {
                details(films[index], house: h)
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

    private func details(_ film: Film, house: House) -> some View {
        VStack(spacing: 6) {
            Text(film.title).font(.system(.title2, design: .serif).weight(.semibold)).lineLimit(2)
            Text([film.year, film.viewingLabel].compactMap { $0 }.joined(separator: "  ·  "))
                .font(.subheadline)
            if let rank = ranks[film.ref] { Text("Ranked · #\(rank)").font(.caption.bold()).foregroundStyle(house.brass) }
            Button { open(film.ref) } label: {
                Label("Film details", systemImage: "ticket").font(.subheadline.weight(.semibold))
            }.buttonStyle(.bordered).tint(house.brass)
        }
        .multilineTextAlignment(.center).padding(.top, 4).frame(maxWidth: .infinity)
    }
}

private struct DVDJacket: View {
    let film: Film
    let width: CGFloat
    let reduceMotion: Bool
    @State private var pointer: CGPoint = .zero

    var body: some View {
        let artWidth = max(1, width - 12)
        let height = artWidth * 1.5 + 8
        return HStack(spacing: 0) {
            LinearGradient(colors: [.black, .gray.opacity(0.65), .black], startPoint: .leading, endPoint: .trailing)
                .frame(width: 8)
            Poster(film: film, width: artWidth)
                .overlay {
                    LinearGradient(stops: [.init(color: .white.opacity(0.18), location: 0),
                                           .init(color: .clear, location: 0.38),
                                           .init(color: .white.opacity(0.06), location: 0.46),
                                           .init(color: .clear, location: 0.54)],
                                   startPoint: UnitPoint(x: pointer.x * 0.16, y: 0), endPoint: .bottomTrailing)
                }
                .padding(.trailing, 4)
        }
        .frame(width: width, height: height)
        .background(Color(white: 0.12))
        .clipShape(RoundedRectangle(cornerRadius: 5))
        .overlay { RoundedRectangle(cornerRadius: 5).strokeBorder(.white.opacity(0.22)) }
        .shadow(color: .black.opacity(0.3), radius: 3, x: 1, y: 3)
        .rotation3DEffect(.degrees(-pointer.y * 4), axis: (x: 1, y: 0, z: 0))
        .rotation3DEffect(.degrees(pointer.x * 7), axis: (x: 0, y: 1, z: 0))
        .onContinuousHover { phase in
            guard !reduceMotion else { pointer = .zero; return }
            switch phase {
            case .active(let p): pointer = CGPoint(x: max(-1, min(1, 2 * p.x / width - 1)),
                                                    y: max(-1, min(1, 2 * p.y / height - 1)))
            case .ended: pointer = .zero
            }
        }
        .onChange(of: reduceMotion) { _, enabled in if enabled { pointer = .zero } }
    }
}
