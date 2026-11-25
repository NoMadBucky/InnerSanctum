"""Plan and rehearse format-only timestamp changes."""

from collections import Counter
from datetime import datetime
from pathlib import Path
import re

from ruamel.yaml.error import YAMLError
from ruamel.yaml.nodes import MappingNode, ScalarNode, SequenceNode
from ruamel.yaml.tokens import ScalarToken, TagToken

from . import handover, migration, writer
from .schema import Refused, existing_fields, mapping, read_text, same, split_document, yaml_reader


NATIVE_TIMESTAMP = "tag:yaml.org,2002:timestamp"
PROVENANCE_PATHS = {("generated", "at"), ("verified", "at"), ("verified", "[]", "at")}
TAG_PATHS = {("created",), ("start",), ("due",)}
DATE = re.compile(r"\d{4}-\d\d-\d\d\Z", re.ASCII)
DATETIME = re.compile(
    r"(\d{4}-\d\d-\d\d)([Tt]|[ \t]+)(\d\d:\d\d:\d\d(?:\.\d+)?)([ \t]*)(Z|[+-]\d\d:\d\d)\Z",
    re.ASCII,
)


def scalar_paths(node, path=()):
    if isinstance(node, MappingNode):
        for key, value in node.value:
            if isinstance(key, ScalarNode):
                yield from scalar_paths(value, (*path, key.value))
    elif isinstance(node, SequenceNode):
        for value in node.value:
            yield from scalar_paths(value, (*path, "[]"))
    elif isinstance(node, ScalarNode):
        yield path, node


def canonical_text(value):
    if DATE.fullmatch(value):
        return value
    if match := DATETIME.fullmatch(value):
        return f"{match[1]}T{match[3]}{match[5]}"
    return None


def plan_record(text):
    fm, _, _ = split_document(text, required=False)
    if fm is None:
        return text, Counter()
    try:
        reader = yaml_reader(fm, allow_opaque_tags=True)
        node = reader.compose(fm)
        selected = []
        for path, value in scalar_paths(node):
            if value.tag != NATIVE_TIMESTAMP:
                continue
            canonical = canonical_text(value.value)
            if path in PROVENANCE_PATHS and canonical is not None and value.value != canonical and value.style is None:
                selected.append((path, value, canonical))
            elif path in TAG_PATHS:
                selected.append((path, value, canonical))
        if not selected:
            return text, Counter()
        tokens = list(reader.scan(fm))
        tags = {t.start_mark.index: t for t in tokens if isinstance(t, TagToken)}
        scalars = {t.end_mark.index: t for t in tokens if isinstance(t, ScalarToken)}
        changes = []
        counts = Counter()
        for path, value, canonical in selected:
            start, end = value.start_mark.index, value.end_mark.index
            tag = tags.get(start)
            if path in TAG_PATHS and tag is None:
                continue
            token = scalars.get(end)
            if (canonical is None or token is None or token.value != value.value
                    or "\n" in fm[start:end] or "\r" in fm[start:end]):
                raise Refused("A timestamp does not have a safely supported scalar spelling.")
            if tag is not None:
                if (path not in TAG_PATHS or tag.value != ("!!", "timestamp")
                        or not re.fullmatch(r"[ \t]+", fm[tag.end_mark.index:token.start_mark.index])):
                    raise Refused("A timestamp tag lacks a supported single-line scalar.")
                counts["explicit_tags"] += 1
            else:
                if token.start_mark.index != start:
                    raise Refused("A timestamp scalar does not match the planned edit.")
                counts["provenance_timestamps"] += 1
            changes.append((start, end, canonical))
        if not changes:
            return text, counts
        replacement = fm
        for start, end, canonical in sorted(changes, reverse=True):
            replacement = replacement[:start] + canonical + replacement[end:]
        if not same(reader.load(fm), mapping(replacement)):
            raise Refused("Timestamp edits would change parsed metadata values or types.")
    except (YAMLError, ValueError, TypeError, RecursionError, OverflowError):
        raise Refused("Timestamp cleanup could not safely read the frontmatter.") from None
    start = text.index("\n") + 1
    return text[:start] + replacement + text[start + len(fm):], counts


AUDIT_ACTION = "Timestamp formatting"


def plan(root):
    writer.require_idle(root)
    counts = Counter()
    edits, changes, originals, blockers = [], [], [], []
    for relative, path in sorted(writer.visible_files(root)):
        if not writer.concept_path(relative):
            continue
        original = read_text(writer.read_file(path))
        try:
            if not existing_fields(original, {"type"}).get("type"):
                continue
            replacement, local = plan_record(original)
        except Refused as error:
            blockers.append({"path": relative, "reason": str(error)})
            continue
        if replacement != original:
            change = writer.Change(relative, writer.digest(original.encode()), replacement)
            edits.append({"path": relative, "before": change.before, "after": change.revision, "changes": dict(local)})
            changes.append(change)
            originals.append(original)
            counts.update(local)
    original_log = read_text(writer.read_file(writer.safe_target(root, "log.md")))
    writer.require_idle(root)
    result = {"status": "blocked" if blockers else "preview", "records": edits, "blockers": blockers,
              "audit_before": writer.digest(original_log.encode()),
              "provenance_timestamps": counts["provenance_timestamps"], "explicit_tags": counts["explicit_tags"]}
    return {**result, "digest": writer.digest(writer.json_bytes(result))}, changes, [*originals, original_log]


def preview(root, successor=None):
    writer.check_authority(root, successor)
    return plan(root)[0]


def audit_update(original, count, actor, when):
    return writer.edit_log(original, "index.md", f"{count} concept records", actor, when, action=AUDIT_ACTION)


def verify_changes(changes, originals, actor, expected, request, checkpoint_sha256=None):
    """Check frozen scope and reproduce each edit from its retained original."""
    writer.validate_actor(actor)
    if (len(changes) < 2 or type(originals) is not list or len(changes) != len(originals)
            or changes[-1].path != "log.md" or any(type(x) is not str for x in originals)):
        raise Refused("Invalid pending timestamp cleanup.")
    paths = [c.path for c in changes[:-1]]
    if paths != sorted(set(paths)) or any(not writer.concept_path(p) for p in paths):
        raise Refused("Invalid pending timestamp cleanup paths.")
    if any(c.before != writer.digest(before.encode()) or c.after is None or c.after == before
           for c, before in zip(changes, originals)):
        raise Refused("Invalid timestamp cleanup before or after revisions.")
    edits, total = [], Counter()
    for c, before in zip(changes[:-1], originals[:-1]):
        if not existing_fields(before, {"type"}).get("type"):
            raise Refused("Only typed concepts can be formatted.")
        replacement, counts = plan_record(before)
        if c.after != replacement:
            raise Refused("The pending concept differs from the format-only change.")
        total.update(counts)
        edits.append({"path": c.path, "before": c.before, "after": c.revision, "changes": dict(counts)})
    result = {"status": "preview", "records": edits, "blockers": [], "audit_before": changes[-1].before,
              "provenance_timestamps": total["provenance_timestamps"], "explicit_tags": total["explicit_tags"]}
    if (expected != writer.digest(writer.json_bytes(result))
            or request != migration_request(expected, actor, request[0], checkpoint_sha256)):
        raise Refused("Pending timestamp cleanup differs from the approved preview.")
    added = (Counter(changes[-1].after.splitlines()) - Counter(originals[-1].splitlines())).elements()
    stamps = [match[1] for line in added
              if (match := re.match(r"^\* \*\*Timestamp formatting\*\* \(([^)]+)\) — ", line))]
    if len(stamps) != 1:
        raise Refused("Missing the original timestamp cleanup audit entry.")
    try:
        when = datetime.fromisoformat(stamps[0])
    except ValueError:
        raise Refused("Invalid timestamp cleanup audit time.") from None
    if when.utcoffset() is None or changes[-1].after != audit_update(originals[-1], len(edits), actor, when):
        raise Refused("Pending timestamp cleanup changed unrelated audit text.")


def migration_request(expected, actor, request_id, checkpoint_sha256=None):
    if type(expected) is not str or not writer.REVISION.fullmatch(expected):
        raise Refused("Provide the reviewed preview digest.")
    writer.validate_actor(actor)
    request = writer.write_request(request_id, writer.TIMESTAMP_OPERATION, expected, actor,
                                   *(() if checkpoint_sha256 is None else (checkpoint_sha256,)))
    if request is None:
        raise Refused("Timestamp cleanup requires a durable request ID.")
    return request


def rehearse(root, expected, actor, request_id):
    return _apply(root, expected, actor, request_id)


def apply(root, expected, actor, request_id, *, successor, checkpoint, checkpoint_sha256, writers_stopped):
    if successor is None:
        raise Refused("Stopped-checkpoint timestamp apply requires the adopted checkout.")
    migration.require_stopped(root, checkpoint, checkpoint_sha256, writers_stopped)
    return _apply(root, expected, actor, request_id, successor=successor, checkpoint=checkpoint,
                  checkpoint_sha256=checkpoint_sha256)


def _apply(root, expected, actor, request_id, *, successor=None, checkpoint=None, checkpoint_sha256=None):
    writer.check_authority(root, successor)
    request = migration_request(expected, actor, request_id, checkpoint_sha256)
    operation = writer.TIMESTAMP_OPERATION
    with writer.locked(root, successor) as state:
        writer.require_idle(root)
        if (receipt := writer.replay(root, state, request)) is not None:
            return receipt
        if successor is not None:
            snapshot, _ = migration.verified_checkpoint(root, successor, checkpoint, checkpoint_sha256)
            handover.compare_checkpoint(root, snapshot)
        result, changes, originals = plan(root)
        if result["digest"] != expected:
            raise Refused("The timestamp cleanup preview changed; review a fresh preview.")
        if result["blockers"] or not changes:
            raise Refused("Timestamp cleanup requires a nonempty preview without blockers.")
        audit = audit_update(originals[-1], len(changes), actor, datetime.now().astimezone())
        changes.append(writer.Change("log.md", result["audit_before"], audit))
        for c in changes:
            read_text(c.after.encode())
        verify_changes(changes, originals, actor, expected, request, checkpoint_sha256)
        review = {"actor": actor, "digest": expected, "originals": originals}
        if successor is not None:
            review["checkpoint_sha256"] = checkpoint_sha256
        writer.freeze(root, state, changes, operation=operation, request=request, timestamp_review=review)
        return writer.publish(root, state, changes, operation=operation, request=request,
                              successor=successor, maintenance=successor is not None)


def recover(root, expected, actor, request_id, *, successor, checkpoint, checkpoint_sha256, writers_stopped):
    if successor is None:
        raise Refused("Stopped-checkpoint timestamp recovery requires the adopted checkout.")
    writer.check_authority(root, successor)
    migration.require_stopped(root, checkpoint, checkpoint_sha256, writers_stopped)
    request = migration_request(expected, actor, request_id, checkpoint_sha256)
    with writer.locked(root, successor) as state:
        changes, operation, _, _, saved, _, _ = writer.read_changes(root, state)
        if operation != writer.TIMESTAMP_OPERATION or saved != request:
            raise Refused("Recovery requires the original timestamp cleanup request.")
        snapshot, _ = migration.verified_checkpoint(root, successor, checkpoint, checkpoint_sha256)
        result, planned, _ = plan(Path(checkpoint).expanduser().absolute())
        if result["digest"] != expected or result["blockers"] or changes[:-1] != planned:
            raise Refused("The pending timestamp cleanup differs from the checkpoint preview.")
        migration.check_recovery_snapshot(root, state, changes, snapshot, request)
        return writer.publish(root, state, changes, recovering=True, operation=operation, request=request,
                              successor=successor, maintenance=True)
