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
    var fit = false
    var body: some View {
        let _ = studio.coverGeneration
        ZStack {
            if let key = film?.posterKey, let url = studio.coverURL(key), let image = image(url) {
                image.resizable().aspectRatio(contentMode: fit ? .fit : .fill)
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
        .frame(width: width, height: width * 1.5).clipped()
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
    @State private var searchingTMDb = false
    @State private var query = ""
    @State private var sort = WatchedSort.viewed
    @State private var shelf = MovieShelf.watched
    @State private var path: [FilmRef] = []
    @State private var entered = false
    var body: some View {
        Group {
            if entered {
                watched
            } else {
                TheaterLobby { entered = true }
            }
        }
        .task(id: phase) {
            guard phase == .active else { return }
            await studio.sync()
            while !Task.isCancelled {
                do { try await Task.sleep(for: .seconds(30)) } catch { return }
                if studio.journal?.pending.isEmpty == false { await studio.sync() }
            }
        }
    }

    private var watched: some View {
        let h = House(scheme)
        let shelfFilms = studio.journal?.base.films.filter(shelf.includes) ?? []
        return NavigationStack(path: $path) {
            ScrollView {
                VStack(alignment: .leading, spacing: 18) {
                    VStack(spacing: 10) {
                        BillingLine(title: "BIJOU").foregroundStyle(MarqueeFinish.gold)
                        Text(shelf.rawValue).font(.system(.largeTitle, design: .serif).weight(.medium))
                            .multilineTextAlignment(.center).accessibilityAddTraits(.isHeader)
                        Rectangle().fill(MarqueeFinish.gold.opacity(0.48)).frame(height: 1)
                        HStack {
                            Text(studio.isSample ? "SAMPLE PROGRAM" : studio.isSnapshot ? "SCREENING COPY" :
                                    studio.journal?.base.origin == "personal" ? "PERSONAL OKF" : "HOME PROGRAM")
                            Spacer()
                            Text("\(shelfFilms.count) FILMS")
                        }.font(.caption.monospaced()).foregroundStyle(MarqueeFinish.gold)
                    }.modifier(MarqueePanel())
                    if let j = studio.journal {
                        Button { home = true } label: {
                            Label(studio.status, systemImage: j.needsReview ? "exclamationmark.circle" : "ticket")
                        }.buttonStyle(.plain).accessibilityHint("Opens home sync")
                        TextField("Find a film or transcript", text: $query).textFieldStyle(.roundedBorder)
                        if j.base.origin == "personal", studio.credentials?.library == j.base.library {
                            Button { searchingTMDb = true } label: { Label("Search TMDb", systemImage: "magnifyingglass") }
                                .buttonStyle(AdmissionStyle())
                        }
                        HStack {
                            Text("Collection").font(.subheadline.bold())
                            Spacer()
                            Picker("Show movies", selection: $shelf) {
                                ForEach(MovieShelf.allCases, id: \.self) { Text($0.rawValue).tag($0) }
                            }.pickerStyle(.menu).labelsHidden()
                        }
                        Picker("Sort movies", selection: $sort) {
                            Text("Recently viewed").tag(WatchedSort.viewed)
                            Text("Ranked").tag(WatchedSort.ranked)
                        }.pickerStyle(.segmented)
                        let ranks = Dictionary(j.order.enumerated().map { ($0.element, $0.offset + 1) },
                                               uniquingKeysWith: min)
                        let matches = shelfFilms.filter { film in
                            query.isEmpty || film.title.localizedCaseInsensitiveContains(query) ||
                                film.archivedReactions?.contains { $0.transcript?.localizedCaseInsensitiveContains(query) == true } == true
                        }
                        let films = sort.films(matches, ranks: ranks)
                        if films.isEmpty { Text(query.isEmpty ? "No films in this collection yet." : "No matching films.") }
                        LazyVStack(alignment: .leading, spacing: 0) {
                            ForEach(films) { film in
                                Button { path.append(film.ref) } label: {
                                    HStack(spacing: 15) {
                                        Poster(film: film, width: 112 * 2 / 3)
                                            .overlay { Rectangle().strokeBorder(h.brass.opacity(0.4)) }
                                        VStack(alignment: .leading, spacing: 4) {
                                            Text(film.title).font(.system(.headline, design: .serif))
                                            Text([film.year, film.viewingLabel].compactMap { $0 }.joined(separator: "  ·  "))
                                                .font(.subheadline).foregroundStyle(.secondary)
                                            if let rank = ranks[film.ref] {
                                                Text("Ranked · #\(rank)").font(.caption.monospacedDigit().weight(.semibold))
                                                    .foregroundStyle(h.brass).padding(.horizontal, 7).padding(.vertical, 3)
                                                    .background(h.brass.opacity(0.09))
                                            }
                                        }
                                        Spacer()
                                        Image(systemName: "chevron.right").font(.caption)
                                    }.contentShape(Rectangle()).padding(.vertical, 12)
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
        .sheet(isPresented: $searchingTMDb) {
            if let creds = studio.credentials, let catalog = studio.journal?.base {
                MovieDiscovery(credentials: creds, catalog: catalog, initial: query) { ref in
                    searchingTMDb = false
                    path.append(ref)
                }
            }
        }
        .onChange(of: studio.journal?.base.library) { _, _ in path.removeAll() }
    }
}

private struct TheaterLobby: View {
    @Environment(\.colorScheme) private var scheme
    let enter: () -> Void

    var body: some View {
        let h = House(scheme)
        GeometryReader { bounds in
            ScrollView {
                VStack(spacing: 18) {
                    Image("LobbyMarquee").resizable().scaledToFit()
                        .frame(width: min(192, bounds.size.width * 0.44, bounds.size.height * 0.32))
                        .clipShape(RoundedRectangle(cornerRadius: 22))
                        .accessibilityHidden(true)
                    Text("Bijou").font(.system(.largeTitle, design: .serif).weight(.medium))
                        .accessibilityAddTraits(.isHeader)
                    BillingLine(title: "MOVIE JOURNAL").foregroundStyle(MarqueeFinish.gold)
                    Button(action: enter) {
                        Label("Enter theater", systemImage: "ticket")
                            .font(.headline).padding(.horizontal, 8).frame(minHeight: 36)
                    }
                    .buttonStyle(AdmissionStyle())
                    .accessibilityHint("Opens your watched films")
                    .accessibilityIdentifier("enter-theater")
                    .padding(.top, 10)
                }
                .multilineTextAlignment(.center).padding(.vertical, 18)
                .modifier(MarqueePanel()).frame(maxWidth: 520).padding(18)
                .frame(maxWidth: .infinity, minHeight: bounds.size.height)
            }
        }.background(h.paper).foregroundStyle(h.ink)
    }
}

struct FilmDetail: View {
    let ref: FilmRef
    @EnvironmentObject private var studio: Studio
    @Environment(\.colorScheme) private var scheme
    @State private var placing = false
    @State private var posterOpen = false
    @State private var dating = false
    @Environment(\.dynamicTypeSize) private var typeSize
    @State private var plexUnavailable = false
    @Environment(\.openURL) private var openURL
    var body: some View {
        let h = House(scheme)
        ScrollView {
            if let j = studio.journal, let f = j.base.films.first(where: { $0.ref == ref }) {
                VStack(alignment: .leading, spacing: 16) {
                    let billing = typeSize.isAccessibilitySize
                        ? AnyLayout(VStackLayout(alignment: .leading, spacing: 14))
                        : AnyLayout(HStackLayout(alignment: .top, spacing: 14))
                    billing {
                        Button { posterOpen = true } label: { Poster(film: f, width: 96) }
                            .buttonStyle(.plain).accessibilityLabel("View full poster for \(f.title)")
                        VStack(alignment: .leading, spacing: 8) {
                            Text("BIJOU  /  FILM NOTES").font(.caption.weight(.semibold)).tracking(1.4)
                                .foregroundStyle(MarqueeFinish.gold)
                            Text(f.title).font(.system(.title, design: .serif).weight(.medium))
                            if let year = f.year { Text(year).font(.headline) }
                            Text(f.viewingLabel).font(.subheadline)
                        }
                    }.frame(maxWidth: .infinity, alignment: .leading).modifier(MarqueePanel())
                    if let d = f.description { Text(d).font(.system(.title3, design: .serif)) }
                    VStack(alignment: .leading, spacing: 10) {
                        if let destination = f.tmdbEntry ?? f.tmdbSearch {
                            Link(destination: destination) {
                                Label(f.tmdbEntry == nil ? "Search TMDb" : "View on TMDb", systemImage: "film")
                            }
                        }
                    #if os(iOS)
                        if f.isInLibrary {
                            if let links = f.plexMovieLinks {
                                Button {
                                    openURL(links.app) { if !$0 { openURL(links.web) } }
                                } label: { Label("Open movie in Plex", systemImage: "play.rectangle") }
                            } else {
                                Button {
                                    openURL(URL(string: "plex://")!) { if !$0 { plexUnavailable = true } }
                                } label: { Label("Open Plex", systemImage: "play.rectangle") }
                            }
                        }
                    #endif
                    }
                    .buttonStyle(AdmissionStyle())
                    let rank = j.order.firstIndex(of: ref)
                    if let rank { Text("Your ranking: #\(rank + 1) of \(j.order.count)").font(.headline).accessibilityIdentifier("rank-position") }
                    if f.isViewed {
                        Button(rank == nil ? "Rank" : "Rerank") { placing = true }
                            .buttonStyle(.borderedProminent).disabled(j.needsReview).accessibilityIdentifier("rank-action")
                    } else if studio.credentials?.library == j.base.library {
                        Button { dating = true } label: { Label("Mark as watched", systemImage: "calendar.badge.checkmark") }
                            .buttonStyle(AdmissionStyle())
                    }
                    if j.needsReview { Text("Open Home Sync to review the ranking.").font(.caption) }
                    if let store = studio.reactionStore(library: j.base.library, film: ref) {
                        Divider()
                        AudioReactions(store: store, viewed: f.watched, film: ref, archived: f.archivedReactions ?? []).id(store.directory)
                    }
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
            } else { Text("This film is no longer in the catalog.") }
        }.background(h.paper).foregroundStyle(h.ink)
        .sheet(isPresented: $dating) { WatchedDateSheet(film: ref) }
        .sheet(isPresented: $placing) {
            if let j = studio.journal { PlacementEditor(film: ref, catalog: j.base, order: j.order, review: false) }
        }
        #if os(iOS)
        .fullScreenCover(isPresented: $posterOpen) { posterPage }
        #else
        .sheet(isPresented: $posterOpen) { posterPage.frame(minWidth: 480, minHeight: 560) }
        #endif
        .alert("Plex could not be opened", isPresented: $plexUnavailable) {
            Button("OK") {}
        } message: { Text("Check that the Plex app is installed on this iPhone.") }
    }
    private var posterPage: some View {
        GeometryReader { bounds in
            ZStack(alignment: .topTrailing) {
                Color.black.ignoresSafeArea()
                if let f = studio.journal?.base.films.first(where: { $0.ref == ref }) {
                    Poster(film: f, width: min(bounds.size.width, bounds.size.height / 1.5), fit: true)
                        .frame(maxWidth: .infinity, maxHeight: .infinity)
                        .accessibilityHidden(false).accessibilityLabel("\(f.title) poster")
                }
                Button { posterOpen = false } label: {
                    Label("Close poster", systemImage: "xmark.circle.fill").labelStyle(.iconOnly)
                        .font(.title).padding(8)
                }.buttonStyle(.plain).foregroundStyle(.white).background(.black.opacity(0.7), in: Circle()).padding()
                    .keyboardShortcut(.cancelAction)
            }
        }
    }
}

private struct WatchedDateSheet: View {
    let film: FilmRef
    @EnvironmentObject private var studio: Studio
    @Environment(\.dismiss) private var dismiss
    @State private var date = Date()
    @State private var saving = false
    @State private var issue: String?
    var body: some View {
        VStack(alignment: .leading, spacing: 18) {
            Text("Mark as watched").font(.system(.title, design: .serif))
            Text(studio.journal?.base.title(film) ?? "Film").font(.headline)
            DatePicker("Watched date", selection: $date, in: ...Date(), displayedComponents: .date)
            if let issue { Text(issue).font(.callout) }
            HStack {
                Button("Cancel") { dismiss() }
                Spacer()
                Button(saving ? "Saving…" : "Save") {
                    saving = true
                    Task {
                        defer { saving = false }
                        do { try await studio.markWatched(film, date: date); dismiss() }
                        catch { issue = error.localizedDescription }
                    }
                }.buttonStyle(AdmissionStyle()).disabled(studio.syncing)
            }
        }.padding(24).disabled(saving).interactiveDismissDisabled(saving)
        #if os(iOS)
        .presentationDetents([.medium, .large])
        #else
        .frame(minWidth: 340)
        #endif
    }
}
