"""Run native client tests against an ephemeral TLS server and verify the OKF bytes."""

import os
from pathlib import Path
import ssl
import subprocess
import tempfile
import threading
from http.server import ThreadingHTTPServer

from fixture import EXPERIMENT, create
from home import Home, advertise, handler
from pack_snapshot import pack
from innersanctum import bijou, writer


def main():
    os.umask(0o077)
    with tempfile.TemporaryDirectory(prefix="bijou-rehearsal-") as private:
        root = create(Path(private).resolve() / "OKF")
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
            elif name not in {bound, "log.md"}:
                assert after[name] == data
        assert set(before) == set(after) and after["log.md"].count(b"**Placement**") == 4
        assert not (root / writer.STATE / writer.PENDING).exists()
        print("Read-back verified: three first placements, one move, four audit entries, original film bodies and watch dates.")


if __name__ == "__main__":
    main()
