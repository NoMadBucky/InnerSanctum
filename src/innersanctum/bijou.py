"""Barry's Bijou: watched movies and recoverable placements."""

from datetime import datetime
import json
from pathlib import Path
import re

from . import writer as w
from .schema import ID, Refused, date_value, datetime_value, document, read_text, resolve_schema, same


BINDING = ".bijou-fixture.json"
MOVIES = "Resources/videos"
RANKINGS = "Documents/rankings"
MOVIE_PATH = re.compile(r"Resources/videos/([0-9]{7})\.md")
RANK_PATH = re.compile(r"Documents/rankings/([0-9]{7})\.md")
ENTRY = re.compile(r"([1-9][0-9]*)\. \[(.*)\]\(/(Resources/videos/[0-9]{7}\.md)\)")
OP = "bijou-place"


class Conflict(Refused):
    """The request definitely did not publish; review the current catalog."""


def binding(root):
    w.open_bundle(root, Path(__file__).resolve().parents[2])
    try:
        cfg = json.loads(w.read_file(root / BINDING, limit=2048))
        rank = RANK_PATH.fullmatch(cfg["path"])
        if (set(cfg) != {"library", "path", "id", "bundle"} or not rank
                or cfg["id"] != "bho:" + rank[1] or cfg["bundle"] != w.bundle_identity(root)
                or not re.fullmatch("[0-9a-f]{32}", cfg["library"])):
            raise ValueError
        return cfg
    except (KeyError, ValueError, TypeError, FileNotFoundError):
        raise Refused("Select the original disposable Bijou fixture.") from None


def source(root, path):
    return read_text(w.read_file(w.safe_target(root, path)))


def parse_order(text, identity):
    data, _, _ = document(text)
    if data.get("type") != "Film Ranking" or data.get("id") != identity:
        raise Refused("The bound Film Ranking identity changed.")
    lines, nl = w.lines_for(text)
    marks = [i for tag, title, i, _ in w.headings(text) if tag == "h2" and title == "Ranking"]
    if len(marks) != 1 or lines[marks[0]] != "## Ranking":
        raise Refused("Expected one managed Ranking section.")
    prefix = nl.join(lines[:marks[0] + 1]) + nl + nl
    entries = {}
    for line in lines[marks[0] + 1:]:
        if not line:
            continue
        m = ENTRY.fullmatch(line)
        if not m or int(m[1]) != len(entries) + 1 or m[3] in entries:
            raise Refused("The ranking contains an unexpected entry or duplicate.")
        entries[m[3]] = m[2]
    return entries, prefix, nl


def movie(data):
    return data.get("type") == "Video" and data.get("video_type") == "Movie"


def watched(data):
    return (movie(data)
            and (date_value(data.get("date_watched")) or data.get("video_status") == "watched"))


def movie_ref(path, identity):
    return {"path": path, **({"personalID": identity} if identity is not None else {})}


def tmdb_entry(data, links, body):
    pattern = r"https?://(?:www\.)?(?:themoviedb\.org|tmdb\.org)/(?:[a-z]{2}(?:-[a-z]{2})?/)?movie/([1-9][0-9]*)(?=[-/?#)\s>]|$)"
    for address in [data.get("url"), *(s["address"] for s in links)]:
        if isinstance(address, str) and (m := re.match(pattern, address, re.I)):
            return "https://www.themoviedb.org/movie/" + m[1]
    ids = set(re.findall(pattern, body, re.I))
    return "https://www.themoviedb.org/movie/" + ids.pop() if len(ids) == 1 else None


def catalog_rows(root, library, revision, entries, *, all_movies=False):
    movies, issues, refs = [], [], {}
    for path, file in w.visible_files(root):
        match = MOVIE_PATH.fullmatch(path)
        if not match:
            continue
        data, body, _ = document(read_text(w.read_file(file)))
        if not movie(data) or not all_movies and not watched(data):
            continue
        identity = data.get("id")
        ref = movie_ref(path, identity)
        if (identity is not None or path in entries) and identity != "bho:" + match[1]:
            issues.append(f"Film identity changed: {path}")
        if type(data.get("ranked", False)) is not bool or data.get("ranked", False) != (path in entries):
            issues.append(f"Membership disagrees with the list: {path}")
        refs[path] = ref
        if path in entries and not watched(data):
            issues.append(f"Ranked movie is no longer watched: {path}")
        release = data.get("release_date")
        day = data.get("date_watched")
        src = data.get("sources") or []
        links = [{"title": s.get("title") or s["resource"], "address": s["resource"]}
                 for s in ([src] if isinstance(src, dict) else src) if isinstance(s, dict) and isinstance(s.get("resource"), str)]
        if not links and data.get("url"):
            links = [{"title": "Film reference", "address": data["url"]}]
        poster = data.get("poster")
        movies.append({"ref": ref, "title": data["title"], "watched": str(day)[:10] if date_value(day) else None,
                       "viewed": watched(data), "watchlist": data.get("video_status") == "watchlist",
                       "inLibrary": data.get("in_library") is True, "tmdb": tmdb_entry(data, links, body),
                       "year": str(release)[:4] if date_value(release) or datetime_value(release) else None,
                       "body": body.strip(), "sources": links, "description": data.get("description"),
                       "metadata": {k: str(data[k]) for k in ("id", "video_type", "video_status", "date_watched",
                                                              "release_date", "in_library", "tags") if k in data},
                       "posterKey": w.digest(poster.encode()) if isinstance(poster, str) and poster else None})
    for path in entries.keys() - refs.keys():
        issues.append(f"Ranked film is unavailable: {path}")
    order = [refs.get(p, movie_ref(p, "bho:" + MOVIE_PATH.fullmatch(p)[1])) for p in entries]
    return {"library": library, "revision": revision, "films": movies,
            "order": order, "labels": {p: re.sub(r"\\(.)", r"\1", s) for p, s in entries.items()},
            "issues": sorted(issues)}


def inspect_catalog(root, cfg, *, all_movies=False):
    text = source(root, cfg["path"])
    entries, _, _ = parse_order(text, cfg["id"])
    return catalog_rows(root, cfg["library"], w.digest(text.encode()), entries, all_movies=all_movies)


def catalog(root, successor=None, *, all_movies=False):
    cfg = personal_config(root, successor) if successor else binding(root)
    with w.locked(root, successor):
        w.require_idle(root)
        snapshot = inspect_catalog(root, cfg, all_movies=all_movies)
        if successor:
            snapshot["origin"] = "personal"
        return snapshot


def validate(command):
    if (type(command) is not dict or set(command) != {"library", "revision", "film", "gap", "requestID"}
            or not isinstance(command["library"], str) or not re.fullmatch("[0-9a-f]{32}", command["library"])
            or not isinstance(command["revision"], str) or not w.REVISION.fullmatch(command["revision"])
            or type(command["gap"]) is not dict or command["gap"].keys() - {"above", "below"}
            or not isinstance(command["requestID"], str) or not w.REQUEST_ID.fullmatch(command["requestID"])):
        raise Refused("Invalid placement request.")
    for ref in [command["film"], *(r for r in command["gap"].values() if r is not None)]:
        if (type(ref) is not dict or ref.keys() - {"path", "personalID"} or type(ref.get("path")) is not str
                or not MOVIE_PATH.fullmatch(ref["path"]) or ref.get("personalID") is not None
                and (type(ref["personalID"]) is not str or not ID.fullmatch(ref["personalID"]))):
            raise Refused("Invalid film reference.")


def mark_watched(root, command, actor, successor=None):
    """Update just this movie's viewing fields through the revision-checked concept writer."""
    from . import concept
    cfg = personal_config(root, successor) if successor else binding(root)
    if set(command) != {"library", "film", "day"} or command["library"] != cfg["library"] or not date_value(command["day"]):
        raise Refused("Expected this library and a valid watched date.")
    ref, day = command["film"], command["day"]
    if (not isinstance(ref, dict) or not isinstance(ref.get("path"), str)
            or not (match := MOVIE_PATH.fullmatch(ref["path"])) or ref != movie_ref(ref["path"], "bho:" + match[1])):
        raise Refused("Expected an identified movie.")
    old = concept.read(root, ref["path"], successor=successor)
    fields, body, end = document(old["markdown"])
    if old["id"] != ref["personalID"] or not movie(fields):
        raise Conflict("The movie has changed.")
    if watched(fields):
        if str(fields.get("date_watched")) == day:
            return {"day": day}
        raise Conflict("Already marked watched. Sync to see the current date.")
    lines, nl = w.lines_for(old["markdown"])
    for key, value in (("video_status", "watched"), ("date_watched", day)):
        if key not in fields:
            lines.insert(1, f'{key}: "{value}"')
            end += 1
        else:
            hits = [i for i in range(1, end - 1) if lines[i].startswith(key + ":")]
            if len(hits) != 1:
                raise Refused("Could not safely update the viewing fields.")
            i = hits[0]
            comment = re.search(r"\s+#.*$", lines[i])
            lines[i] = f'{key}: "{value}"' + (comment[0] if comment else "")
    replacement = nl.join(lines)
    after, after_body, _ = document(replacement)
    if after_body != body or not same(after, {**fields, "video_status": "watched", "date_watched": day}):
        raise Refused("Viewing edit would change unrelated content.")
    concept.change(root, ref["personalID"], old["revision"], actor, replacement=replacement.encode(),
                   successor=successor, expected_path=ref["path"])
    return {"day": day}


def with_flag(text):
    data, body, offset = document(text)
    lines, nl = w.lines_for(text)
    if "ranked" not in data:
        lines.insert(1, "ranked: true")
    elif data["ranked"] is False:
        candidates = [i for i in range(1, offset - 1) if re.fullmatch(r"ranked: *false(?: *#.*)? *", lines[i])]
        if len(candidates) != 1:
            raise Refused("Cannot preserve the existing ranked field formatting.")
        i = candidates[0]
        lines[i] = lines[i].replace("false", "true", 1)
    else:
        raise Refused("First placement needs an absent or false ranked flag.")
    after = nl.join(lines)
    fields, after_body, _ = document(after)
    if not same(fields, {**data, "ranked": True}) or after_body != body:
        raise Refused("Membership edit would change unrelated content.")
    return after


def plan(cfg, command, originals, actor, when):
    """Derive the only permitted after-bytes, also when verifying a frozen journal."""
    validate(command)
    w.validate_actor(actor)
    rank, film, audit = originals
    path = command["film"]["path"]
    entries, prefix, nl = parse_order(rank, cfg["id"])
    fields, _, _ = document(film)
    if (command["library"] != cfg["library"] or command["revision"] != w.digest(rank.encode())
            or not watched(fields) or command["film"].get("personalID") != fields.get("id")):
        raise Conflict("Library, film or ranking revision changed.")
    old = list(entries)
    others = [p for p in old if p != path]
    above, below = (command["gap"].get(k) for k in ("above", "below"))
    neighbors = (above and above["path"], below and below["path"])
    gaps = list(zip([None, *others], [*others, None]))
    if neighbors not in gaps:
        raise Conflict("These films no longer bound the selected gap.")
    others.insert(gaps.index(neighbors), path)
    if others == old:
        raise Conflict("The film is already in this position.")
    entries[path] = w.escape_label(fields["title"])
    updated = prefix + "".join(f"{i}. [{entries[p]}](/{p}){nl}" for i, p in enumerate(others, 1))
    changes = [w.Change(cfg["path"], w.digest(rank.encode()), updated)]
    if path not in old:
        changes.append(w.Change(path, w.digest(film.encode()), with_flag(film)))
    changes.append(w.Change("log.md", w.digest(audit.encode()), w.edit_log(
        audit, cfg["path"], "Reranked film" if path in old else "Ranked film", actor, when, action="Placement")))
    return changes


def verify(root, changes, request, review, successor=None):
    if set(review) != {"command", "originals", "actor", "at"}:
        raise Refused("Invalid frozen placement.")
    command, originals, actor = (review[k] for k in ("command", "originals", "actor"))
    validate(command)
    if type(originals) is not list or len(originals) != 3 or any(type(s) is not str for s in originals):
        raise Refused("Invalid placement preimages.")
    when = datetime.fromisoformat(review["at"])
    cfg = personal_config(root, successor) if successor else binding(root)
    operation = PERSONAL_PLACE if successor else OP
    if (when.utcoffset() is None or request != w.write_request(command["requestID"], operation, command, actor)
            or changes != plan(cfg, command, originals, actor, when)):
        raise Refused("Frozen placement does not match the original request.")


def place(root, command, actor, successor=None):
    cfg = personal_config(root, successor) if successor else binding(root)
    validate(command)
    if cfg["library"] != command["library"]:
        raise Refused("Wrong Bijou library.")
    w.validate_actor(actor)
    operation = PERSONAL_PLACE if successor else OP
    request = w.write_request(command["requestID"], operation, command, actor)
    with w.locked(root, successor) as state:
        w.require_idle(root)
        if (prior := w.replay(root, state, request)) is not None:
            return prior
        snap = inspect_catalog(root, cfg)
        films = {f["ref"]["path"]: f["ref"] for f in snap["films"]}
        if (snap["issues"] or command["revision"] != snap["revision"]
                or any(films.get(ref["path"]) != ref for ref in [command["film"], *command["gap"].values()] if ref)):
            raise Conflict("The catalog or rankings changed; review placement.")
        originals = [source(root, p) for p in (cfg["path"], command["film"]["path"], "log.md")]
        when = datetime.now().astimezone().replace(microsecond=0)
        changes = plan(cfg, command, originals, actor, when)
        indexes, _ = w.inventory(root, collect_ids=False)
        route = resolve_schema("Video", MOVIES, indexes, declaring=MOVIES + "/index.md")
        if route.fields.get("ranked") not in ("bool", {"type": "bool"}) or "ranked" in route.required:
            raise Refused("Expected an optional boolean ranked declaration.")
        route.validate(document(changes[1].after if len(changes) == 3 else originals[1])[0])
        resolve_schema("Film Ranking", RANKINGS, indexes, declaring=RANKINGS + "/index.md").validate(
            document(changes[0].after)[0])
        for c in changes:
            read_text(c.after.encode())
        review = dict(command=command, originals=originals, actor=actor, at=when.isoformat())
        w.freeze(root, state, changes, operation=operation, request=request, bijou_review=review)
        return w.publish(root, state, changes, operation=operation, request=request, successor=successor)


PERSONAL_PLACE = "bijou-personal-place"
IMPORT = "bijou-personal-import"
IMPORT_ID = "bijou-personal-first-import-v1"
PARENT = "Documents/index.md"
INDEX = RANKINGS + "/index.md"
SCHEMA = """# Film Rankings

```yaml
okf_schema:
  type: Film Ranking
  directory: Documents/rankings
  required: [id, type, title]
  fields:
    id: {type: bho}
    type: {const: Film Ranking}
    title: {type: string}
```

## Directory Listing
"""


def library_key(root, successor):
    from .handover import SUCCESSOR, binding as adopted_binding
    if not successor or not (m := SUCCESSOR.fullmatch(successor)) or m[1] != adopted_binding(root):
        raise Refused("Expected the adopted Personal checkout.")
    w.check_authority(root, successor)
    return w.digest(b"bijou-personal-v1\0" + successor)[:32]


def personal_config(root, successor):
    key = library_key(root, successor)
    receipt = w.read_receipt(root, root / w.STATE, IMPORT_ID)
    if not receipt:
        raise Refused("Personal Bijou has not been initialized.")
    record = receipt[1]
    rank = RANK_PATH.fullmatch(record.get("path", ""))
    if not rank or record.get("operation") != IMPORT or record.get("id") != "bho:" + rank[1]:
        raise Refused("The initial Personal ranking receipt is invalid.")
    return {"library": key, "path": record["path"], "id": record["id"]}


def ordered_rows(export):
    lines = export.splitlines()
    if (lines[:1] not in (["# Bijou"], ["# Barry’s Bijou"]) or lines[1:4] != ["", "## Ranking", ""]
            or not 1 <= len(lines[4:]) <= 1000):
        raise Refused("Expected a nonempty Bijou Markdown ranking export.")
    rows = {}
    for i, line in enumerate(lines[4:], 1):
        match = ENTRY.fullmatch(line)
        if not match or match[1] != str(i) or match[3] in rows:
            raise Refused("Invalid, duplicate or out-of-order exported link.")
        rows[match[3]] = match[2]
    return rows


def import_plan(review):
    if set(review) != {"export", "parent", "audit", "records", "id", "actor", "at", "library"}:
        raise Refused("Invalid import preimages.")
    rows = ordered_rows(review["export"])
    identity, actor = review["id"], review["actor"]
    at = datetime.fromisoformat(review["at"])
    w.validate_actor(actor)
    if not ID.fullmatch(identity) or at.utcoffset() is None or set(review["records"]) != set(rows):
        raise Refused("Invalid import identity, time or movie set.")
    path = f"{RANKINGS}/{identity[4:]}.md"
    title = "Barry’s Film Ranking"
    rank = (f'---\nid: "{identity}"\ntype: Film Ranking\ntitle: {title}\ngenerated:\n'
            f'  by: {json.dumps(actor)}\n  at: "{at.isoformat()}"\n---\n\n## Ranking\n\n')
    movies = []
    for i, (p, label) in enumerate(rows.items(), 1):
        original = review["records"][p]
        fields = document(original)[0]
        name = fields["title"]
        export_label = name.replace("\\", "\\\\").replace("[", "\\[").replace("]", "\\]")
        if not watched(fields) or fields.get("id") != "bho:" + MOVIE_PATH.fullmatch(p)[1] or label != export_label:
            raise Refused("An exported link no longer matches the exact watched movie.")
        rank += f"{i}. [{w.escape_label(name)}](/{p})\n"
        movies.append(w.Change(p, w.digest(original.encode()), with_flag(original)))
    parent, audit = review["parent"], review["audit"]
    return [w.Change(path, None, rank),
            w.Change(INDEX, None, w.edit_index(SCHEMA, identity[4:] + ".md", title)),
            w.Change(PARENT, w.digest(parent.encode()), w.edit_index(parent, "rankings/index.md", "Film Rankings")),
            *movies, w.Change("log.md", w.digest(audit.encode()), w.edit_log(
                audit, path, f"Imported {len(rows)} film rankings", actor, at, action="Ranking import"))]


def import_request(library, export, actor):
    return w.write_request(IMPORT_ID, IMPORT, library, w.digest(export.encode()), actor)


def verify_import(root, changes, request, review, successor):
    if (library_key(root, successor) != review["library"]
            or request != import_request(review["library"], review["export"], review["actor"])
            or changes != import_plan(review)):
        raise Refused("Invalid frozen Personal ranking import.")


def initialize(root, successor, export, actor):
    from .schema import declarations
    library = library_key(root, successor)
    request = import_request(library, export, actor)
    rows = ordered_rows(export)
    with w.locked(root, successor) as state:
        w.require_idle(root)
        if (receipt := w.replay(root, state, request)) is not None:
            return receipt
        if w.present(w.safe_target(root, RANKINGS, missing=True)):
            raise Refused("Rankings already exist; refusing to replace them.")
        indexes, ids = w.inventory(root, collect_ids=True)
        if any(k == "Film Ranking" for text in indexes.values() for k, _ in declarations(text)):
            raise Refused("A Film Ranking declaration already exists.")
        if catalog_rows(root, library, "", {})["issues"]:
            raise Refused("Existing movie identities or ranked flags need review.")
        log = source(root, "log.md")
        review = dict(library=library, export=export, actor=actor, at=datetime.now().astimezone().isoformat(timespec="seconds"),
                      id=w.allocate_id(ids | w.retired_ids(log)), parent=source(root, PARENT), audit=log,
                      records={p: source(root, p) for p in rows})
        changes = import_plan(review)
        video = resolve_schema("Video", MOVIES, indexes, declaring=MOVIES + "/index.md")
        if video.fields.get("ranked") not in ("bool", {"type": "bool"}) or "ranked" in video.required:
            raise Refused("Expected optional Video.ranked boolean.")
        for c in changes[3:-1]:
            video.validate(document(c.after)[0])
        resolve_schema("Film Ranking", RANKINGS, {**indexes, INDEX: changes[1].after}, declaring=INDEX).validate(
            document(changes[0].after)[0])
        for c in changes:
            read_text(c.after.encode())
        w.freeze(root, state, changes, operation=IMPORT, request=request, bijou_review=review)
        return w.publish(root, state, changes, operation=IMPORT, request=request, successor=successor, directory=RANKINGS)
