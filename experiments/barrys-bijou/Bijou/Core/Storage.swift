import Foundation
import SQLite3

/// A library is never overwritten when switching between the sample and a paired Mac.
final class Storage {
    private var db: OpaquePointer?
    private let transient = unsafeBitCast(-1, to: sqlite3_destructor_type.self)
    let directory: URL

    init(directory: URL) throws {
        self.directory = directory
        try FileManager.default.createDirectory(at: directory, withIntermediateDirectories: true,
                                                 attributes: [.posixPermissions: 0o700])
        let path = directory.appendingPathComponent("bijou.sqlite").path
        guard sqlite3_open_v2(path, &db, SQLITE_OPEN_READWRITE | SQLITE_OPEN_CREATE | SQLITE_OPEN_FULLMUTEX, nil) == SQLITE_OK else {
            sqlite3_close(db); db = nil
            throw BijouError("Could not open the local movie journal.")
        }
        try exec("PRAGMA synchronous=FULL")
        try exec("CREATE TABLE IF NOT EXISTS journals (library TEXT PRIMARY KEY, state BLOB NOT NULL)")
    }

    deinit { sqlite3_close(db) }

    private func exec(_ sql: String) throws {
        guard sqlite3_exec(db, sql, nil, nil, nil) == SQLITE_OK else { throw failure() }
    }
    private func failure() -> BijouError { BijouError("Local journal: \(String(cString: sqlite3_errmsg(db)))") }

    func load(_ key: String) throws -> Journal? {
        var stmt: OpaquePointer?
        guard sqlite3_prepare_v2(db, "SELECT state FROM journals WHERE library=?", -1, &stmt, nil) == SQLITE_OK else { throw failure() }
        defer { sqlite3_finalize(stmt) }
        guard sqlite3_bind_text(stmt, 1, key, -1, transient) == SQLITE_OK else { throw failure() }
        switch sqlite3_step(stmt) {
        case SQLITE_DONE: return nil
        case SQLITE_ROW:
            guard let bytes = sqlite3_column_blob(stmt, 0) else { throw BijouError("The saved journal is empty.") }
            return try JSONDecoder().decode(Journal.self, from: Data(bytes: bytes, count: Int(sqlite3_column_bytes(stmt, 0))))
        default: throw failure()
        }
    }

    func save(_ journal: Journal) throws {
        let bytes = try JSONEncoder().encode(journal)
        var stmt: OpaquePointer?
        guard sqlite3_prepare_v2(db, "INSERT OR REPLACE INTO journals(library,state) VALUES(?,?)", -1, &stmt, nil) == SQLITE_OK else { throw failure() }
        defer { sqlite3_finalize(stmt) }
        guard sqlite3_bind_text(stmt, 1, journal.base.library, -1, transient) == SQLITE_OK,
              bytes.withUnsafeBytes({ sqlite3_bind_blob(stmt, 2, $0.baseAddress, Int32($0.count), transient) }) == SQLITE_OK,
              sqlite3_step(stmt) == SQLITE_DONE else { throw failure() }
    }
}
