"""Pair and serve a disposable Bijou library over pinned HTTPS on the Mac."""

import argparse
import base64
from contextlib import closing
import hashlib
import http.server
import json
import os
from pathlib import Path
import re
import secrets
import sqlite3
import ssl
import subprocess
import threading
import time
from urllib.parse import urlsplit
import urllib.request

from innersanctum import bijou, writer
from innersanctum.schema import Refused, document


def hashed(s):
    return hashlib.sha256(s.encode()).hexdigest()


class Home:
    def __init__(self, root):
        self.root = root
        self.cfg = bijou.binding(root)
        self.state = root / ".bijou-home"
        self.state.mkdir(mode=0o700, exist_ok=True)
        writer.validate_state(root, self.state)
        self.db = self.state / "devices.sqlite"
        with closing(sqlite3.connect(self.db)) as con, con:
            con.execute("CREATE TABLE IF NOT EXISTS invites (hash TEXT PRIMARY KEY, expires INTEGER)")
            con.execute("CREATE TABLE IF NOT EXISTS devices (id TEXT PRIMARY KEY, token TEXT UNIQUE)")
        self.cert, self.key = (self.state / n for n in ("server.pem", "key.pem"))

    def identity(self):
        if not self.cert.exists() and not self.key.exists():
            subprocess.run(["/usr/bin/openssl", "req", "-x509", "-newkey", "rsa:2048", "-nodes", "-sha256",
                            "-days", "365", "-subj", "/CN=Bijou Home", "-keyout", self.key, "-out", self.cert],
                           check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        der = ssl.PEM_cert_to_DER_cert(self.cert.read_text())
        return hashlib.sha256(der).hexdigest()

    def invitation(self, url):
        invite = secrets.token_urlsafe(24)
        with closing(sqlite3.connect(self.db)) as con, con:
            con.execute("DELETE FROM invites WHERE expires < ?", (time.time(),))
            con.execute("INSERT INTO invites VALUES (?,?)", (hashed(invite), int(time.time()) + 600))
        config = {"url": url, "fingerprint": self.identity(), "invitation": invite}
        return base64.urlsafe_b64encode(writer.json_bytes(config)).decode()

    def enroll(self, invite):
        if not isinstance(invite, str) or len(invite) > 128:
            return None
        with closing(sqlite3.connect(self.db)) as con, con:
            if not con.execute("DELETE FROM invites WHERE hash=? AND expires>=?",
                               (hashed(invite), time.time())).rowcount:
                return None
            token = secrets.token_urlsafe(32)
            device = secrets.token_hex(8)
            con.execute("INSERT INTO devices VALUES (?,?)", (device, hashed(token)))
            return {"device": device, "token": token, "library": self.cfg["library"]}

    def authenticated(self, token):
        with closing(sqlite3.connect(self.db)) as con:
            return con.execute("SELECT 1 FROM devices WHERE token=?", (hashed(token),)).fetchone() is not None

    def cache_covers(self, allowed):
        cache_covers(self.root, self.state, allowed)


def cache_covers(root, directory, allowed):
    """Only the Mac reads source URLs. Never follow redirects or arbitrary local paths."""
    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, *args):
            return None

    opener = urllib.request.build_opener(NoRedirect())
    for name, file in writer.visible_files(root):
        if not bijou.MOVIE_PATH.fullmatch(name):
            continue
        data, _, _ = document(writer.read_file(file).decode())
        url = data.get("poster")
        if not bijou.watched(data) or not isinstance(url, str):
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
                parts = urlsplit(url)
                if parts.scheme != "https" or parts.hostname not in allowed or parts.username or parts.password:
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
                if self.command == "POST" and self.path == "/pair":
                    device = home.enroll(payload.get("invitation"))
                    return self.reply(200, device) if device else self.reply(403, {"error": "Code expired or used."})
                auth = self.headers.get("Authorization", "")
                if not auth.startswith("Bearer ") or not home.authenticated(auth[7:]):
                    return self.reply(401, {"error": "Pair this device."})
                if self.command == "GET" and self.path == "/catalog":
                    return self.reply(200, bijou.catalog(home.root))
                if self.command == "POST" and self.path == "/place":
                    return self.reply(200, bijou.place(home.root, payload, "process:bijou-fixture"))
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


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("action", choices=["serve", "invite", "devices", "revoke"])
    p.add_argument("--bundle", type=Path, required=True)
    p.add_argument("--host", default="127.0.0.1", help="Loopback or the Mac's home LAN address")
    p.add_argument("--port", type=int, default=8765)
    p.add_argument("--device", help="Device ID to revoke")
    p.add_argument("--art-host", action="append", default=[], help="Allow this HTTPS artwork hostname")
    args = p.parse_args()
    os.umask(0o077)
    home = Home(args.bundle.absolute())
    url = f"https://{args.host}:{args.port}"
    if args.action in {"devices", "revoke"}:
        with closing(sqlite3.connect(home.db)) as con, con:
            if args.action == "devices":
                for device, in con.execute("SELECT id FROM devices"):
                    print(device)
            elif not con.execute("DELETE FROM devices WHERE id=?", (args.device,)).rowcount:
                p.error("Unknown device ID.")
        return
    if args.action == "invite":
        print(home.invitation(url))
        return
    home.identity()
    server = http.server.ThreadingHTTPServer((args.host, args.port), handler(home))
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    ctx.minimum_version = ssl.TLSVersion.TLSv1_2
    ctx.load_cert_chain(home.cert, home.key)
    server.socket = ctx.wrap_socket(server.socket, server_side=True)
    print("Pair in Bijou → Home Sync (one use, ten minutes):", home.invitation(url), sep="\n", flush=True)
    threading.Thread(target=home.cache_covers, args=(args.art_host,), daemon=True).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
