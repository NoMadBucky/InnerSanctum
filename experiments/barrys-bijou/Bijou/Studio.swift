import CryptoKit
import SwiftUI

@MainActor
final class Studio: ObservableObject {
    @Published private(set) var journal: Journal?
    @Published private(set) var credentials: Credentials?
    @Published private(set) var syncing = false
    @Published private(set) var coverGeneration = 0
    @Published var notice: String?
    private var storage: Storage?
    private var sample: Catalog?
    private var coverJob: Task<Void, Never>?
    static let sampleID = "local-screening-room"

    init() {
        do {
            var testDirectory: URL?
            #if DEBUG
            let args = ProcessInfo.processInfo.arguments
            if let i = args.firstIndex(of: "--sample-ui-test"), args.indices.contains(i + 1),
               let id = UUID(uuidString: args[i + 1]) {
                testDirectory = FileManager.default.temporaryDirectory.appendingPathComponent("bijou-ui-\(id.uuidString)")
            }
            #endif
            let dir = try testDirectory ?? FileManager.default.url(for: .applicationSupportDirectory, in: .userDomainMask,
                                                                   appropriateFor: nil, create: true)
                .appendingPathComponent("org.innersanctum.bijou", isDirectory: true)
            let storage = try Storage(directory: dir)
            self.storage = storage
            guard let url = Bundle.main.url(forResource: "Sample", withExtension: "json") else {
                throw BijouError("The sample program is missing from this build.")
            }
            let films = try JSONDecoder().decode([Film].self, from: Data(contentsOf: url))
            let sample = Catalog(library: Self.sampleID, revision: "sample", films: films, order: [], labels: [:], issues: [])
            self.sample = sample
            journal = try storage.load(Self.sampleID) ?? Journal(sample)
            if testDirectory != nil { return }
            credentials = try Keyring.read()
            if let credentials, !UserDefaults.standard.bool(forKey: "preferSample"),
               let saved = try storage.load(credentials.library) { journal = saved }
            if let key = UserDefaults.standard.string(forKey: "activeScreeningCopy"),
               key.hasPrefix("snapshot-"), let saved = try storage.load(key) { journal = saved }
        } catch { notice = error.localizedDescription }
    }

    var isSample: Bool { journal?.base.library == Self.sampleID }
    var isSnapshot: Bool { journal?.base.library.hasPrefix("snapshot-") == true }
    var status: String {
        guard let j = journal else { return "Library unavailable" }
        if j.needsReview { return "Needs review" }
        if isSample || isSnapshot || !j.pending.isEmpty { return "Saved on this device" }
        return "Synced to OKF"
    }

    private func install(_ next: Journal) throws {
        guard let storage else { throw BijouError("Local storage is unavailable.") }
        try storage.save(next)
        journal = next
    }

    private func mutate(_ action: (inout Journal) throws -> Void) throws {
        guard var next = journal else { throw BijouError("The journal is unavailable.") }
        try action(&next)
        try install(next)
    }

    func confirm(_ film: FilmRef, gap: Gap, reviewing revision: String?) throws {
        if let revision { try mutate { try $0.resolve(on: revision, gap: gap) } }
        else { try mutate { try $0.confirm(film, gap: gap) } }
        if !isSample && !isSnapshot { Task { await sync() } }
    }

    func keepCurrent(on revision: String) throws {
        try mutate { try $0.resolve(on: revision, gap: nil) }
        Task { await sync() }
    }

    func showSample() {
        guard !syncing, let sample else { return }
        do {
            coverJob?.cancel()
            try install(storage?.load(Self.sampleID) ?? Journal(sample))
            UserDefaults.standard.removeObject(forKey: "activeScreeningCopy")
            UserDefaults.standard.set(true, forKey: "preferSample")
            notice = nil
        } catch { notice = error.localizedDescription }
    }

    func pair(_ code: PairCode, at address: URL) async -> Bool {
        guard !syncing else { return false }
        syncing = true; defer { syncing = false }
        do {
            let next = try await HomeClient.pair(code, at: address)
            if let old = credentials, old.library != next.library,
               let saved = try storage?.load(old.library), !saved.pending.isEmpty {
                throw BijouError("The previous home library has saved moves. Sync those before changing libraries.")
            }
            try Keyring.store(next)
            credentials = next
            try await loadHome(next)
            notice = nil
            return true
        } catch { notice = error.localizedDescription; return false }
    }

    private func loadHome(_ creds: Credentials) async throws {
        if let saved = try storage?.load(creds.library) {
            try install(saved)
        } else {
            let remote = try await HomeClient(creds).catalog()
            guard remote.library == creds.library else { throw BijouError("The Mac returned a different library.") }
            try install(Journal(remote))
        }
        UserDefaults.standard.set(false, forKey: "preferSample")
        UserDefaults.standard.removeObject(forKey: "activeScreeningCopy")
        Task { await sync() }
    }

    func importScreeningCopy(_ url: URL) async {
        guard !syncing, let storage else { return }
        syncing = true; defer { syncing = false }
        let access = url.startAccessingSecurityScopedResource()
        defer { if access { url.stopAccessingSecurityScopedResource() } }
        do {
            let copy = try await Task.detached { try ScreeningCopy.read(url) }.value
            try FileManager.default.createDirectory(at: storage.directory.appendingPathComponent("Covers"),
                                                   withIntermediateDirectories: true)
            for (key, bytes) in copy.covers {
                guard let path = coverURL(key, library: copy.catalog.library) else { throw BijouError("Invalid thumbnail key.") }
                try bytes.write(to: path, options: .atomic)
            }
            try install(storage.load(copy.catalog.library) ?? Journal(copy.catalog))
            coverGeneration += 1
            UserDefaults.standard.set(copy.catalog.library, forKey: "activeScreeningCopy")
            notice = nil
        } catch { notice = error.localizedDescription }
    }

    func showHome() async {
        guard !syncing, let credentials else { return }
        syncing = true
        do { try await loadHome(credentials); notice = nil } catch { notice = error.localizedDescription }
        syncing = false
    }

    func sync(manual: Bool = false) async {
        guard !syncing, !isSample, !isSnapshot, let creds = credentials,
              let j = journal, j.base.library == creds.library else { return }
        syncing = true; defer { syncing = false }
        let client = HomeClient(creds)
        do {
            while let current = journal, !current.pending.isEmpty && !current.needsReview {
                var request: Placement?
                try mutate { request = $0.outgoing() }
                guard let request else { break }
                do {
                    let receipt = try await client.place(request)
                    try mutate { try $0.acknowledge(receipt) }
                } catch let err as HomeResponse where err.status == 409 {
                    let remote = try await client.catalog()
                    try mutate { try $0.receive(remote, rejected: request.requestID) }
                    notice = "The ranking changed on the Mac. Your local order is saved for review."
                    cache(remote, client: client)
                    return
                }
            }
            let fresh = try await client.catalog()
            try mutate { try $0.receive(fresh) }
            notice = nil
            cache(fresh, client: client)
        } catch {
            if manual || !(error is URLError) { notice = error.localizedDescription }
        }
    }

    func coverURL(_ key: String, library: String? = nil) -> URL? {
        guard key.range(of: "^[0-9a-f]{64}$", options: .regularExpression) != nil,
              let library = library ?? journal?.base.library else { return nil }
        let scope = SHA256.hash(data: Data(library.utf8)).map { String(format: "%02x", $0) }.joined()
        return storage?.directory.appendingPathComponent("Covers").appendingPathComponent("\(scope)-\(key).jpg")
    }
    private func cache(_ fresh: Catalog, client: HomeClient) {
        guard coverJob == nil, let dir = storage?.directory.appendingPathComponent("Covers") else { return }
        coverJob = Task {
            defer { coverJob = nil }
            try? FileManager.default.createDirectory(at: dir, withIntermediateDirectories: true)
            for key in Set(fresh.films.compactMap(\.posterKey)) {
                guard !Task.isCancelled else { return }
                guard let path = coverURL(key, library: fresh.library), !FileManager.default.fileExists(atPath: path.path) else { continue }
                if let bytes = try? await client.cover(key), bytes.count <= 1024 * 1024,
                   (try? bytes.write(to: path, options: .atomic)) != nil { coverGeneration += 1 }
            }
        }
    }
}
