"""Recoverable, single-writer Create for explicitly selected standalone bundles."""

from contextlib import contextmanager
from dataclasses import dataclass
from datetime import date, datetime
import fcntl
from hashlib import sha256
import json
import os
from pathlib import Path, PurePosixPath
import re
import secrets
import stat
import tempfile
import unicodedata

from .schema import LIMIT, MANAGED, MD, Refused, document, existing_identity, path_parts, read_text, resolve_route


STATE = ".innersanctum"
PENDING = "pending-create.json"
MARKER = ".personal-writer.lock"
STRUCTURAL = {"index.md", "log.md", "AGENTS.md", "SPEC.md"}
PLAN_LIMIT = 12 * LIMIT
REVISION = re.compile(r"[0-9a-f]{64}")


def present(path):
    return path.exists() or path.is_symlink()


def folded(name):
    return unicodedata.normalize("NFC", name).casefold()


def check_authority(root, successor=None):
    matches = [name for name in os.listdir(root) if folded(name) == MARKER]
    if successor is None and matches:
        raise Refused("This bundle is managed by MatterKeep Personal. No publication was attempted.")
    if successor is not None and (matches != [MARKER]
                                  or read_file(root / MARKER, limit=256) != successor):
        raise Refused("The approved InnerSanctum writer marker changed.")


def open_bundle(path, checkout):
    root = Path(path).expanduser().absolute()
    if (root.resolve(strict=True) != root or not root.is_dir()
            or root.is_relative_to(checkout) or checkout.is_relative_to(root)
            or any(folded(part) == "synologydrive" for part in root.parts)
            or any(present(parent / ".git") for parent in (root, *root.parents))):
        raise Refused("Select a physical standalone bundle outside repositories and SynologyDrive.")
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


def visible_files(root):
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
        for name in sorted(files):
            if not name.startswith(".") and (path / name).suffix.lower() == ".md":
                candidate = path / name
                relative = candidate.relative_to(root).as_posix()
                path_parts(relative)
                yield relative, candidate


def inventory(root, *, collect_ids):
    indexes, identities = {}, set()
    for relative, path in visible_files(root):
        if path.name == "index.md":
            indexes[relative] = read_text(read_file(path))
        elif collect_ids and path.name not in STRUCTURAL:
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


def edit_log(text, path, title, actor, now):
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
        raise Refused("Root log has more than one section for the Create date.")
    entry = (f"* **Create** ({now.isoformat(timespec='seconds')}) — "
             f"[{escape_label(title)}]({encoded_path(path)}) · {escape_label(actor)}")
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
    from urllib.parse import quote

    return quote(path, safe="/")


@dataclass(frozen=True)
class Change:
    path: str
    before: str | None
    after: str


def digest(data):
    return sha256(data).hexdigest()


def plan_create(root, routes, raw, actor, *, now=None):
    if not actor.strip() or not actor.isprintable() or len(actor) > 256:
        raise Refused("Provide the actual producer as a single-line actor.")
    text = read_text(raw)
    lines, newline = lines_for(text)
    data, _, _ = document(text)
    if MANAGED.intersection(data):
        raise Refused("Omit id, generated, verified, owner and scope from Create input.")
    kind = data.get("type")
    if type(kind) is not str or not kind.strip() or not kind.isprintable():
        raise Refused("Concept input needs a nonblank type.")
    indexes, ids = inventory(root, collect_ids=True)
    route = resolve_route(kind, routes, indexes)
    for _ in range(64):
        identity = f"bho:{1_000_000 + secrets.randbelow(9_000_000)}"
        path = route.target(identity)
        filename = PurePosixPath(path).name
        if identity not in ids and folded(filename) not in map(folded, os.listdir((root / path).parent)):
            break
    else:
        raise Refused("Could not allocate an unused concept ID.")
    now = now or datetime.now().astimezone()
    generated = {"by": actor, "at": now.isoformat(timespec="seconds")}
    route.validate({**data, "id": identity, "generated": generated})
    lines[1:1] = [f'id: "{identity}"', "generated:",
                  f"  by: {json.dumps(actor, ensure_ascii=False)}",
                  f'  at: "{generated["at"]}"']
    source = newline.join(lines)
    index = indexes[route.index]
    log = read_text(read_file(root / "log.md"))
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


@contextmanager
def locked(root, successor=None):
    check_authority(root, successor)
    state = root / STATE
    try:
        state.mkdir(mode=0o700)
    except FileExistsError:
        pass
    info = state.lstat()
    if (not stat.S_ISDIR(info.st_mode) or info.st_uid != os.getuid()
            or stat.S_IMODE(info.st_mode) != 0o700 or info.st_dev != root.stat().st_dev):
        raise Refused("InnerSanctum state must be a private directory on the bundle volume.")
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
        if (set(data) != {"version", "bundle", "changes"} or type(data["version"]) is not int
                or data["version"] != 1 or data["bundle"] != bundle_identity(root)):
            raise ValueError
        if type(data["changes"]) is not list or len(data["changes"]) != 3:
            raise ValueError
        record, index, audit = changes = [Change(**item) for item in data["changes"]]
        path_parts(record.path)
        target = PurePosixPath(record.path)
        if (not re.fullmatch(r"[0-9]{7}\.md", target.name) or record.before is not None
                or index.path != str(target.with_name("index.md")) or audit.path != "log.md"
                or any(type(c.before) is not str or not REVISION.fullmatch(c.before) for c in (index, audit))
                or any(type(c.after) is not str or len(c.after.encode()) > LIMIT for c in changes)):
            raise ValueError
        return changes
    except (OSError, ValueError, TypeError, KeyError):
        raise Refused("Create journal is invalid; retain it for inspection.") from None


def publish(root, state, changes, *, recovering=False):
    def current(change):
        target = safe_target(root, change.path, missing=change.before is None)
        before = digest(read_file(target)) if present(target) else None
        return target, before

    # Preflight every member before changing another; recovery never rebases.
    for change in changes:
        _, observed = current(change)
        after = digest(change.after.encode())
        if observed != change.before and not (recovering and observed == after):
            raise Refused("A Create target changed; retain the original journal and do not overwrite it.")
    for change in changes:
        target, observed = current(change)
        data = change.after.encode()
        if recovering and observed == digest(data):
            sync_directory(target.parent)
            continue
        if observed != change.before:
            raise Refused("A Create target changed during publication; retain the journal.")
        install(state, target, data, absent=change.before is None)
    for change in changes:
        target = safe_target(root, change.path)
        if read_file(target) != change.after.encode():
            raise Refused("Create read-back did not match; retain the journal.")
    (state / PENDING).unlink()
    sync_directory(state)
    return describe(changes, "created")


def describe(changes, status):
    record = changes[0]
    return {"status": status, "path": record.path, "id": f"bho:{PurePosixPath(record.path).stem}",
            "revision": digest(record.after.encode()), "files": [change.path for change in changes]}


def create(root, routes, raw, actor, *, dry_run=False, successor=None):
    check_authority(root, successor)
    if dry_run:
        if present(root / STATE / PENDING):
            raise Refused("A Create is pending; recover it before planning another.")
        return describe(plan_create(root, routes, raw, actor), "planned")
    with locked(root, successor) as state:
        if present(state / PENDING):
            raise Refused("A Create is pending; run concept recover before trying another.")
        changes = plan_create(root, routes, raw, actor)
        data = json.dumps({"version": 1, "bundle": bundle_identity(root),
                           "changes": [vars(change) for change in changes]},
                          ensure_ascii=False).encode()
        if len(data) > PLAN_LIMIT:
            raise Refused("The Create journal is too large.")
        # Freeze all before revisions and after bytes before the first canonical mutation.
        install(state, state / PENDING, data, absent=True)
        return publish(root, state, changes)


def recover(root, *, successor=None):
    check_authority(root, successor)
    if not present(root / STATE / PENDING):
        raise Refused("No Create is pending.")
    with locked(root, successor) as state:
        return publish(root, state, read_changes(root, state), recovering=True)
