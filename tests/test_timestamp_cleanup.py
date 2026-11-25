import json

from innersanctum import cli, timestamp_cleanup, writer
from innersanctum.schema import document, same, split_document, yaml_reader


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
