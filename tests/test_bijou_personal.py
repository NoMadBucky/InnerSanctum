import json
import io
import uuid
import wave

import pytest

from innersanctum import bijou, cli, handover, writer
from innersanctum.schema import Refused
from test_bijou import adapter, move
from test_handover import bundle, put, selection, transfer  # noqa: F401


def test_bound_personal_source_import_and_interrupted_schema(selection, monkeypatch):
    from innersanctum import reaction_filing as filing
    checkout, root, _, _ = selection
    transfer(selection)
    (root / "Documents").mkdir(mode=0o700)
    put(root / bijou.PARENT, b"# Documents\n\n## Directory Listing\n")
    put(root / bijou.MOVIES / "index.md", adapter("fixture").VIDEO_SCHEMA.encode())
    path = bijou.MOVIES + "/1234567.md"
    put(root / path, b"---\nid: bho:1234567\ntype: Video\ntitle: Example\nvideo_type: Movie\nvideo_status: watched\n---\n")
    source = checkout / "SourceFiles"
    old = {"legacy": {"path": "original.bin", "size": len(b"synthetic attachment"),
                      "sha256": writer.digest(b"synthetic attachment"), "storage": "local"}}
    baseline = writer.json_bytes({"version": 1, "sources": old})
    catalog = source / "catalog.json"
    put(catalog, baseline)
    with handover.live_checkout(checkout) as (_, successor):
        bijou.initialize(root, successor, f"# Bijou\n\n## Ranking\n\n1. [Example](/{path})\n", "human:test")
        with pytest.raises(Refused, match="baseline"):
            filing.prepare_personal(root, successor, "0" * 64)
        assert not (source / filing.PERSONAL_STATE).exists()
        install = writer.install
        def stop_at_parent(state, target, raw, **kwargs):
            if target == root / bijou.PARENT:
                raise OSError("simulated interruption")
            install(state, target, raw, **kwargs)
        with monkeypatch.context() as patch:
            patch.setattr(writer, "install", stop_at_parent)
            with pytest.raises(OSError):
                filing.prepare_personal(root, successor, writer.digest(baseline))
        writer.recover(root, successor=successor)
        pin = filing.prepare_personal(root, successor, writer.digest(baseline))
        assert catalog.read_bytes() == baseline
        stream = io.BytesIO()
        with wave.open(stream, "wb") as wav:
            wav.setparams((1, 2, 8000, 0, "NONE", "not compressed"))
            wav.writeframes(b"\x11\x05" * 8000)
        audio = stream.getvalue()
        meta = dict(library=bijou.library_key(root, successor), film=bijou.movie_ref(path, "bho:1234567"),
                    take=str(uuid.uuid4()), recordedAt="2026-11-26T00:00:00Z", sha256=writer.digest(audio))
        def send(token=pin, **overrides):
            return filing.file_personal(root, successor, token, {**meta, **overrides}, audio)
        with pytest.raises(Refused, match="pin"):
            send("1" * 64)
        with monkeypatch.context() as patch:
            def interrupt(*args, **kw):
                raise OSError("lost power after source write")
            patch.setattr(writer, "create", interrupt)
            with pytest.raises(OSError):
                send()
        with pytest.raises(Refused, match="awaits recovery"):
            send(take=str(uuid.uuid4()))
        receipt = send()
        assert send() == receipt
        registered = catalog.read_bytes()
        sources = json.loads(registered)["sources"]
        assert sources["legacy"] == old["legacy"] and len(sources) == 2
        assert (source / sources[f"Documents/reactions/{meta['take']}.wav"]["path"]).read_bytes() == audio
        assert (root / receipt["path"]).exists() and (root / "log.md").read_text().count(receipt["path"]) == 1
        put(catalog, baseline)
        with pytest.raises(Refused, match="Stale"):
            send()
        assert catalog.read_bytes() == baseline
        put(catalog, registered)
        source.rename(checkout / "old-source")
        source.mkdir(mode=0o700)
        import shutil
        shutil.copytree(checkout / "old-source", source, dirs_exist_ok=True)
        with pytest.raises(Refused, match="binding changed"):
            send()


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
