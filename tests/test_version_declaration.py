import json
import shutil

import pytest

from innersanctum import cli, version_declaration, writer
from innersanctum.schema import Refused
from test_create import bundle  # noqa: F401
from test_handover import put, selection, transfer  # noqa: F401


REQUEST = "test-version-declaration"
ACTOR = "test:synthetic"


def test_declaration_preserves_index_body_and_existing_metadata():
    original = '# Index\n\n- [Item](item.md)\n'
    assert version_declaration.updated_index(original) == '---\nokf_version: "0.3"\n---\n\n' + original
    existing = '---\r\ntitle: "Fixture"\r\n---\r\n\r\n# Index\r\n'
    expected = existing.replace('title:', 'okf_version: "0.3"\r\ntitle:')
    assert version_declaration.updated_index(existing) == expected
    with pytest.raises(Refused, match="already declares"):
        version_declaration.updated_index(expected)


def test_rehearsal_replays_receipt_and_refuses_outstanding_timestamp_cleanup(bundle):
    (bundle / "index.md").write_text("# Fixture\n\n- [Resources](Resources/index.md)\n")
    original = (bundle / "index.md").read_text()
    (bundle / "fixture.md").write_text("---\ntype: Note\ngenerated: {at: 2026-01-02 01:00:00-06:00}\n---\n")
    plan = version_declaration.preview(bundle)
    with pytest.raises(Refused, match="outstanding timestamp"):
        version_declaration.rehearse(bundle, plan["digest"], ACTOR, REQUEST)
    assert (bundle / "index.md").read_text() == original
    (bundle / "fixture.md").unlink()
    result = version_declaration.rehearse(bundle, plan["digest"], ACTOR, REQUEST)
    assert result["status"] == "declared" and result["okf_version"] == "0.3"
    assert (bundle / "index.md").read_text() == version_declaration.updated_index(original)
    assert version_declaration.rehearse(bundle, plan["digest"], ACTOR, REQUEST) == result
    assert (bundle / "log.md").read_text().count("**OKF version declaration**") == 1


@pytest.fixture
def stopped_version(selection, tmp_path):
    checkout, root, _, adoption = selection
    transfer(selection)
    put(root / "index.md", b"# Fixture\n\n* [Resources](Resources/index.md)\n")
    with writer.locked(root, (root / writer.MARKER).read_bytes()):
        pass
    container = tmp_path / "version-stopped"
    container.mkdir(mode=0o700)
    backup = container / "canonical"
    shutil.copytree(root, backup)
    return checkout, root, backup, adoption


def live_args(stopped_version, capsys):
    checkout, _, backup, adoption = stopped_version
    target = ["--live-checkout", str(checkout)]
    assert cli.main(["migration", "version-preview", *target]) == 0
    preview = json.loads(capsys.readouterr().out)
    common = [*target, "--canonical-checkpoint", str(backup), "--expect-adoption", adoption]
    assert cli.main(["migration", "version-checkpoint", *common]) == 0
    evidence = json.loads(capsys.readouterr().out)
    return [*common, "--checkpoint-sha256", evidence["checkpoint_sha256"], "--expect-digest",
            preview["digest"], "--actor", ACTOR, "--request-id", REQUEST, "--writers-stopped"]


def test_adopted_version_apply_checks_checkpoint_and_changes_only_index_and_log(stopped_version, capsys):
    checkout, root, backup, _ = stopped_version
    args = live_args(stopped_version, capsys)
    command = ["migration", "version-apply", *args]
    with pytest.raises(SystemExit):
        cli.main(command[:-1])
    capsys.readouterr()
    unrelated = root / "unexpected.txt"
    put(unrelated, b"Unrelated drift")
    assert cli.main(command) == 2
    assert "inventory changed" in capsys.readouterr().err
    unrelated.unlink()
    assert cli.main(command) == 0
    result = json.loads(capsys.readouterr().out)
    assert result["okf_version"] == "0.3"
    files = {p.relative_to(root) for p in root.rglob("*.md") if p.read_bytes() != (backup / p.relative_to(root)).read_bytes()}
    assert {p.as_posix() for p in files} == {"index.md", "log.md"}
    assert (checkout / "SourceFiles/original.bin").read_bytes() == b"synthetic attachment"
    assert cli.main(command) == 0 and json.loads(capsys.readouterr().out) == result


def test_adopted_version_recovers_original_after_interruption(stopped_version, capsys, monkeypatch):
    checkout, root, _, _ = stopped_version
    args = live_args(stopped_version, capsys)
    real_install = writer.install

    def interrupt(state, path, data, **kwargs):
        real_install(state, path, data, **kwargs)
        if path == root / "index.md":
            raise OSError("simulated interruption")

    with monkeypatch.context() as patch:
        patch.setattr(writer, "install", interrupt)
        assert cli.main(["migration", "version-apply", *args]) == 2
    capsys.readouterr()
    assert cli.main(["concept", "recover", "--live-checkout", str(checkout)]) == 2
    assert "stopped-checkpoint version recovery" in capsys.readouterr().err
    assert cli.main(["migration", "version-recover", *args]) == 0
    assert json.loads(capsys.readouterr().out)["okf_version"] == "0.3"
    assert not (root / writer.STATE / writer.PENDING).exists()
    assert (root / "log.md").read_text().count("**OKF version declaration**") == 1
