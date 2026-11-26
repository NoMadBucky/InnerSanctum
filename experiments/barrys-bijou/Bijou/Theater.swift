import SwiftUI
#if os(macOS)
import AppKit
#else
import UIKit
#endif

struct House {
    let dark: Bool
    init(_ scheme: ColorScheme) { dark = scheme == .dark }
    var paper: Color { dark ? Color(red: 0.07, green: 0.10, blue: 0.14) : Color(red: 0.97, green: 0.94, blue: 0.87) }
    var ink: Color { dark ? Color(red: 0.97, green: 0.93, blue: 0.84) : Color(red: 0.13, green: 0.17, blue: 0.20) }
    var brass: Color { dark ? Color(red: 0.91, green: 0.77, blue: 0.48) : Color(red: 0.47, green: 0.32, blue: 0.13) }
}

struct Poster: View {
    @EnvironmentObject var studio: Studio
    let film: Film?
    let width: CGFloat
    var body: some View {
        let _ = studio.coverGeneration
        ZStack {
            if let key = film?.posterKey, let url = studio.coverURL(key), let image = image(url) {
                image.resizable().scaledToFill()
            } else {
                let colors: [Color] = [Color(red: 0.17, green: 0.29, blue: 0.32), Color(red: 0.33, green: 0.17, blue: 0.24),
                                       Color(red: 0.18, green: 0.29, blue: 0.23), Color(red: 0.20, green: 0.22, blue: 0.34)]
                let index = (film?.id.utf8.reduce(0) { ($0 + Int($1)) % colors.count }) ?? 0
                colors[index]
                if studio.isSample && film?.year != nil {
                    Canvas { ctx, size in
                        var rays = Path()
                        let foot = CGPoint(x: size.width * 0.5, y: size.height * 1.18)
                        for i in -4...10 {
                            rays.move(to: foot); rays.addLine(to: CGPoint(x: Double(i) * size.width / 6, y: 0))
                        }
                        ctx.stroke(rays, with: .color(.white.opacity(0.18)), lineWidth: 1)
                        var step = Path()
                        for d in [0.09, 0.14, 0.19] {
                            let offset = size.width * d
                            step.move(to: CGPoint(x: offset, y: size.height * 0.34))
                            step.addLine(to: CGPoint(x: offset, y: offset))
                            step.addLine(to: CGPoint(x: size.width - offset, y: offset))
                            step.addLine(to: CGPoint(x: size.width - offset, y: size.height * 0.34))
                        }
                        ctx.stroke(step, with: .color(.yellow.opacity(0.42)), lineWidth: 1)
                    }
                }
                Rectangle().strokeBorder(.white.opacity(0.3), lineWidth: 1).padding(4)
                VStack(spacing: 6) {
                    Image(systemName: ["sparkles", "moon.stars", "sun.horizon", "diamond"][index])
                        .font(.system(size: width * 0.26, weight: .light))
                    if width >= 88 { Text(film?.title ?? "Unavailable").font(.system(.caption, design: .serif)).multilineTextAlignment(.center) }
                }.foregroundStyle(Color(red: 0.95, green: 0.84, blue: 0.60)).padding(7)
            }
        }
        .frame(width: width, height: width * 1.48).clipped()
        .accessibilityHidden(true)
    }
    private func image(_ url: URL) -> Image? {
        #if os(macOS)
        return NSImage(contentsOf: url).map(Image.init(nsImage:))
        #else
        return UIImage(contentsOfFile: url.path).map(Image.init(uiImage:))
        #endif
    }
}

struct Theater: View {
    @EnvironmentObject private var studio: Studio
    @Environment(\.colorScheme) private var scheme
    @Environment(\.scenePhase) private var phase
    @State private var home = false
    @State private var query = ""
    @State private var path: [FilmRef] = []
    var body: some View {
        let h = House(scheme)
        NavigationStack(path: $path) {
            ScrollView {
                VStack(alignment: .leading, spacing: 18) {
                    VStack(alignment: .leading, spacing: 8) {
                        Text("B A R R Y ’ S   B I J O U").font(.caption.weight(.bold)).foregroundStyle(h.brass)
                        Text("Watched").font(.system(size: 44, weight: .medium, design: .serif))
                        Rectangle().fill(h.brass).frame(height: 2)
                        HStack {
                            Text(studio.isSample ? "SAMPLE PROGRAM" : studio.isSnapshot ? "SCREENING COPY" :
                                    studio.journal?.base.origin == "personal" ? "PERSONAL OKF" : "HOME PROGRAM")
                            Spacer()
                            Text("\(studio.journal?.base.films.count ?? 0) FILMS")
                        }.font(.caption.monospaced()).foregroundStyle(h.brass)
                    }
                    if let j = studio.journal {
                        Button { home = true } label: {
                            Label(studio.status, systemImage: j.needsReview ? "exclamationmark.circle" : "ticket")
                        }.buttonStyle(.plain).accessibilityHint("Opens home sync")
                        TextField("Find a film", text: $query).textFieldStyle(.roundedBorder)
                        let films = j.base.films.sorted(by: Film.viewingOrder)
                            .filter { query.isEmpty || $0.title.localizedCaseInsensitiveContains(query) }
                        if films.isEmpty { Text(query.isEmpty ? "Your watched films will appear here." : "No matching films.") }
                        LazyVStack(alignment: .leading, spacing: 0) {
                            ForEach(films) { film in
                                Button { path.append(film.ref) } label: {
                                    HStack(spacing: 15) {
                                        Poster(film: film, width: 46)
                                        VStack(alignment: .leading, spacing: 4) {
                                            Text(film.title).font(.system(.headline, design: .serif))
                                            Text([film.year, film.watched ?? "Watch date unknown"].compactMap { $0 }.joined(separator: "  ·  "))
                                                .font(.subheadline).foregroundStyle(.secondary)
                                            if let i = j.order.firstIndex(of: film.ref) { Text("Ranked · #\(i + 1)").font(.caption.bold()).foregroundStyle(h.brass) }
                                        }
                                        Spacer()
                                        Image(systemName: "chevron.right").font(.caption)
                                    }.contentShape(Rectangle()).padding(.vertical, 9)
                                }.buttonStyle(.plain).accessibilityIdentifier("film-\(film.id)")
                                Divider()
                            }
                        }
                    } else {
                        Text(studio.notice ?? "Loading the film catalog…")
                    }
                }.frame(maxWidth: 720).padding(22).frame(maxWidth: .infinity)
            }.background(h.paper).foregroundStyle(h.ink)
            .toolbar { Button { home = true } label: { Label("Home Sync", systemImage: "house") } }
            .navigationDestination(for: FilmRef.self) { ref in FilmDetail(ref: ref) }
        }
        .sheet(isPresented: $home) { HomePanel() }
        .onChange(of: studio.journal?.base.library) { _, _ in path.removeAll() }
        .task(id: phase) {
            guard phase == .active else { return }
            await studio.sync()
            while !Task.isCancelled {
                do { try await Task.sleep(for: .seconds(30)) } catch { return }
                if studio.journal?.pending.isEmpty == false { await studio.sync() }
            }
        }
    }
}

struct FilmDetail: View {
    let ref: FilmRef
    @EnvironmentObject private var studio: Studio
    @Environment(\.colorScheme) private var scheme
    @State private var placing = false
    var body: some View {
        let h = House(scheme)
        ScrollView {
            if let j = studio.journal, let f = j.base.films.first(where: { $0.ref == ref }) {
                VStack(alignment: .leading, spacing: 16) {
                    HStack(alignment: .top, spacing: 18) {
                        Poster(film: f, width: 96)
                        VStack(alignment: .leading, spacing: 8) {
                            Text("FILM DETAIL").font(.caption.monospaced()).foregroundStyle(h.brass)
                            Text(f.title).font(.system(.title, design: .serif).weight(.medium))
                            if let year = f.year { Text(year).font(.headline) }
                            Text(f.watched.map { "Watched \($0)" } ?? "Watch date unknown").font(.subheadline)
                        }
                    }
                    if let d = f.description { Text(d).font(.system(.title3, design: .serif)) }
                    let rank = j.order.firstIndex(of: ref)
                    if let rank { Text("Your ranking: #\(rank + 1) of \(j.order.count)").font(.headline).accessibilityIdentifier("rank-position") }
                    Button(rank == nil ? "Rank" : "Rerank") { placing = true }
                        .buttonStyle(.borderedProminent).disabled(j.needsReview).accessibilityIdentifier("rank-action")
                    if j.needsReview { Text("Open Home Sync to review the ranking.").font(.caption) }
                    Divider()
                    ForEach(Array(f.body.components(separatedBy: "\n\n").enumerated()), id: \.offset) { _, block in
                        if block.hasPrefix("#") {
                            Text(block.trimmingCharacters(in: CharacterSet(charactersIn: "# "))).font(.headline)
                        } else {
                            Text((try? AttributedString(markdown: block, options: .init(interpretedSyntax: .inlineOnlyPreservingWhitespace))) ?? AttributedString(block))
                                .textSelection(.enabled)
                        }
                    }
                    if !f.sources.isEmpty { Text("Sources").font(.headline) }
                    ForEach(Array(f.sources.enumerated()), id: \.offset) { _, s in
                        if let u = URL(string: s.address), ["https", "http"].contains(u.scheme ?? "") { Link(s.title, destination: u) }
                        else { Text("\(s.title) · \(s.address)").textSelection(.enabled) }
                    }
                    if let fields = f.metadata, !fields.isEmpty {
                        DisclosureGroup("Recorded metadata") {
                            VStack(alignment: .leading, spacing: 4) {
                                ForEach(fields.keys.sorted(), id: \.self) { key in
                                    Text("\(key): \(fields[key] ?? "")").font(.callout).textSelection(.enabled)
                                }
                            }.frame(maxWidth: .infinity, alignment: .leading)
                        }
                    }
                }.frame(maxWidth: 700, alignment: .leading).padding(22).frame(maxWidth: .infinity)
            } else { Text("This film is no longer in the watched catalog.") }
        }.background(h.paper).foregroundStyle(h.ink)
        .sheet(isPresented: $placing) {
            if let j = studio.journal { PlacementEditor(film: ref, catalog: j.base, order: j.order, review: false) }
        }
    }
}
