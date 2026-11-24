import json
from pathlib import Path

import pytest

from innersanctum import cli, concept, journal, writer
from innersanctum.schema import Refused, document
from test_create import ACTOR, DEST, DRAFT, ROUTES, bundle, snapshot  # noqa: F401
from test_journal import DAY, FAMILY, MONTHLY, OLD, STAMP, TEXT, existing, ledgers  # noqa: F401


def call(root, capsys, group, action, *args):
    assert cli.main([group, action, *args, "--bundle", str(root)]) == 0
    return json.loads(capsys.readouterr().out)


def test_concept_crud_through_cli(bundle, tmp_path, capsys):
    result = writer.create(bundle, ROUTES, DRAFT.encode(), ACTOR)
    path, identity = result["path"], result["id"]
    assert call(bundle, capsys, "concept", "read", path) == call(bundle, capsys, "concept", "read", identity)
    record = concept.read(bundle, identity)
    assert record["markdown"].encode() == (bundle / path).read_bytes()
    assert record["revision"] == result["revision"]
    parent = bundle / DEST
    href = f"]({Path(path).name})"
    parent.write_text(parent.read_text().replace(href, href + " - Keep this description."))
    draft = tmp_path / "replace.md"
    draft.write_text(record["markdown"].replace('Synthetic [film] *one*', 'Changed [title]'))
    before = snapshot(bundle)
    plan = call(bundle, capsys, "concept", "update", path, "--from", str(draft),
                "--revision", record["revision"], "--actor", ACTOR, "--dry-run")
    assert plan["status"] == "planned" and snapshot(bundle) == before
    edited = call(bundle, capsys, "concept", "update", identity, "--from", str(draft),
                  "--revision", record["revision"], "--actor", ACTOR)
    assert edited["status"] == "updated" and edited["id"] == identity
    assert edited["path"] == path and edited["previous_revision"] == record["revision"]
    assert edited["files"] == [path, DEST, "log.md"]
    assert parent.read_text() == before[DEST].decode().replace(
        r"Synthetic \[film\] \*one\*", r"Changed \[title\]")
    assert draft.read_bytes() == (bundle / path).read_bytes()
    assert document(record["markdown"])[0]["generated"] == document(draft.read_text())[0]["generated"]
    with pytest.raises(Refused, match="stale"):
        concept.change(bundle, path, record["revision"], ACTOR)
    before = snapshot(bundle)
    plan = call(bundle, capsys, "concept", "delete", path, "--revision", edited["revision"],
                "--actor", ACTOR, "--dry-run")
    assert plan["status"] == "planned" and snapshot(bundle) == before
    deleted = call(bundle, capsys, "concept", "delete", path, "--revision", edited["revision"], "--actor", ACTOR)
    assert deleted["status"] == "deleted" and deleted["revision"] is None and not (bundle / path).exists()
    assert parent.read_text() == "".join(line for line in before[DEST].decode().splitlines(keepends=True)
                                         if href not in line)
    audit = (bundle / "log.md").read_text()
    assert "**Create**" in audit and "**Update**" in audit and "**Delete**" in audit
    assert r"bho\:" + identity[4:] in audit
    assert not (bundle / writer.STATE / writer.PENDING).exists()


def test_concept_read_is_nonmutating_and_reads_legacy_tags(bundle):
    path = "Resources/videos/1234567.md"
    (bundle / path).write_text("---\nid: bho:1234567\ntype: Video\nlegacy: !opaque one\n---\n")
    raw = (bundle / path).read_bytes()
    assert concept.read(bundle, "bho:1234567")["markdown"].encode() == raw
    assert not (bundle / writer.STATE).exists()
    (bundle / "copy.md").write_bytes(raw)
    with pytest.raises(Refused, match="ambiguous"):
        concept.read(bundle, "bho:1234567")


def test_updates_named_legacy_path_and_root_relative_listing(bundle):
    parent = bundle / DEST
    path = "Resources/videos/film one.md"
    source = '---\nid: bho:1234567\ntype: Video\ntitle: Existing\n---\n'
    (bundle / "Resources/videos/1234567.md").rename(bundle / path)
    (bundle / path).write_text(source)
    index = parent.read_text().replace("1234567.md", f"/{path.replace(' ', '%20')}#body")
    parent.write_bytes(index.replace("\n", "\r\n").encode())
    revision = concept.read(bundle, path)["revision"]
    edited = concept.change(bundle, path, revision, ACTOR, replacement=source.replace("Existing", "New").encode())
    assert edited["id"] == "bho:1234567"
    assert parent.read_bytes() == index.replace("[Existing]", "[New]").replace("\n", "\r\n").encode()


@pytest.mark.parametrize("old,new,error", [
    ("type: Video", "type: Note", "managed fields"),
    ("generated:", "verified:", "managed fields"),
    ("type: Video", "type: Video\nowner: new", "managed fields"),
    ("status: watched", "status: unknown", "invalid status"),
])
def test_replacement_must_match_schema_and_keep_managed_fields(bundle, old, new, error):
    result = writer.create(bundle, ROUTES, DRAFT.encode(), ACTOR)
    record = concept.read(bundle, result["path"])
    before = snapshot(bundle)
    with pytest.raises(Refused, match=error):
        concept.change(bundle, record["path"], record["revision"], ACTOR,
                       replacement=record["markdown"].replace(old, new).encode())
    assert snapshot(bundle) == before and not (bundle / writer.STATE / writer.PENDING).exists()


@pytest.mark.parametrize("suffix", [
    "\n\n* [Other title]({name})\n",
    "\n  continued text under the same bullet\n",
    "\n\n  * A nested bullet in the matching item\n",
    "  Another [listing](1234567.md) on the same line\n",
])
def test_refuses_ambiguous_or_multiline_listing(bundle, suffix):
    created = writer.create(bundle, ROUTES, DRAFT.encode(), ACTOR)
    name = Path(created["path"]).name
    index = bundle / DEST
    after = index.read_text().replace(f"]({name})\n", f"]({name})" + suffix.format(name=name))
    index.write_text(after)
    before = snapshot(bundle)
    with pytest.raises(Refused, match="Parent index"):
        concept.change(bundle, created["path"], created["revision"], ACTOR)
    assert snapshot(bundle) == before


def test_deleted_concept_id_is_not_reissued(ledgers, monkeypatch):
    picks = iter([234568, 234568, 234569, 234568, 234570])
    monkeypatch.setattr(writer.secrets, "randbelow", lambda _: next(picks))
    created = writer.create(ledgers, ROUTES, DRAFT.encode(), ACTOR)
    assert created["id"] == "bho:1234568"
    concept.change(ledgers, created["path"], created["revision"], ACTOR)
    assert writer.create(ledgers, ROUTES, DRAFT.encode(), ACTOR)["id"] == "bho:1234569"
    assert journal.add(ledgers, TEXT, ACTOR, at=STAMP)["id"] == "bho:1234570"


@pytest.mark.parametrize("selector", ["../escape.md", "/index.md", "log.md", "Resources/videos/INDEX.md", DAY])
def test_concept_protected_paths(ledgers, selector):
    with pytest.raises(Refused):
        concept.read(ledgers, selector)


def test_journal_crud_selects_one_entry_even_with_duplicate_timestamps(ledgers, tmp_path, capsys):
    first = journal.add(ledgers, b"Older of the two.", "original:author", at=STAMP, subject="Retained")
    journal.add(ledgers, b"Newer of the two.", ACTOR, at=STAMP, subject="Remove this")
    day = first["date"]
    read = call(ledgers, capsys, "journal", "read", day)
    assert [e["at"] for e in read["entries"]] == [STAMP, STAMP]
    assert [e["entry"] for e in read["entries"]] == [1, 2]
    draft = tmp_path / "entry.md"
    draft.write_bytes(TEXT)
    before = snapshot(ledgers)
    plan = call(ledgers, capsys, "journal", "update", day, "--entry", "2", "--from", str(draft),
                "--revision", read["revision"], "--actor", ACTOR, "--dry-run")
    assert plan["status"] == "planned" and snapshot(ledgers) == before
    updated = call(ledgers, capsys, "journal", "update", day, "--entry", "2", "--from", str(draft),
                   "--revision", read["revision"], "--actor", ACTOR, "--category", "Work", "--subject", "Revised")
    assert updated["status"] == "updated" and updated["files"] == [DAY, "log.md"]
    second = journal.read(ledgers, day)
    old_first, new_second = second["entries"]
    assert old_first == read["entries"][0]
    assert "**Author:** original:author" in new_second["markdown"]
    assert "**Category:** Work" in new_second["markdown"] and "**Subject:** Revised" in new_second["markdown"]
    assert "A **synthetic** entry." in new_second["markdown"] and "Older of the two." not in new_second["markdown"]
    cleared = call(ledgers, capsys, "journal", "update", day, "--entry", "2", "--from", str(draft),
                   "--revision", updated["revision"], "--actor", ACTOR, "--clear-subject")
    assert "**Subject:**" not in journal.read(ledgers, day)["entries"][1]["markdown"]
    with pytest.raises(Refused, match="stale"):
        journal.change(ledgers, day, 1, read["revision"], ACTOR)
    gone = call(ledgers, capsys, "journal", "delete", day, "--entry", "1",
                "--revision", cleared["revision"], "--actor", ACTOR)
    assert gone["status"] == "deleted" and gone["id"] == first["id"]
    assert "Newer of the two." not in (ledgers / DAY).read_text()
    journal.change(ledgers, day, 1, gone["revision"], ACTOR)
    assert journal.read(ledgers, day)["entries"] == []
    for index in (FAMILY, MONTHLY):
        assert (ledgers / index).read_bytes() == before[index]
    audit = (ledgers / "log.md").read_text()
    assert audit.count("**Journal entry update**") == audit.count("**Journal entry delete**") == 2
    assert all(secret not in audit for secret in ("Revised", "Older of the two.", "synthetic** entry"))
    assert journal.add(ledgers, TEXT, ACTOR, at=STAMP)["id"] == first["id"]


def test_journal_removing_entry_preserves_crlf_and_non_ledger_sections(ledgers):
    source = OLD.replace("\n", "\r\n")
    existing(ledgers, source)
    day = Path(DAY).stem
    read = journal.read(ledgers, day)
    with pytest.raises(Refused, match="entry number"):
        journal.change(ledgers, day, 3, read["revision"], ACTOR)
    result = journal.change(ledgers, day, 2, read["revision"], ACTOR)
    after = (ledgers / DAY).read_bytes().decode()
    removed = read["entries"][1]["markdown"] + "\r\n"
    assert after == source.replace(removed, "")
    assert result["revision"] == writer.digest(after.encode())


@pytest.mark.parametrize("operation", ["concept-update", "concept-delete", "journal-update", "journal-delete"])
@pytest.mark.parametrize("stop", ["pending", "record", "audit"])
def test_edit_recovery_rolls_forward_once(ledgers, monkeypatch, operation, stop):
    group, action = operation.split("-")
    if group == "concept":
        record = writer.create(ledgers, ROUTES, DRAFT.encode(), ACTOR)
        reloaded = concept.read(ledgers, record["path"])
        replacement = reloaded["markdown"].replace("Text and", "Revised text and").encode()
        edit = lambda: concept.change(ledgers, record["path"], record["revision"], ACTOR,
                                      replacement=replacement if action == "update" else None)
    else:
        record = journal.add(ledgers, TEXT, ACTOR, at=STAMP)
        edit = lambda: journal.change(ledgers, record["date"], 1, record["revision"], ACTOR,
                                      replacement=b"Replacement." if action == "update" else None)
    install, unlink = writer.install, Path.unlink
    target = ledgers / record["path"]

    def interrupted_install(state, path, *args, **kwargs):
        install(state, path, *args, **kwargs)
        if ((stop == "pending" and path.name == writer.PENDING)
                or (stop == "record" and path == target) or (stop == "audit" and path == ledgers / "log.md")):
            raise KeyboardInterrupt

    def interrupted_unlink(path, *args, **kwargs):
        unlink(path, *args, **kwargs)
        if stop == "record" and path == target:
            raise KeyboardInterrupt

    with monkeypatch.context() as patch:
        patch.setattr(writer, "install", interrupted_install)
        patch.setattr(Path, "unlink", interrupted_unlink)
        with pytest.raises(KeyboardInterrupt):
            edit()
    with pytest.raises(Refused, match="pending"):
        edit()
    recovered = writer.recover(ledgers)
    assert recovered["status"] == ("updated" if action == "update" else "deleted")
    assert recovered["id"] == record["id"]
    label = action.capitalize() if group == "concept" else "Journal entry " + action
    assert (ledgers / "log.md").read_text().count(f"**{label}**") == 1
    assert not (ledgers / writer.STATE / writer.PENDING).exists()
    assert target.exists() == (operation != "concept-delete")


def test_recovery_checks_all_targets_before_unlinking(bundle, monkeypatch):
    created = writer.create(bundle, ROUTES, DRAFT.encode(), ACTOR)
    with monkeypatch.context() as patch:
        def interrupt(*args, **kwargs):
            raise KeyboardInterrupt
        patch.setattr(writer, "publish", interrupt)
        with pytest.raises(KeyboardInterrupt):
            concept.change(bundle, created["path"], created["revision"], ACTOR)
    parent = bundle / DEST
    parent.write_text(parent.read_text() + "\nUnknown change.\n")
    before = snapshot(bundle)
    with pytest.raises(Refused, match="retain the original journal"):
        writer.recover(bundle)
    assert snapshot(bundle) == before and (bundle / writer.STATE / writer.PENDING).is_file()
