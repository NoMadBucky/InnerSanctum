import json

import pytest

from innersanctum import bijou, cli, handover, writer
from innersanctum.schema import Refused
from test_bijou import adapter, move
from test_handover import bundle, put, selection, transfer  # noqa: F401


def test_personal_import_recovery_and_ongoing_placements(selection, tmp_path, monkeypatch, capsys):
    checkout, root, _, pin = selection
    transfer(selection)
    (root / "Documents").mkdir(mode=0o700)
    put(root / bijou.PARENT, b"# Documents\n\n## Directory Listing\n")
    put(root / bijou.MOVIES / "index.md", adapter("fixture").VIDEO_SCHEMA.encode())
    for i in range(3):
        key = 1234567 + i
        put(root / bijou.MOVIES / f"{key}.md", (
            f"---\nid: bho:{key}\ntype: Video\ntitle: Film {i}\nvideo_type: Movie\nvideo_status: watched\n---\n\nNotes.\n").encode())
    export = "# Barry’s Bijou\n\n## Ranking\n\n1. [Film 1](/Resources/videos/1234568.md)\n2. [Film 0](/Resources/videos/1234567.md)\n"
    file = tmp_path / "export.md"
    file.write_text(export)
    target = ["--live-checkout", str(checkout), "--expect-adoption", pin]
    cmd = ["bijou", "import", *target, "--from", str(file), "--actor", "human:test"]
    assert cli.main(cmd[:cmd.index("--expect-adoption")] + cmd[cmd.index("--from"):]) == 2
    assert not (root / bijou.RANKINGS).exists()
    normal_install = writer.install

    def interrupt(state, path, raw, **opts):
        if path == root / "log.md":
            raise OSError("interrupted")
        normal_install(state, path, raw, **opts)

    with monkeypatch.context() as patch:
        patch.setattr(writer, "install", interrupt)
        assert cli.main(cmd) == 2
    assert cli.main(["concept", "recover", *target]) == 0
    capsys.readouterr()
    assert cli.main(cmd) == 0
    assert json.loads(capsys.readouterr().out)["count"] == 2
    assert (root / "log.md").read_text().count("**Ranking import**") == 1
    with handover.live_checkout(checkout) as (_, successor):
        s = bijou.catalog(root, successor)
        assert s["origin"] == "personal" and len(s["order"]) == 2 and not s["issues"]
        a, b = s["order"]
        before = (root / a["path"]).read_bytes()
        cmd = move(s, a, above=b)
        with monkeypatch.context() as patch:
            patch.setattr(writer, "install", interrupt)
            with pytest.raises(OSError):
                bijou.place(root, cmd, "human:test", successor)
        receipt = writer.recover(root, successor=successor)
        assert bijou.place(root, cmd, "human:test", successor) == receipt
        assert (root / a["path"]).read_bytes() == before
        s = bijou.catalog(root, successor)
        assert s["order"] == [b, a]
        c = next(f["ref"] for f in s["films"] if f["ref"] not in s["order"])
        bijou.place(root, move(s, c, below=b), "human:test", successor)
        assert bijou.catalog(root, successor)["order"] == [c, b, a]
        with pytest.raises(Refused):
            bijou.place(root, cmd, "human:test")
