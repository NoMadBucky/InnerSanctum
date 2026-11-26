"""Recoverable concept and journal publication for explicitly selected bundles."""

from contextlib import contextmanager
from dataclasses import dataclass
from datetime import date, datetime
import fcntl
from hashlib import sha256
import json
import os
from pathlib import Path, PurePosixPath
import posixpath
import re
import secrets
import stat
import tempfile
import unicodedata
from urllib.parse import quote, unquote, urlsplit

from .schema import (
    DATE, ID, LIMIT, MANAGED, MD, Refused, date_value, document, existing_fields, existing_identity,
    path_parts, read_text, resolve_route,
)


STATE = ".innersanctum"
PENDING = "pending-create.json"
MARKER = ".personal-writer.lock"
JOURNAL_ROOT = "Documents/journal"
STRUCTURAL = {"index.md", "log.md", "agents.md", "spec.md"}
PLAN_LIMIT = 12 * LIMIT
REVISION = re.compile(r"[0-9a-f]{64}")
REQUEST_ID = re.compile(r"[A-Za-z0-9_-]{16,128}")
RECEIPT_LIMIT = 32 * 1024
EDITS = {"concept-update", "concept-delete", "journal-update", "journal-delete"}
VIDEO_STATUS_OPERATION = "video-status-migration"
TIMESTAMP_OPERATION = "timestamp-format-migration"
VERSION_OPERATION = "okf-version-declaration"
DELETED_ID = re.compile(r"^\* \*\*Delete\*\* \([^\r\n]+\) — bho\\:([0-9]{7}) · ", re.M)


def present(path):
    return path.exists() or path.is_symlink()


def folded(name):
    return unicodedata.normalize("NFC", name).casefold()


def concept_path(path):
    parts = path_parts(path)
    return parts[-1].lower().endswith(".md") and folded(parts[-1]) not in STRUCTURAL


def check_authority(root, successor=None):
    matches = [name for name in os.listdir(root) if folded(name) == MARKER]
    if successor is None and matches:
        raise Refused("This bundle is managed by MatterKeep Personal. No publication was attempted.")
    if successor is not None and (matches != [MARKER]
                                  or read_file(root / MARKER, limit=256) != successor):
        raise Refused("The approved InnerSanctum writer marker changed.")


def external_root(path, checkout):
    root = Path(path).expanduser().absolute()
    if (root.resolve(strict=True) != root or not root.is_dir()
            or root.is_relative_to(checkout) or checkout.is_relative_to(root)
            or any(folded(part) == "synologydrive" for part in root.parts)
            or any(present(parent / ".git") for parent in (root, *root.parents))):
        raise Refused("Select a physical standalone bundle outside repositories and SynologyDrive.")
    return root


def open_bundle(path, checkout):
    root = external_root(path, checkout)
    check_authority(root)
    return root


def read_file(path, *, limit=LIMIT):
    with os.fdopen(os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK), "rb") as stream:
        info = os.fstat(stream.fileno())
        if (not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or info.st_size > limit):
            raise Refused("Expected a bounded regular file with one link.")
        data = stream.read(limit + 1)
        if len(data) > limit:
            raise Refused("A file exceeds the supported size.")
        return data


def visible_files(root, *, include_entries=False):
    def fail(error):
        raise error

    for parent, dirs, files in os.walk(root, followlinks=False, onerror=fail):
        path = Path(parent)
        visible = [name for name in (*dirs, *files) if not name.startswith(".")]
        if len(visible) != len(set(map(folded, visible))):
            raise Refused("Bundle contains ambiguous case or Unicode-equivalent paths.")
        dirs[:] = sorted(name for name in dirs if not name.startswith("."))
        for name in visible:
            if (path / name).is_symlink():
                raise Refused("Bundle contains a visible symbolic link.")
        for name in sorted(visible if include_entries else files):
            if not name.startswith(".") and (include_entries or (path / name).suffix.lower() == ".md"):
                candidate = path / name
                relative = candidate.relative_to(root).as_posix()
                path_parts(relative)
                yield relative, candidate


def inventory(root, *, collect_ids):
    indexes, identities = {}, set()
    for relative, path in visible_files(root):
        if path.name == "index.md":
            indexes[relative] = read_text(read_file(path))
        elif collect_ids and concept_path(relative):
            identity = existing_identity(read_text(read_file(path)))
            if identity is None:
                continue
            if type(identity) is not str or not identity.strip() or identity in identities:
                raise Refused("Bundle contains an invalid or duplicate concept ID.")
            identities.add(identity)
    if "index.md" not in indexes:
        raise Refused("A bundle needs an existing root index.md.")
    return indexes, identities


def lines_for(text):
    newline = "\r\n" if "\r\n" in text else "\n"
    if re.search(r"[\r\n]", text.replace(newline, "")):
        raise Refused("Index, audit log or draft uses mixed line endings.")
    return text.split(newline), newline


def headings(text):
    tokens = MD.parse(text)
    return [(token.tag, tokens[i + 1].content, token.map[0], token.markup)
            for i, token in enumerate(tokens)
            if token.type == "heading_open" and token.level == 0]


def escape_label(label):
    # All ASCII punctuation is escapable in CommonMark.
    return re.sub(r"([!-/:-@\[-`{-~])", r"\\\1", label)


def edit_index(text, filename, title):
    _, body, offset = document(text, required=False)
    matches = [(line, markup) for tag, title_text, line, markup in headings(body)
               if tag == "h2" and title_text == "Directory Listing"]
    if len(matches) != 1 or matches[0][1] != "##":
        raise Refused("Destination index needs one top-level ## Directory Listing heading.")
    if filename in body:
        raise Refused("Destination index already mentions the proposed filename.")
    lines, newline = lines_for(text)
    position = matches[0][0] + offset + 1
    lines[position:position] = ["", f"* [{escape_label(title)}]({filename})"]
    if position + 2 < len(lines) and lines[position + 2]:
        lines.insert(position + 2, "")
    text = newline.join(lines)
    return text if text.endswith(newline) else text + newline


def clerk_log_suffix(session, revision):
    from .clerk_archive import reference

    uri = reference(session).uri
    if not REVISION.fullmatch(revision or ""):
        raise Refused("Clerk audit attribution requires the resulting revision.")
    return f" · revision `{revision}` · [Clerk session]({uri})"


def edit_log(text, path, title, actor, now, *, action="Create", link=True, clerk_session=None, revision=None):
    lines, newline = lines_for(text)
    sections = headings(text)
    if not sections or sections[0][0] != "h1" or sum(tag == "h1" for tag, *_ in sections) != 1:
        raise Refused("Root log needs one level-one title.")
    day = now.date()
    dated = []
    for tag, heading, line, markup in sections:
        if tag != "h2":
            continue
        try:
            section_day = date.fromisoformat(heading)
            if section_day.isoformat() != heading or markup != "##":
                raise ValueError
        except ValueError:
            raise Refused("Root log needs unambiguous ## YYYY-MM-DD sections.") from None
        if dated and dated[-1][0] < section_day:
            raise Refused("Root log dates must be newest first.")
        dated.append((section_day, line))
    if sum(section_day == day for section_day, _ in dated) > 1:
        raise Refused(f"Root log has more than one section for the {action} date.")
    record = (f"[{escape_label(title)}]({encoded_path(path)})" if link
              else f"{escape_label(title)} · {escape_label(path)}")
    entry = (f"* **{action}** ({now.isoformat(timespec='seconds')}) — "
             f"{record} · {escape_label(actor)}")
    if clerk_session is not None:
        entry += clerk_log_suffix(clerk_session, revision)
    for existing, line in dated:
        if existing == day:
            pos, insertion = line + 1, ["", entry]
            break
        if existing < day:
            pos, insertion = line, [f"## {day}", "", entry, ""]
            break
    else:
        pos, insertion = len(lines), ["", f"## {day}", "", entry]
        if lines[-1] == "":
            pos -= 1
    lines[pos:pos] = insertion
    if pos + len(insertion) < len(lines) and lines[pos + len(insertion)] and insertion[-1]:
        lines.insert(pos + len(insertion), "")
    result = newline.join(lines)
    return result if result.endswith(newline) else result + newline


def encoded_path(path):
    return quote(path, safe="/")


def link_destination(href, index):
    try:
        value = urlsplit(href)
    except ValueError:
        return None
    if value.scheme or value.netloc or not value.path:
        return None
    clean = unquote(value.path)
    return (posixpath.normpath(clean.lstrip("/")) if clean.startswith("/") else
            posixpath.normpath(str(PurePosixPath(index).parent / clean)))


@dataclass(frozen=True)
class Change:
    path: str
    before: str | None
    after: str | None

    @property
    def revision(self):
        return None if self.after is None else digest(self.after.encode())


def digest(data):
    return sha256(data).hexdigest()


def json_bytes(value):
    return json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":")).encode("ascii")


def write_request(request_id, operation, *arguments):
    if request_id is None:
        return None
    if type(request_id) is not str or not REQUEST_ID.fullmatch(request_id):
        raise Refused("Request ID must be 16–128 ASCII letters, digits, underscores or hyphens.")
    return [request_id, digest(json_bytes([operation, *arguments]))]


def receipt_path(state, request_id):
    return state / ("receipt-" + digest(request_id.encode("ascii")) + ".json")


def receipt_bytes(root, request, result):
    data = {"bundle": bundle_identity(root), "request": request, "result": result}
    return json_bytes({"data": data, "sha256": digest(json_bytes(data))})


def read_receipt(root, state, request_id):
    path = receipt_path(state, request_id)
    if not present(path):
        return None
    try:
        info = path.lstat()
        if (not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid()
                or stat.S_IMODE(info.st_mode) != 0o600):
            raise ValueError
        raw = read_file(path, limit=RECEIPT_LIMIT)
        data = json.loads(raw)["data"]
        saved, result = data["request"], data["result"]
        if (not valid_request(saved) or saved[0] != request_id or type(result) is not dict
                or result.get("request_id") != saved[0] or raw != receipt_bytes(root, saved, result)):
            raise ValueError
    except (Refused, OSError, ValueError, TypeError, KeyError, RecursionError):
        raise Refused("The write receipt is invalid; retain it for inspection.") from None
    return saved, result


def replay(root, state, request):
    retained = read_receipt(root, state, request[0]) if request is not None else None
    if retained is None:
        return None
    saved, result = retained
    if saved != request:
        raise Refused("This request ID was already used with different arguments.")
    return result


def receipt_status(root, request_id, *, successor=None):
    """Observe a write's disposition without recovering or exposing source."""
    check_authority(root, successor)
    write_request(request_id, "status")
    state = root / STATE
    if present(state):
        validate_state(root, state)
        if present(state / PENDING):
            return {"state": "pending"}
    receipt = read_receipt(root, state, request_id) if present(state) else None
    return {"state": "missing"} if receipt is None else {
        "state": "completed", "fingerprint": receipt[0][1], "receipt": receipt[1],
    }


def valid_request(request):
    return (type(request) is list and len(request) == 2
            and all(type(field) is str for field in request)
            and REQUEST_ID.fullmatch(request[0]) and REVISION.fullmatch(request[1]))


def validate_actor(actor):
    if not actor.strip() or not actor.isprintable() or len(actor) > 256:
        raise Refused("Provide the actual producer as a single-line actor.")


def require_revision(expected, observed):
    if not REVISION.fullmatch(expected):
        raise Refused("Provide the SHA-256 revision returned by read.")
    if expected != observed:
        raise Refused("The revision is stale; read the current record before retrying.")


def require_idle(root):
    if present(root / STATE / PENDING):
        raise Refused("A write is pending; recover it before continuing.")


def allocate_id(ids, available=lambda _: True):
    for _ in range(64):
        identity = f"bho:{1_000_000 + secrets.randbelow(9_000_000)}"
        if identity not in ids and available(identity):
            return identity
    raise Refused("Could not allocate an unused concept ID.")


def retired_ids(log):
    # Delete keeps the ID in the audit log so old references cannot acquire a new meaning.
    return {"bho:" + number for number in DELETED_ID.findall(log)}


def plan_create(root, routes, raw, actor, *, now=None):
    validate_actor(actor)
    text = read_text(raw)
    lines, newline = lines_for(text)
    data, _, _ = document(text)
    if MANAGED.intersection(data):
        raise Refused("Omit id, generated, verified, owner and scope from Create input.")
    kind = data.get("type")
    if type(kind) is not str or not kind.strip() or not kind.isprintable():
        raise Refused("Concept input needs a nonblank type.")
    if kind == "Journal":
        raise Refused("Use journal add for date-named Journal records.")
    indexes, ids = inventory(root, collect_ids=True)
    route = resolve_route(kind, routes, indexes)
    if in_journal(route.index):
        raise Refused("Use journal commands for the journal directory.")
    names = {folded(name) for name in os.listdir((root / route.index).parent)}
    log = read_text(read_file(root / "log.md"))
    identity = allocate_id(ids | retired_ids(log), lambda id_: folded(f"{id_[4:]}.md") not in names)
    path = route.target(identity)
    filename = PurePosixPath(path).name
    now = now or datetime.now().astimezone()
    generated = {"by": actor, "at": now.isoformat(timespec="seconds")}
    route.validate({**data, "id": identity, "generated": generated})
    lines[1:1] = [f'id: "{identity}"', "generated:",
                  f"  by: {json.dumps(actor, ensure_ascii=False)}",
                  f'  at: "{generated["at"]}"']
    source = newline.join(lines)
    index = indexes[route.index]
    changes = [Change(path, None, source),
               Change(route.index, digest(index.encode()), edit_index(index, filename, data["title"])),
               Change("log.md", digest(log.encode()), edit_log(log, path, data["title"], actor, now))]
    for change in changes:
        read_text(change.after.encode())
    return changes


def sync_directory(path):
    fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def validate_state(root, state):
    info = state.lstat()
    if (not stat.S_ISDIR(info.st_mode) or info.st_uid != os.getuid()
            or stat.S_IMODE(info.st_mode) != 0o700 or info.st_dev != root.stat().st_dev):
        raise Refused("InnerSanctum state must be a private directory on the bundle volume.")


@contextmanager
def locked(root, successor=None):
    check_authority(root, successor)
    state = root / STATE
    try:
        state.mkdir(mode=0o700)
    except FileExistsError:
        pass
    validate_state(root, state)
    sync_directory(root)
    flags = os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW | os.O_NONBLOCK
    with os.fdopen(os.open(state / "lock", flags, 0o600), "rb") as lock:
        info = os.fstat(lock.fileno())
        if (not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or info.st_uid != os.getuid()
                or stat.S_IMODE(info.st_mode) != 0o600):
            raise Refused("The InnerSanctum lock is not a private regular file.")
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise Refused("Another InnerSanctum write is in progress.") from None
        check_authority(root, successor)
        # A crash after linking a staged new concept can leave a second link.
        # Stages are never the recovery authority; the durable journal is.
        for leftover in state.glob("stage-*"):
            if not stat.S_ISREG(leftover.lstat().st_mode):
                raise Refused("Unexpected staging member; inspect the private writer state.")
            leftover.unlink()
        sync_directory(state)
        yield state


def safe_target(root, name, *, missing=False):
    parts = path_parts(name)
    current = root
    for part in parts[:-1]:
        names = os.listdir(current)
        if ([n for n in names if folded(n) == folded(part)] != [part]
                or (current / part).is_symlink() or not (current / part).is_dir()):
            raise Refused("Publication requires an existing exact-case directory.")
        current /= part
    filename = parts[-1]
    matches = [n for n in os.listdir(current) if folded(n) == folded(filename)]
    if matches != [filename] and (matches or not missing):
        raise Refused("Publication path is missing or has a case-equivalent collision.")
    if current.stat().st_dev != root.stat().st_dev:
        raise Refused("Publication targets must be on the bundle volume.")
    return current / filename


def stage(state, data):
    fd, name = tempfile.mkstemp(prefix="stage-", dir=state)
    with os.fdopen(fd, "wb") as stream:
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())
    return Path(name)


def install(state, target, data, *, absent=False):
    member = stage(state, data)
    try:
        if absent:
            os.link(member, target, follow_symlinks=False)  # Cannot overwrite a target.
        else:
            os.replace(member, target)
        sync_directory(target.parent)
    finally:
        member.unlink(missing_ok=True)
        sync_directory(state)


def bundle_identity(root):
    info = root.stat()
    return [info.st_dev, info.st_ino]


def read_changes(root, state):
    try:
        data = json.loads(read_file(state / PENDING, limit=PLAN_LIMIT))
        if type(data) is not dict or type(data.get("version")) is not int:
            raise ValueError
        request, clerk_session, archive_pin = None, None, None
        if data["version"] in {4, 5, 6}:
            expected = {"version", "plan", "request"}
            if data["version"] in {5, 6}:
                expected.add("clerk_session")
                from .clerk_archive import reference
                clerk_session = reference(data["clerk_session"]).uri
            if data["version"] == 6:
                expected.add("archive_sha256")
                archive_pin = data["archive_sha256"]
                if not REVISION.fullmatch(archive_pin):
                    raise ValueError
            if set(data) != expected or not valid_request(data["request"]):
                raise ValueError
            request, data = data["request"], data["plan"]
        if (type(data) is not dict or type(data.get("version")) is not int
                or data.get("bundle") != bundle_identity(root) or type(data.get("changes")) is not list):
            raise ValueError
        version = data["version"]
        if version == 1:
            if set(data) != {"version", "bundle", "changes"} or len(data["changes"]) != 3:
                raise ValueError
            operation, directory, identity = "create", None, None
        elif version == 2:
            if (set(data) != {"version", "bundle", "changes", "operation", "directory"}
                    or data["operation"] != "journal-add" or not 2 <= len(data["changes"]) <= 4):
                raise ValueError
            operation, directory, identity = "journal-add", data["directory"], None
        elif version == 3:
            if (set(data) != {"version", "bundle", "changes", "operation", "identity"}
                    or data["operation"] not in EDITS):
                raise ValueError
            operation, directory, identity = data["operation"], None, data["identity"]
        elif version == 7:
            if (set(data) != {"version", "bundle", "changes", "operation"}
                    or data["operation"] != VIDEO_STATUS_OPERATION or request is None):
                raise ValueError
            operation, directory, identity = VIDEO_STATUS_OPERATION, None, None
        elif version == 8:
            if (set(data) != {"version", "bundle", "changes", "operation", "timestamp_review"}
                    or data["operation"] != TIMESTAMP_OPERATION or request is None):
                raise ValueError
            operation, directory, identity = TIMESTAMP_OPERATION, None, None
        elif version == 9:
            if (set(data) != {"version", "bundle", "changes", "operation", "version_review"}
                    or data["operation"] != VERSION_OPERATION or request is None):
                raise ValueError
            operation, directory, identity = VERSION_OPERATION, None, None
        elif version == 10:
            if (set(data) != {"version", "bundle", "changes", "operation", "bijou_review"}
                    or data["operation"] != "bijou-place" or request is None or clerk_session is not None):
                raise ValueError
            operation, directory, identity = "bijou-place", None, None
        else:
            raise ValueError
        changes = [Change(**item) for item in data["changes"]]
        for change in changes:
            path_parts(change.path)
            if (change.after is not None and
                    (type(change.after) is not str or len(change.after.encode()) > LIMIT)
                    or change.before is not None and
                    (type(change.before) is not str or not REVISION.fullmatch(change.before))):
                raise ValueError
        if operation in EDITS:
            verify_edit_changes(changes, operation, identity)
            if clerk_session is not None:
                verify_clerk_log(changes, operation, clerk_session)
            return changes, operation, directory, identity, request, clerk_session, archive_pin
        if clerk_session is not None:
            raise ValueError
        if any(c.after is None for c in changes):
            raise ValueError
        if operation == "bijou-place":
            from .bijou import verify

            verify(root, changes, request, data["bijou_review"])
            return changes, operation, None, None, request, None, None
        if operation == VIDEO_STATUS_OPERATION:
            from .migration import verify_changes

            verify_changes(changes)
            return changes, operation, directory, identity, request, None, None
        if operation in {TIMESTAMP_OPERATION, VERSION_OPERATION}:
            from . import timestamp_cleanup, version_declaration

            handler = timestamp_cleanup if operation == TIMESTAMP_OPERATION else version_declaration
            review = data["timestamp_review" if operation == TIMESTAMP_OPERATION else "version_review"]
            base = {"originals", "actor", "digest"}
            if (type(review) is not dict or set(review) not in (base, base | {"checkpoint_sha256"})
                    or type(review["digest"]) is not str or not REVISION.fullmatch(review["digest"])
                    or type(review["actor"]) is not str or type(review["originals"]) is not list
                    or any(type(t) is not str or len(t.encode()) > LIMIT for t in review["originals"])):
                raise ValueError
            checkpoint_sha256 = review.get("checkpoint_sha256")
            if "checkpoint_sha256" in review and (type(checkpoint_sha256) is not str
                                                    or not REVISION.fullmatch(checkpoint_sha256)):
                raise ValueError
            handler.verify_changes(changes, review["originals"], review["actor"], review["digest"], request,
                                   checkpoint_sha256)
            return changes, operation, directory, identity, request, None, None
        if operation == "journal-add":
            verify_journal_changes(changes, directory)
            return changes, operation, directory, identity, request, None, None
        record, index, audit = changes
        target = PurePosixPath(record.path)
        if (not re.fullmatch(r"[0-9]{7}\.md", target.name) or record.before is not None
                or index.path != str(target.with_name("index.md")) or audit.path != "log.md"
                or index.before is None or audit.before is None):
            raise ValueError
        return changes, operation, directory, identity, request, None, None
    except (Refused, OSError, ValueError, TypeError, KeyError, RecursionError):
        raise Refused("Pending write journal is invalid; retain it for inspection.") from None


def journal_path(day):
    if not DATE.fullmatch(day) or not date_value(day):
        raise Refused("Journal date must be YYYY-MM-DD.")
    return f"{JOURNAL_ROOT}/{day[:7]}/{day}.md"


def in_journal(path):
    return folded(path).startswith(folded(JOURNAL_ROOT) + "/")


def verify_edit_changes(changes, operation, identity):
    record, *middle, audit = changes
    if (type(identity) is not str or not ID.fullmatch(identity) or any(c.before is None for c in changes)
            or audit.path != "log.md" or any(c.after is None for c in changes[1:])):
        raise ValueError
    if operation.startswith("journal-"):
        if middle or record.after is None or journal_path(PurePosixPath(record.path).stem) != record.path:
            raise ValueError
    else:
        index = str(PurePosixPath(record.path).with_name("index.md"))
        if (not concept_path(record.path) or in_journal(record.path)
                or (record.after is None) != (operation == "concept-delete")
                or [c.path for c in middle] not in ([], [index])
                or operation == "concept-delete" and not middle):
            raise ValueError
    if record.after is not None:
        verify_edit_record(record.after, operation, identity)


def verify_edit_record(text, operation, identity):
    fields = existing_fields(text, {"id", "type"}, required=True)
    if (fields.get("id") != identity or "type" not in fields
            or (fields["type"] == "Journal") != operation.startswith("journal-")):
        raise Refused("The record does not match the planned edit.")


def verify_journal_changes(changes, directory):
    record, audit = changes[0], changes[-1]
    day = PurePosixPath(record.path).stem
    month = f"{JOURNAL_ROOT}/{day[:7]}"
    if (record.path != journal_path(day) or audit.path != "log.md" or audit.before is None):
        raise ValueError
    meta, _, _ = document(record.after)
    if meta.get("type") != "Journal" or type(meta.get("id")) is not str or not ID.fullmatch(meta["id"]):
        raise ValueError
    if record.before is not None:
        if len(changes) != 2 or directory is not None:
            raise ValueError
        return
    if directory not in (None, month):
        raise ValueError
    monthly, parent = f"{month}/index.md", f"{JOURNAL_ROOT}/index.md"
    paths = [c.path for c in changes[1:-1]]
    if (paths != [p for p in (monthly, parent) if p in paths]
            or (directory is not None and monthly not in paths)
            or any((c.before is None) != (directory is not None and c.path == monthly)
                   for c in changes[1:-1])):
        raise ValueError


def verify_clerk_log(changes, operation, session):
    if operation != "concept-update" or len(changes) != 2:
        raise Refused("Clerk attribution is only supported for body-only concept updates.")
    suffix = clerk_log_suffix(session, changes[0].revision)
    if not any(line.startswith("* **Update** ") and line.endswith(suffix)
               for line in changes[-1].after.splitlines()):
        raise Refused("The pending audit does not include its Clerk snapshot and revision.")


def publish(root, state, changes, *, recovering=False, operation="create", directory=None, identity=None,
            request=None, clerk_session=None, successor=None, archive_pin=None, maintenance=False):
    if operation == "bijou-place" and successor is not None:
        raise Refused("Bijou placements are standalone-fixture operations only.")
    if operation == VIDEO_STATUS_OPERATION and successor is not None and not maintenance:
        raise Refused("Use stopped-checkpoint Video migration recovery on the adopted checkout.")
    if operation == TIMESTAMP_OPERATION and successor is not None and not maintenance:
        raise Refused("Use stopped-checkpoint timestamp recovery on the adopted checkout.")
    if operation == VERSION_OPERATION and successor is not None and not maintenance:
        raise Refused("Use stopped-checkpoint version recovery on the adopted checkout.")
    status = {"create": "created", "journal-add": "added"}.get(operation)
    result = describe(changes, status or ("deleted" if operation.endswith("-delete") else "updated"),
                      operation=operation, directory=directory, identity=identity, clerk_session=clerk_session)
    if clerk_session is not None:
        from .clerk_archive import read
        verify_clerk_log(changes, operation, clerk_session)
        read(root, clerk_session, successor=successor, pin=archive_pin)
    retained = replay(root, state, request)
    if request is not None:
        result["request_id"] = request[0]
        receipt = receipt_bytes(root, request, result)
        if len(receipt) > RECEIPT_LIMIT or (retained is not None and (not recovering or retained != result)):
            raise Refused("The receipt does not match the pending write.")

    month = safe_target(root, directory, missing=True) if directory is not None else None
    month_absent = month is not None and not present(month)
    if month is not None and not month_absent:
        info = month.lstat()
        planned = {PurePosixPath(c.path).name for c in changes if PurePosixPath(c.path).parent.as_posix() == directory}
        if (not recovering or not stat.S_ISDIR(info.st_mode) or info.st_uid != os.getuid()
                or stat.S_IMODE(info.st_mode) != 0o700 or info.st_dev != root.stat().st_dev
                or not set(os.listdir(month)) <= planned):
            raise Refused("A journal month changed; retain the original write journal.")

    def current(change):
        target = safe_target(root, change.path, missing=change.before is None or change.after is None)
        before = digest(read_file(target)) if present(target) else None
        return target, before

    # Preflight every member before changing another; recovery never rebases.
    for change in changes:
        if month_absent and PurePosixPath(change.path).parent.as_posix() == directory:
            observed = None
        else:
            _, observed = current(change)
        if observed != change.before and not (recovering and observed == change.revision):
            raise Refused("A write target changed; retain the original journal and do not overwrite it.")
    if month_absent:
        month.mkdir(mode=0o700)
        sync_directory(month.parent)
    elif month is not None:
        sync_directory(month.parent)
    for change in changes:
        target, observed = current(change)
        if recovering and observed == change.revision:
            sync_directory(target.parent)
            continue
        if observed != change.before:
            raise Refused("A target changed during publication; retain the write journal.")
        if change.after is None:
            raw = read_file(target)
            if digest(raw) != change.before:
                raise Refused("A target changed during publication; retain the write journal.")
            verify_edit_record(read_text(raw), operation, identity)
            target.unlink()
            sync_directory(target.parent)
        else:
            install(state, target, change.after.encode(), absent=change.before is None)
    for change in changes:
        _, observed = current(change)
        if observed != change.revision:
            raise Refused("Write read-back did not match; retain the journal.")
    if request is not None and retained is None:
        install(state, receipt_path(state, request[0]), receipt, absent=True)
    elif retained is not None:
        sync_directory(state)
    (state / PENDING).unlink()
    sync_directory(state)
    return result


def describe(changes, status, *, operation="create", directory=None, identity=None, clerk_session=None):
    if operation == "bijou-place":
        return {"status": "placed", "revision": changes[0].revision, "files": [c.path for c in changes]}
    if operation == VIDEO_STATUS_OPERATION:
        return {"status": "migrated", "operation": operation, "renames": len(changes) - 2,
                "index_revision": changes[-2].revision, "audit_revision": changes[-1].revision}
    if operation == TIMESTAMP_OPERATION:
        return {"status": "migrated", "operation": operation, "records": len(changes) - 1,
                "audit_revision": changes[-1].revision}
    if operation == VERSION_OPERATION:
        return {"status": "declared", "operation": operation, "okf_version": "0.3",
                "index_revision": changes[0].revision, "audit_revision": changes[1].revision}
    record = changes[0]
    result = {"status": status, "path": record.path, "id": identity or f"bho:{PurePosixPath(record.path).stem}",
              "revision": record.revision, "files": [change.path for change in changes]}
    if operation == "journal-add":
        result.update(id=existing_identity(record.after), date=PurePosixPath(record.path).stem,
                      created=record.before is None, directories=[directory] if directory else [])
    elif operation.startswith("journal-"):
        result["date"] = PurePosixPath(record.path).stem
    if operation in EDITS:
        result["previous_revision"] = record.before
    if clerk_session is not None:
        result["clerk_session"] = clerk_session
    return result


def freeze(root, state, changes, *, operation="create", directory=None, identity=None, request=None,
           clerk_session=None, archive_pin=None, timestamp_review=None, version_review=None, bijou_review=None):
    data = {"version": 1, "bundle": bundle_identity(root), "changes": [vars(change) for change in changes]}
    if operation == "journal-add":
        data.update(version=2, operation=operation, directory=directory)
    elif operation in EDITS:
        data.update(version=3, operation=operation, identity=identity)
    elif operation == VIDEO_STATUS_OPERATION:
        if request is None:
            raise Refused("The Video migration requires a durable request ID.")
        data.update(version=7, operation=operation)
    elif operation == TIMESTAMP_OPERATION:
        if request is None or timestamp_review is None:
            raise Refused("Timestamp cleanup requires a durable request and reviewed preimages.")
        data.update(version=8, operation=operation, timestamp_review=timestamp_review)
    elif operation == VERSION_OPERATION:
        if request is None or version_review is None:
            raise Refused("Version declaration requires a durable request and reviewed preimages.")
        data.update(version=9, operation=operation, version_review=version_review)
    elif operation == "bijou-place":
        if request is None or bijou_review is None:
            raise Refused("Bijou placement requires a durable request and its preimages.")
        data.update(version=10, operation=operation, bijou_review=bijou_review)
    if request is not None:
        data = {"version": 4, "plan": data, "request": request}
    if clerk_session is not None:
        if request is None:
            raise Refused("Clerk attribution requires a durable request ID.")
        data.update(version=5, clerk_session=clerk_session)
        if archive_pin is not None:
            data.update(version=6, archive_sha256=archive_pin)
    raw = json.dumps(data, ensure_ascii=False).encode()
    if len(raw) > PLAN_LIMIT:
        raise Refused("The pending write journal is too large.")
    install(state, state / PENDING, raw, absent=True)


def create(root, routes, raw, actor, *, dry_run=False, successor=None, request_id=None):
    check_authority(root, successor)
    request = write_request(request_id, "create", routes, digest(raw), actor)
    if dry_run:
        if present(root / STATE / PENDING):
            raise Refused("A write is pending; recover it before planning another.")
        return describe(plan_create(root, routes, raw, actor), "planned")
    with locked(root, successor) as state:
        if present(state / PENDING):
            raise Refused("A write is pending; run concept recover before trying another.")
        retained = replay(root, state, request)
        if retained is not None:
            return retained
        changes = plan_create(root, routes, raw, actor)
        # Freeze all before revisions and after bytes before the first canonical mutation.
        freeze(root, state, changes, request=request)
        return publish(root, state, changes, request=request)


def recover(root, *, successor=None, archive_pin=None):
    check_authority(root, successor)
    if not present(root / STATE / PENDING):
        raise Refused("No Create, concept edit, journal write or Video migration is pending.")
    with locked(root, successor) as state:
        changes, operation, directory, identity, request, clerk_session, retained_pin = read_changes(root, state)
        if retained_pin != archive_pin or (clerk_session is not None and (successor is None) != (archive_pin is None)):
            raise Refused("Recovery requires the original archive binding.")
        return publish(root, state, changes, recovering=True, operation=operation,
                       directory=directory, identity=identity, request=request, clerk_session=clerk_session,
                       successor=successor, archive_pin=archive_pin)


def edit(root, operation, prepare, *, dry_run=False, successor=None, request=None, clerk_session=None, archive_pin=None):
    check_authority(root, successor)
    if clerk_session is not None and successor is None:
        from .clerk_archive import standalone
        standalone(root)

    def checked_plan():
        require_idle(root)
        changes, identity = prepare()
        for change in changes:
            if change.after is not None:
                read_text(change.after.encode())
        verify_edit_changes(changes, operation, identity)
        if clerk_session is not None:
            from .clerk_archive import read
            verify_clerk_log(changes, operation, clerk_session)
            read(root, clerk_session, successor=successor, pin=archive_pin)
        return changes, identity

    if dry_run:
        changes, identity = checked_plan()
        return describe(changes, "planned", operation=operation, identity=identity, clerk_session=clerk_session)
    with locked(root, successor) as state:
        require_idle(root)
        retained = replay(root, state, request)
        if retained is not None:
            return retained
        changes, identity = checked_plan()
        freeze(root, state, changes, operation=operation, identity=identity, request=request,
               clerk_session=clerk_session, archive_pin=archive_pin)
        return publish(root, state, changes, operation=operation, identity=identity, request=request,
                       clerk_session=clerk_session, successor=successor, archive_pin=archive_pin)
