import json
from pathlib import Path

import pytest

from innersanctum import cli, journal, writer
from innersanctum.schema import Refused, document
from test_create import ACTOR, DRAFT, ROUTES, bundle, snapshot  # noqa: F401


SCHEMA = """# Journal index

```yaml
okf_schema:
  type: Journal
  directory: Documents/journal
  required: [id, type, title, generated]
  fields:
    id: {type: bho}
    type: {const: Journal}
    title: {type: string}
    generated:
      type: dict
      required: [at, by]
      fields:
        at: {type: date}
        by: {type: string}
```

## Directory Listing
"""
BASE = "Documents/journal"
FAMILY = f"{BASE}/index.md"
MONTH = f"{BASE}/2020-06"
MONTHLY = f"{MONTH}/index.md"
DAY = f"{MONTH}/2020-06-22.md"
STAMP = "2020-06-22T13:00:00-05:00"
TEXT = b"A **synthetic** entry.\nAn extra line.\n\nMore [text](https://example.com/).\n"
OLD = """---
id: bho:9876543
title: "Prior day title"
type: Journal
generated: {by: test:original, at: "2020-06-22T08:00:00-05:00"}
---

## Entries

* **Time:** 2020-06-22T15:00:00-05:00  
  **Author:** test:original  
  **Entry:** An evening entry.

* **Timestamp**: 2020-06-22T09:00:00-05:00  
  **Entry**: An early entry.

## References

Other material stays exact.
"""


@pytest.fixture
def ledgers(bundle):
    (bundle / BASE).mkdir(parents=True)
    (bundle / FAMILY).write_text(SCHEMA)
    return bundle


def existing(root, text):
    (root / MONTH).mkdir()
    (root / MONTHLY).write_text("# Journal month\n\n## Directory Listing\n\n* [Old label](2020-06-22.md)\n")
    (root / DAY).write_bytes(text.encode())


def test_cli_creates_month_and_day_and_preserves_body_privacy(ledgers, tmp_path, capsys):
    src = tmp_path / "draft"
    src.write_bytes(TEXT)
    before = snapshot(ledgers)
    assert cli.main(["journal", "add", "--bundle", str(ledgers), "--from", str(src),
                     "--actor", ACTOR, "--at", STAMP, "--subject", "Private subject"]) == 0
    captured = capsys.readouterr()
    result = json.loads(captured.out)
    assert result["status"] == "added" and result["created"] is True
    assert result["path"] == DAY and result["date"] == "2020-06-22" and result["directories"] == [MONTH]
    assert "Private subject" not in captured.out
    source = (ledgers / DAY).read_text()
    meta, body, _ = document(source)
    assert meta["type"] == "Journal" and meta["id"] == result["id"]
    assert meta["generated"]["by"] == ACTOR and result["revision"] == writer.digest(source.encode())
    assert f"* **Time:** {STAMP}" in body
    assert f"  **Author:** {ACTOR}" in body and "  **Category:** Personal" in body
    assert "  **Subject:** Private subject" in body and "  **Entry:** A **synthetic** entry. An extra line." in body
    assert "\n\n  More [text](https://example.com/)." in body
    assert "](2020-06-22.md)" in (ledgers / MONTHLY).read_text()
    assert "](2020-06/index.md)" in (ledgers / FAMILY).read_text()
    assert f"](/{DAY})" in (ledgers / FAMILY).read_text()
    log = (ledgers / "log.md").read_text()
    assert "**Journal entry**" in log and f"]({DAY})" in log
    assert "A **synthetic** entry." not in log and "Private subject" not in log
    assert {key for key, raw in snapshot(ledgers).items() if before.get(key) != raw} == set(result["files"])
    assert (ledgers / MONTH).stat().st_mode & 0o777 == 0o700
    assert (ledgers / DAY).stat().st_mode & 0o777 == 0o600


@pytest.mark.parametrize("at,prior,following", [
    ("2020-06-22T16:00:00-05:00", "## Entries", "An evening entry."),
    (STAMP, "An evening entry.", "An early entry."),
    ("2020-06-22T07:00:00-05:00", "An early entry.", "## References"),
])
def test_existing_day_preserves_crlf_content_and_indexes(ledgers, at, prior, following):
    crlf = OLD.replace("\n", "\r\n")
    existing(ledgers, crlf)
    before = snapshot(ledgers)
    result = journal.add(ledgers, TEXT, ACTOR, at=at)
    after = (ledgers / DAY).read_bytes().decode()
    assert result["id"] == "bho:9876543" and result["created"] is False
    assert result["files"] == [DAY, "log.md"]
    assert after.index(prior) < after.index("A **synthetic** entry.") < after.index(following)
    assert after.startswith(crlf[:crlf.index("## Entries")])
    assert all(line == "" or line in after for line in crlf.split("\r\n"))
    assert "\n" not in after.replace("\r\n", "")
    assert snapshot(ledgers)[MONTHLY] == before[MONTHLY] and snapshot(ledgers)[FAMILY] == before[FAMILY]


def test_reuses_existing_links_without_replacing_indexes(ledgers):
    (ledgers / MONTH).mkdir()
    (ledgers / MONTHLY).write_text(f"# Month\n\n## Directory Listing\n\n* [Present](/{DAY})\n")
    (ledgers / FAMILY).write_text(SCHEMA + f"\n* [Day]({DAY.removeprefix(BASE + '/')})\n"
                                  f"* [Month](/{MONTHLY})\n")
    before = snapshot(ledgers)
    result = journal.add(ledgers, TEXT, ACTOR, at=STAMP)
    assert result["files"] == [DAY, "log.md"]
    assert snapshot(ledgers)[MONTHLY] == before[MONTHLY] and snapshot(ledgers)[FAMILY] == before[FAMILY]


def test_adds_missing_day_to_existing_month(ledgers):
    (ledgers / MONTH).mkdir()
    (ledgers / MONTHLY).write_text("# Month\n\n## Directory Listing\n")
    (ledgers / FAMILY).write_text(SCHEMA + f"\n* [Month](/{MONTHLY})\n")
    result = journal.add(ledgers, TEXT, ACTOR, at=STAMP)
    assert result["files"] == [DAY, MONTHLY, FAMILY, "log.md"] and result["directories"] == []
    assert (ledgers / FAMILY).read_text().count(f"](/" + MONTHLY + ")") == 1
    assert f"](/{DAY})" in (ledgers / FAMILY).read_text()
    assert "](2020-06-22.md)" in (ledgers / MONTHLY).read_text()


def test_refuses_mixed_operations_until_existing_append_recovers(ledgers, monkeypatch, capsys):
    existing(ledgers, OLD)
    install = writer.install

    def interrupt(state, target, *args, **kwargs):
        install(state, target, *args, **kwargs)
        if target == ledgers / DAY:
            raise KeyboardInterrupt

    with monkeypatch.context() as patch:
        patch.setattr(writer, "install", interrupt)
        with pytest.raises(KeyboardInterrupt):
            journal.add(ledgers, TEXT, ACTOR, at=STAMP)
    with pytest.raises(Refused, match="pending"):
        journal.add(ledgers, TEXT, ACTOR, at=STAMP, dry_run=True)
    assert cli.main(["journal", "recover", "--bundle", str(ledgers)]) == 0
    result = json.loads(capsys.readouterr().out)
    assert result["status"] == "added" and result["created"] is False and result["id"] == "bho:9876543"
    assert (ledgers / DAY).read_text().count("A **synthetic** entry.") == 1
    assert (ledgers / "log.md").read_text().count(f"]({DAY})") == 1


def test_dry_run_creates_nothing(ledgers):
    before = snapshot(ledgers)
    result = journal.add(ledgers, TEXT, ACTOR, at=STAMP, dry_run=True)
    assert result["status"] == "planned" and result["directories"] == [MONTH]
    assert snapshot(ledgers) == before and not (ledgers / MONTH).exists() and not (ledgers / writer.STATE).exists()


@pytest.mark.parametrize("raw,options,error", [
    (b" \n", {}, "nonblank"),
    (b"## Fake heading", {}, "inline Markdown"),
    (b"**Time:** spoof", {}, "field markers"),
    (b"<script>spoof</script>", {}, "inline Markdown"),
    (TEXT, {"day": "2020-06-21"}, "fall on"),
    (TEXT, {"at": "2020-06-22T13:00:00+00:99"}, "UTC offset"),
    (TEXT, {"subject": "Subject\nSpoof"}, "single line"),
])
def test_invalid_inputs_do_not_write(ledgers, raw, options, error):
    before = snapshot(ledgers)
    with pytest.raises(Refused, match=error):
        journal.add(ledgers, raw, ACTOR, **{"at": STAMP, **options})
    assert snapshot(ledgers) == before and not (ledgers / writer.STATE / writer.PENDING).exists()


@pytest.mark.parametrize("text,error", [
    (OLD.replace("## Entries", "## Notes"), "exactly one"),
    (OLD.replace("## References", "## Journal Entries"), "exactly one"),
    (OLD.replace("09:00:00", "17:00:00"), "newest first"),
    (OLD.replace("type: Journal", "type: Video"), "not an identified Journal"),
])
def test_ambiguous_existing_file_is_not_rewritten(ledgers, text, error):
    existing(ledgers, text)
    before = snapshot(ledgers)
    with pytest.raises(Refused, match=error):
        journal.add(ledgers, TEXT, ACTOR, at=STAMP)
    assert snapshot(ledgers) == before


@pytest.mark.parametrize("stop", [writer.PENDING, "month-directory", DAY, MONTHLY, FAMILY, "log.md"])
def test_interrupt_rolls_forward_original_write(ledgers, monkeypatch, stop):
    install = writer.install
    mkdir = Path.mkdir

    def interrupted_install(state, target, *args, **kwargs):
        install(state, target, *args, **kwargs)
        if ((target.name == writer.PENDING and stop == writer.PENDING) or target == ledgers / stop):
            raise KeyboardInterrupt

    def interrupted_mkdir(path, *args, **kwargs):
        mkdir(path, *args, **kwargs)
        if path == ledgers / MONTH and stop == "month-directory":
            raise KeyboardInterrupt

    with monkeypatch.context() as patch:
        patch.setattr(writer, "install", interrupted_install)
        patch.setattr(Path, "mkdir", interrupted_mkdir)
        with pytest.raises(KeyboardInterrupt):
            journal.add(ledgers, TEXT, ACTOR, at=STAMP)
    assert (ledgers / writer.STATE / writer.PENDING).is_file()
    with pytest.raises(Refused, match="pending"):
        writer.create(ledgers, ROUTES, DRAFT.encode(), ACTOR)
    result = writer.recover(ledgers)
    assert result["status"] == "added" and result["path"] == DAY
    assert (ledgers / DAY).read_text().count("A **synthetic** entry.") == 1
    assert (ledgers / "log.md").read_text().count(f"]({DAY})") == 1
    assert not (ledgers / writer.STATE / writer.PENDING).exists()


def test_unknown_file_in_interrupted_new_month_refuses_recovery(ledgers, monkeypatch):
    install = writer.install

    def interrupt(state, target, *args, **kwargs):
        install(state, target, *args, **kwargs)
        if target == ledgers / DAY:
            raise KeyboardInterrupt

    with monkeypatch.context() as patch:
        patch.setattr(writer, "install", interrupt)
        with pytest.raises(KeyboardInterrupt):
            journal.add(ledgers, TEXT, ACTOR, at=STAMP)
    (ledgers / MONTH / "unrelated.md").write_text("Other bytes.")
    before = snapshot(ledgers)
    with pytest.raises(Refused, match="journal month changed"):
        writer.recover(ledgers)
    assert snapshot(ledgers) == before
    assert (ledgers / writer.STATE / writer.PENDING).exists()
