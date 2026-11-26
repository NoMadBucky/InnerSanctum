import Combine
import Foundation
import Network
import dnssd

@MainActor
final class HomeDiscovery: ObservableObject {
    struct Mac: Identifiable, Equatable {
        let name: String
        let url: URL
        var id: String { url.absoluteString }
    }
    enum Problem {
        case permission, network
        var message: String {
            switch self {
            case .permission: return "Allow Bijou in Settings → Privacy & Security → Local Network, then try finding the Mac again."
            case .network: return "Mac discovery is unavailable. Check that both devices are on the same home Wi-Fi."
            }
        }
    }
    @Published private(set) var macs: [Mac] = []
    @Published private(set) var problem: Problem?
    private var browser: NWBrowser?

    func start() {
        guard browser == nil else { return }
        let b = NWBrowser(for: .bonjourWithTXTRecord(type: "_bijou-home._tcp", domain: "local."), using: .tcp)
        browser = b
        b.stateUpdateHandler = { [weak self, weak b] state in
            Task { @MainActor [weak self, weak b] in
                guard let self, let b, self.browser === b else { return }
                switch state {
                case .failed(let error), .waiting(let error):
                    self.macs = []
                    let denied: Bool
                    switch error {
                    case .dns(let code): denied = code == kDNSServiceErr_PolicyDenied
                    case .posix(.EACCES), .posix(.EPERM): denied = true
                    default: denied = false
                    }
                    self.problem = denied ? .permission : .network
                case .ready: self.problem = nil
                default: break
                }
            }
        }
        b.browseResultsChangedHandler = { [weak self, weak b] results, _ in
            let found = results.compactMap { result -> Mac? in
                guard case .service(let name, _, _, _) = result.endpoint,
                      case .bonjour(let txt) = result.metadata,
                      let raw = txt.dictionary["url"], let url = try? HomeAddress.parse(raw) else { return nil }
                return Mac(name: name, url: url)
            }
            Task { @MainActor [weak self, weak b] in
                guard let self, let b, self.browser === b else { return }
                var seen = Set<String>()
                self.macs = found.sorted { ($0.name, $0.id) < ($1.name, $1.id) }.filter { seen.insert($0.id).inserted }
            }
        }
        b.start(queue: .main)
    }

    func stop() {
        browser?.cancel()
        browser = nil
        macs = []
        problem = nil
    }
}
