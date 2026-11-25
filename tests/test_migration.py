import json
import shutil

import pytest

from innersanctum import cli, migration, writer
from innersanctum.schema import Refused
from test_handover import put, selection, transfer  # noqa: F401


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
    (root / "log.md").write_text("# History\n\n## 2000-01-01\n\n* Existing entry.\n")
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


REQUEST = "test-video-status-migration"
ACTOR = "test:synthetic"


def test_rehearsal_at_full_scale_and_durable_replay(bundle, capsys):
    expected = {record(bundle, n, "status: watched\n") for n in range(1000001, 1000223)}
    record(bundle, 1000223, "video_status: watchlist\n")
    record(bundle, 1000224, "status: stable\n")
    before = snapshot(bundle)
    preview = migration.preview_video_status(bundle)
    cmd = ["migration", "video-status-rehearse", "--bundle", str(bundle), "--expect-digest",
           preview["digest"], "--actor", ACTOR, "--request-id", REQUEST]
    assert cli.main(cmd) == 0
    first = json.loads(capsys.readouterr().out)
    assert first["renames"] == 222 and first["request_id"] == REQUEST
    after = snapshot(bundle)
    changed = {path.as_posix() for path in after if after[path] != before[path]}
    assert changed == expected | {migration.VIDEO_INDEX, "log.md"}
    for report in preview["records"]:
        assert writer.digest((bundle / report["path"]).read_bytes()) == report["after"]
    assert writer.digest((bundle / migration.VIDEO_INDEX).read_bytes()) == preview["declaration"]["after"]
    assert (bundle / "log.md").read_text().count("**Video status migration**") == 1
    assert not (bundle / writer.STATE / writer.PENDING).exists()
    assert cli.main(cmd) == 0
    assert json.loads(capsys.readouterr().out) == first
    assert snapshot(bundle) == after


def test_stale_preview_refused_if_audit_changes(bundle):
    record(bundle, 1234567, "status: watched\n")
    preview = migration.preview_video_status(bundle)
    with (bundle / "log.md").open("a") as stream:
        stream.write("* An intervening event.\n")
    before = snapshot(bundle)
    with pytest.raises(Refused, match="preview changed"):
        migration.apply_video_status(bundle, preview["digest"], ACTOR, REQUEST)
    assert snapshot(bundle) == before and not (bundle / writer.STATE / writer.PENDING).exists()


def test_rehearsal_recovers_original_plan_after_interruption(bundle, monkeypatch):
    changed = record(bundle, 1234567, "status: watched\n")
    another = record(bundle, 2345678, "status: watchlist\n")
    preview = migration.preview_video_status(bundle)
    install = writer.install

    def interrupted(state, target, data, **kwargs):
        if target == bundle / another:
            raise OSError("simulated interruption")
        return install(state, target, data, **kwargs)

    with monkeypatch.context() as patch:
        patch.setattr(writer, "install", interrupted)
        with pytest.raises(OSError, match="simulated"):
            migration.apply_video_status(bundle, preview["digest"], ACTOR, REQUEST)
    assert (bundle / writer.STATE / writer.PENDING).exists()
    assert "video_status: watched" in (bundle / changed).read_text()
    assert "video_status:" not in (bundle / migration.VIDEO_INDEX).read_text()
    with pytest.raises(Refused, match="pending"):
        migration.preview_video_status(bundle)
    assert writer.recover(bundle)["renames"] == 2
    assert "video_status: watchlist" in (bundle / another).read_text()
    assert (bundle / "log.md").read_text().count("**Video status migration**") == 1
    assert not (bundle / writer.STATE / writer.PENDING).exists()


def test_rehearsal_apply_refuses_managed_bundle(bundle):
    (bundle / writer.MARKER).write_text("managed")
    with pytest.raises(Refused, match="managed"):
        migration.apply_video_status(bundle, "0" * 64, ACTOR, REQUEST)
    assert not (bundle / writer.STATE).exists()


def test_recovery_refuses_drift_without_changing_other_targets(bundle, monkeypatch):
    first = record(bundle, 1234567, "status: watched\n")
    second = record(bundle, 2345678, "status: watchlist\n")
    preview = migration.preview_video_status(bundle)
    publish = writer.publish

    def interrupt(*args, **kwargs):
        raise OSError("simulated interruption after freeze")

    with monkeypatch.context() as patch:
        patch.setattr(writer, "publish", interrupt)
        with pytest.raises(OSError, match="simulated"):
            migration.apply_video_status(bundle, preview["digest"], ACTOR, REQUEST)
    with (bundle / second).open("a") as stream:
        stream.write("\nUnexpected intervening content.\n")
    before = snapshot(bundle)
    assert writer.publish is publish
    with pytest.raises(Refused, match="target changed"):
        writer.recover(bundle)
    assert "status: watched" in (bundle / first).read_text()
    assert snapshot(bundle) == before and (bundle / writer.STATE / writer.PENDING).is_file()


@pytest.fixture
def stopped_selection(selection, tmp_path):
    checkout, root, _, adoption = selection
    transfer(selection)
    a = record(root, 1234567, "status: watched\n")
    b = record(root, 2345678, "status: watchlist\n")
    for path in (a, b):
        (root / path).chmod(0o600)
    successor = (root / writer.MARKER).read_bytes()
    with writer.locked(root, successor):
        pass
    private = tmp_path / "stopped"
    private.mkdir(mode=0o700)
    backup = private / "canonical"
    shutil.copytree(root, backup)
    return checkout, root, backup, adoption, (a, b)


def live_args(stopped_selection, capsys):
    checkout, _, backup, adoption, _ = stopped_selection
    target = ["--live-checkout", str(checkout)]
    assert cli.main(["migration", "video-status-preview", *target]) == 0
    preview = json.loads(capsys.readouterr().out)
    common = [*target, "--canonical-checkpoint", str(backup), "--expect-adoption", adoption]
    assert cli.main(["migration", "video-status-checkpoint", *common]) == 0
    checkpoint = json.loads(capsys.readouterr().out)
    assert checkpoint["status"] == "verified_canonical_copy"
    return [*common, "--checkpoint-sha256", checkpoint["checkpoint_sha256"], "--expect-digest",
            preview["digest"], "--actor", ACTOR, "--request-id", REQUEST, "--writers-stopped"]


def test_adopted_migration_requires_exact_checkpoint_and_original_cli_request(stopped_selection, capsys):
    checkout, root, backup, _, paths = stopped_selection
    args = live_args(stopped_selection, capsys)
    command = ["migration", "video-status-apply", *args]
    before = snapshot(root)
    with pytest.raises(SystemExit):
        cli.main(command[:-1])
    capsys.readouterr()
    wrong = command[:]
    wrong[wrong.index("--checkpoint-sha256") + 1] = "0" * 64
    assert cli.main(wrong) == 2
    assert "reviewed digest" in capsys.readouterr().err
    put(root / "unexpected.txt", b"an unrelated change")
    assert cli.main(command) == 2
    assert "inventory changed" in capsys.readouterr().err
    (root / "unexpected.txt").unlink()
    assert snapshot(root) == before == snapshot(backup)
    assert cli.main(command) == 0
    result = json.loads(capsys.readouterr().out)
    assert result["renames"] == 2
    after = snapshot(root)
    assert {p.as_posix() for p in before if before[p] != after[p]} == {*paths, migration.VIDEO_INDEX, "log.md"}
    assert snapshot(backup) == before
    assert (checkout / "SourceFiles/original.bin").read_bytes() == b"synthetic attachment"
    assert cli.main(command) == 0 and json.loads(capsys.readouterr().out) == result


@pytest.mark.parametrize("cut", ["record", "receipt"])
def test_adopted_migration_only_recovers_with_guarded_command(stopped_selection, capsys, monkeypatch, cut):
    checkout, root, backup, _, paths = stopped_selection
    args = live_args(stopped_selection, capsys)
    install = writer.install
    target = root / paths[0] if cut == "record" else writer.receipt_path(root / writer.STATE, REQUEST)

    def interrupt(state, path, data, **kwargs):
        install(state, path, data, **kwargs)
        if target == path:
            raise OSError("simulated interruption")

    with monkeypatch.context() as patch:
        patch.setattr(writer, "install", interrupt)
        assert cli.main(["migration", "video-status-apply", *args]) == 2
    capsys.readouterr()
    frozen = snapshot(root)
    assert cli.main(["concept", "recover", "--live-checkout", str(checkout)]) == 2
    assert "stopped-checkpoint" in capsys.readouterr().err
    wrong = args[:]
    wrong[wrong.index("--request-id") + 1] = "test-different-migration"
    assert cli.main(["migration", "video-status-recover", *wrong]) == 2
    assert "original Video migration request" in capsys.readouterr().err
    assert snapshot(root) == frozen
    unexpected = root / "unexpected.txt"
    put(unexpected, b"not part of the frozen migration")
    assert cli.main(["migration", "video-status-recover", *args]) == 2
    assert "inventory changed" in capsys.readouterr().err
    assert snapshot(root) == frozen and (root / writer.STATE / writer.PENDING).exists()
    unexpected.unlink()
    assert cli.main(["migration", "video-status-recover", *args]) == 0
    assert json.loads(capsys.readouterr().out)["renames"] == 2
    assert not (root / writer.STATE / writer.PENDING).exists()
    assert (root / "log.md").read_text().count("**Video status migration**") == 1
    assert (backup / "log.md").read_text().count("**Video status migration**") == 0
