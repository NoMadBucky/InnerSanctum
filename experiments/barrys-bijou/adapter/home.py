"""Pair and serve a disposable Bijou library over pinned HTTPS on the Mac."""

import argparse
from contextlib import closing, contextmanager
import hashlib
import hmac
import http.server
import ipaddress
import json
import os
from pathlib import Path
import re
import secrets
import signal
import socket
import sqlite3
import ssl
import subprocess
import threading
import time
from urllib.parse import urlsplit
import urllib.request

from innersanctum import bijou, handover, writer
from innersanctum.schema import Refused, document


def hashed(s):
    return hashlib.sha256(s.encode()).hexdigest()


CODE_ALPHABET = "23456789ABCDEFGHJKMNPQRSTUVWXYZ"  # No 0/O or 1/I/L.
MAX_GUESSES = 6
CODE_LIFETIME = 600


def pairing_keys(code, salt, fingerprint):
    """Bind both proofs to this invitation window and the actual TLS certificate."""
    context = b"Bijou home pairing v2\0" + bytes.fromhex(salt) + bytes.fromhex(fingerprint)
    key = hashlib.pbkdf2_hmac("sha256", code.encode("ascii"), context, 600_000)
    return hmac.digest(key, b"enroll", "sha256").hex(), hmac.digest(key, b"confirm", "sha256")


class Home:
    def __init__(self, root):
        self.root = root
        self.cfg = bijou.binding(root)
        self.state = root / ".bijou-home"
        self.prepare_state(root)

    def prepare_state(self, root):
        self.state.mkdir(mode=0o700, exist_ok=True)
        writer.validate_state(root, self.state)
        self.db = self.state / "devices.sqlite"
        with closing(sqlite3.connect(self.db)) as con, con:
            con.execute("""CREATE TABLE IF NOT EXISTS pair_codes (
                claim_hash TEXT PRIMARY KEY, confirmation BLOB NOT NULL, salt TEXT NOT NULL,
                expires INTEGER NOT NULL, remaining INTEGER NOT NULL)""")
            con.execute("CREATE TABLE IF NOT EXISTS devices (id TEXT PRIMARY KEY, token TEXT UNIQUE)")
        self.cert, self.key = (self.state / n for n in ("server.pem", "key.pem"))

    def identity(self):
        if not self.cert.exists() and not self.key.exists():
            subprocess.run(["/usr/bin/openssl", "req", "-x509", "-newkey", "rsa:2048", "-nodes", "-sha256",
                            "-days", "365", "-subj", "/CN=Bijou Home", "-keyout", self.key, "-out", self.cert],
                           check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        der = ssl.PEM_cert_to_DER_cert(self.cert.read_text())
        return hashlib.sha256(der).hexdigest()

    def invitation(self):
        with closing(sqlite3.connect(self.db)) as con, con:
            con.execute("BEGIN IMMEDIATE")
            now = int(time.time())
            con.execute("DELETE FROM pair_codes WHERE expires<=?", (now,))
            active = con.execute("SELECT salt FROM pair_codes WHERE remaining>0 LIMIT 1").fetchone()
            salt = active[0] if active else secrets.token_hex(16)
            fingerprint = self.identity()
            while True:
                code = "".join(secrets.choice(CODE_ALPHABET) for _ in range(7))
                claim, confirmation = pairing_keys(code, salt, fingerprint)
                if con.execute("INSERT OR IGNORE INTO pair_codes VALUES (?,?,?,?,?)",
                               (hashed(claim), confirmation, salt, now + CODE_LIFETIME, MAX_GUESSES)).rowcount:
                    return code

    def pairing_options(self):
        # Public bootstrap: no code, proof, credential, or offline password verifier.
        with closing(sqlite3.connect(self.db)) as con:
            row = con.execute("SELECT salt FROM pair_codes WHERE expires>? AND remaining>0 LIMIT 1",
                              (time.time(),)).fetchone()
            return {"version": 2, "salt": row[0]} if row else None

    def enroll(self, salt, claim):
        if (not isinstance(salt, str) or not re.fullmatch("[0-9a-f]{32}", salt)
                or not isinstance(claim, str) or not re.fullmatch("[0-9a-f]{64}", claim)):
            return None
        with closing(sqlite3.connect(self.db)) as con, con:
            con.execute("BEGIN IMMEDIATE")
            now = time.time()
            row = con.execute("UPDATE pair_codes SET remaining=0 WHERE salt=? AND claim_hash=? "
                              "AND expires>? AND remaining>0 RETURNING confirmation", (salt, hashed(claim), now)).fetchone()
            if not row:
                con.execute("UPDATE pair_codes SET remaining=remaining-1 WHERE salt=? AND expires>? AND remaining>0",
                            (salt, now))
                return None
            token = secrets.token_urlsafe(32)
            device = secrets.token_hex(8)
            con.execute("INSERT INTO devices VALUES (?,?)", (device, hashed(token)))
            library = self.cfg["library"]
            receipt = f"Bijou enrolled v2:{device}:{token}:{library}".encode("ascii")
            return {"device": device, "token": token, "library": library,
                    "proof": hmac.digest(row[0], receipt, "sha256").hex()}

    def authenticated(self, token):
        with closing(sqlite3.connect(self.db)) as con:
            return con.execute("SELECT 1 FROM devices WHERE token=?", (hashed(token),)).fetchone() is not None

    def cache_covers(self, allowed):
        cache_covers(self.root, self.state, allowed)

    def catalog(self, *, all_movies=False):
        return bijou.catalog(self.root, all_movies=all_movies)

    def place(self, payload):
        return bijou.place(self.root, payload, "process:bijou-fixture")

    def watch(self, payload):
        return bijou.mark_watched(self.root, payload, "process:bijou-fixture")


class PersonalHome(Home):
    """Separate enrollment database, TLS identity and cache; never reuse practice tokens."""
    def __init__(self, checkout, expected):
        if checkout != Path(__file__).resolve().parents[3]:
            raise Refused("Select this adapter's exact InnerSanctum checkout.")
        self.checkout, self.expected = checkout, expected
        with self.target() as (root, successor):
            self.cfg = bijou.personal_config(root, successor)
            self.root = root
        parent = Path.home() / "Library/Application Support"
        self.state = parent / ("BijouPersonal-" + self.cfg["library"])
        self.prepare_state(parent)

    @contextmanager
    def target(self):
        with handover.live_checkout(self.checkout) as (root, successor):
            if handover.SUCCESSOR.fullmatch(successor)[2].decode() != self.expected:
                raise Refused("Personal adoption changed.")
            yield root, successor

    def catalog(self, *, all_movies=False):
        with self.target() as (root, successor):
            catalog = bijou.catalog(root, successor, all_movies=all_movies)
        file = self.state / "plex-movies.json"
        if all_movies and file.exists():
            links = json.loads(writer.read_file(file))
            for film in catalog["films"]:
                if film["inLibrary"] and film["tmdb"]:
                    pair = links.get(film["tmdb"].rsplit("/", 1)[1])
                    if (isinstance(pair, list) and len(pair) == 2
                            and all(isinstance(v, str) for v in pair)
                            and re.fullmatch("[A-Za-z0-9-]{8,128}", pair[0]) and re.fullmatch("[1-9][0-9]*", pair[1])):
                        film["plex"] = f"plex://preplay/?metadataKey=%2Flibrary%2Fmetadata%2F{pair[1]}&metadataType=1&server={pair[0]}"
        return catalog

    def place(self, payload):
        with self.target() as (root, successor):
            return bijou.place(root, payload, "human:barry", successor)

    def watch(self, payload):
        with self.target() as (root, successor):
            return bijou.mark_watched(root, payload, "human:barry", successor)


class ArtworkRedirects(urllib.request.HTTPRedirectHandler):
    max_redirections = 4

    def __init__(self, allowed):
        self.hosts = frozenset(host.lower() for host in allowed)

    def permits(self, url):
        parts = urlsplit(url)
        return (parts.scheme == "https" and parts.hostname in self.hosts and parts.port in (None, 443)
                and parts.username is None and parts.password is None)

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if not self.permits(newurl):
            return None
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def cache_covers(root, directory, allowed):
    """Fetch only approved HTTPS artwork, including every redirect hop."""
    policy = ArtworkRedirects(allowed)
    opener = urllib.request.build_opener(policy)
    for name, file in writer.visible_files(root):
        if not bijou.MOVIE_PATH.fullmatch(name):
            continue
        data, _, _ = document(writer.read_file(file).decode())
        url = data.get("poster")
        if not bijou.movie(data) or not isinstance(url, str):
            continue
        dest = directory / (hashed(url) + ".jpg")
        if dest.exists():
            continue
        scratch = directory / ("art-" + secrets.token_hex(8))
        output = scratch.with_suffix(".jpg")
        try:
            if re.fullmatch(r"/Art/[0-9]+\.png", url):
                raw = writer.read_file(writer.safe_target(root, url[1:]))
            else:
                if not policy.permits(url):
                    continue
                with opener.open(url, timeout=5) as response:
                    raw = response.read(8 * 1024 * 1024 + 1)
                if len(raw) > 8 * 1024 * 1024:
                    continue
            scratch.write_bytes(raw)
            subprocess.run(["/usr/bin/sips", "-Z", "400", "-s", "format", "jpeg", scratch, "--out", output],
                           check=True, capture_output=True, timeout=12)
            os.replace(output, dest)
        except (ValueError, OSError, Refused, subprocess.SubprocessError):
            continue
        finally:
            scratch.unlink(missing_ok=True)
            output.unlink(missing_ok=True)


def handler(home):
    class Handler(http.server.BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def reply(self, status, data, kind="application/json"):
            raw = writer.json_bytes(data) if kind == "application/json" else data
            self.send_response(status)
            self.send_header("Content-Type", kind)
            self.send_header("Content-Length", str(len(raw)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(raw)

        def route(self):
            payload = {}
            try:
                if self.command == "POST":
                    length = int(self.headers.get("Content-Length", "0"))
                    if not 0 < length <= 8192:
                        return self.reply(400, {"error": "Invalid request size."})
                    payload = json.loads(self.rfile.read(length))
                    if not isinstance(payload, dict):
                        return self.reply(400, {"error": "Expected an object."})
                if self.command == "GET" and self.path == "/pair/options":
                    options = home.pairing_options()
                    return self.reply(200, options) if options else self.reply(410, {"error": "Ask the Mac for a fresh pairing code."})
                if self.command == "POST" and self.path == "/pair":
                    if "invitation" in payload:
                        return self.reply(400, {"error": "Update Bijou to enter the seven-character code."})
                    device = home.enroll(payload.get("salt"), payload.get("claim"))
                    return self.reply(200, device) if device else self.reply(403, {"error": "Code not accepted. Check the code and selected Mac, or get a fresh code."})
                auth = self.headers.get("Authorization", "")
                if not auth.startswith("Bearer ") or not home.authenticated(auth[7:]):
                    return self.reply(401, {"error": "Pair this device."})
                if self.command == "GET" and self.path in {"/catalog", "/catalog/all"}:
                    return self.reply(200, home.catalog(all_movies=self.path == "/catalog/all"))
                if self.command == "POST" and self.path == "/place":
                    return self.reply(200, home.place(payload))
                if self.command == "POST" and self.path == "/watched":
                    return self.reply(200, home.watch(payload))
                if self.command == "GET" and (m := re.fullmatch(r"/covers/([0-9a-f]{64})", self.path)):
                    p = home.state / (m[1] + ".jpg")
                    if p.is_file():
                        return self.reply(200, writer.read_file(p), "image/jpeg")
                return self.reply(404, {"error": "Unavailable."})
            except bijou.Conflict as err:
                return self.reply(409, {"error": str(err)})
            except Refused as err:
                return self.reply(503, {"error": str(err)})
            except (ValueError, RecursionError):
                return self.reply(400, {"error": "Malformed request."})
            except OSError:
                return self.reply(503, {"error": "Publication interrupted; retain the original request."})

        do_POST = do_GET = route
    return Handler


@contextmanager
def advertise(address, port, *, personal=False):
    """Announce a locator only. A loopback server is discoverable only on this Mac."""
    if ipaddress.ip_address(address).is_unspecified:
        raise ValueError("Choose a home-network address, or 127.0.0.1 for a Mac-only trial.")
    # NWBrowser sees multicast on lo0; DNSService's special LocalOnly index is not a network path.
    options = ["-i", "lo0"] if ipaddress.ip_address(address).is_loopback else []
    name = ("Bijou Personal on " if personal else "Bijou on ") + socket.gethostname().split(".")[0][:35]
    try:
        process = subprocess.Popen(
            ["/usr/bin/dns-sd", *options, "-R", name, "_bijou-home._tcp", "local.", str(port),
             f"url=https://{address}:{port}"],
            stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except OSError:
        print("Bonjour unavailable. Use Enter Mac address manually.")
        process = None
    try:
        yield
    finally:
        if process is not None:
            process.terminate()
            process.wait()


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("action", choices=["serve", "invite", "devices", "revoke"])
    target = p.add_mutually_exclusive_group(required=True)
    target.add_argument("--bundle", type=Path)
    target.add_argument("--live-checkout", type=Path)
    p.add_argument("--expect-adoption")
    p.add_argument("--host", default="127.0.0.1", help="Serve on loopback or the Mac's home LAN address")
    p.add_argument("--port", type=int, default=8765)
    p.add_argument("--device", help="Device ID to revoke")
    p.add_argument("--art-host", action="append", default=[], help="Allow this HTTPS artwork hostname")
    args = p.parse_args()
    os.umask(0o077)
    home = (PersonalHome(args.live_checkout.absolute(), args.expect_adoption)
            if args.live_checkout else Home(args.bundle.absolute()))
    if args.action in {"devices", "revoke"}:
        with closing(sqlite3.connect(home.db)) as con, con:
            if args.action == "devices":
                for device, in con.execute("SELECT id FROM devices"):
                    print(device)
            elif not con.execute("DELETE FROM devices WHERE id=?", (args.device,)).rowcount:
                p.error("Unknown device ID.")
        return
    if args.action == "invite":
        print(home.invitation())
        return
    home.identity()
    server = http.server.ThreadingHTTPServer((args.host, args.port), handler(home))
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    ctx.minimum_version = ssl.TLSVersion.TLSv1_2
    ctx.load_cert_chain(home.cert, home.key)
    server.socket = ctx.wrap_socket(server.socket, server_side=True)
    def interrupt(*_):
        raise KeyboardInterrupt

    signal.signal(signal.SIGTERM, interrupt)
    with server:
        address, port = server.server_address
        if ipaddress.ip_address(address).is_unspecified:
            p.error("Choose the Mac’s home-network address, or 127.0.0.1 for a Mac-only trial.")
        with advertise(address, port, personal=bool(args.live_checkout)):
            print(f"Mac address: https://{address}:{port}\nPairing code (one use, ten minutes): {home.invitation()}", flush=True)
            threading.Thread(target=home.cache_covers, args=(args.art_host,), daemon=True).start()
            try:
                server.serve_forever()
            except KeyboardInterrupt:
                pass


if __name__ == "__main__":
    main()
