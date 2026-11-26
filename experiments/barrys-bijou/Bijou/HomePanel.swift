import SwiftUI
import UniformTypeIdentifiers
#if os(iOS)
import UIKit
#endif

private struct RankingExport: FileDocument {
    static let markdown = UTType(filenameExtension: "md") ?? .plainText
    static var readableContentTypes: [UTType] { [markdown] }
    var text: String
    init(_ text: String) { self.text = text }
    init(configuration: ReadConfiguration) throws {
        guard let bytes = configuration.file.regularFileContents,
              let string = String(data: bytes, encoding: .utf8) else { throw BijouError("Invalid Markdown.") }
        text = string
    }
    func fileWrapper(configuration: WriteConfiguration) throws -> FileWrapper {
        FileWrapper(regularFileWithContents: Data(text.utf8))
    }
}

struct HomePanel: View {
    @EnvironmentObject private var studio: Studio
    @Environment(\.dismiss) private var dismiss
    @Environment(\.openURL) private var openURL
    @Environment(\.colorScheme) private var scheme
    @AppStorage("houseLights") private var lights = "Automatic"
    @StateObject private var nearby = HomeDiscovery()
    @State private var draft = PairingDraft()
    @State private var showPairingHint = false
    @State private var pairing = false
    @FocusState private var pairingFocus: PairingDraft.Field?
    @State private var reviewing = false
    @State private var exporting = false
    @State private var importing = false
    @State private var pairExpanded = false
    var body: some View {
        let form = draft.check(nearby: nearby.macs.map(\.url))
        ScrollView {
            VStack(alignment: .leading, spacing: 16) {
                HStack {
                    Text("Settings").font(.system(.largeTitle, design: .serif)).accessibilityAddTraits(.isHeader)
                    Spacer()
                    Button("Done") { dismiss() }
                }
                settingsSection("Appearance", icon: "circle.lefthalf.filled") {
                    Picker("House lights", selection: $lights) {
                        ForEach(["Automatic", "Working Hours", "After Hours"], id: \.self) { Text($0) }
                    }
                }
                settingsSection("Library & sync", icon: "arrow.triangle.2.circlepath") {
                    if let j = studio.journal {
                        Text(studio.isSample ? "Sample screening room" : studio.isSnapshot ? "Private screening copy" :
                                j.base.origin == "personal" ? "Personal OKF library" : "Paired home library").font(.headline)
                        Text(studio.isSample
                             ? "These fictional films are yours to try offline. Sample placements stay on this device."
                             : studio.isSnapshot ? "Rankings on this copy stay on this device. You can export them as Markdown."
                             : "\(studio.status) · \(j.pending.count) pending placement\(j.pending.count == 1 ? "" : "s")")
                        if !studio.isSample && !studio.isSnapshot {
                            Button(studio.syncing ? "Syncing…" : "Sync now") { Task { await studio.sync(manual: true) } }
                                .disabled(studio.syncing)
                        }
                        if let fresh = j.review, let move = j.pending.first {
                            Divider()
                            Text("Review \(j.base.title(move.film))").font(.headline)
                            Text("Your saved order and the Mac’s order differ. Choose this film’s place in the Mac’s list.")
                            orderList("Saved on this device", j.order, j.base, move.film)
                            orderList("Latest from the Mac", fresh.order, fresh, move.film)
                            Button("Choose placement…") { reviewing = true }
                                .disabled(!fresh.issues.isEmpty || studio.syncing)
                            if fresh.order.contains(move.film) {
                                Button("Keep its current Mac placement") {
                                    do { try studio.keepCurrent(on: fresh.revision) } catch { studio.notice = error.localizedDescription }
                                }.disabled(!fresh.issues.isEmpty || studio.syncing)
                            }
                        }
                        ForEach(Array((j.review?.issues ?? j.base.issues).enumerated()), id: \.offset) { _, message in
                            Label(message, systemImage: "exclamationmark.circle")
                        }
                    }
                    if let message = studio.notice { Text(message).font(.callout).textSelection(.enabled) }
                }
                settingsSection("Mac connection", icon: "desktopcomputer") {
                    DisclosureGroup("Pair with a Mac", isExpanded: $pairExpanded) {
                        VStack(alignment: .leading, spacing: 12) {
                            if let problem = nearby.problem {
                                Text(problem.message).font(.callout)
                                #if os(iOS)
                                if problem == .permission, let settings = URL(string: UIApplication.openSettingsURLString) {
                                    Button("Open Bijou settings") { openURL(settings) }
                                }
                                #endif
                                Button("Find Macs again") { nearby.stop(); nearby.start() }
                            }
                            if draft.manual || nearby.macs.isEmpty {
                                if nearby.macs.isEmpty && nearby.problem == nil {
                                    Text("No Mac listed yet. Enter its address from Terminal, or wait for it to appear on home Wi-Fi.")
                                        .font(.subheadline)
                                }
                                TextField("Mac address (from Terminal)", text: Binding(
                                    get: { draft.address }, set: { draft.manual = true; draft.address = $0 }
                                )).textFieldStyle(.roundedBorder)
                                    .focused($pairingFocus, equals: .address)
                                    .autocorrectionDisabled()
                                    #if os(iOS)
                                    .textInputAutocapitalization(.never).keyboardType(.URL)
                                    #endif
                                if !nearby.macs.isEmpty {
                                    Button("Find nearby Macs instead") { draft.manual = false; pairingFocus = nil }
                                }
                            } else {
                                if nearby.macs.count > 1 {
                                    Picker("Home Mac", selection: $draft.selectedMac) {
                                        Text("Choose a Mac").tag("")
                                        ForEach(nearby.macs) { mac in Text("\(mac.name) (\(mac.url.host ?? ""))").tag(mac.id) }
                                    }.focused($pairingFocus, equals: .mac)
                                } else if let mac = nearby.macs.first {
                                    Label(mac.name, systemImage: "desktopcomputer")
                                }
                                Button("Enter Mac address manually") { draft.manual = true; pairingFocus = .address }
                            }
                            Text("Type the seven-character code shown in Terminal on your Mac.").font(.subheadline)
                            TextField("7-character code", text: $draft.code)
                                .textFieldStyle(.roundedBorder).font(.body.monospaced()).autocorrectionDisabled()
                                .focused($pairingFocus, equals: .code)
                                #if os(iOS)
                                .textInputAutocapitalization(.characters).keyboardType(.asciiCapable)
                                #endif
                                .onSubmit { submitPairing() }
                            if case .incomplete(let field, let message) = form, showPairingHint || field != .code {
                                Text(message).font(.callout).accessibilityIdentifier("pairing-hint")
                            }
                            Button(pairing ? "Pairing…" : "Pair this device", action: submitPairing)
                                .buttonStyle(.borderedProminent)
                                .disabled(pairing || studio.syncing)
                            if !pairing && studio.syncing { Text("Wait for the current sync to finish, then pair.").font(.callout) }
                        }.padding(.top, 8)
                    }
                }
                settingsSection("Screening copies & exports", icon: "folder") {
                    if studio.credentials != nil && (studio.isSample || studio.isSnapshot) {
                        Button("Open paired library") { Task { await studio.showHome() } }.disabled(studio.syncing)
                    }
                    if !studio.isSample { Button("Visit sample screening room") { studio.showSample() }.disabled(studio.syncing) }
                    Button("Open screening copy…") { importing = true }.disabled(studio.syncing)
                    if studio.journal != nil {
                        Button { exporting = true } label: { Label("Export ranking as Markdown", systemImage: "square.and.arrow.up") }
                    }
                }
            }.padding(22).frame(maxWidth: 660, alignment: .leading)
        }.frame(maxWidth: .infinity).background(House(scheme).paper).foregroundStyle(House(scheme).ink)
        #if os(macOS)
        .frame(minWidth: 490, minHeight: 490)
        #endif
        .sheet(isPresented: $reviewing) {
            if let j = studio.journal, let fresh = j.review, let first = j.pending.first {
                PlacementEditor(film: first.film, catalog: fresh, order: fresh.order, review: true)
            }
        }
        .fileExporter(isPresented: $exporting, document: RankingExport(studio.journal?.markdown ?? ""),
                      contentType: RankingExport.markdown, defaultFilename: "Bijou Ranking.md") { result in
            if case let .failure(error) = result { studio.notice = error.localizedDescription }
        }
        .fileImporter(isPresented: $importing, allowedContentTypes: [.json]) { result in
            if case let .success(url) = result { Task { await studio.importScreeningCopy(url) } }
        }
        .onAppear { pairExpanded = studio.credentials == nil }
        .onChange(of: pairExpanded) { _, open in if open { nearby.start() } else { nearby.stop() } }
        .onDisappear { nearby.stop() }
        .onChange(of: pairingFocus) { _, field in
            if field == .address { draft.manual = true }
        }
    }
    private func settingsSection<Content: View>(_ title: String, icon: String,
                                                 @ViewBuilder content: () -> Content) -> some View {
        VStack(alignment: .leading, spacing: 12) {
            Label(title, systemImage: icon).font(.headline).foregroundStyle(House(scheme).brass)
                .accessibilityAddTraits(.isHeader)
            Divider()
            content()
        }.padding(16).frame(maxWidth: .infinity, alignment: .leading)
            .background(House(scheme).brass.opacity(0.06), in: RoundedRectangle(cornerRadius: 10))
    }
    private func submitPairing() {
        guard !pairing, !studio.syncing else { return }
        switch draft.check(nearby: nearby.macs.map(\.url)) {
        case .incomplete(let field, _):
            showPairingHint = true
            if field == .address { draft.manual = true }
            pairingFocus = field
        case .ready(let entry, let dest):
            showPairingHint = false
            pairingFocus = nil
            pairing = true
            let submitted = draft.code
            Task {
                defer { pairing = false }
                if await studio.pair(entry, at: dest), draft.code == submitted { draft.code = "" }
            }
        }
    }
    private func orderList(_ heading: String, _ order: [FilmRef], _ catalog: Catalog, _ selected: FilmRef) -> some View {
        DisclosureGroup(heading) {
            VStack(alignment: .leading) {
                if order.isEmpty { Text("No ranked films yet.") }
                ForEach(Array(order.enumerated()), id: \.element) { i, ref in
                    Text("\(i + 1). \(catalog.title(ref))\(ref == selected ? "  ← this film" : "")")
                        .fontWeight(ref == selected ? .bold : .regular)
                }
            }.frame(maxWidth: .infinity, alignment: .leading)
        }
    }
}
