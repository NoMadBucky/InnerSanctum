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


def test_create_watchlist_movie_retry_then_watch_with_same_identity(root):
    library = bijou.catalog(root)["library"]
    details = dict(id=123, title="Fixture premiere", release_date="2025-09-02", overview="A fictional synopsis.",
                   poster_path="/mock.jpg")
    before = canonical(root)
    def add():
        return bijou.add_watchlist(root, library, details, [], "human:tester")["film"]
    ref = add()
    after = canonical(root)
    assert set(after) - set(before) == {ref["path"]}
    assert {p for p in before if before[p] != after[p]} == {"Resources/videos/index.md", "log.md"}
    assert add() == ref and canonical(root) == after
    film = next(f for f in bijou.catalog(root, all_movies=True)["films"] if f["ref"] == ref)
    assert film["watchlist"] and not film["viewed"] and not film["inLibrary"] and film["year"] == "2025"
    assert film["tmdb"].endswith("/123") and film["posterKey"] and details["overview"] in film["body"]
    bijou.mark_watched(root, dict(library=library, film=ref, day="2025-10-10"), "human:tester")
    assert add() == ref
    assert any(f["ref"] == ref and f["watched"] == "2025-10-10" for f in bijou.catalog(root)["films"])


def test_possible_match_requires_explicit_choice(root):
    snap = bijou.catalog(root, all_movies=True)
    old = next(f for f in snap["films"] if not f["tmdb"])
    details = dict(id=456, title=old["title"], release_date=(old["year"] or "2025") + "-01-01")
    before = canonical(root)
    check = bijou.add_watchlist(root, snap["library"], details, [], "human:tester")
    assert [c["ref"] for c in check["matches"]] == [old["ref"]] and canonical(root) == before
    added = bijou.add_watchlist(root, snap["library"], details, [old["ref"]["path"]], "human:tester")
    assert added["film"] != old["ref"]


def test_watchlist_date_is_saved_without_ranking_or_duplicate_log(root):
    snap = bijou.catalog(root, all_movies=True)
    film = next(f for f in snap["films"] if f["watchlist"])
    request = dict(library=snap["library"], film=film["ref"], day="2024-02-29")
    before = canonical(root)
    with pytest.raises(Refused):
        bijou.mark_watched(root, {**request, "day": "2025-02-29"}, "human:tester")
    bijou.mark_watched(root, request, "human:tester")
    after = canonical(root)
    assert {p for p in before if before[p] != after[p]} == {film["ref"]["path"], "log.md"}
    saved = next(f for f in bijou.catalog(root)["films"] if f["ref"] == film["ref"])
    assert saved["watched"] == request["day"] and not saved["watchlist"]
    bijou.mark_watched(root, request, "human:tester")
    with pytest.raises(bijou.Conflict):
        bijou.mark_watched(root, {**request, "day": "2024-03-01"}, "human:tester")
    assert canonical(root) == after


def test_tmdb_search_encodes_titles_and_returns_only_movie_fields(monkeypatch):
    import io
    from types import SimpleNamespace
    from urllib.parse import parse_qs, urlsplit
    home = adapter("home")
    monkeypatch.setattr(home.subprocess, "run", lambda *a, **kw: SimpleNamespace(stdout=b"fixture-only\n"))
    def search(request, timeout):
        assert urlsplit(request.full_url).netloc == "api.themoviedb.org"
        assert parse_qs(urlsplit(request.full_url).query) == {"query": ["A & B"], "page": ["2"]}
        assert request.get_header("Authorization") == "Bearer fixture-only"
        return io.BytesIO(b'{"results":[{"id":22,"title":"A & B","release_date":null}],"total_pages":612}')
    monkeypatch.setattr(home.urllib.request, "build_opener", lambda *_: SimpleNamespace(open=search))
    assert home.tmdb_search({"query": " A & B ", "page": 2}) == {
        "results": [{"id": 22, "title": "A & B", "year": "", "overview": ""}], "pages": 500}


def test_artwork_redirects_check_every_hop():
    from urllib.request import Request

    redirects = adapter("home").ArtworkRedirects(["media.themoviedb.org", "image.tmdb.org"])
    original = Request("https://media.themoviedb.org/poster.jpg")
    final = "https://image.tmdb.org/poster.jpg"
    next_request = redirects.redirect_request(original, None, 301, "Moved", {}, final)
    assert next_request.full_url == final
    for disallowed in ("http://image.tmdb.org/poster.jpg", "https://other.example/poster.jpg",
                       "https://user@image.tmdb.org/poster.jpg", "https://image.tmdb.org:8000/poster.jpg"):
        assert redirects.redirect_request(next_request, None, 302, "Found", {}, disallowed) is None


def move(snap, film, **gap):
    return dict(library=snap["library"], revision=snap["revision"], requestID=uuid.uuid4().hex, film=film, gap=gap)


def test_documented_home_fixture_when_checkout_is_also_under_home(tmp_path, monkeypatch):
    fixture = adapter("fixture")
    home = tmp_path.resolve()
    checkout = home / "GitHub/InnerSanctum"
    (checkout / ".git").mkdir(parents=True)
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setattr(fixture, "CHECKOUT", checkout)
    room = fixture.create("~/BijouPractice")
    assert room == home / "BijouPractice" and len(bijou.catalog(room)["films"]) == 6
    before = canonical(room)
    with pytest.raises(Refused, match="already exists"):
        fixture.create(room)
    assert canonical(room) == before


def test_forbidden_new_fixture_leaves_no_directory(tmp_path):
    fixture = adapter("fixture")
    parent = tmp_path.resolve()
    repo = parent / "repo"
    (repo / ".git").mkdir(parents=True)
    linked = parent / "alias"
    linked.symlink_to(parent, target_is_directory=True)
    managed = parent / "managed"
    managed.mkdir()
    (managed / writer.MARKER).touch()
    for dest in (repo / "practice", linked / "practice", managed / "practice", parent / "SynologyDrive"):
        with pytest.raises(Refused):
            fixture.create(dest)
        assert not dest.exists()


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
    import hmac
    import sqlite3

    server = adapter("home")
    home = server.Home(root)
    code = home.invitation()
    assert len(code) == 7 and set(code) <= set(server.CODE_ALPHABET)
    options = home.pairing_options()
    assert set(options) == {"version", "salt"} and options["version"] == 2
    salt = options["salt"]
    pin = home.identity()
    claim, confirmation = server.pairing_keys(code, salt, pin)
    wrong_pin_claim, _ = server.pairing_keys(code, salt, "0" * 64)
    assert home.enroll(salt, wrong_pin_claim) is None
    assert home.enroll(salt, code) is None
    device = home.enroll(salt, claim)
    assert home.authenticated(device["token"]) and not home.authenticated("wrong")
    msg = "Bijou enrolled v2:{device}:{token}:{library}".format(**device).encode()
    assert device["proof"] == hmac.digest(confirmation, msg, "sha256").hex()
    assert home.enroll(salt, claim) is None
    code = home.invitation()
    salt = home.pairing_options()["salt"]
    claim, _ = server.pairing_keys(code, salt, pin)
    with sqlite3.connect(home.db) as con:
        con.execute("UPDATE pair_codes SET expires=0")
        con.execute("DELETE FROM devices WHERE id=?", (device["device"],))
    assert home.pairing_options() is None
    assert home.enroll(salt, claim) is None and not home.authenticated(device["token"])


def test_pair_attempt_budget_survives_restart_and_new_code_restores_pairing(root):
    server = adapter("home")
    home = server.Home(root)
    code = home.invitation()
    salt = home.pairing_options()["salt"]
    correct, _ = server.pairing_keys(code, salt, home.identity())
    for _ in range(server.MAX_GUESSES):
        assert server.Home(root).enroll(salt, "0" * 64) is None
    assert home.pairing_options() is None and home.enroll(salt, correct) is None
    new_code = home.invitation()
    new_salt = home.pairing_options()["salt"]
    assert new_salt != salt
    assert home.enroll(salt, correct) is None
    valid, _ = server.pairing_keys(new_code, new_salt, home.identity())
    assert home.enroll(new_salt, valid) is not None


def test_short_pairing_preserves_existing_device_tokens_and_single_use_under_contention(root):
    from concurrent.futures import ThreadPoolExecutor
    import sqlite3

    server = adapter("home")
    state = root / ".bijou-home"
    state.mkdir(mode=0o700)
    with sqlite3.connect(state / "devices.sqlite") as con:
        con.execute("CREATE TABLE devices (id TEXT PRIMARY KEY, token TEXT UNIQUE)")
        con.execute("CREATE TABLE invites (hash TEXT PRIMARY KEY, expires INTEGER)")
        con.execute("INSERT INTO devices VALUES (?,?)", ("already-paired", server.hashed("previous-token")))
    home = server.Home(root)
    assert home.authenticated("previous-token")
    code = home.invitation()
    salt = home.pairing_options()["salt"]
    claim, _ = server.pairing_keys(code, salt, home.identity())
    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(lambda _: home.enroll(salt, claim), range(2)))
    assert sum(x is not None for x in results) == 1
    assert home.authenticated("previous-token")
