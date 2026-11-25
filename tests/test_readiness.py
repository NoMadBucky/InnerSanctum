import json
from pathlib import Path

import pytest

from innersanctum import cli, readiness, writer
from test_migration import bundle, record  # noqa: F401


ACTOR = "test:synthetic"
CATALOG_ASSET = "evidence/source file.bin"
VIDEO = "Resources/videos/1234567.md"
NOTE = "Documents/notes/example.md"


def put(root, path, text):
    target = root / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text)
    return target


def snapshot(root):
    return {path.relative_to(root).as_posix(): path.read_bytes() for path in root.rglob("*.md")}


def run_report(root, capsys, *, code=0):
    assert cli.main(["migration", "version-readiness", "--snapshot", str(root)]) == code
    return json.loads(capsys.readouterr().out)


@pytest.fixture
def candidate(bundle):  # noqa: F811
    put(bundle, "index.md", "---\ntitle: Synthetic fixture\nx-extension: true\n---\n\n"
        "# Contents\n\n* [Movies](Resources/videos/index.md)\n")
    record(bundle, 1234567, "status: watched\nvideo_type: movie\n")
    put(bundle, CATALOG_ASSET, "Synthetic bytes")
    put(bundle, NOTE, "---\ntype: Note\n"
        'generated: {by: "test:synthetic", at: 2026-01-02 01:00:00-06:00}\n'
        "sources: {resource: evidence/source%20file.bin?view=1#section}\n"
        "---\n\n[Movie](/Resources/videos/1234567.md) and [broken](missing.md).\n")
    return bundle


def test_readiness_rehearsal(candidate, capsys):
    before = snapshot(candidate)
    blocked = run_report(candidate, capsys, code=1)
    assert blocked["status"] == "blocked"
    assert blocked["declared_version"] is None
    assert {(f["group"], f["code"], f["path"]) for f in blocked["findings"]} == {
        ("migration", "legacy-video-state", VIDEO),
        ("migration", "legacy-video-declaration", "Resources/videos/index.md"),
        ("migration", "timestamp-cleanup-needed", NOTE),
        ("migration", "v02-path-fallback", NOTE),
    }
    assert blocked == run_report(candidate, capsys, code=1)
    assert before == snapshot(candidate)
    assert not (candidate / writer.STATE).exists()

    def migrate(family):
        command = ["migration", f"{family}-preview", "--bundle", str(candidate)]
        assert cli.main(command) == 0
        preview = json.loads(capsys.readouterr().out)
        command[1] = f"{family}-rehearse"
        assert cli.main([*command, "--expect-digest", preview["digest"], "--actor", ACTOR,
                         "--request-id", f"readiness-rehearse-{family}"]) == 0
        return json.loads(capsys.readouterr().out)

    assert migrate("timestamp")["records"] == 1
    assert migrate("video-status")["renames"] == 1
    note = candidate / NOTE
    note.write_text(note.read_text().replace("resource: evidence/", "resource: /evidence/"))
    ready = run_report(candidate, capsys)
    assert ready["status"] == "ready" and ready["declared_version"] is None and not ready["findings"]
    assert ready["inventory_sha256"] != blocked["inventory_sha256"]
    assert "reader-compatibility" in ready["unchecked"]
    assert migrate("version")["okf_version"] == "0.3"
    declared = run_report(candidate, capsys)
    assert declared["status"] == "ready" and declared["declared_version"] == "0.3"
    after = snapshot(candidate)
    assert {path for path in after if before.get(path) != after[path]} == {
        NOTE, VIDEO, "Resources/videos/index.md", "index.md", "log.md",
    }
    assert after[VIDEO] == before[VIDEO].replace(b"\nstatus:", b"\nvideo_status:")
    assert after[NOTE].split(b"\n---\n", 1)[1] == before[NOTE].split(b"\n---\n", 1)[1]
    for action in ("Video status migration", "Timestamp formatting", "OKF version declaration"):
        assert after["log.md"].count(f"**{action}**".encode()) == 1
    assert (candidate / CATALOG_ASSET).read_text() == "Synthetic bytes"
    assert not (candidate / writer.STATE / writer.PENDING).exists()
    assert len(list((candidate / writer.STATE).glob("receipt-*.json"))) == 3


def test_structural_and_inspection_findings_are_distinct(candidate, capsys):
    put(candidate, "index.md", '---\nokf_version: "0.2"\n---\n\n# Contents\n')
    put(candidate, "Documents/index.md", "---\nextra: true\n---\n\n# Notes\n")
    put(candidate, "Documents/log.md", "# History\n\n## 2026-02-30\n\n"
        "## 2026-02-20\n\n## 2026-02-21\n")
    put(candidate, "evidence/log.md", "---\nx: 1\n---\n")
    put(candidate, "plain.md", "# Not a concept\n")
    put(candidate, "metadata.md", "---\nnote: Some metadata without type\n---\n")
    put(candidate, "array.md", "---\n- not a mapping\n---\n")
    put(candidate, "broken.md", "---\ntype: Note\n")
    put(candidate, "opaque.md", "---\ntype: Note\ncustom: !unknown selector\n---\n")
    put(candidate, "duplicate.md", "---\ntype: Note\ntype: Video\n---\n")
    report = run_report(candidate, capsys, code=1)
    assert report["declared_version"] == "0.2"
    got = {(f["group"], f["code"], f["path"]) for f in report["findings"]}
    assert {
        ("migration", "existing-version-blocks-declaration", "index.md"),
        ("conformance", "index-without-listing", "index.md"),
        ("conformance", "reserved-frontmatter", "Documents/index.md"),
        ("conformance", "invalid-log-date", "Documents/log.md"),
        ("conformance", "log-not-newest-first", "Documents/log.md"),
        ("conformance", "reserved-frontmatter", "evidence/log.md"),
        ("conformance", "nonmapping-frontmatter", "array.md"),
        ("conformance", "unclosed-frontmatter", "broken.md"),
        ("inspection", "unsupported-yaml", "opaque.md"),
        ("conformance", "duplicate-yaml-key", "duplicate.md"),
    } <= got
    assert not {"plain.md", "metadata.md"} & {item["path"] for item in report["findings"]}
    assert "selector" not in json.dumps(report)


def test_only_fallback_dependent_path_fields_are_reported(candidate, capsys):
    put(candidate, "Documents/notes/local.bin", "asset")
    put(candidate, "asset.bin", "root asset")
    put(candidate, NOTE, "---\ntype: Note\nresource: local.bin\n"
        "computation: asset.bin\nsuperseded_by: /Resources/videos/1234567.md\n"
        "executor: {resource: 'okf://Personal/synthetic/asset.bin'}\n"
        "attester: {resource: '../../asset.bin'}\n"
        "sources:\n"
        "  - {resource: 'evidence/source%20file.bin'}\n"
        "  - {resource: 'https://example.test/asset.bin'}\n"
        "  - {resource: 'all queries in a workspace'}\n"
        "  - {resource: 'missing.md'}\n"
        "  - {resource: 'Evidence/source%20file.bin'}\n"
        "  - {resource: 'evidence%2Fsource%20file.bin'}\n"
        "---\n\n[Not a path field](asset.bin)\n")
    report = run_report(candidate, capsys, code=1)
    assert [(f["path"], f["field"]) for f in report["findings"] if f["code"] == "v02-path-fallback"] == [
        (NOTE, "computation"), (NOTE, "sources[0].resource"),
    ]


def test_external_snapshot_may_retain_marker_but_not_pending_work(candidate, capsys):
    marker = put(candidate, writer.MARKER, "Retained marker in a disposable snapshot")
    report = run_report(candidate, capsys, code=1)
    assert report["findings"] and marker.read_text() == "Retained marker in a disposable snapshot"
    assert not (candidate / writer.STATE).exists()
    put(candidate, f"{writer.STATE}/{writer.PENDING}", "unsettled")
    assert cli.main(["migration", "version-readiness", "--snapshot", str(candidate)]) == 2
    assert "pending" in capsys.readouterr().err
    assert cli.main(["migration", "version-preview", "--bundle", str(candidate)]) == 2
    assert "managed" in capsys.readouterr().err


def test_video_lifecycle_is_separate_and_attachment_contents_are_not_read(candidate, capsys, monkeypatch):
    record(candidate, 1234567, "status: deprecated\nvideo_status: watched\n")
    record(candidate, 2345678, "status: watched\nvideo_status: watchlist\n")
    record(candidate, 3456789, "video_status: deprecated\n")
    index = candidate / "Resources/videos/index.md"
    index.write_text(index.read_text().replace("    status:", "    video_status:"))
    put(candidate, ".hidden/skip.md", "invalid frontmatter is out of scope")
    read = writer.read_file
    observed = []

    def observe(path):
        observed.append(path.relative_to(candidate).as_posix())
        assert path.suffix == ".md"
        return read(path)

    monkeypatch.setattr(writer, "read_file", observe)
    report = run_report(candidate, capsys, code=1)
    assert [(f["path"], f["code"]) for f in report["findings"] if "video-" in f["code"]] == [
        ("Resources/videos/2345678.md", "conflicting-video-state"),
        ("Resources/videos/3456789.md", "invalid-video-state"),
    ]
    assert ".hidden/skip.md" not in observed


def test_refuses_repository_symlink_and_observed_drift(candidate, tmp_path, capsys, monkeypatch):
    checkout = Path(cli.__file__).resolve().parents[2]
    assert cli.main(["migration", "version-readiness", "--snapshot", str(checkout)]) == 2
    assert "outside repositories" in capsys.readouterr().err
    state = candidate / writer.STATE
    state.symlink_to(tmp_path)
    assert cli.main(["migration", "version-readiness", "--snapshot", str(candidate)]) == 2
    assert "physical directory" in capsys.readouterr().err
    state.unlink()

    scan = readiness.inventory
    asset = candidate / CATALOG_ASSET

    def drift(root):
        result = scan(root)
        if asset.read_text() == "Synthetic bytes":
            asset.write_text("Changed snapshot")
        return result

    monkeypatch.setattr(readiness, "inventory", drift)
    assert cli.main(["migration", "version-readiness", "--snapshot", str(candidate)]) == 2
    assert "Snapshot changed" in capsys.readouterr().err
