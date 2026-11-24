import json
import os
from pathlib import Path
import shutil
import subprocess

import pytest

from innersanctum import cli, handover, writer
from innersanctum.schema import Refused
from test_create import ACTOR, DRAFT, ROUTES, bundle, snapshot  # noqa: F401


OLD = b"personal-writer-2\n" + b"a" * 64 + b"\n"


def put(path, content):
    path.write_bytes(content)
    path.chmod(0o600)


def file_record(path):
    data = path.read_bytes()
    return {"size": len(data), "sha256": writer.digest(data)}


@pytest.fixture
def selection(bundle, tmp_path):
    checkout = tmp_path / "InnerSanctum"
    checkout.mkdir()
    root = bundle.rename(checkout / "OKF")
    assets = checkout / "SourceFiles"
    assets.mkdir(mode=0o700)
    put(assets / "original.bin", b"synthetic attachment")
    put(root / writer.MARKER, OLD)
    for path in [root, *root.rglob("*")]:
        path.chmod(0o700 if path.is_dir() else 0o600)
    (checkout / ".gitignore").write_text("/OKF/\n/SourceFiles/\n")
    for args in (("init", "-q"), ("add", ".gitignore"),
                 ("-c", "user.name=Fixture", "-c", "user.email=fixture@example.com",
                  "commit", "--no-gpg-sign", "-qm", "synthetic checkout")):
        subprocess.run(["/usr/bin/git", *args], cwd=checkout, check=True, capture_output=True)
    evidence = tmp_path / "evidence"
    evidence.mkdir(mode=0o700)
    checkpoint = evidence / "checkpoint"
    checkpoint.mkdir(mode=0o700)
    shutil.copytree(root, checkpoint / "canonical")
    notes = checkpoint / "notes"
    notes.mkdir(mode=0o700)
    put(notes / "notes.sqlite3", b"synthetic Notes checkpoint bytes")
    notes_items = {"notes.sqlite3": file_record(notes / "notes.sqlite3")}
    canonical = {
        "directories": {"": {}, **{p.relative_to(root).as_posix(): {} for p in root.rglob("*") if p.is_dir()}},
        "files": {p.relative_to(root).as_posix(): file_record(p) for p in root.rglob("*") if p.is_file()},
    }
    source = {
        "format": "personal-pair-handoff-2", "marker": OLD.decode(),
        "binding": {"okf": str(root), "state": str(tmp_path / "personal-state")},
        "snapshot": {"canonical": canonical, "database": notes_items["notes.sqlite3"]},
    }
    raw = json.dumps(source).encode()
    put(checkpoint / "handoff.json", raw)
    seal = {"format": "personal-clean-checkpoint-2", "handoff_sha256": writer.digest(raw),
            "source_notes": notes_items, "checkpoint": {"notes": notes_items}}
    receipt = json.dumps(seal).encode()
    put(checkpoint / "receipt.json", receipt)
    return checkout, root, checkpoint, writer.digest(receipt)


def transfer(selection):
    checkout, _, checkpoint, approved = selection
    return handover.adopt(checkout, checkpoint, approved, writers_stopped=True)


def test_handover_then_create_from_exact_checkout(selection, tmp_path, capsys):
    checkout, root, checkpoint, _ = selection
    with pytest.raises(Refused, match="does not own"):
        with handover.live_checkout(checkout):
            pytest.fail("Personal marker admitted InnerSanctum")
    before = snapshot(root)
    assert transfer(selection)["status"] == "adopted"
    assert snapshot(root) == before
    assert (checkpoint / "canonical" / writer.MARKER).read_bytes() == OLD
    assert (checkout / "SourceFiles/original.bin").read_bytes() == b"synthetic attachment"
    successor = (root / writer.MARKER).read_bytes()
    assert handover.SUCCESSOR.fullmatch(successor)
    assert not successor.startswith(b"personal-writer-2\n")
    with pytest.raises(Refused, match="do not reapply"):
        transfer(selection)
    routes = tmp_path / "routes.toml"
    routes.write_text(ROUTES)
    draft = tmp_path / "draft.md"
    draft.write_text(DRAFT)
    assert cli.main(["concept", "create", "--live-checkout", str(checkout),
                     "--routes", str(routes), "--from", str(draft), "--actor", ACTOR]) == 0
    dto = json.loads(capsys.readouterr().out)
    assert (root / dto["path"]).exists()
    assert (root / writer.MARKER).read_bytes() == successor
    assert {path for path, value in snapshot(root).items() if before.get(path) != value} == set(dto["files"])


def test_crud_requires_the_adopted_checkout(selection, tmp_path, capsys):
    checkout, root, _, _ = selection
    selector = "bho:1234567"
    live = ["--live-checkout", str(checkout)]
    assert cli.main(["concept", "read", selector, *live]) == 2
    assert "does not own" in capsys.readouterr().err
    transfer(selection)
    marker = (root / writer.MARKER).read_bytes()
    assert cli.main(["concept", "read", selector, "--bundle", str(root)]) == 2
    assert cli.main(["concept", "read", selector, *live]) == 0
    record = json.loads(capsys.readouterr().out)
    draft = tmp_path / "revision.md"
    draft.write_text(record["markdown"].replace("type: Video", "type: Video\ntitle: Revised"))
    assert cli.main(["concept", "update", selector, *live, "--from", str(draft),
                     "--revision", record["revision"], "--actor", ACTOR]) == 0
    updated = json.loads(capsys.readouterr().out)
    assert cli.main(["concept", "delete", selector, *live,
                     "--revision", updated["revision"], "--actor", ACTOR]) == 0
    assert not (root / record["path"]).exists()
    assert (root / writer.MARKER).read_bytes() == marker
    assert (checkout / "SourceFiles/original.bin").read_bytes() == b"synthetic attachment"


def test_receipt_lookup_is_passive_and_update_can_pin_identity_and_path(selection, tmp_path, capsys, monkeypatch):
    checkout, root, _, _ = selection
    transfer(selection)
    live = ["--live-checkout", str(checkout)]
    request = "test-notes-request"
    receipt = ["concept", "receipt", request, *live]
    assert cli.main([*receipt, "--expect-adoption", "0" * 64]) == 2
    assert "expected checkpoint receipt" in capsys.readouterr().err
    receipt.extend(("--expect-adoption", selection[3]))
    assert cli.main(receipt) == 0 and json.loads(capsys.readouterr().out) == {"state": "missing"}
    assert not (root / writer.STATE).exists()
    old = "Resources/videos/1234567.md"
    source = (root / old).read_text()
    draft = tmp_path / "edit.md"
    draft.write_text(source.replace("type: Video", "type: Video\ntitle: Revised"))
    args = ["concept", "update", "bho:1234567", *live, "--request-id", request, "--from", str(draft),
            "--revision", writer.digest(source.encode()), "--actor", ACTOR]
    assert cli.main([*args, "--expect-path", "Resources/videos/1234568.md"]) == 2
    assert "not at the expected path" in capsys.readouterr().err
    original = writer.install

    def interrupt(state, target, raw, *, absent=False):
        if target == root / "log.md":
            raise OSError("synthetic")
        return original(state, target, raw, absent=absent)

    with monkeypatch.context() as patch:
        patch.setattr(writer, "install", interrupt)
        assert cli.main([*args, "--expect-path", old]) == 2
    capsys.readouterr()
    before = snapshot(root)
    assert cli.main(receipt) == 0 and json.loads(capsys.readouterr().out) == {"state": "pending"}
    assert snapshot(root) == before
    assert cli.main(["concept", "recover", *live]) == 0
    result = json.loads(capsys.readouterr().out)
    assert cli.main(receipt) == 0
    observed = json.loads(capsys.readouterr().out)
    assert observed == {"state": "completed", "receipt": result, "fingerprint": writer.write_request(
        request, "concept-update", "bho:1234567", writer.digest(source.encode()), ACTOR,
        writer.digest(draft.read_bytes()), old)[1]}
    assert source not in str(observed)


@pytest.mark.parametrize("failure", ["checkpoint", "drift", "notes", "sha", "tracked", "wrong-checkout", "lock"])
def test_handover_refuses_until_evidence_matches(selection, failure, monkeypatch):
    checkout, root, checkpoint, approved = selection
    if failure == "checkpoint":
        put(checkpoint / "canonical/log.md", b"altered copy")
    elif failure == "drift":
        put(root / "log.md", b"changed canonical bytes")
    elif failure == "notes":
        put(checkpoint / "notes/notes.sqlite3", b"altered Notes copy")
    elif failure == "sha":
        selection = checkout, root, checkpoint, "f" * 64
    elif failure == "tracked":
        subprocess.run(["/usr/bin/git", "add", "-f", "OKF/log.md"], cwd=checkout, check=True)
    elif failure == "wrong-checkout":
        selection = checkout / "OKF", root, checkpoint, approved
    else:
        def busy(*args):
            raise BlockingIOError

        monkeypatch.setattr(handover.fcntl, "flock", busy)
    with pytest.raises(Refused):
        transfer(selection)
    assert (root / writer.MARKER).read_bytes() == OLD
    assert not (root / writer.STATE).exists()


def test_handover_interruption_before_and_after_marker_exchange(selection, monkeypatch):
    checkout, root, checkpoint, _ = selection
    install = writer.install

    def interrupt(*args):
        raise KeyboardInterrupt

    with monkeypatch.context() as patch:
        patch.setattr(writer, "install", interrupt)
        with pytest.raises(KeyboardInterrupt):
            transfer(selection)
    assert (root / writer.MARKER).read_bytes() == OLD

    def after(*args):
        install(*args)
        raise KeyboardInterrupt

    with monkeypatch.context() as patch:
        patch.setattr(writer, "install", after)
        with pytest.raises(KeyboardInterrupt):
            transfer(selection)
    with handover.live_checkout(checkout) as (selected, marker):
        assert selected == root and handover.SUCCESSOR.fullmatch(marker)
    assert (checkpoint / "canonical" / writer.MARKER).read_bytes() == OLD
    assert not (root / writer.STATE).exists()


def test_successor_cannot_be_copied_to_a_different_bundle(selection):
    checkout, root, _, _ = selection
    transfer(selection)
    copy = root.with_name("Copy")
    shutil.copytree(root, copy)
    os.rename(root, root.with_name("Original"))
    os.rename(copy, root)
    with pytest.raises(Refused, match="does not own"):
        with handover.live_checkout(checkout):
            pytest.fail("Copied marker must not authorize a different inode")
