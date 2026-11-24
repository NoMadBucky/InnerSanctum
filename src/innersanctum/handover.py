"""Exact-checkout writer fencing; service and checkpoint control stay external."""

from contextlib import contextmanager
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import subprocess

from .schema import Refused
from . import writer


PERSONAL = re.compile(rb"personal-writer-2\n[0-9a-f]{64}\n")
SUCCESSOR = re.compile(rb"innersanctum-writer-1\n([0-9a-f]{64})\n([0-9a-f]{64})\n")
CHECKPOINT_LIMIT = 16 * 1024 * 1024


def owned(path, *, directory):
    info = path.lstat()
    if (info.st_uid != os.getuid()
            or not (stat.S_ISDIR(info.st_mode) if directory else stat.S_ISREG(info.st_mode))
            or stat.S_IMODE(info.st_mode) != (0o700 if directory else 0o600)
            or (not directory and info.st_nlink != 1)):
        raise Refused("Live cutover requires owned private directories and files.")
    return info


def physical(path):
    return (path.is_absolute() and path.resolve(strict=True) == path
            and all(item == item.parent or item.name in os.listdir(item.parent)
                    for item in (path, *path.parents)))


def git(checkout, *args, data=None):
    command = ["/usr/bin/git", "--no-optional-locks", f"--git-dir={checkout / '.git'}",
               f"--work-tree={checkout}", "-c", "core.fsmonitor=false",
               "-c", "core.excludesFile=/dev/null", *args]
    env = {"PATH": "/usr/bin:/bin", "LC_ALL": "C", "GIT_CONFIG_NOSYSTEM": "1",
           "GIT_CONFIG_GLOBAL": "/dev/null", "GIT_TERMINAL_PROMPT": "0",
           "GIT_NO_LAZY_FETCH": "1", "GIT_NO_REPLACE_OBJECTS": "1"}
    try:
        return subprocess.run(command, cwd=checkout, env=env, input=data, stdout=subprocess.PIPE,
                              stderr=subprocess.DEVNULL, timeout=10, check=True).stdout
    except subprocess.SubprocessError:
        raise Refused("The checkout's Git safety checks failed.") from None


def checkout_bundle(checkout):
    if (checkout.name != "InnerSanctum" or not physical(checkout)
            or any(writer.folded(part) == "synologydrive" for part in checkout.parts)
            or any(writer.present(parent / ".git") for parent in checkout.parents)):
        raise Refused("Live use is restricted to the exact InnerSanctum checkout.")
    metadata = checkout / ".git"
    ignore = checkout / ".gitignore"
    if (metadata.is_symlink() or not metadata.is_dir()
            or any(writer.present(metadata / name) for name in ("commondir", "gitdir"))
            or not stat.S_ISREG(ignore.lstat().st_mode)):
        raise Refused("Live use needs a physical, independent Git checkout.")
    data_roots = (checkout / "OKF", checkout / "SourceFiles")
    for root in data_roots:
        if not physical(root):
            raise Refused("A live data root is not physical and exact-case.")
        owned(root, directory=True)
        for parent, dirs, files in os.walk(root, onerror=raise_error):
            if any(writer.folded(name) == ".git" for name in (*dirs, *files)):
                raise Refused("A live data root contains nested Git metadata.")
    if git(checkout, "ls-files", "--cached", "-z", "--", ":(icase)OKF", ":(icase)SourceFiles"):
        raise Refused("Live data must not be Git-tracked.")
    tracked = git(checkout, "ls-tree", "--full-tree", "--name-only", "-z", "HEAD")
    if {b"okf", b"sourcefiles"} & set(tracked.lower().split(b"\0")):
        raise Refused("Live data must not appear in HEAD.")
    paths = (b"OKF/", b"SourceFiles/")
    evidence = git(checkout, "check-ignore", "--no-index", "-v", "-z", "--stdin",
                   data=b"\0".join(paths) + b"\0").split(b"\0")
    if (len(evidence) != 9 or evidence[-1] or any(
            evidence[i] != b".gitignore" or not evidence[i + 1].isdigit()
            or evidence[i + 2] != b"/" + path or evidence[i + 3] != path
            for i, path in zip((0, 4), paths))):
        raise Refused("Live data needs the two checkout-wide .gitignore rules.")
    return data_roots[0]


def raise_error(error):
    raise error


def binding(root):
    return writer.digest(json.dumps([str(root), *writer.bundle_identity(root)],
                                    ensure_ascii=True).encode()).encode("ascii")


@contextmanager
def marker_locked(root):
    matches = [name for name in os.listdir(root) if writer.folded(name) == writer.MARKER]
    if matches != [writer.MARKER]:
        raise Refused("The exact canonical writer marker is required.")
    marker = root / writer.MARKER
    before = owned(marker, directory=False)
    flags = os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK
    with os.fdopen(os.open(marker, flags), "rb") as stream:
        try:
            fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise Refused("The canonical writer marker is busy.") from None
        assert_marker(marker, stream, before)
        data = stream.read(257)
        if len(data) > 256:
            raise Refused("Invalid canonical writer marker.")
        yield marker, stream, before, data


def assert_marker(marker, stream, before):
    if stamp(owned(marker, directory=False)) != stamp(before) or stamp(os.fstat(stream.fileno())) != stamp(before):
        raise Refused("The canonical writer marker changed.")


def stamp(info):
    return (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns)


@contextmanager
def live_checkout(checkout):
    root = checkout_bundle(checkout)
    with marker_locked(root) as (_, _, _, raw):
        successor = SUCCESSOR.fullmatch(raw)
        if successor is None or successor[1] != binding(root):
            raise Refused("InnerSanctum does not own this checkout. No write was attempted.")
        yield root, raw


def compare_checkpoint(root, snapshot):
    """Check the canonical stopped preimage, not Notes/Auth or checkpoint custody."""
    files, directories = snapshot["files"], snapshot["directories"]
    if type(files) is not dict or type(directories) is not dict:
        raise ValueError
    observed_files, observed_dirs = set(), set()
    for parent, children, names in os.walk(root, followlinks=False, onerror=raise_error):
        path = Path(parent)
        owned(path, directory=True)
        relative = path.relative_to(root).as_posix()
        observed_dirs.add("" if relative == "." else relative)
        for name in children:
            owned(path / name, directory=True)
        for name in names:
            target = path / name
            relative = target.relative_to(root).as_posix()
            if relative not in files:
                raise Refused("Canonical inventory changed after the checkpoint.")
            size = owned(target, directory=False).st_size
            expected = files[relative]
            if size != expected["size"] or writer.digest(writer.read_file(target, limit=CHECKPOINT_LIMIT)) != expected["sha256"]:
                raise Refused("Canonical bytes changed after the checkpoint.")
            observed_files.add(relative)
    if observed_files != set(files) or observed_dirs != set(directories):
        raise Refused("Canonical inventory changed after the checkpoint.")


def verify_notes(checkpoint, expected, source):
    if (type(expected) is not dict or type(source) is not dict
            or set(expected) != set(source) or "notes.sqlite3" not in expected
            or set(expected) - {"notes.sqlite3", "notes.sqlite3-journal", "notes.sqlite3-wal",
                                "notes.sqlite3-shm"}):
        raise ValueError
    notes = checkpoint / "notes"
    owned(notes, directory=True)
    if set(os.listdir(notes)) != set(expected):
        raise ValueError
    for name, record in expected.items():
        path = notes / name
        info = owned(path, directory=False)
        if any(source[name][key] != record[key] for key in ("size", "sha256")):
            raise ValueError
        with os.fdopen(os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK), "rb") as stream:
            if (stamp(os.fstat(stream.fileno())) != stamp(info) or info.st_size != record["size"]
                    or hashlib.file_digest(stream, "sha256").hexdigest() != record["sha256"]
                    or stamp(os.fstat(stream.fileno())) != stamp(info) or stamp(path.lstat()) != stamp(info)):
                raise ValueError


def verify_evidence(root, checkpoint, approved, old):
    if (type(approved) is not str or not writer.REVISION.fullmatch(approved)
            or not physical(checkpoint)
            or checkpoint.is_relative_to(root.parent) or root.parent.is_relative_to(checkpoint)
            or any(writer.present(parent / ".git") for parent in (checkpoint, *checkpoint.parents))):
        raise Refused("Use an exact, approved external Personal checkpoint receipt.")
    owned(checkpoint, directory=True)
    owned(checkpoint.parent, directory=True)
    if (set(os.listdir(checkpoint)) != {"canonical", "notes", "handoff.json", "receipt.json"}
            or checkpoint.parent.stat().st_dev != root.stat().st_dev):
        raise Refused("The completed checkpoint must be on the bundle volume.")
    try:
        paths = (checkpoint / "receipt.json", checkpoint / "handoff.json")
        for path in paths:
            owned(path, directory=False)
        receipt, handoff = [writer.read_file(path, limit=CHECKPOINT_LIMIT) for path in paths]
        if writer.digest(receipt) != approved:
            raise ValueError
        seal, evidence = json.loads(receipt), json.loads(handoff)
        if (seal["format"] != "personal-clean-checkpoint-2"
                or seal["handoff_sha256"] != writer.digest(handoff)
                or evidence["format"] != "personal-pair-handoff-2"
                or evidence["binding"]["okf"] != str(root)
                or evidence["marker"].encode("ascii") != old):
            raise ValueError
        state = Path(evidence["binding"]["state"])
        if not state.is_absolute() or checkpoint.is_relative_to(state) or state.is_relative_to(checkpoint):
            raise ValueError
        canonical = checkpoint / "canonical"
        owned(canonical, directory=True)
        owned(canonical / writer.MARKER, directory=False)
        if writer.read_file(canonical / writer.MARKER, limit=256) != old:
            raise ValueError
        stopped = evidence["snapshot"]["canonical"]
        compare_checkpoint(canonical, stopped)
        compare_checkpoint(root, stopped)
        notes = seal["checkpoint"]["notes"]
        verify_notes(checkpoint, notes, seal["source_notes"])
        if any(evidence["snapshot"]["database"][key] != notes["notes.sqlite3"][key]
               for key in ("size", "sha256")):
            raise ValueError
    except (ValueError, TypeError, KeyError, AttributeError):
        raise Refused("The stopped checkpoint does not match the approved canonical pair.") from None


def adopt(checkout, checkpoint, approved, *, writers_stopped):
    if not writers_stopped:
        raise Refused("Explicit stopped-writer and publisher exclusion is required.")
    root = checkout_bundle(checkout)
    with marker_locked(root) as (marker, stream, before, old):
        if not PERSONAL.fullmatch(old):
            raise Refused("Expected the active Personal v2 marker; do not reapply a handover.")
        if writer.present(root / writer.STATE):
            raise Refused("Unexpected InnerSanctum state before handover.")
        checkpoint = Path(checkpoint).absolute()
        verify_evidence(root, checkpoint, approved, old)
        successor = b"innersanctum-writer-1\n" + binding(root) + b"\n" + approved.encode("ascii") + b"\n"
        # One atomic fence switch. Personal rejects the new marker format;
        # processes waiting on the old inode fail Personal's inode recheck.
        # The checkpoint retains the exact original marker and Notes state.
        assert_marker(marker, stream, before)
        writer.install(checkpoint.parent, marker, successor)
        if writer.read_file(marker, limit=256) != successor:
            raise Refused("Handover was not confirmed. Do not retry or restart Personal.")
    return {"status": "adopted", "checkpoint_sha256": approved}
