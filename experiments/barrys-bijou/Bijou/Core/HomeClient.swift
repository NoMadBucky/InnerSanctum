import CryptoKit
import Foundation
import Security

struct PairCode: Codable {
    let url: URL
    let fingerprint: String
    let invitation: String

    static func parse(_ text: String) throws -> PairCode {
        let raw = text.trimmingCharacters(in: .whitespacesAndNewlines)
            .replacingOccurrences(of: "-", with: "+").replacingOccurrences(of: "_", with: "/")
        guard raw.count < 2048, let bytes = Data(base64Encoded: raw),
              let code = try? JSONDecoder().decode(Self.self, from: bytes),
              code.url.scheme == "https", let host = code.url.host, !host.isEmpty,
              code.url.user == nil, code.url.password == nil, code.url.query == nil,
              code.url.fragment == nil, ["", "/"].contains(code.url.path),
              code.fingerprint.range(of: "^[0-9a-f]{64}$", options: .regularExpression) != nil,
              !code.invitation.isEmpty else { throw BijouError("Paste a complete pairing code from the Mac.") }
        return code
    }
}

struct Credentials: Codable {
    let url: URL
    let fingerprint: String
    let device: String
    let token: String
    let library: String
}

enum Keyring {
    private static let query: [String: Any] = [kSecClass as String: kSecClassGenericPassword,
        kSecAttrService as String: "org.innersanctum.bijou.home", kSecAttrAccount as String: "home"]

    static func read() throws -> Credentials? {
        var q = query; q[kSecReturnData as String] = true
        var value: CFTypeRef?
        let status = SecItemCopyMatching(q as CFDictionary, &value)
        if status == errSecItemNotFound { return nil }
        guard status == errSecSuccess, let data = value as? Data else { throw BijouError("Could not read the paired Mac from Keychain (\(status)).") }
        return try JSONDecoder().decode(Credentials.self, from: data)
    }

    static func store(_ creds: Credentials) throws {
        let change: [String: Any] = [kSecValueData as String: try JSONEncoder().encode(creds),
                                     kSecAttrAccessible as String: kSecAttrAccessibleAfterFirstUnlockThisDeviceOnly]
        var status = SecItemUpdate(query as CFDictionary, change as CFDictionary)
        if status == errSecItemNotFound {
            status = SecItemAdd(query.merging(change) { _, b in b } as CFDictionary, nil)
        }
        guard status == errSecSuccess else { throw BijouError("Could not save this pairing in Keychain (\(status)).") }
    }
}

private final class Pin: NSObject, URLSessionTaskDelegate, @unchecked Sendable {
    let host: String
    let digest: String
    init(_ host: String, _ digest: String) { self.host = host; self.digest = digest }
    func urlSession(_ session: URLSession, didReceive challenge: URLAuthenticationChallenge,
                    completionHandler: @escaping (URLSession.AuthChallengeDisposition, URLCredential?) -> Void) {
        let space = challenge.protectionSpace
        guard space.authenticationMethod == NSURLAuthenticationMethodServerTrust, space.host == host,
              let trust = space.serverTrust, let chain = SecTrustCopyCertificateChain(trust) as? [SecCertificate],
              let leaf = chain.first,
              SHA256.hash(data: SecCertificateCopyData(leaf) as Data).map({ String(format: "%02x", $0) }).joined() == digest else {
            completionHandler(.cancelAuthenticationChallenge, nil); return
        }
        completionHandler(.useCredential, URLCredential(trust: trust))
    }
    func urlSession(_ session: URLSession, task: URLSessionTask, willPerformHTTPRedirection response: HTTPURLResponse,
                    newRequest request: URLRequest, completionHandler: @escaping (URLRequest?) -> Void) {
        completionHandler(nil)
    }
}

struct HomeResponse: LocalizedError {
    let status: Int
    let detail: String
    var errorDescription: String? { detail }
}

final class HomeClient {
    let url: URL
    private let token: String?
    private let session: URLSession
    init(url: URL, fingerprint: String, token: String? = nil) {
        self.url = url; self.token = token
        let config = URLSessionConfiguration.ephemeral
        config.timeoutIntervalForRequest = 8
        config.timeoutIntervalForResource = 15
        config.httpShouldSetCookies = false
        config.urlCredentialStorage = nil
        config.allowsCellularAccess = false
        session = URLSession(configuration: config, delegate: Pin(url.host ?? "", fingerprint), delegateQueue: nil)
    }
    convenience init(_ creds: Credentials) {
        self.init(url: creds.url, fingerprint: creds.fingerprint, token: creds.token)
    }
    deinit { session.invalidateAndCancel() }

    private func send(_ path: String, data: Data? = nil) async throws -> Data {
        var req = URLRequest(url: url.appendingPathComponent(path))
        if let token { req.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization") }
        if let data { req.httpMethod = "POST"; req.httpBody = data; req.setValue("application/json", forHTTPHeaderField: "Content-Type") }
        let (bytes, response) = try await session.data(for: req)
        guard let http = response as? HTTPURLResponse else { throw BijouError("No response from the Mac.") }
        guard http.statusCode == 200 else {
            let message = (try? JSONDecoder().decode([String: String].self, from: bytes))?["error"]
            throw HomeResponse(status: http.statusCode, detail: message ?? "Mac responded with \(http.statusCode).")
        }
        return bytes
    }

    static func pair(_ code: PairCode) async throws -> Credentials {
        struct Enrolled: Decodable { let device, token, library: String }
        let client = HomeClient(url: code.url, fingerprint: code.fingerprint)
        let data = try await client.send("pair", data: JSONEncoder().encode(["invitation": code.invitation]))
        let r = try JSONDecoder().decode(Enrolled.self, from: data)
        guard r.library.range(of: "^[0-9a-f]{32}$", options: .regularExpression) != nil,
              !r.token.isEmpty, !r.device.isEmpty else { throw BijouError("Invalid home enrollment.") }
        return Credentials(url: code.url, fingerprint: code.fingerprint, device: r.device, token: r.token, library: r.library)
    }
    func catalog() async throws -> Catalog { try await JSONDecoder().decode(Catalog.self, from: send("catalog")) }
    func place(_ p: Placement) async throws -> Receipt {
        try await JSONDecoder().decode(Receipt.self, from: send("place", data: JSONEncoder().encode(p)))
    }
    func cover(_ key: String) async throws -> Data { try await send("covers/\(key)") }
}
