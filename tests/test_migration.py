import json

import pytest

from innersanctum import cli, migration, writer
from innersanctum.schema import Refused


SCHEMA = """# Synthetic videos

```yaml
okf_schema:
  type: Video
  directory: Resources
  required: [id, type, title]
  fields:
    status:
      type: enum
      values: [watched, watchlist, unread, to-read, reading, read]
    date_watched: { type: date }
```

## Directory Listing

* [Synthetic](1234567.md)
"""


@pytest.fixture
def bundle(tmp_path):
    root = tmp_path.resolve() / "bundle"
    index = root / migration.VIDEO_INDEX
    index.parent.mkdir(parents=True)
    index.write_text(SCHEMA)
    (root / "index.md").write_text('---\nokf_version: "0.2"\n---\n\n# Synthetic\n')
    return root


def record(bundle, number, metadata, *, subject="Video", newline="\n"):
    path = f"Resources/videos/{number}.md"
    content = (f"---\nid: bho:{number}\ntype: {subject}\ntitle: Synthetic\n"
               f"{metadata}---\n\nBody mentions `status: watched`.\n")
    (bundle / path).write_bytes(content.replace("\n", newline).encode())
    return path


def snapshot(bundle):
    return {p.relative_to(bundle): p.read_bytes() for p in bundle.rglob("*.md")}


def test_preview_is_read_only_and_preserves_source(bundle, capsys):
    changed = record(bundle, 1234567, 'status: "watched" # preserve comment\n', newline="\r\n")
    record(bundle, 2345678, "video_status: watched\n")
    record(bundle, 3456789, "status: deprecated\n")
    record(bundle, 4567890, "")
    record(bundle, 5678901, "status: watched\n", subject="Note")
    before = snapshot(bundle)
    assert cli.main(["migration", "video-status-preview", "--bundle", str(bundle)]) == 0
    plan = json.loads(capsys.readouterr().out)
    assert plan["status"] == "preview"
    assert (plan["videos"], plan["renames"], plan["already_uses_video_status"],
            plan["no_legacy_status"]) == (4, 1, 1, 2)
    old = (bundle / changed).read_bytes()
    wanted = old.replace(b'\r\nstatus: "watched" # preserve comment', b'\r\nvideo_status: "watched" # preserve comment')
    assert plan["records"] == [{"path": changed, "before": writer.digest(old), "after": writer.digest(wanted)}]
    assert plan["declaration"]["after"] == writer.digest(SCHEMA.replace("    status:", "    video_status:").encode())
    assert migration.preview_video_status(bundle)["digest"] == plan["digest"]
    assert snapshot(bundle) == before
    assert not (bundle / writer.STATE).exists()


def test_preview_flags_conflicts_and_preexisting_authoring_refusals(bundle):
    conflict = record(bundle, 1234567, "status: watched\nvideo_status: watchlist\n")
    invalid_date = record(bundle, 2345678, "status: watched\ndate_watched: not-a-date\n")
    unknown = record(bundle, 3456789, "status: unknown-value\n")
    before = snapshot(bundle)
    plan = migration.preview_video_status(bundle)
    assert plan["status"] == "blocked"
    assert plan["renames"] == 1
    assert plan["validation_issues"] == {"preexisting": 1}
    assert {item["path"] for item in plan["blockers"]} == {conflict, invalid_date, unknown}
    assert snapshot(bundle) == before


def test_preview_refuses_pending_work(bundle):
    state = bundle / writer.STATE
    state.mkdir()
    (state / writer.PENDING).write_text("pending")
    with pytest.raises(Refused, match="pending"):
        migration.preview_video_status(bundle)
