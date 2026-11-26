"""Narrow, fixture-only source catalog writer for Bijou's PCM recordings."""

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

from . import bijou, writer as w
from .schema import Refused, date_value, document

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
    for directory in (store, store / "audio", store / ".requests"):
        w.validate_state(store, directory)
    marker = store / ".fixture-writer"
    expected = w.json_bytes(binding(root, library, store))
    if w.read_file(marker) != expected:
        raise Refused("The fixture source-store binding changed.")
    if (not isinstance(meta, dict) or set(meta) - {"library", "film", "take", "recordedAt", "viewingDate", "sha256"}
            or meta.get("library") != library or not 0 < len(audio) <= LIMIT or meta.get("sha256") != w.digest(audio)):
        raise Refused("Wrong fixture library or audio checksum.")
    ref = meta.get("film")
    if not isinstance(ref, dict) or not isinstance(ref.get("path"), str) or not (m := bijou.MOVIE_PATH.fullmatch(ref["path"])):
        raise Refused("Invalid movie reference.")
    if ref != bijou.movie_ref(ref["path"], "bho:" + m[1]):
        raise Refused("Expected the identified fixture movie.")
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
        w.require_idle(root)
        film = document(bijou.source(root, ref["path"]))[0]
        if film.get("id") != ref["personalID"] or not bijou.movie(film):
            raise Refused("The movie changed.")
        catalog_path = store / "catalog.json"
        catalog = json.loads(w.read_file(catalog_path))
        if catalog.get("version") != 1 or not isinstance(catalog.get("sources"), dict):
            raise Refused("Unknown source catalog.")
        request = store / ".requests" / take
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
            catalog["sources"][key] = {**row, "preserved_at": datetime.now(timezone.utc).isoformat()}
            atomic(catalog_path, w.json_bytes(catalog))
        if json.loads(w.read_file(catalog_path))["sources"][key] != catalog["sources"][key]:
            raise Refused("Source catalog read-back failed.")
        result = w.create(root, ROUTES, raw, "process:bijou-fixture", request_id="reaction-" + take)
        saved = document(bijou.source(root, result["path"]))[0]
        if saved.get("id") != result["id"] or any(saved.get(k) != v for k, v in fields.items()):
            raise Refused("Filed reaction failed read-back.")
        return {"id": result["id"], "path": result["path"], "take": take, "sha256": digest}
