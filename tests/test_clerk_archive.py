import json
import os

import pytest

from innersanctum import clerk_archive, cli, concept, writer
from innersanctum.schema import MD, Refused
from test_create import ACTOR, DRAFT, ROUTES, bundle, snapshot  # noqa: F401


SESSION = "9" * 32
OTHER = "8" * 32
REQUEST = "clerk-body-edit-001"
TEXT = b"# Synthetic conversation\n\nConfidential test prompt and answer.\n"


@pytest.fixture
def archive(bundle):
    source = bundle.parent / "SourceFiles"
    source.mkdir(mode=0o700)
    directory = source / "ClerkArchive"
    directory.mkdir(mode=0o700)
    return directory


def test_archive_without_edit_leaves_entire_bundle_alone(bundle, archive, tmp_path, capsysbinary):
    before = snapshot(bundle)
    export = tmp_path / "export.md"
    export.write_bytes(TEXT)
    target = ["--bundle", str(bundle)]
    args = ["clerk-archive", "store", "--session", SESSION, "--from", str(export), *target]
    assert cli.main(args) == 0
    first = json.loads(capsysbinary.readouterr().out)
    assert first["status"] == "archived"
    assert cli.main(args) == 0
    assert json.loads(capsysbinary.readouterr().out) == {**first, "status": "existing"}
    export.write_bytes(TEXT + b"\nLater conversation.\n")
    assert cli.main(args) == 0
    second = json.loads(capsysbinary.readouterr().out)["reference"]
    assert second != first["reference"] and second.startswith(f"clerk-archive:{SESSION}/")
    assert cli.main(["clerk-archive", "read", first["reference"], *target]) == 0
    assert capsysbinary.readouterr().out == TEXT
    assert len(list(archive.iterdir())) == 2
    assert all(path.stat().st_mode & 0o777 == 0o600 for path in archive.iterdir())
    assert snapshot(bundle) == before and not (bundle / writer.STATE).exists()


def edit_arguments(bundle):
    created = writer.create(bundle, ROUTES, DRAFT.encode(), ACTOR)
    source = concept.read(bundle, created["id"])["markdown"]
    replacement = source.encode() + b"\nEdited from the conversation.\n"
    return created, replacement


def test_body_update_logs_archive_and_exact_revision_once(bundle, archive, tmp_path, capsys):
    created, raw = edit_arguments(bundle)
    source = tmp_path / "edit.md"
    source.write_bytes(raw)
    ref = clerk_archive.store(bundle, SESSION, TEXT)["reference"]
    args = ["concept", "update", created["id"], "--bundle", str(bundle), "--revision", created["revision"],
            "--clerk-session", ref, "--request-id", REQUEST, "--actor", ACTOR, "--from", str(source)]
    before = snapshot(bundle)
    assert cli.main([*args, "--dry-run"]) == 0
    plan = json.loads(capsys.readouterr().out)
    assert plan["status"] == "planned" and plan["clerk_session"] == ref and snapshot(bundle) == before
    assert cli.main(args) == 0
    saved = json.loads(capsys.readouterr().out)
    assert saved["revision"] == writer.digest(raw)
    assert writer.receipt_status(bundle, REQUEST)["receipt"] == saved
    assert saved["files"] == [created["path"], "log.md"]
    log = (bundle / "log.md").read_text()
    links = [child.attrGet("href") for item in MD.parse(log) for child in item.children or []
             if child.type == "link_open"]
    assert links.count(ref) == 1 and f"revision `{saved['revision']}`" in log
    assert "Confidential test prompt" not in log
    assert clerk_archive.read(bundle, ref) == TEXT
    assert cli.main(args) == 0 and json.loads(capsys.readouterr().out) == saved
    other = clerk_archive.store(bundle, OTHER, TEXT)["reference"]
    with pytest.raises(Refused, match="different arguments"):
        concept.change(bundle, created["id"], created["revision"], ACTOR, replacement=raw,
                       request_id=REQUEST, clerk_session=other)
    assert (bundle / "log.md").read_text() == log
    assert (bundle / created["path"]).read_bytes() == raw


def test_recovery_preserves_the_frozen_clerk_proof(bundle, archive, monkeypatch):
    created, raw = edit_arguments(bundle)
    ref = clerk_archive.store(bundle, SESSION, TEXT)["reference"]
    install = writer.install

    def interrupt(state, target, raw, **options):
        if target.name == "log.md":
            raise OSError("synthetic interruption")
        return install(state, target, raw, **options)

    with monkeypatch.context() as patch:
        patch.setattr(writer, "install", interrupt)
        with pytest.raises(OSError, match="interruption"):
            concept.change(bundle, created["id"], created["revision"], ACTOR, replacement=raw,
                           request_id=REQUEST, clerk_session=ref)
    pending = bundle / writer.STATE / writer.PENDING
    frozen = json.loads(pending.read_bytes())
    assert frozen["version"] == 5 and frozen["clerk_session"] == ref
    log = (bundle / "log.md").read_bytes()
    member = archive / clerk_archive.reference(ref).filename
    member.write_bytes(TEXT + b"tampered")
    with pytest.raises(Refused, match="retained digest"):
        writer.recover(bundle)
    assert (bundle / "log.md").read_bytes() == log and pending.exists()
    member.write_bytes(TEXT)
    result = writer.recover(bundle)
    assert result["clerk_session"] == ref and not pending.exists()
    assert (bundle / "log.md").read_text().count(ref) == 1
    assert (bundle / created["path"]).read_bytes() == raw


@pytest.mark.parametrize("after_link", [False, True])
def test_exact_archive_retry_finishes_an_intact_interrupted_stage(bundle, archive, after_link):
    snapshot = clerk_archive.Snapshot(SESSION, writer.digest(TEXT))
    stage = archive / (".pending-" + snapshot.filename)
    stage.write_bytes(TEXT)
    stage.chmod(0o600)
    if after_link:
        os.link(stage, archive / snapshot.filename)
    result = clerk_archive.store(bundle, SESSION, TEXT)
    assert result["reference"] == snapshot.uri and not stage.exists()
    assert clerk_archive.read(bundle, snapshot.uri) == TEXT


@pytest.mark.parametrize("invalid", ["missing", "external", "metadata", "no-request", "delete", "marker"])
def test_refusal_does_not_publish_an_unproved_edit(bundle, archive, invalid):
    created, raw = edit_arguments(bundle)
    ref = clerk_archive.store(bundle, SESSION, TEXT)["reference"]
    kwargs = dict(replacement=raw, request_id=REQUEST, clerk_session=ref)
    if invalid == "missing":
        kwargs["clerk_session"] = f"clerk-archive:{SESSION}/{'1' * 64}"
    elif invalid == "external":
        kwargs["clerk_session"] = "https://example.test/private-transcript"
    elif invalid == "metadata":
        kwargs["replacement"] = raw.replace(b"title:", b"description: Comment\ntitle:")
    elif invalid == "no-request":
        kwargs["request_id"] = None
    elif invalid == "delete":
        kwargs["replacement"] = None
    else:
        marker = bundle / writer.MARKER
        marker.write_bytes(b"synthetic adopted marker")
        kwargs["successor"] = marker.read_bytes()
    before = snapshot(bundle)
    with pytest.raises(Refused):
        concept.change(bundle, created["id"], created["revision"], ACTOR, **kwargs)
    assert snapshot(bundle) == before and not (bundle / writer.STATE / writer.PENDING).exists()


@pytest.mark.parametrize("drift", ["symlink", "hardlink", "mode"])
def test_refuses_untrusted_archive_member(bundle, archive, tmp_path, drift):
    ref = clerk_archive.store(bundle, SESSION, TEXT)["reference"]
    member = archive / clerk_archive.reference(ref).filename
    if drift == "symlink":
        member.unlink()
        outside = tmp_path / "outside"
        outside.write_bytes(TEXT)
        member.symlink_to(outside)
    elif drift == "hardlink":
        os.link(member, archive / "other.md")
    else:
        member.chmod(0o644)
    with pytest.raises(Refused):
        clerk_archive.read(bundle, ref)
    with pytest.raises(Refused):
        clerk_archive.store(bundle, SESSION, TEXT)


def test_archive_must_be_private_and_cannot_be_inside_a_bundle(bundle, archive):
    archive.chmod(0o755)
    with pytest.raises(Refused, match="owned directories"):
        clerk_archive.store(bundle, SESSION, TEXT)
    archive.chmod(0o700)
    with pytest.raises(Refused, match="outside the selected bundle"):
        clerk_archive.store(archive.parent, SESSION, TEXT)
    assert not list(archive.iterdir())


def test_partial_archive_stage_is_left_for_inspection(bundle, archive):
    ref = clerk_archive.Snapshot(SESSION, writer.digest(TEXT))
    stage = archive / (".pending-" + ref.filename)
    stage.write_bytes(TEXT[:10])
    stage.chmod(0o600)
    with pytest.raises(Refused, match="retained digest"):
        clerk_archive.store(bundle, SESSION, TEXT)
    assert stage.read_bytes() == TEXT[:10] and not (archive / ref.filename).exists()
