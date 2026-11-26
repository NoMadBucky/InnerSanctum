"""Create a NEW external Bijou fixture. No private data or network input."""

import argparse
import json
import os
from pathlib import Path
import struct
import uuid
import zlib

from innersanctum import bijou, reaction_filing, writer
from innersanctum.schema import Refused


EXPERIMENT = Path(__file__).resolve().parents[1]
CHECKOUT = EXPERIMENT.parents[1]
ROUTES = '[types."Film Ranking"]\nschema="Documents/rankings/index.md"\ndirectory="Documents/rankings"\n'
VIDEO_SCHEMA = """# Videos

```yaml
okf_schema:
  type: Video
  directory: Resources
  required: [id, type, title]
  fields:
    id: {type: bho}
    type: {const: Video}
    title: {type: string}
    ranked: {type: bool}
    date_watched: {type: date}
    video_status: {type: enum, values: [watched, watchlist]}
```

## Directory Listing

"""
RANK_SCHEMA = """# Film Rankings

```yaml
okf_schema:
  type: Film Ranking
  directory: Documents/rankings
  required: [id, type, title]
  fields:
    id: {type: bho}
    type: {const: Film Ranking}
    title: {type: string}
```

## Directory Listing
"""


def poster(number):
    """Small original, deterministic geometric test artwork (RGB PNG)."""
    width, height = 160, 240
    palette = [(38, 66, 75), (83, 42, 55), (40, 74, 61), (48, 51, 85), (105, 64, 41)]
    base = palette[number % len(palette)]
    rows = bytearray()
    for y in range(height):
        rows.append(0)
        for x in range(width):
            edge = min(x, width - 1 - x, y, height - 1 - y)
            diamond = abs(x - width // 2) + abs(y - height // 2)
            ray = (x + (1 + number % 3) * y) % 35
            brass = edge in (4, 8) or diamond in (42, 43, 48, 49, 53) or (diamond < 32 and ray < 4)
            rows.extend((214, 180, 110) if brass else base)

    def chunk(tag, data):
        return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag + data))

    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">2I5B", width, height, 8, 2, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(rows)) + chunk(b"IEND", b""))


def create(directory, *, reactions=False):
    root = writer.external_root(directory, CHECKOUT, new=True)
    if any(writer.present(p / writer.MARKER) or writer.present(p / writer.STATE)
           or (writer.present(p / "index.md") and writer.present(p / "log.md")) for p in root.parents):
        raise Refused("Create the disposable fixture outside existing bundles.")
    if root.name.startswith(".") or "/" in root.name or root.name in {".", ".."}:
        raise Refused("Choose a new, visible fixture directory.")
    root.mkdir(mode=0o700, exist_ok=False)
    writer.open_bundle(root, CHECKOUT)
    for folder in ("Resources/videos", "Documents/rankings", "Art"):
        (root / folder).mkdir(parents=True)
    (root / "index.md").write_text('---\nokf_version: "0.3"\n---\n\n# Bijou fixture\n\n'
                                   '* [Resources](Resources/index.md)\n* [Documents](Documents/index.md)\n')
    (root / "Documents/index.md").write_text("# Documents\n\n## Directory Listing\n\n* [Rankings](rankings/index.md)\n")
    (root / "Resources/index.md").write_text("# Resources\n\n## Directory Listing\n\n* [Videos](videos/index.md)\n")
    (root / "Documents/rankings/index.md").write_text(RANK_SCHEMA)
    (root / "log.md").write_text("# Fixture history\n")
    samples = json.loads((EXPERIMENT / "Bijou/Sample.json").read_bytes())
    listing = []
    for i, sample in enumerate(samples + [{"title": "Unseen preview"}, {"title": "Recorded interview"}]):
        path = f"Resources/videos/{8100001 + i}.md"
        values = {"id": f"bho:{8100001 + i}", "type": "Video", "title": sample["title"],
                  "video_type": "YouTube" if i == len(samples) + 1 else "Movie",
                  "video_status": "watchlist" if i == len(samples) else "watched"}
        if sample.get("watched"):
            values["date_watched"] = sample["watched"]
        if sample.get("year"):
            values["release_date"] = sample["year"] + ("-06-01T02:00:00-05:00" if i == 2 else "-06-01")
        if i < len(samples) - 1:
            values["poster"] = f"/Art/{i}.png"
            (root / f"Art/{i}.png").write_bytes(poster(i))
        for key in ("sources", "description"):
            if sample.get(key):
                values[key] = ([{"title": s["title"], "resource": s["address"]} for s in sample[key]]
                               if key == "sources" else sample[key])
        (root / path).write_text("---\n" + "".join(f"{k}: {json.dumps(v)}\n" for k, v in values.items())
                                 + "---\n\n" + sample.get("body", "") + "\n")
        listing.append(f"* [{sample['title']}]({Path(path).name})\n")
    (root / "Resources/videos/index.md").write_text(VIDEO_SCHEMA + "".join(listing))
    result = writer.create(root, ROUTES, b"---\ntype: Film Ranking\ntitle: Bijou ranking\n---\n\n## Ranking\n\n",
                           "process:bijou-fixture")
    cfg = {"id": result["id"], "path": result["path"], "library": uuid.uuid4().hex,
           "bundle": writer.bundle_identity(root)}
    (root / bijou.BINDING).write_bytes(writer.json_bytes(cfg))
    if reactions:
        (root / "Documents/reactions").mkdir()
        (root / "Documents/reactions/index.md").write_text(reaction_filing.SCHEMA)
        with (root / "Documents/index.md").open("a") as index:
            index.write("* [Film reactions](reactions/index.md)\n")
        reaction_filing.initialize(root)
    return root


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("new_directory")
    parser.add_argument("--reactions", action="store_true", help="Create a paired disposable source store too.")
    os.umask(0o077)
    try:
        args = parser.parse_args()
        print(create(args.new_directory, reactions=args.reactions))
    except (Refused, OSError) as error:
        parser.exit(2, f"{parser.prog}: {error}\n")
