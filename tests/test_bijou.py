import importlib.util
import json
from pathlib import Path
import uuid

import pytest

from innersanctum import bijou, cli, writer
from innersanctum.schema import Refused, document


def adapter(name):
    path = Path(__file__).resolve().parents[1] / "experiments/barrys-bijou/adapter" / f"{name}.py"
    spec = importlib.util.spec_from_file_location("bijou_" + name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def root(tmp_path):
    return adapter("fixture").create(tmp_path.resolve() / "screening-room")


def canonical(root):
    return {path: f.read_bytes() for path, f in writer.visible_files(root)}


def move(snap, film, **gap):
    return dict(library=snap["library"], revision=snap["revision"], requestID=uuid.uuid4().hex, film=film, gap=gap)


def test_catalog_and_placement_round_trip(root, tmp_path, capsys):
    assert cli.main(["bijou", "catalog", "--bundle", str(root)]) == 0
    s = json.loads(capsys.readouterr().out)
    assert s["order"] == s["issues"] == []
    assert len(s["films"]) == 6
    assert sum(f["watched"] is None for f in s["films"]) == 1
    assert sum(f["year"] is None for f in s["films"]) == 1
    assert sum(f["posterKey"] is not None for f in s["films"]) == 5
    a, b, c = [f["ref"] for f in s["films"][:3]]
    before = canonical(root)
    req = move(s, a)
    order = tmp_path / "place.json"
    order.write_text(json.dumps(req))
    args = ["bijou", "place", "--bundle", str(root), "--actor", "test:fixture", "--from", str(order)]
    assert cli.main(args) == 0
    receipt = json.loads(capsys.readouterr().out)
    after = canonical(root)
    path = bijou.binding(root)["path"]
    assert {p for p in after if after[p] != before[p]} == {path, a["path"], "log.md"}
    assert after[a["path"]] == before[a["path"]].replace(b"---\n", b"---\nranked: true\n", 1)
    assert after["log.md"].count(b"**Placement**") == 1
    assert cli.main(args) == 0 and json.loads(capsys.readouterr().out) == receipt
    assert canonical(root) == after
    for film, gap in ((b, {"above": a}), (c, {"above": a, "below": b})):
        bijou.place(root, move(bijou.catalog(root), film, **gap), "test:fixture")
    latest = bijou.catalog(root)
    assert latest["order"] == [a, c, b]
    before = canonical(root)
    bijou.place(root, move(latest, a, above=b), "test:fixture")
    after = canonical(root)
    assert {p for p in after if after[p] != before[p]} == {path, "log.md"}
    assert bijou.catalog(root)["order"] == [c, b, a] and not bijou.catalog(root)["issues"]
    assert bijou.place(root, req, "test:fixture") == receipt  # Historical receipt, not a fourth placement.
    assert canonical(root) == after


def test_stale_or_changed_gap_and_identity_keep_all_work(root):
    s = bijou.catalog(root)
    a, b = [f["ref"] for f in s["films"][:2]]
    old = move(s, b)
    bijou.place(root, move(s, a), "test:fixture")
    s = bijou.catalog(root)
    before = canonical(root)
    for req in (old, move(s, b), move(s, b, above={**a, "personalID": b["personalID"]}),
                move(s, {**b, "personalID": a["personalID"]}, above=a)):
        with pytest.raises(bijou.Conflict):
            bijou.place(root, req, "test:fixture")
    assert canonical(root) == before
    (root / a["path"]).unlink()
    problem = bijou.catalog(root)
    assert problem["issues"] and problem["order"] == [a] and a["path"] in problem["labels"]
    with pytest.raises(bijou.Conflict):
        bijou.place(root, move(problem, b, above=a), "test:fixture")


def test_interrupted_write_is_recoverable_but_never_rebound(root, monkeypatch):
    s = bijou.catalog(root)
    a = s["films"][0]["ref"]
    req = move(s, a)
    original = writer.install

    def interrupt(state, target, data, **kwargs):
        if target == root / a["path"]:
            raise OSError("simulated interruption")
        original(state, target, data, **kwargs)

    with monkeypatch.context() as patch:
        patch.setattr(writer, "install", interrupt)
        with pytest.raises(OSError, match="simulated"):
            bijou.place(root, req, "test:fixture")
    with pytest.raises(Refused, match="pending"):
        bijou.catalog(root)
    report = writer.recover(root)
    assert bijou.place(root, req, "test:fixture") == report
    assert (root / "log.md").read_bytes().count(b"**Placement**") == 1
    assert document((root / a["path"]).read_text())[0]["ranked"] is True
    (root / writer.MARKER).write_text("managed")
    with pytest.raises(Refused, match="managed"):
        bijou.catalog(root)


def test_false_flag_preserves_comments_and_a_changed_ranked_identity_needs_review(root):
    initial = bijou.catalog(root)
    film = initial["films"][0]["ref"]
    file = root / film["path"]
    old = file.read_bytes().replace(b"---\n", b"---\nranked: false  # keep this comment\n", 1)
    file.write_bytes(old)
    bijou.place(root, move(initial, film), "test:fixture")
    assert file.read_bytes() == old.replace(b"ranked: false", b"ranked: true")
    lines = file.read_bytes().splitlines(keepends=True)
    file.write_bytes(b"".join(line for line in lines if not line.startswith(b"id: ")))
    result = bijou.catalog(root)
    assert result["issues"] and len(result["order"]) == 1


def test_home_pairing_expires_is_single_use_and_revocable(root):
    import base64
    import sqlite3

    home = adapter("home").Home(root)
    code = json.loads(base64.urlsafe_b64decode(home.invitation("https://127.0.0.1:8765")))
    assert home.enroll("wrong") is None
    device = home.enroll(code["invitation"])
    assert home.authenticated(device["token"]) and not home.authenticated("wrong")
    assert home.enroll(code["invitation"]) is None
    code = json.loads(base64.urlsafe_b64decode(home.invitation("https://127.0.0.1:8765")))
    with sqlite3.connect(home.db) as con:
        con.execute("UPDATE invites SET expires=0")
        con.execute("DELETE FROM devices WHERE id=?", (device["device"],))
    assert home.enroll(code["invitation"]) is None and not home.authenticated(device["token"])
