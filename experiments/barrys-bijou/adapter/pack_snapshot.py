"""Prepare one local read-only screening copy from an approved, external OKF snapshot."""

import argparse
import base64
import os
from pathlib import Path
import re
import stat
from tempfile import TemporaryDirectory

from home import cache_covers
from innersanctum import bijou, writer
from innersanctum.schema import Refused, document


CHECKOUT = Path(__file__).resolve().parents[3]


def inputs(root):
    writer.require_idle(root)
    return {p: writer.digest(writer.read_file(f)) for p, f in writer.visible_files(root)
            if p == "index.md" or p.startswith((bijou.MOVIES + "/", bijou.RANKINGS + "/"))}


def pack(snapshot, output, art_hosts=()):
    root = writer.external_root(snapshot, CHECKOUT)
    dest = Path(output).expanduser().absolute()
    parent = writer.external_root(dest.parent, CHECKOUT)
    if (parent.is_relative_to(root) or not dest.name.endswith(".bijou.json") or writer.present(dest)
            or stat.S_IMODE(parent.stat().st_mode) != 0o700
            or any(writer.present(p / writer.MARKER) or (writer.present(p / "index.md") and writer.present(p / "log.md"))
                   for p in (parent, *parent.parents))):
        raise Refused("Choose a new .bijou.json in a private (0700) directory outside all bundles.")
    original = inputs(root)
    if document(bijou.source(root, "index.md"))[0].get("okf_version") != "0.3":
        raise Refused("Expected an offline v0.3 bundle.")
    ranks = [p for p in original if bijou.RANK_PATH.fullmatch(p)
             and document(bijou.source(root, p))[0].get("type") == "Film Ranking"]
    if len(ranks) > 1:
        raise Refused("Multiple Film Ranking records; a single ranking is required for this preview.")
    entries, revision = {}, writer.digest(b"")
    if ranks:
        path = ranks[0]
        entries, _, _ = bijou.parse_order(bijou.source(root, path), "bho:" + bijou.RANK_PATH.fullmatch(path)[1])
        revision = original[path]
    library = "snapshot-" + writer.digest(writer.json_bytes(original))
    catalog = bijou.catalog_rows(root, library, revision, entries)
    with TemporaryDirectory(dir=parent) as scratch:
        folder = Path(scratch)
        cache_covers(root, folder, art_hosts)
        covers = {}
        total = 0
        for file in folder.glob("*.jpg"):
            if not re.fullmatch("[0-9a-f]{64}", file.stem):
                raise Refused("Unexpected thumbnail.")
            data = writer.read_file(file)
            total += len(data)
            if total > 24 * 1024 * 1024:
                raise Refused("Snapshot artwork exceeds the mobile import limit.")
            covers[file.stem] = base64.b64encode(data).decode("ascii")
        raw = writer.json_bytes({"format": "bijou-screening-1", "catalog": catalog, "covers": covers})
        if len(raw) > 40 * 1024 * 1024 or inputs(root) != original:
            raise Refused("Snapshot too large or changed while preparing the screening copy.")
        file = folder / "screening"
        with file.open("xb") as f:
            os.fchmod(f.fileno(), 0o600)
            f.write(raw)
            f.flush()
            os.fsync(f.fileno())
        os.link(file, dest)  # Never overwrite an existing screening copy.
    return len(catalog["films"]), len(covers)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--snapshot", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--art-host", action="append", default=[])
    args = parser.parse_args()
    os.umask(0o077)
    print("Watched films: %d; thumbnails: %d." % pack(args.snapshot, args.output, args.art_host))
