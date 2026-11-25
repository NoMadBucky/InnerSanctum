import json
import shutil

import pytest

from innersanctum import cli, timestamp_cleanup, writer
from innersanctum.schema import Refused, document, same, split_document, yaml_reader
from test_create import bundle  # noqa: F401
from test_handover import put, selection, transfer  # noqa: F401


def test_formats_provenance_without_changing_meaning_or_body():
    text = (
        '---\n'
        'type: Note\n'
        'title: Café\n'
        'generated: {by: "human:author", at: 2026-01-02 23:30:00-06:00} # retain\n'
        'verified:\n'
        '  - by: "human:reviewer"\n'
        '    at: 2026-01-03 08:00:00+01:00\n'
        'sources:\n'
        '  - resource: https://example.test/\n'
        '    last_modified: unknown\n'
        '---\n'
        '\n'
        'Keep 2026-01-02 23:30:00-06:00 in the body.\n'
    ).replace("\n", "\r\n")
    after, counts = timestamp_cleanup.plan_record(text)
    expected = text.replace("at: 2026-01-02 ", "at: 2026-01-02T").replace("at: 2026-01-03 ", "at: 2026-01-03T")
    assert after == expected
    assert counts == {"provenance_timestamps": 2}
    assert same(document(text)[0], document(after)[0])
    assert timestamp_cleanup.plan_record(after) == (after, {})


def test_removes_only_explicit_timestamp_tags_and_preserves_native_types():
    text = ('---\n'
            'type: Task\n'
            'created: !!timestamp "2026-01-02 07:00:00-06:00" # retain\n'
            'due: !!timestamp "2026-01-03"\n'
            'title: "2026-01-02 07:00:00-06:00"\n'
            '---\n'
            'Body unchanged.\n')
    fm, _, _ = split_document(text)
    before = yaml_reader(fm, allow_opaque_tags=True).load(fm)
    after, counts = timestamp_cleanup.plan_record(text)
    assert counts == {"explicit_tags": 2}
    assert same(before, document(after)[0])
    assert after == text.replace('!!timestamp "2026-01-02 07:00:00-06:00"', '2026-01-02T07:00:00-06:00'
                                  ).replace('!!timestamp "2026-01-03"', '2026-01-03')


def test_preview_reports_revisions_and_refuses_unrecognized_timestamps(tmp_path, capsys):
    root = tmp_path.resolve() / "bundle"
    root.mkdir()
    valid = root / "known.md"
    valid.write_text("---\ntype: Task\ndue: !!timestamp '2026-01-02'\n---\n")
    malformed = root / "unknown.md"
    malformed.write_text("---\ntype: Task\ncreated: !!timestamp '2026-01-02T07:00:00'\n---\n")
    (root / "log.md").write_text("# History\n")
    observed = {p: p.read_bytes() for p in (valid, malformed)}
    assert cli.main(["migration", "timestamp-preview", "--bundle", str(root)]) == 0
    report = json.loads(capsys.readouterr().out)
    assert report["status"] == "blocked" and report["explicit_tags"] == 1
    assert report["records"] == [{"path": "known.md", "before": writer.digest(observed[valid]),
                                  "after": writer.digest(b"---\ntype: Task\ndue: 2026-01-02\n---\n"),
                                  "changes": {"explicit_tags": 1}}]
    assert [row["path"] for row in report["blockers"]] == ["unknown.md"]
    assert not (root / writer.STATE).exists()
    assert all(p.read_bytes() == raw for p, raw in observed.items())


@pytest.fixture
def timestamp_bundle(tmp_path):
    root = tmp_path.resolve() / "bundle"
    root.mkdir()
    (root / "index.md").write_text('---\nokf_version: "0.2"\n---\n# Fixture\n')
    (root / "log.md").write_text("# History\n\n## 2000-01-01\n\n* Existing entry.\n")
    return root


ACTOR = "test:synthetic"
REQUEST = "timestamp-rehearsal-0001"
NOTE = "---\ntype: Note\ngenerated: {by: 'human:author', at: 2026-01-02 01:00:00-06:00}\n"
TASK = "---\ntype: Task\ndue: !!timestamp '2026-01-03'\n"


def test_full_scale_cli_rehearsal_and_replay(timestamp_bundle, capsys):
    root = timestamp_bundle
    for i in range(71):
        extra = "verified: {by: 'human:reviewer', at: 2026-01-03 01:00:00-06:00}\n" if i == 0 else ""
        (root / f"note-{i}.md").write_text(NOTE + extra + "---\n\nKeep the original body.\n")
    for i in range(4):
        extra = "created: !!timestamp '2026-01-02 01:00:00-06:00'\n" if i < 2 else ""
        (root / f"task-{i}.md").write_text(TASK + extra + "---\n")
    before = {p.name: p.read_bytes() for p in root.glob("*.md")}
    plan = timestamp_cleanup.preview(root)
    assert (len(plan["records"]), plan["provenance_timestamps"], plan["explicit_tags"]) == (75, 72, 6)
    cmd = ["migration", "timestamp-rehearse", "--bundle", str(root), "--expect-digest", plan["digest"],
           "--actor", ACTOR, "--request-id", REQUEST]
    assert cli.main(cmd) == 0
    result = json.loads(capsys.readouterr().out)
    assert result["records"] == 75 and result["request_id"] == REQUEST
    after = {p.name: p.read_bytes() for p in root.glob("*.md")}
    assert set(before) == set(after)
    assert {p for p in before if before[p] != after[p]} == {e["path"] for e in plan["records"]} | {"log.md"}
    assert all(writer.digest(after[e["path"]]) == e["after"] for e in plan["records"])
    assert after["log.md"].count(b"**Timestamp formatting**") == 1
    assert timestamp_cleanup.preview(root)["records"] == []
    assert cli.main(cmd) == 0 and json.loads(capsys.readouterr().out) == result
    assert {p.name: p.read_bytes() for p in root.glob("*.md")} == after


def test_recovery_replays_original_and_refuses_drift(timestamp_bundle, monkeypatch):
    root = timestamp_bundle
    a, b = root / "a.md", root / "b.md"
    a.write_text(NOTE + "---\n")
    b.write_text(TASK + "---\n")
    approved = timestamp_cleanup.preview(root)
    install = writer.install

    def interrupt(state, path, raw, **kwargs):
        if path == b:
            raise OSError("simulated interruption")
        return install(state, path, raw, **kwargs)

    with monkeypatch.context() as patch:
        patch.setattr(writer, "install", interrupt)
        with pytest.raises(OSError, match="simulated"):
            timestamp_cleanup.rehearse(root, approved["digest"], ACTOR, REQUEST)
    assert writer.digest(a.read_bytes()) == approved["records"][0]["after"]
    log = (root / "log.md").read_bytes()
    b.write_text(TASK + "---\nUnexpected text.\n")
    with pytest.raises(Refused, match="target changed"):
        writer.recover(root)
    assert (root / "log.md").read_bytes() == log
    b.write_text(TASK + "---\n")
    assert writer.recover(root)["records"] == 2
    assert not (root / writer.STATE / writer.PENDING).exists()
    assert (root / "log.md").read_bytes().count(b"**Timestamp formatting**") == 1


def test_rehearsal_refuses_stale_log_or_managed_bundle(timestamp_bundle):
    root = timestamp_bundle
    record = root / "a.md"
    record.write_text(NOTE + "---\n")
    approved = timestamp_cleanup.preview(root)
    with (root / "log.md").open("a") as log:
        log.write("* An intervening edit.\n")
    with pytest.raises(Refused, match="preview changed"):
        timestamp_cleanup.rehearse(root, approved["digest"], ACTOR, REQUEST)
    assert record.read_text() == NOTE + "---\n"
    (root / writer.MARKER).write_text("managed")
    with pytest.raises(Refused, match="managed"):
        timestamp_cleanup.rehearse(root, approved["digest"], ACTOR, REQUEST)


@pytest.fixture
def adopted_timestamps(selection, tmp_path):
    checkout, root, _, adoption = selection
    transfer(selection)
    put(root / "a.md", (NOTE + "---\nKeep this body.\n").encode())
    put(root / "b.md", (TASK + "---\nKeep this body too.\n").encode())
    successor = (root / writer.MARKER).read_bytes()
    with writer.locked(root, successor):
        pass
    directory = tmp_path / "stopped-timestamps"
    directory.mkdir(mode=0o700)
    backup = directory / "canonical"
    shutil.copytree(root, backup)
    return checkout, root, backup, adoption


def adopted_args(adopted_timestamps, capsys):
    checkout, _, backup, adoption = adopted_timestamps
    target = ["--live-checkout", str(checkout)]
    assert cli.main(["migration", "timestamp-preview", *target]) == 0
    preview = json.loads(capsys.readouterr().out)
    common = [*target, "--canonical-checkpoint", str(backup), "--expect-adoption", adoption]
    assert cli.main(["migration", "timestamp-checkpoint", *common]) == 0
    checkpoint = json.loads(capsys.readouterr().out)
    assert checkpoint["status"] == "verified_canonical_copy"
    return [*common, "--checkpoint-sha256", checkpoint["checkpoint_sha256"], "--expect-digest",
            preview["digest"], "--actor", ACTOR, "--request-id", REQUEST, "--writers-stopped"]


def test_adopted_timestamp_apply_pins_checkpoint_and_preview(adopted_timestamps, capsys):
    checkout, root, backup, _ = adopted_timestamps
    args = adopted_args(adopted_timestamps, capsys)
    command = ["migration", "timestamp-apply", *args]
    initial = {p.relative_to(root): p.read_bytes() for p in root.rglob("*.md")}
    with pytest.raises(SystemExit):
        cli.main(command[:-1])
    capsys.readouterr()
    for flag, message in (("--expect-adoption", "expected checkpoint receipt"),
                          ("--checkpoint-sha256", "reviewed digest"), ("--expect-digest", "preview changed")):
        wrong = command[:]
        wrong[wrong.index(flag) + 1] = "0" * 64
        assert cli.main(wrong) == 2
        assert message in capsys.readouterr().err
    put(root / "unexpected.txt", b"Unrelated file")
    assert cli.main(command) == 2
    assert "inventory changed" in capsys.readouterr().err
    (root / "unexpected.txt").unlink()
    assert {p.relative_to(root): p.read_bytes() for p in root.rglob("*.md")} == initial
    assert cli.main(command) == 0
    result = json.loads(capsys.readouterr().out)
    assert result["records"] == 2
    after = {p.relative_to(root): p.read_bytes() for p in root.rglob("*.md")}
    assert {p.as_posix() for p in initial if initial[p] != after[p]} == {"a.md", "b.md", "log.md"}
    assert all((backup / path).read_bytes() == raw for path, raw in initial.items())
    assert (checkout / "SourceFiles/original.bin").read_bytes() == b"synthetic attachment"
    assert cli.main(command) == 0 and json.loads(capsys.readouterr().out) == result


@pytest.mark.parametrize("cut", ["record", "receipt"])
def test_adopted_timestamp_recovery_refuses_drift_and_generic_command(adopted_timestamps, capsys, monkeypatch, cut):
    checkout, root, _, _ = adopted_timestamps
    args = adopted_args(adopted_timestamps, capsys)
    install = writer.install
    target = root / "a.md" if cut == "record" else writer.receipt_path(root / writer.STATE, REQUEST)

    def interrupt(state, path, data, **kwargs):
        install(state, path, data, **kwargs)
        if target == path:
            raise OSError("simulated interruption")

    with monkeypatch.context() as patch:
        patch.setattr(writer, "install", interrupt)
        assert cli.main(["migration", "timestamp-apply", *args]) == 2
    capsys.readouterr()
    assert cli.main(["concept", "recover", "--live-checkout", str(checkout)]) == 2
    assert "stopped-checkpoint timestamp recovery" in capsys.readouterr().err
    wrong = args[:]
    wrong[wrong.index("--request-id") + 1] = "timestamp-different-request"
    assert cli.main(["migration", "timestamp-recover", *wrong]) == 2
    assert "original timestamp cleanup request" in capsys.readouterr().err
    frozen = (root / writer.STATE / writer.PENDING).read_bytes()
    put(root / "unexpected.txt", b"Unrelated file")
    assert cli.main(["migration", "timestamp-recover", *args]) == 2
    assert "inventory changed" in capsys.readouterr().err
    assert (root / writer.STATE / writer.PENDING).read_bytes() == frozen
    (root / "unexpected.txt").unlink()
    assert cli.main(["migration", "timestamp-recover", *args]) == 0
    assert json.loads(capsys.readouterr().out)["records"] == 2
    assert not (root / writer.STATE / writer.PENDING).exists()
    assert (root / "log.md").read_text().count("**Timestamp formatting**") == 1
