"""Private, immutable Clerk conversation snapshots outside the OKF bundle."""

from contextlib import contextmanager
from dataclasses import dataclass
import fcntl
from hashlib import sha256
import json
import os
from pathlib import Path
import re
import stat

from .schema import Refused


LIMIT = 8 * 1024 * 1024
SESSION = re.compile(r"[0-9a-f]{32}")
REFERENCE = re.compile(r"clerk-archive:([0-9a-f]{32})/([0-9a-f]{64})")
BINDING = ".owner-binding.json"
OWNER = re.compile(r"[!-~]{1,256}")
NAMESPACE = re.compile(r"[A-Za-z0-9._-]{1,80}")
SHA = re.compile(r"[0-9a-f]{64}")


@dataclass(frozen=True)
class Snapshot:
    session: str
    digest: str

    @property
    def uri(self):
        return f"clerk-archive:{self.session}/{self.digest}"

    @property
    def filename(self):
        return f"{self.session}-{self.digest}.md"


def reference(value):
    match = REFERENCE.fullmatch(value) if type(value) is str else None
    if match is None:
        raise Refused("Use the exact clerk-archive reference returned by archive storage.")
    return Snapshot(*match.groups())


def standalone(bundle):
    from . import writer

    return writer.open_bundle(bundle, Path(__file__).resolve().parents[2])


def stamp(info):
    return (info.st_dev, info.st_ino, info.st_uid, info.st_mode, info.st_nlink,
            info.st_size, info.st_mtime_ns, info.st_ctime_ns)


def private(info, *, directory=False):
    return (info.st_uid == os.getuid() and stat.S_IMODE(info.st_mode) == (0o700 if directory else 0o600)
            and (stat.S_ISDIR(info.st_mode) if directory else stat.S_ISREG(info.st_mode) and info.st_nlink == 1))


@contextmanager
def archive_directory(bundle):
    # Pin both named directories without following links or accepting case aliases.
    # The CLI has already verified the physical bundle and its authority.
    flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
    if bundle.name.casefold() == "sourcefiles":
        raise Refused("The Clerk archive must be outside the selected bundle.")
    try:
        parent = os.open(bundle.parent, flags)
        try:
            for name in ("SourceFiles", "ClerkArchive"):
                if [n for n in os.listdir(parent) if n.casefold() == name.casefold()] != [name]:
                    raise Refused("Archive storage requires exact SourceFiles/ClerkArchive directories.")
                child = os.open(name, flags, dir_fd=parent)
                os.close(parent)
                parent = child
                if not private(os.fstat(parent), directory=True):
                    raise Refused("Archive storage requires owned directories with mode 0700.")
            yield parent
        finally:
            os.close(parent)
    except OSError:
        raise Refused("The private Clerk archive is unavailable.") from None


def exact_member(directory, filename):
    matches = [name for name in os.listdir(directory) if name.casefold() == filename]
    if matches and matches != [filename]:
        raise Refused("The Clerk archive snapshot path is ambiguous.")
    return bool(matches)


def validate_source(raw):
    if not 0 < len(raw) <= LIMIT or b"\0" in raw:
        raise Refused("Provide a nonempty UTF-8 Clerk export of at most 8 MiB without NULs.")
    try:
        if not raw.decode("utf-8").strip():
            raise ValueError
    except ValueError:
        raise Refused("Provide a nonblank UTF-8 Clerk export.") from None


def read_snapshot(directory, snapshot, *, name=None, links=1, durable=False):
    filename = snapshot.filename if name is None else name
    if not exact_member(directory, filename):
        raise Refused("The referenced Clerk archive snapshot does not exist.")
    fd = os.open(filename, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=directory)
    with os.fdopen(fd, "rb") as stream:
        before = os.fstat(fd)
        if (before.st_uid != os.getuid() or stat.S_IMODE(before.st_mode) != 0o600
                or not stat.S_ISREG(before.st_mode) or before.st_nlink != links or before.st_size > LIMIT):
            raise Refused("The Clerk archive snapshot must be a private, bounded regular file.")
        raw = stream.read(LIMIT + 1)
        if (stamp(os.fstat(fd)) != stamp(before)
                or stamp(os.stat(filename, dir_fd=directory, follow_symlinks=False)) != stamp(before)
                or sha256(raw).hexdigest() != snapshot.digest):
            raise Refused("The Clerk archive snapshot does not match its retained digest.")
        if durable:
            os.fsync(fd)
    validate_source(raw)
    return raw


def binding_bytes(bundle, directory, successor, owner, namespace):
    from .handover import SUCCESSOR
    from .writer import bundle_identity, check_authority, json_bytes

    check_authority(bundle, successor)
    marker = SUCCESSOR.fullmatch(successor or b"")
    if marker is None or not OWNER.fullmatch(owner) or not NAMESPACE.fullmatch(namespace):
        raise Refused("An adopted archive requires an explicit owner and publisher namespace.")
    archive = os.fstat(directory)
    return json_bytes({"version": 1, "owner": owner, "namespace": namespace, "adoption": marker[2].decode(),
                       "bundle": bundle_identity(bundle), "archive": [archive.st_dev, archive.st_ino]})


def check_binding(bundle, directory, successor, pin):
    if type(pin) is not str or not SHA.fullmatch(pin) or not exact_member(directory, BINDING):
        raise Refused("The exact adopted archive binding is required.")
    fd = os.open(BINDING, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=directory)
    with os.fdopen(fd, "rb") as stream:
        before = os.fstat(fd)
        if not private(before) or before.st_size > 4096:
            raise Refused("The adopted archive binding must be a private regular file.")
        raw = stream.read(4097)
        if (stamp(os.fstat(fd)) != stamp(before)
                or stamp(os.stat(BINDING, dir_fd=directory, follow_symlinks=False)) != stamp(before)
                or sha256(raw).hexdigest() != pin):
            raise Refused("The adopted archive binding changed.")
    try:
        value = json.loads(raw)
        if raw != binding_bytes(bundle, directory, successor, value["owner"], value["namespace"]):
            raise ValueError
    except (ValueError, KeyError, TypeError, RecursionError):
        raise Refused("The adopted archive does not match its owner binding.") from None
    return {"owner": value["owner"], "namespace": value["namespace"], "archive_sha256": pin}


def bind(bundle, successor, owner, namespace):
    """One-time explicit operator provision of an already private, empty archive."""
    from .writer import require_idle

    require_idle(bundle)
    with archive_directory(bundle) as directory:
        lock(directory, fcntl.LOCK_EX)
        raw = binding_bytes(bundle, directory, successor, owner, namespace)
        pin = sha256(raw).hexdigest()
        if os.listdir(directory):
            if os.listdir(directory) != [BINDING]:
                raise Refused("Archive provisioning requires an empty directory; do not rebind it.")
            return check_binding(bundle, directory, successor, pin)
        fd = os.open(BINDING, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=directory)
        with os.fdopen(fd, "wb") as stream:
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
        os.fsync(directory)
        return check_binding(bundle, directory, successor, pin)


def selected(bundle, directory, successor, pin):
    if successor is not None:
        return check_binding(bundle, directory, successor, pin)
    if pin is not None:
        raise Refused("An archive binding pin requires the adopted checkout.")
    standalone(bundle)
    return None


def inspect(bundle, successor, pin):
    with archive_directory(bundle) as directory:
        lock(directory, fcntl.LOCK_SH)
        return check_binding(bundle, directory, successor, pin)


def read(bundle, uri, *, successor=None, pin=None):
    snapshot = reference(uri)
    with archive_directory(bundle) as directory:
        lock(directory, fcntl.LOCK_SH)
        selected(bundle, directory, successor, pin)
        return read_snapshot(directory, snapshot)


def lock(directory, kind):
    try:
        fcntl.flock(directory, kind | fcntl.LOCK_NB)
    except BlockingIOError:
        raise Refused("Another Clerk archive store is in progress.") from None


def store(bundle, session, raw, *, successor=None, pin=None):
    """Store a snapshot only for a standalone or explicitly bound adopted archive."""
    bundle = Path(bundle).absolute()
    if type(session) is not str or not SESSION.fullmatch(session):
        raise Refused("Choose a stable opaque session ID of 32 lowercase hex characters.")
    validate_source(raw)
    snapshot = Snapshot(session, sha256(raw).hexdigest())
    with archive_directory(bundle) as directory:
        lock(directory, fcntl.LOCK_EX)
        selected(bundle, directory, successor, pin)
        existed = exact_member(directory, snapshot.filename)
        stage = ".pending-" + snapshot.filename
        staged = exact_member(directory, stage)
        if staged:
            kept = read_snapshot(directory, snapshot, name=stage, links=2 if existed else 1, durable=True)
            if kept != raw:
                raise Refused("The pending archive snapshot differs; retain it for inspection.")
            if existed:
                st = os.stat(stage, dir_fd=directory, follow_symlinks=False)
                named = os.stat(snapshot.filename, dir_fd=directory, follow_symlinks=False)
                if stamp(st) != stamp(named):
                    raise Refused("The pending archive snapshot differs; retain it for inspection.")
        elif not existed:
            # Exclusive stage and no-clobber final link. If interrupted, the
            # exact same export can finish an intact stage under this lock.
            fd = os.open(stage, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                         0o600, dir_fd=directory)
            with os.fdopen(fd, "wb") as stream:
                stream.write(raw)
                stream.flush()
                os.fsync(stream.fileno())
        if not existed:
            os.link(stage, snapshot.filename, src_dir_fd=directory, dst_dir_fd=directory, follow_symlinks=False)
        if not existed or staged:
            os.fsync(directory)
            os.unlink(stage, dir_fd=directory)
            os.fsync(directory)
        if read_snapshot(directory, snapshot) != raw:
            raise Refused("Clerk archive read-back did not match.")
        return {"status": "existing" if existed else "archived", "reference": snapshot.uri}
