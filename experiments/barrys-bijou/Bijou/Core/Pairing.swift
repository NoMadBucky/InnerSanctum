import CommonCrypto
import CryptoKit
import Foundation

struct PairCode {
    static let alphabet = "23456789ABCDEFGHJKMNPQRSTUVWXYZ"
    let value: String

    static func parse(_ text: String) throws -> PairCode {
        let raw = text.trimmingCharacters(in: .whitespacesAndNewlines)
        guard raw.utf8.count <= 16, raw.utf8.allSatisfy({ $0 < 128 }) else {
            throw BijouError("Enter the seven-character code shown on the Mac.")
        }
        let code = raw.uppercased().filter { $0 != " " && $0 != "-" }
        guard code.allSatisfy({ alphabet.contains($0) }) else {
            throw BijouError("Check the code in Terminal. Codes never contain 0, 1, I, L or O.")
        }
        guard code.count == 7 else {
            throw BijouError(code.count > 7 ? "Enter only the seven-character code, without its Terminal label."
                             : "Enter all seven characters from Terminal (\(code.count) of 7 entered).")
        }
        return PairCode(value: code)
    }
}

struct PairingDraft {
    enum Field: Hashable { case code, address, mac }
    enum Check {
        case incomplete(Field, String)
        case ready(PairCode, URL)
    }

    var code = ""
    var manual = false
    var address = ""
    var selectedMac = ""

    func check(nearby: [URL]) -> Check {
        let entry: PairCode
        do { entry = try PairCode.parse(code) }
        catch { return .incomplete(.code, error.localizedDescription) }

        if manual || (nearby.isEmpty && !address.isEmpty) {
            if address.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty {
                return .incomplete(.address, "Enter the Mac address printed above the code in Terminal.")
            }
            do { return .ready(entry, try HomeAddress.parse(address)) }
            catch { return .incomplete(.address, error.localizedDescription) }
        }
        if nearby.isEmpty {
            return .incomplete(.address, "No Mac found yet. Enter the Mac address from Terminal or check your home Wi-Fi.")
        }
        if nearby.count == 1, let url = nearby.first { return .ready(entry, url) }
        if let url = nearby.first(where: { $0.absoluteString == selectedMac }) { return .ready(entry, url) }
        return .incomplete(.mac, "Choose your Mac from the Home Mac list above.")
    }
}

enum HomeAddress {
    /// Both Bonjour and manual entry are untrusted locators. The code authenticates the host.
    static func parse(_ text: String) throws -> URL {
        let raw = text.trimmingCharacters(in: .whitespacesAndNewlines)
        let error = BijouError("Enter the Mac’s home address, such as 192.168.1.20:8765.")
        guard !raw.isEmpty, raw.utf8.count < 256,
              var parts = URLComponents(string: raw.contains("://") ? raw : "https://" + raw),
              parts.scheme?.lowercased() == "https", let host = parts.host?.lowercased(),
              parts.user == nil, parts.password == nil, parts.query == nil, parts.fragment == nil,
              ["", "/"].contains(parts.path) else { throw error }
        let octets = host.split(separator: ".", omittingEmptySubsequences: false)
        let ips = octets.compactMap { UInt8($0) }
        let lan = octets.count == 4 && ips.count == 4 && zip(octets, ips).allSatisfy { String($0) == String($1) }
            && (ips[0] == 10 || ips[0] == 127 || (ips[0] == 192 && ips[1] == 168)
                || (ips[0] == 172 && (16...31).contains(ips[1])) || (ips[0] == 169 && ips[1] == 254))
        guard lan || host == "localhost" || (host.hasSuffix(".local") && host.count > 6),
              (1...65535).contains(parts.port ?? 8765) else { throw error }
        parts.scheme = "https"; parts.host = host; parts.port = parts.port ?? 8765; parts.path = ""
        guard let url = parts.url else { throw error }
        return url
    }
}

private extension Data {
    init?(lowerHex: String, bytes: Int) {
        let chars = Array(lowerHex.utf8)
        guard chars.count == bytes * 2,
              chars.allSatisfy({ (48...57).contains($0) || (97...102).contains($0) }) else { return nil }
        var result = Data()
        for i in stride(from: 0, to: chars.count, by: 2) {
            let digits = String(decoding: chars[i...i + 1], as: UTF8.self)
            guard let byte = UInt8(digits, radix: 16) else { return nil }
            result.append(byte)
        }
        self = result
    }
}

struct PairingProof {
    let claim: String
    private let confirmation: SymmetricKey

    init(code: PairCode, salt: String, certificate: String) throws {
        guard let window = Data(lowerHex: salt, bytes: 16), let leaf = Data(lowerHex: certificate, bytes: 32) else {
            throw BijouError("Unexpected pairing information from the Mac.")
        }
        let context = Array(Data("Bijou home pairing v2\0".utf8) + window + leaf)
        var secret = [UInt8](repeating: 0, count: 32)
        let status = code.value.withCString {
            CCKeyDerivationPBKDF(CCPBKDFAlgorithm(kCCPBKDF2), $0, code.value.utf8.count, context, context.count,
                                 CCPseudoRandomAlgorithm(kCCPRFHmacAlgSHA256), 600_000, &secret, 32)
        }
        guard status == kCCSuccess else { throw BijouError("Could not prepare this pairing request.") }
        let key = SymmetricKey(data: secret)
        claim = HMAC<SHA256>.authenticationCode(for: Data("enroll".utf8), using: key)
            .map { String(format: "%02x", $0) }.joined()
        confirmation = SymmetricKey(data: HMAC<SHA256>.authenticationCode(for: Data("confirm".utf8), using: key))
    }

    func verifies(_ proof: String, device: String, token: String, library: String) -> Bool {
        guard let mac = Data(lowerHex: proof, bytes: 32) else { return false }
        let receipt = Data("Bijou enrolled v2:\(device):\(token):\(library)".utf8)
        return HMAC<SHA256>.isValidAuthenticationCode(mac, authenticating: receipt, using: confirmation)
    }
}
