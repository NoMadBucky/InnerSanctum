"""Run native client tests against an ephemeral TLS server and verify the OKF bytes."""

import os
import json
import wave
from pathlib import Path
import ssl
import subprocess
import tempfile
import threading
from http.server import ThreadingHTTPServer

from fixture import EXPERIMENT, create
from home import Home, advertise, handler
from pack_snapshot import pack
from innersanctum import bijou, reaction_filing, writer
from innersanctum.schema import document


def main():
    os.umask(0o077)
    with tempfile.TemporaryDirectory(prefix="bijou-rehearsal-") as private:
        root = create(Path(private).resolve() / "OKF", reactions=True)
        before = {p: f.read_bytes() for p, f in writer.visible_files(root)}
        whole = {f.relative_to(root): f.read_bytes() for f in root.rglob("*") if f.is_file()}
        package = root.parent / "practice.bijou.json"
        assert pack(root, package) == (7, 5)
        assert whole == {f.relative_to(root): f.read_bytes() for f in root.rglob("*") if f.is_file()}
        home = Home(root)
        home.identity()
        home.cache_covers([])
        with ThreadingHTTPServer(("127.0.0.1", 0), handler(home)) as server:
            ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
            ctx.load_cert_chain(home.cert, home.key)
            server.socket = ctx.wrap_socket(server.socket, server_side=True)
            url = f"https://127.0.0.1:{server.server_port}"
            native = {**os.environ, "BIJOU_TEST_HOME": url, "BIJOU_TEST_PIN": home.identity(),
                      "BIJOU_TEST_MAC": home.invitation(), "BIJOU_TEST_PHONE": home.invitation(),
                      "BIJOU_TEST_SCREENING": str(package)}
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                with advertise(*server.server_address):
                    subprocess.run(["/usr/bin/xcrun", "swift", "test"], cwd=EXPERIMENT, env=native, check=True)
            finally:
                server.shutdown()
                thread.join()
        after = {p: f.read_bytes() for p, f in writer.visible_files(root)}
        bound = bijou.binding(root)["path"]
        for name, data in before.items():
            if name in [f"Resources/videos/{i}.md" for i in (8100001, 8100002, 8100003)]:
                assert after[name] == data.replace(b"---\n", b"---\nranked: true\n", 1)
            elif name not in {bound, "log.md", "Documents/reactions/index.md"}:
                assert after[name] == data
        reaction, = set(after) - set(before)
        assert reaction.startswith("Documents/reactions/") and after["log.md"].count(b"**Placement**") == 4
        assert after["Documents/reactions/index.md"].count(Path(reaction).name.encode()) == 1
        assert after["log.md"].count(reaction.encode()) == 1
        fields, body, _ = document(after[reaction].decode())
        movie = next(f for f in bijou.catalog(root)["films"] if f["title"] == "The Last Projection")
        assert fields["film_id"] == movie["ref"]["personalID"] and movie["ref"]["path"] in body
        _, _, store = reaction_filing.target(root)
        catalog = json.loads((store / "catalog.json").read_bytes())["sources"]
        assert list(catalog) == [fields["source_key"]]
        blob, = (store / "audio").iterdir()
        entry = catalog[fields["source_key"]]
        assert blob == store / entry["path"] and blob.stat().st_size == entry["size"]
        assert writer.digest(blob.read_bytes()) == fields["source_sha256"] == entry["sha256"]
        with wave.open(str(blob)) as wav:
            assert wav.getnframes() == wav.getframerate() and fields["duration_ms"] == 1000
            assert any(wav.readframes(wav.getnframes()))
        assert not (root / writer.STATE / writer.PENDING).exists()
        print("Read-back verified: three first placements, one move, four audit entries, original film bodies and watch dates.")
        print("Reaction upload, retry and local removal: one verified WAV, one source entry and one linked concept.")


if __name__ == "__main__":
    main()
