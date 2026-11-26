import CryptoKit
import Foundation
import Security

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
    private let lock = NSLock()
    private var digest: String?
    var observed: String? { lock.withLock { digest } }
    init(_ host: String, _ digest: String?) { self.host = host; self.digest = digest }
    func urlSession(_ session: URLSession, didReceive challenge: URLAuthenticationChallenge,
                    completionHandler: @escaping (URLSession.AuthChallengeDisposition, URLCredential?) -> Void) {
        let space = challenge.protectionSpace
        guard space.authenticationMethod == NSURLAuthenticationMethodServerTrust, space.host == host,
              let trust = space.serverTrust, let chain = SecTrustCopyCertificateChain(trust) as? [SecCertificate],
              let leaf = chain.first else {
            completionHandler(.cancelAuthenticationChallenge, nil); return
        }
        let actual = SHA256.hash(data: SecCertificateCopyData(leaf) as Data).map { String(format: "%02x", $0) }.joined()
        let matches = lock.withLock {
            if digest == nil { digest = actual } // Only the isolated, credential-free bootstrap session.
            return digest == actual
        }
        guard matches else {
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
    private let pin: Pin
    private init(url: URL, pin: Pin, token: String?) {
        self.url = url; self.token = token; self.pin = pin
        let config = URLSessionConfiguration.ephemeral
        config.timeoutIntervalForRequest = 8
        config.timeoutIntervalForResource = 15
        config.httpShouldSetCookies = false
        config.urlCredentialStorage = nil
        config.allowsCellularAccess = false
        session = URLSession(configuration: config, delegate: pin, delegateQueue: nil)
    }
    convenience init(url: URL, fingerprint: String, token: String? = nil) {
        self.init(url: url, pin: Pin(url.host ?? "", fingerprint), token: token)
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

    static func pair(_ code: PairCode, at address: URL) async throws -> Credentials {
        struct Options: Decodable { let version: Int; let salt: String }
        struct Enrolled: Decodable { let device, token, library, proof: String }
        let url = try HomeAddress.parse(address.absoluteString)
        let bootstrap = HomeClient(url: url, pin: Pin(url.host ?? "", nil), token: nil)
        let raw = try await bootstrap.send("pair/options")
        let options = try JSONDecoder().decode(Options.self, from: raw)
        guard options.version == 2, let fingerprint = bootstrap.pin.observed else {
            throw BijouError("Restart the updated home adapter and request a new code.")
        }
        let proof = try PairingProof(code: code, salt: options.salt, certificate: fingerprint)
        // Only a public salt is fetched before locking the request to the actual TLS leaf.
        let client = HomeClient(url: url, fingerprint: fingerprint)
        let data = try await client.send("pair", data: JSONEncoder().encode(["salt": options.salt, "claim": proof.claim]))
        let r = try JSONDecoder().decode(Enrolled.self, from: data)
        guard r.library.range(of: "^[0-9a-f]{32}$", options: .regularExpression) != nil,
              r.device.range(of: "^[0-9a-f]{16}$", options: .regularExpression) != nil,
              r.token.range(of: "^[a-zA-Z0-9_-]{43}$", options: .regularExpression) != nil,
              proof.verifies(r.proof, device: r.device, token: r.token, library: r.library) else {
            throw BijouError("This Mac could not confirm the pairing code.")
        }
        return Credentials(url: url, fingerprint: fingerprint, device: r.device, token: r.token, library: r.library)
    }
    func catalog() async throws -> Catalog {
        do { return try await JSONDecoder().decode(Catalog.self, from: send("catalog/all")) }
        catch let error as HomeResponse where error.status == 404 {
            return try await JSONDecoder().decode(Catalog.self, from: send("catalog"))
        }
    }
    func place(_ p: Placement) async throws -> Receipt {
        try await JSONDecoder().decode(Receipt.self, from: send("place", data: JSONEncoder().encode(p)))
    }
    func markWatched(_ film: FilmRef, day: String, library: String) async throws {
        struct Watch: Encodable { let film: FilmRef; let day, library: String }
        let data = try JSONEncoder().encode(Watch(film: film, day: day, library: library))
        do { _ = try await send("watched", data: data) }
        catch let error as HomeResponse where error.status == 404 {
            throw BijouError("Restart the updated Bijou sync adapter on your Mac, then try again.")
        }
    }
    func cover(_ key: String) async throws -> Data { try await send("covers/\(key)") }
}
