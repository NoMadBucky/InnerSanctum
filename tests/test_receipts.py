import json

import pytest

from innersanctum import cli, concept, journal, writer
from innersanctum.schema import Refused
from test_create import ACTOR, DRAFT, ROUTES, bundle, snapshot  # noqa: F401
from test_journal import DAY, STAMP, TEXT, ledgers  # noqa: F401


KEY = "operation-unique-01"


def test_cli_replays_original_create_after_update_and_delete(ledgers, tmp_path, capsys):
    draft, routes = tmp_path / "draft", tmp_path / "routes"
    draft.write_text(DRAFT)
    routes.write_text(ROUTES)
    args = ["concept", "create", "--from", str(draft), "--routes", str(routes),
            "--actor", ACTOR, "--bundle", str(ledgers), "--request-id", KEY]
    assert cli.main([*args, "--dry-run"]) == 0
    assert json.loads(capsys.readouterr().out)["status"] == "planned"
    assert not (ledgers / writer.STATE).exists()
    assert cli.main(args) == 0
    created = json.loads(capsys.readouterr().out)
    assert created["request_id"] == KEY
    record = concept.read(ledgers, created["id"])
    edit = (ledgers, created["id"], record["revision"], ACTOR)
    update = dict(replacement=(record["markdown"] + "\nNew body\n").encode(), request_id=KEY + "-edit")
    changed = concept.change(*edit, **update)
    delete = (ledgers, created["id"], changed["revision"], ACTOR)
    removed = concept.change(*delete, request_id=KEY + "-delete")
    before = snapshot(ledgers)
    assert concept.change(*edit, **update) == changed
    assert concept.change(*delete, request_id=KEY + "-delete") == removed
    assert cli.main(args) == 0 and json.loads(capsys.readouterr().out) == created
    with pytest.raises(Refused, match="different arguments"):
        journal.add(ledgers, TEXT, ACTOR, at=STAMP, request_id=KEY)
    assert snapshot(ledgers) == before


@pytest.mark.parametrize("failure", ["between-files", "before-receipt", "after-receipt"])
def test_journal_retry_across_publication_and_receipt_interruptions(ledgers, monkeypatch, failure):
    state = ledgers / writer.STATE
    store = writer.receipt_path(state, KEY)
    install = writer.install

    def interrupted(folder, target, data, *, absent=False):
        if failure == "before-receipt" and target == store:
            raise OSError("injected")
        install(folder, target, data, absent=absent)
        if (failure == "between-files" and target == ledgers / DAY
                or failure == "after-receipt" and target == store):
            raise OSError("injected")

    def add():
        return journal.add(ledgers, TEXT, ACTOR, at=STAMP, subject="Do not retain", request_id=KEY)

    with monkeypatch.context() as patch:
        patch.setattr(writer, "install", interrupted)
        with pytest.raises(OSError, match="injected"):
            add()
    with pytest.raises(Refused, match="pending"):
        add()
    result = writer.recover(ledgers)
    assert result == add()
    assert len(journal.read(ledgers, STAMP[:10])["entries"]) == 1
    assert not (state / writer.PENDING).exists()
    assert b"Do not retain" not in store.read_bytes() and TEXT not in store.read_bytes()
    assert store.stat().st_mode & 0o777 == 0o600


def test_invalid_or_corrupt_receipt_refuses_without_writing(ledgers):
    with pytest.raises(Refused, match="16–128"):
        journal.add(ledgers, TEXT, ACTOR, at=STAMP, request_id="../bad")
    assert not (ledgers / writer.STATE).exists()
    journal.add(ledgers, TEXT, ACTOR, at=STAMP, request_id=KEY)
    saved = writer.receipt_path(ledgers / writer.STATE, KEY)
    saved.write_bytes(saved.read_bytes().replace(b'"status":"added"', b'"status":"other"'))
    before = snapshot(ledgers)
    with pytest.raises(Refused, match="receipt is invalid"):
        journal.add(ledgers, TEXT, ACTOR, at=STAMP, request_id=KEY)
    assert snapshot(ledgers) == before


def test_append_cas_refuses_changed_or_missing_day(ledgers):
    with pytest.raises(Refused, match="no longer exists"):
        journal.add(ledgers, TEXT, ACTOR, at=STAMP, revision="a" * 64)
    first = journal.add(ledgers, TEXT, ACTOR, at=STAMP)
    assert not (ledgers / writer.STATE / writer.PENDING).exists()
    journal.add(ledgers, TEXT, ACTOR, at=STAMP, revision=first["revision"])
    before = snapshot(ledgers)
    with pytest.raises(Refused, match="stale"):
        journal.add(ledgers, TEXT, ACTOR, at=STAMP, revision=first["revision"])
    assert snapshot(ledgers) == before


def test_structured_entry_passes_subject_with_body_on_stdin(ledgers, capsys, monkeypatch):
    import io
    import sys

    def run(source):
        monkeypatch.setattr(sys, "stdin", io.TextIOWrapper(io.BytesIO(source), encoding="utf-8"))
        return cli.main(["journal", "add", "--bundle", str(ledgers), "--entry-json", "--at", STAMP,
                         "--request-id", KEY, "--actor", ACTOR])

    assert run(b'{"markdown":"Synthetic.","subject":"A title","subject":null}') == 2
    assert not (ledgers / writer.STATE).exists()
    capsys.readouterr()
    assert run(b'{"markdown":"Synthetic.","subject":"A title"}') == 0
    assert "A title" not in capsys.readouterr().out
    assert "**Subject:** A title" in (ledgers / DAY).read_text()
