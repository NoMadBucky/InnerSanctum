"""Narrow, separately bound source catalog writer for Bijou's PCM recordings."""

from datetime import datetime, timezone
import fcntl
import io
import json
import os
from pathlib import Path
import re
import tempfile
import uuid
import wave

from . import bijou, handover, writer as w
from .schema import Refused, date_value, declarations, document

CHECKOUT = Path(__file__).resolve().parents[2]
LIMIT = 48 * 1024 * 1024
ROUTES = '[types."Film Reaction"]\nschema="Documents/reactions/index.md"\ndirectory="Documents/reactions"\n'
SCHEMA = """# Film Reactions

```yaml
okf_schema:
  type: Film Reaction
  directory: Documents/reactions
  required: [id, type, title, film_id, take_id, recorded_at, duration_ms, source_key, source_sha256]
  fields:
    id: {type: bho}
    type: {const: Film Reaction}
    title: {type: string}
    film_id: {type: bho}
    take_id: {type: string}
    recorded_at: {type: datetime}
    viewing_date: {type: date}
    duration_ms: {type: integer}
    source_key: {type: string}
    source_sha256: {type: string}
```

## Directory Listing
"""


def target(root, new=False):
    root = w.open_bundle(root, CHECKOUT)
    library = bijou.binding(root)["library"]
    store = w.external_root(root.parent / ("BijouSources-" + library), CHECKOUT, new=new)
    return root, library, store


def binding(root, library, store):
    return dict(library=library, bundle=w.bundle_identity(root), sources=w.bundle_identity(store))


def initialize(root):
    """Called only while constructing a new, explicitly opted-in fixture."""
    root, library, store = target(root, new=True)
    store.mkdir(mode=0o700)
    for sub in ("audio", ".requests"):
        (store / sub).mkdir(mode=0o700)
    atomic(store / "catalog.json", w.json_bytes({"version": 1, "sources": {}}))
    atomic(store / ".fixture-writer", w.json_bytes(binding(root, library, store)))
    w.sync_directory(store.parent)


def atomic(path, raw):
    with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as stage:
        try:
            stage.write(raw)
            stage.flush()
            os.fsync(stage.fileno())
            os.replace(stage.name, path)
            w.sync_directory(path.parent)
        finally:
            Path(stage.name).unlink(missing_ok=True)


def file_take(root, meta, audio):
    root, library, store = target(root)
    return _file(root, library, store, store / ".fixture-writer", w.json_bytes(binding(root, library, store)),
                 store / ".requests", meta, audio)


PERSONAL_STATE = ".innersanctum-sources"
DIR = "Documents/reactions"
INDEX = DIR + "/index.md"
SCHEMA_OP = "bijou-reaction-schema"


def schema_plan(review):
    actor = "process:bijou-reactions"
    return [w.Change(INDEX, None, SCHEMA),
            w.Change(bijou.PARENT, w.digest(review["parent"].encode()),
                     w.edit_index(review["parent"], "reactions/index.md", "Film Reactions")),
            w.Change("log.md", w.digest(review["audit"].encode()), w.edit_log(
                review["audit"], INDEX, "Film Reactions", actor, datetime.fromisoformat(review["at"]), action="Install schema"))]


def schema_request(root, successor):
    return w.write_request("bijou-reaction-schema-v1", SCHEMA_OP, bijou.library_key(root, successor), w.digest(SCHEMA.encode()))


def verify_schema(root, changes, request, review, successor):
    if (set(review) != {"parent", "audit", "at"} or request != schema_request(root, successor)
            or changes != schema_plan(review)):
        raise Refused("Invalid frozen reaction schema installation.")


def install_schema(root, successor):
    request = schema_request(root, successor)
    with w.locked(root, successor) as state:
        w.require_idle(root)
        if w.replay(root, state, request):
            if not bijou.source(root, INDEX).startswith(SCHEMA):
                raise Refused("Installed Film Reaction schema changed.")
            return
        indexes, _ = w.inventory(root, collect_ids=False)
        if (w.present(w.safe_target(root, DIR, missing=True))
                or any(kind == "Film Reaction" for index in indexes.values() for kind, _ in declarations(index))):
            raise Refused("A reaction directory or declaration already exists.")
        review = dict(parent=bijou.source(root, bijou.PARENT), audit=bijou.source(root, "log.md"),
                      at=datetime.now().astimezone().isoformat(timespec="seconds"))
        changes = schema_plan(review)
        w.freeze(root, state, changes, operation=SCHEMA_OP, request=request, bijou_review=review)
        w.publish(root, state, changes, operation=SCHEMA_OP, directory=DIR, request=request, successor=successor)


def source_target(root, successor):
    library = bijou.personal_config(root, successor)["library"]
    store = root.parent / "SourceFiles"
    if root.name != "OKF" or not handover.physical(store):
        raise Refused("Expected the physical sibling Personal source store.")
    handover.owned(store, directory=True)
    return library, store


def prepare_personal(root, successor, catalog_revision):
    """Stopped operator step, called inside live_checkout. Never run by uploads."""
    library, store = source_target(root, successor)
    w.require_idle(root)
    catalog = store / "catalog.json"
    handover.owned(catalog, directory=False)
    raw = w.read_file(catalog)
    if w.digest(raw) != catalog_revision:
        raise Refused("The approved source catalog baseline changed.")
    data = json.loads(raw)
    if (set(data) != {"version", "sources"} or data["version"] != 1 or not isinstance(data["sources"], dict)
            or any(k.casefold().startswith("documents/reactions/") for k in data["sources"])):
        raise Refused("Unexpected catalog format or existing reaction keys.")
    state = store / PERSONAL_STATE
    marker = state / "binding"
    expected = w.json_bytes({**binding(root, library, store), "baseline": catalog_revision, "version": 1})
    if w.present(state):
        handover.owned(state, directory=True)
        if w.read_file(marker) != expected:
            raise Refused("Source writer state already exists with another binding.")
    else:
        if w.present(store / "audio"):
            raise Refused("Refusing to adopt an existing audio directory.")
        state.mkdir(mode=0o700)
        atomic(marker, expected)
        w.sync_directory(store)
    for sub in (state / "requests", store / "audio"):
        sub.mkdir(mode=0o700, exist_ok=True)
        w.validate_state(store, sub)
    cursor = state / "catalog-revision"
    if not w.present(cursor):
        atomic(cursor, w.json_bytes({"current": catalog_revision}))
    elif json.loads(w.read_file(cursor)) != {"current": catalog_revision}:
        raise Refused("Source writer has already advanced.")
    w.sync_directory(store)
    w.sync_directory(state)
    install_schema(root, successor)
    return w.digest(expected)


def personal_binding(root, successor, pin):
    library, store = source_target(root, successor)
    state = store / PERSONAL_STATE
    handover.owned(state, directory=True)
    marker = state / "binding"
    handover.owned(marker, directory=False)
    raw = w.read_file(marker, limit=2048)
    if not pin or w.digest(raw) != pin:
        raise Refused("Personal source writer pin changed.")
    expected = json.loads(raw)
    if (not isinstance(expected, dict)
            or expected != {**binding(root, library, store), "version": 1, "baseline": expected.get("baseline")}
            or not isinstance(expected["baseline"], str) or not w.REVISION.fullmatch(expected["baseline"])
            or not w.replay(root, root / w.STATE, schema_request(root, successor))
            or not bijou.source(root, INDEX).startswith(SCHEMA)):
        raise Refused("Personal source store or reaction schema binding changed.")
    return library, store, state, marker, raw


def file_personal(root, successor, pin, meta, audio):
    library, store, state, marker, expected = personal_binding(root, successor, pin)
    return _file(root, library, store, marker, expected, state / "requests", meta, audio,
                 successor=successor, cursor=state / "catalog-revision")


TRANSCRIPT = "\n## Reviewed transcript\n\n"


def split_transcript(text):
    head, marker, quote = text.partition(TRANSCRIPT)
    if not marker:
        return text, None
    lines = quote.rstrip("\n").split("\n")
    if not all(line.startswith("> ") for line in lines):
        raise Refused("Transcript section has other content; review the concept on the Mac.")
    return head, "\n".join(line[2:] for line in lines)


def save_transcript(root, library, payload, successor=None):
    from . import concept
    path = payload.get("path")
    text = payload.get("text")
    if (payload.get("library") != library or not isinstance(path, str)
            or not re.fullmatch(r"Documents/reactions/[0-9]{7}\.md", path)
            or not isinstance(text, str) or not text.strip() or len(text.encode()) > 24000
            or any(ord(c) < 32 and c not in "\n\t" for c in text)):
        raise Refused("Invalid transcript or reaction.")
    old = concept.read(root, path, successor=successor)
    fields = document(old["markdown"])[0]
    if fields.get("type") != "Film Reaction" or fields.get("take_id") != payload.get("take"):
        raise Refused("Reaction identity changed.")
    head, current = split_transcript(old["markdown"])
    text = text.strip()
    if current != text:
        if old["revision"] != payload.get("revision"):
            raise bijou.Conflict("This reaction changed on the Mac. Keep your draft, sync and review before saving.")
        replacement = head + TRANSCRIPT + "\n".join("> " + line for line in text.split("\n")) + "\n"
        concept.change(root, old["id"], old["revision"], "human:barry" if successor else "process:bijou-fixture",
                       replacement=replacement.encode(), successor=successor, expected_path=path)
    saved = concept.read(root, path, successor=successor)
    if split_transcript(saved["markdown"])[1] != text:
        raise Refused("Transcript read-back failed. Keep the local draft.")
    return {"revision": saved["revision"], "text": text}


def archived(root, store, *, take=None):
    """Resolve only filed Film Reactions; no client-selected filesystem paths."""
    w.require_idle(root)
    rows = json.loads(w.read_file(store / "catalog.json"))["sources"]
    results = {}
    for concept in sorted((root / DIR).glob("[0-9]*.md")):
        path = concept.relative_to(root).as_posix()
        if not re.fullmatch(r"Documents/reactions/[0-9]{7}\.md", path):
            continue
        markdown = bijou.source(root, path)
        fields = document(markdown)[0]
        if fields.get("type") != "Film Reaction":
            continue
        tid = str(uuid.UUID(fields["take_id"]))
        if take is not None and tid != take:
            continue
        digest = fields["source_sha256"]
        key = f"Documents/reactions/{tid}.wav"
        row = rows.get(key, {})
        if (not w.REVISION.fullmatch(digest) or fields["source_key"] != key
                or row.get("storage") != "local" or row.get("sha256") != digest
                or row.get("path") != f"audio/{digest}.wav"):
            raise Refused("The reaction source and catalog disagree.")
        if take is not None:
            raw = w.read_file(w.safe_target(store, row["path"]), limit=LIMIT)
            if len(raw) != row.get("size") or w.digest(raw) != digest:
                raise Refused("The archived recording failed verification.")
            return raw
        stamp = datetime.fromisoformat(str(fields["recorded_at"]))
        results.setdefault(fields["film_id"], []).append(dict(
            id=tid, recordedAt=stamp.timestamp() - 978307200,  # Foundation's reference date
            viewingDate=str(fields["viewing_date"]) if fields.get("viewing_date") else None,
            seconds=fields["duration_ms"] / 1000,
            revision=w.digest(markdown.encode()), transcript=split_transcript(markdown)[1],
            receipt=dict(id=fields["id"], path=path, sha256=digest, take=tid)))
    return results if take is None else None


def _file(root, library, store, marker, expected, requests, meta, audio, *, successor=None, cursor=None):
    for directory in (store, store / "audio", requests):
        w.validate_state(store, directory)
    if w.read_file(marker) != expected:
        raise Refused("The source-store binding changed.")
    if (not isinstance(meta, dict) or set(meta) - {"library", "film", "take", "recordedAt", "viewingDate", "sha256"}
            or meta.get("library") != library or not 0 < len(audio) <= LIMIT or meta.get("sha256") != w.digest(audio)):
        raise Refused("Wrong library or audio checksum.")
    ref = meta.get("film")
    if not isinstance(ref, dict) or not isinstance(ref.get("path"), str) or not (m := bijou.MOVIE_PATH.fullmatch(ref["path"])):
        raise Refused("Invalid movie reference.")
    if ref != bijou.movie_ref(ref["path"], "bho:" + m[1]):
        raise Refused("Expected an identified movie.")
    try:
        take = str(uuid.UUID(meta["take"]))
        recorded = datetime.fromisoformat(meta["recordedAt"])
        if recorded.utcoffset() is None or (meta.get("viewingDate") is not None and not date_value(meta["viewingDate"])):
            raise ValueError
        with wave.open(io.BytesIO(audio)) as wav:
            frames, rate, channels = wav.getnframes(), wav.getframerate(), wav.getnchannels()
            if (not 1 <= channels <= 8 or wav.getsampwidth() != 2 or not 8000 <= rate <= 192000
                    or not 0.25 <= frames / rate <= 120.01 or len(wav.readframes(frames)) != frames * channels * 2):
                raise ValueError
    except (TypeError, KeyError, ValueError, AttributeError, EOFError, wave.Error):
        raise Refused("Expected a valid dated Bijou take and a complete PCM WAV recording.") from None
    key = f"Documents/reactions/{take}.wav"
    digest = meta["sha256"]
    blob = store / "audio" / (digest + ".wav")
    fields = dict(type="Film Reaction", title=f"Film reaction · {recorded.date()}", film_id=ref["personalID"],
                  take_id=take, recorded_at=recorded.isoformat(), duration_ms=round(1000 * frames / rate),
                  source_key=key, source_sha256=digest)
    if meta.get("viewingDate"):
        fields["viewing_date"] = meta["viewingDate"]
    raw = ("---\n" + "".join(f"{k}: {json.dumps(v, ensure_ascii=False)}\n" for k, v in fields.items())
           + f'---\n\nReaction to [film](/{ref["path"]}).\n').encode()
    # One order for both locks: source store, then the OKF writer. The marker is never replaced.
    with os.fdopen(os.open(marker, os.O_RDONLY | os.O_NOFOLLOW), "rb") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        if lock.read(len(expected) + 1) != expected or not os.path.samestat(os.fstat(lock.fileno()), marker.lstat()):
            raise Refused("Source binding changed while acquiring the lock.")
        w.require_idle(root)
        film = document(bijou.source(root, ref["path"]))[0]
        if film.get("id") != ref["personalID"] or not bijou.movie(film):
            raise Refused("The movie changed.")
        catalog_path = store / "catalog.json"
        original = w.read_file(catalog_path)
        revision = w.digest(original)
        wanted = revision
        catalog = json.loads(original)
        if catalog.get("version") != 1 or not isinstance(catalog.get("sources"), dict):
            raise Refused("Unknown source catalog.")
        stamp = json.loads(w.read_file(cursor)) if cursor else {}
        if cursor and not (stamp == {"current": revision} or stamp.get("take") == take
                           and revision in (stamp.get("before"), stamp.get("after"))):
            raise Refused("Stale source catalog or another filing awaits recovery.")
        request = requests / take
        fingerprint = w.json_bytes({"concept": w.digest(raw), "path": ref["path"]})
        if w.present(request):
            if w.read_file(request) != fingerprint:
                raise Refused("This take ID was already used for a different recording or movie.")
        else:
            atomic(request, fingerprint)
        if not w.present(blob):
            atomic(blob, audio)
        if w.digest(w.read_file(blob, limit=LIMIT)) != digest:
            raise Refused("Stored audio failed checksum verification.")
        row = dict(storage="local", path="audio/" + blob.name, sha256=digest, size=len(audio))
        if key in catalog["sources"]:
            if any(catalog["sources"][key].get(k) != v for k, v in row.items()):
                raise Refused("Existing source entry disagrees with this take.")
        else:
            catalog["sources"][key] = {**row, "preserved_at": stamp.get("at") or datetime.now(timezone.utc).isoformat()}
            updated = w.json_bytes(catalog)
            wanted = w.digest(updated)
            if cursor:
                pending = dict(take=take, before=revision, after=wanted, at=catalog["sources"][key]["preserved_at"])
                if "take" in stamp and pending != stamp:
                    raise Refused("The pending source update changed.")
                atomic(cursor, w.json_bytes(pending))
            if w.read_file(catalog_path) != original:
                raise Refused("Catalog changed during filing.")
            atomic(catalog_path, updated)
        if json.loads(w.read_file(catalog_path))["sources"][key] != catalog["sources"][key]:
            raise Refused("Source catalog read-back failed.")
        result = w.create(root, ROUTES, raw, "human:barry" if successor else "process:bijou-fixture",
                          request_id="reaction-" + take, successor=successor)
        saved = document(bijou.source(root, result["path"]))[0]
        if saved.get("id") != result["id"] or any(saved.get(k) != v for k, v in fields.items()):
            raise Refused("Filed reaction failed read-back.")
        if cursor:
            if w.digest(w.read_file(catalog_path)) != wanted:
                raise Refused("Catalog changed before filing receipt.")
            atomic(cursor, w.json_bytes({"current": wanted}))
        return {"id": result["id"], "path": result["path"], "take": take, "sha256": digest}
