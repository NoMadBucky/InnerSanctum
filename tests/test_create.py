import fcntl
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import shutil

import pytest

from innersanctum import cli, writer
from innersanctum.schema import Refused, document


SCHEMA = """# Synthetic videos

```yaml
okf_schema:
  type: Video
  directory: Resources
  required: [id, type, title]
  fields:
    id: {type: bho}
    type: {const: Video}
    title: {type: string}
    date_watched: {type: date}
    in_library: {type: bool}
    status: {type: enum, values: [watched, watchlist]}
```

## Directory Listing

* [Existing](1234567.md)
"""
ROUTES = """[types.Video]
schema = "Resources/videos/index.md"
directory = "Resources/videos"
"""
DRAFT = """---
type: Video
title: "Synthetic [film] *one*"
status: watched
date_watched: 2026-11-22
in_library: false
---

Text and [a link](https://example.com/).
"""
ACTOR = "test:synthetic"
DEST = "Resources/videos/index.md"


@pytest.fixture
def bundle(tmp_path):
    root = tmp_path.resolve() / "bundle"
    (root / "Resources/videos").mkdir(parents=True)
    (root / DEST).write_text(SCHEMA)
    (root / "Resources/videos/1234567.md").write_text("---\nid: bho:1234567\ntype: Video\n---\n")
    (root / "Resources/index.md").write_text("# Resources\n\n* [Videos](videos/index.md)\n")
    (root / "index.md").write_text('---\nokf_version: "0.2"\n---\n\n# Synthetic fixture\n')
    (root / "log.md").write_text("# History\n\n## 2000-01-01\n\n* Existing entry.\n")
    return root


def snapshot(root):
    return {path.relative_to(root).as_posix(): path.read_bytes() for path in root.rglob("*.md")}


def invoke(bundle, tmp_path, *args):
    routes = tmp_path / "routes.toml"
    routes.write_text(ROUTES)
    return cli.main(["concept", args[0], "--bundle", str(bundle), "--routes", str(routes), *args[1:]])


def test_template_and_cli_create_preserve_source(bundle, tmp_path, capsys):
    assert invoke(bundle, tmp_path, "template", "Video") == 0
    template = capsys.readouterr().out
    assert '"title": null' in template and '# "status": null' in template
    draft = tmp_path / "draft.md"
    draft.write_text(DRAFT)
    before = snapshot(bundle)
    assert invoke(bundle, tmp_path, "create", "--from", str(draft), "--actor", ACTOR) == 0
    dto = json.loads(capsys.readouterr().out)
    assert dto["status"] == "created"
    record = (bundle / dto["path"]).read_text()
    fields, body, _ = document(record)
    assert fields["id"] == dto["id"]
    assert fields["generated"]["by"] == ACTOR
    assert record.split("\n", 5)[5] == DRAFT.split("\n", 1)[1]
    assert body == document(DRAFT)[1]
    assert dto["revision"] == writer.digest(record.encode())
    index = (bundle / DEST).read_text()
    assert r"Synthetic \[film\] \*one\*" in index
    assert f"]({Path(dto['path']).name})" in index
    assert "](" + dto["path"] + ")" in (bundle / "log.md").read_text()
    assert {path for path, data in snapshot(bundle).items() if before.get(path) != data} == set(dto["files"])
    assert not (bundle / writer.STATE / writer.PENDING).exists()
    assert (bundle / dto["path"]).stat().st_mode & 0o777 == 0o600


def test_schema_and_destination_are_generic(bundle):
    (bundle / "Places").mkdir()
    (bundle / "Places/index.md").write_text(
        "# Places\n\n```yaml\nokf_schema:\n  type: Place\n  directory: Places\n"
        "  required: [title, country]\n  fields:\n    country: {type: string}\n```\n\n## Directory Listing\n")
    routes = ROUTES + '\n[types.Place]\nschema = "Places/index.md"\ndirectory = "Places"\n'
    raw = b"---\ntype: Place\ntitle: Synthetic place\ncountry: XY\n---\n\nExample.\n"
    result = writer.create(bundle, routes, raw, ACTOR)
    assert result["path"].startswith("Places/")
    assert "Synthetic place" in (bundle / "Places/index.md").read_text()


def test_dry_run_does_not_write_or_stage(bundle):
    before = snapshot(bundle)
    result = writer.create(bundle, ROUTES, DRAFT.encode(), ACTOR, dry_run=True)
    assert result["status"] == "planned" and not (bundle / result["path"]).exists()
    assert snapshot(bundle) == before and not (bundle / writer.STATE).exists()


def test_create_preserves_crlf_and_ignores_fenced_example_headings(bundle):
    index = bundle / DEST
    fake = "```markdown\n## Directory Listing\n```\n\n"
    index.write_bytes((fake + SCHEMA).replace("\n", "\r\n").encode())
    raw = DRAFT.replace("\n", "\r\n").encode()
    dto = writer.create(bundle, ROUTES, raw, ACTOR)
    result = (bundle / dto["path"]).read_bytes()
    assert result.split(b"\r\n", 5)[5] == raw.split(b"\r\n", 1)[1]
    assert index.read_bytes().startswith(fake.replace("\n", "\r\n").encode())
    assert b"\n" not in index.read_bytes().replace(b"\r\n", b"")


@pytest.mark.parametrize("old,new,problem", [
    ("status: watched", "status: unknown", "invalid status"),
    ("in_library: false", 'in_library: "false"', "invalid in_library"),
    ("date_watched: 2026-11-22", 'date_watched: "2026-02-30"', "invalid date_watched"),
    ('title: "Synthetic [film] *one*"', "description: No title", "missing title"),
    ("status: watched", "status: watched\nid: bho:7654321", "Omit id"),
    ("status: watched", "status: watched\nstatus: watched", "duplicate key"),
    ("status: watched", "status: &status watched", "anchors"),
    ("type: Video", "type: Unrouted", "no explicit creation route"),
])
def test_refuses_invalid_drafts(bundle, old, new, problem):
    before = snapshot(bundle)
    with pytest.raises(Refused, match=problem):
        writer.create(bundle, ROUTES, DRAFT.replace(old, new).encode(), ACTOR)
    assert snapshot(bundle) == before
    assert not (bundle / writer.STATE / writer.PENDING).exists()


@pytest.mark.parametrize("routes", [
    ROUTES.replace('directory = "Resources/videos"', 'directory = "/"'),
    ROUTES.replace('directory = "Resources/videos"', 'directory = "Resources/no-index"'),
    ROUTES.replace('directory = "Resources/videos"', 'directory = "Resources/../videos"'),
    ROUTES.replace('schema = "Resources/videos/index.md"', 'schema = "Resources/index.md"'),
])
def test_refuses_invalid_routes(bundle, routes):
    before = snapshot(bundle)
    with pytest.raises(Refused):
        writer.create(bundle, routes, DRAFT.encode(), ACTOR)
    assert snapshot(bundle) == before


def test_refuses_duplicate_declaration_and_reuses_no_ids(bundle, monkeypatch):
    other = bundle / "Resources/index.md"
    original = other.read_text()
    other.write_text(SCHEMA)
    with pytest.raises(Refused, match="one matching declaration"):
        writer.create(bundle, ROUTES, DRAFT.encode(), ACTOR, dry_run=True)
    other.write_text(original)
    picks = iter([234567, 234568])
    monkeypatch.setattr(writer.secrets, "randbelow", lambda _: next(picks))
    result = writer.create(bundle, ROUTES, DRAFT.encode(), ACTOR)
    assert result["id"] == "bho:1234568"
    assert (bundle / "Resources/videos/1234567.md").exists()


def test_id_scan_preserves_opaque_legacy_metadata(bundle, monkeypatch):
    existing = bundle / "Resources/videos/1234567.md"
    legacy = b"---\n'id': 'bho:1234567'\ntype: Video\nlegacy: !private opaque\n---\n"
    existing.write_bytes(legacy)
    picks = iter([234567, 234568])
    monkeypatch.setattr(writer.secrets, "randbelow", lambda _: next(picks))
    result = writer.create(bundle, ROUTES, DRAFT.encode(), ACTOR)
    assert result["id"] == "bho:1234568"
    assert existing.read_bytes() == legacy


@pytest.mark.parametrize("field", [
    "id: !private bho:1234567",
    "id: bho:1234567\n'id': bho:2345678",
    "id: &identity bho:1234567",
    'id: bho:1234567\n"<<": {id: bho:2345678}',
])
def test_id_scan_refuses_ambiguous_id_or_merge(bundle, field):
    (bundle / "Resources/videos/1234567.md").write_text(f"---\n{field}\n---\n")
    before = snapshot(bundle)
    with pytest.raises(Refused):
        writer.create(bundle, ROUTES, DRAFT.encode(), ACTOR)
    assert snapshot(bundle) == before


def test_preserves_repeated_historical_log_sections(bundle):
    audit = bundle / "log.md"
    history = audit.read_text() + "\n## 2000-01-01\n\n* Another historical entry.\n"
    audit.write_text(history)
    changes = writer.plan_create(bundle, ROUTES, DRAFT.encode(), ACTOR,
                                 now=datetime(2026, 11, 24, tzinfo=timezone.utc))
    after = changes[-1].after
    assert "## 2026-11-24" in after
    assert after[after.index("## 2000-01-01"):] == history[history.index("## 2000-01-01"):]
    with pytest.raises(Refused, match="more than one section for the Create date"):
        writer.plan_create(bundle, ROUTES, DRAFT.encode(), ACTOR,
                           now=datetime(2000, 1, 1, tzinfo=timezone.utc))


def test_integrates_into_existing_unique_log_section(bundle):
    audit = bundle / "log.md"
    today = "## 2026-11-24"
    old = audit.read_text().replace("# History\n\n", f"# History\n\n{today}\n\n* Current entry.\n\n")
    audit.write_text(old)
    changes = writer.plan_create(bundle, ROUTES, DRAFT.encode(), ACTOR,
                                 now=datetime(2026, 11, 24, tzinfo=timezone.utc))
    after = changes[-1].after
    assert after.count(today) == 1
    assert after.index(today) < after.index("**Create**") < after.index("* Current entry.")


@pytest.mark.parametrize("after", [writer.PENDING, "record", "index.md", "log.md"])
def test_recovery_finishes_original_create_once(bundle, monkeypatch, after):
    install = writer.install

    def interrupt(state, target, *args, **kwargs):
        install(state, target, *args, **kwargs)
        if target.name == after or after == "record" and target.stem.isdecimal():
            raise KeyboardInterrupt

    with monkeypatch.context() as patch:
        patch.setattr(writer, "install", interrupt)
        with pytest.raises(KeyboardInterrupt):
            writer.create(bundle, ROUTES, DRAFT.encode(), ACTOR)
    assert (bundle / writer.STATE / writer.PENDING).is_file()
    with pytest.raises(Refused, match="pending"):
        writer.create(bundle, ROUTES, DRAFT.encode(), ACTOR)
    result = writer.recover(bundle)
    assert (bundle / "log.md").read_text().count(f"]({result['path']})") == 1
    assert (bundle / DEST).read_text().count(f"]({Path(result['path']).name})") == 1
    with pytest.raises(Refused, match="No Create"):
        writer.recover(bundle)


def test_recovery_cleans_interrupted_link_stage(bundle, monkeypatch):
    def crash_after_link(member, target, **kwargs):
        os_link(member, target, **kwargs)
        if target.stem.isdecimal():
            # Model process death by leaving an extra staging link after install.
            os_link(member, member.with_name("stage-interrupted"))
            raise KeyboardInterrupt

    os_link = os.link
    with monkeypatch.context() as patch:
        patch.setattr(writer.os, "link", crash_after_link)
        with pytest.raises(KeyboardInterrupt):
            writer.create(bundle, ROUTES, DRAFT.encode(), ACTOR)
    result = writer.recover(bundle)
    assert (bundle / result["path"]).stat().st_nlink == 1
    assert not (bundle / writer.STATE / "stage-interrupted").exists()


def test_recovery_refuses_to_rebase_unknown_bytes(bundle, monkeypatch):
    with monkeypatch.context() as patch:
        patch.setattr(writer, "publish", lambda *_: pytest.fail("injected before publication"))
        with pytest.raises(pytest.fail.Exception):
            writer.create(bundle, ROUTES, DRAFT.encode(), ACTOR)
    (bundle / DEST).write_text(SCHEMA + "\nUnrelated edit.\n")
    before = snapshot(bundle)
    with pytest.raises(Refused, match="retain the original journal"):
        writer.recover(bundle)
    assert snapshot(bundle) == before
    assert (bundle / writer.STATE / writer.PENDING).is_file()


def test_recovery_refuses_a_journal_from_a_different_bundle(bundle, monkeypatch):
    with monkeypatch.context() as patch:
        patch.setattr(writer, "publish", lambda *_: pytest.fail("injected before publication"))
        with pytest.raises(pytest.fail.Exception):
            writer.create(bundle, ROUTES, DRAFT.encode(), ACTOR)
    copy = bundle.with_name("other-bundle")
    shutil.copytree(bundle, copy)
    before = snapshot(copy)
    with pytest.raises(Refused, match="journal is invalid"):
        writer.recover(copy)
    assert snapshot(copy) == before


def test_refuses_writer_overlap(bundle):
    with writer.locked(bundle) as state:
        with (state / "lock").open("rb") as lock:
            with pytest.raises(BlockingIOError):
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        with pytest.raises(Refused, match="Another InnerSanctum write"):
            writer.create(bundle, ROUTES, DRAFT.encode(), ACTOR)


def test_refuses_protected_roots_and_symlinks(bundle, tmp_path):
    checkout = tmp_path.resolve() / "checkout"
    checkout.mkdir()
    (checkout / "OKF").mkdir()
    with pytest.raises(Refused, match="standalone"):
        writer.open_bundle(checkout / "OKF", checkout)
    assert not (checkout / "OKF" / writer.STATE).exists()
    assert writer.open_bundle(bundle, checkout) == bundle
    (bundle / writer.MARKER).touch()
    with pytest.raises(Refused, match="managed by MatterKeep"):
        writer.open_bundle(bundle, checkout)
    with pytest.raises(Refused, match="managed by MatterKeep"):
        writer.create(bundle, ROUTES, DRAFT.encode(), ACTOR)
    assert not (bundle / writer.STATE).exists()
    (bundle / writer.MARKER).unlink()
    alias = tmp_path / "alias"
    alias.symlink_to(bundle, target_is_directory=True)
    with pytest.raises(Refused, match="standalone"):
        writer.open_bundle(alias, checkout)
    (bundle / "Resources/symlink").symlink_to(checkout, target_is_directory=True)
    with pytest.raises(Refused, match="symbolic link"):
        writer.create(bundle, ROUTES, DRAFT.encode(), ACTOR, dry_run=True)
