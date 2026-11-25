"""Plan and rehearse the Personal Video field rename."""

from collections import Counter
from datetime import datetime
from pathlib import Path, PurePosixPath
import re

from . import handover, writer
from .schema import ID, MD, Refused, declarations, document, existing_fields, mapping, read_text, resolve_schema, same


VIDEO_INDEX = "Resources/videos/index.md"
LEGACY_VALUES = frozenset({"watched", "watchlist", "unread", "to-read", "reading", "read"})
LIFECYCLE_VALUES = frozenset({"draft", "stable", "deprecated"})


def rename_key(text, start, stop, indent, source, target):
    """Only touch a single plain key; callers verify the resulting YAML."""
    lines = text.split("\n")
    prefix = " " * indent
    key = prefix + source + ":"
    matches = [i for i in range(start, stop) if lines[i].startswith(key)]
    if len(matches) != 1:
        raise Refused(f"Expected one plain {source} key at the supported indentation.")
    i = matches[0]
    lines[i] = prefix + target + ":" + lines[i][len(key):]
    return "\n".join(lines)


def updated_index(text, *, source="status", target="video_status"):
    original = list(declarations(text))
    video = [schema for kind, schema in original if kind == "Video"]
    if len(video) != 1:
        raise Refused("The Video index must contain one Video declaration.")
    schema = video[0]
    fields = schema.get("fields", {})
    rule = fields.get(source)
    if (type(rule) is not dict or rule.get("type") != "enum"
            or type(rule.get("values")) is not list
            or len(rule["values"]) != len(LEGACY_VALUES)
            or not all(type(value) is str and value in LEGACY_VALUES for value in rule["values"])
            or len(set(rule["values"])) != len(LEGACY_VALUES)
            or target in fields
            or any("status" in schema.get(k, ()) or "video_status" in schema.get(k, ())
                   for k in ("required", "variants", "legacy", "never"))):
        raise Refused("Expected the optional six-value legacy Video status declaration.")
    expected_fields = {(target if key == source else key): value for key, value in fields.items()}
    expected = [(kind, {**decl, "fields": expected_fields} if kind == "Video" else decl)
                for kind, decl in original]
    _, body, offset = document(text, required=False)
    for token in MD.parse(body):
        if (token.level or token.type != "fence" or token.info.strip().lower() not in {"yaml", "yml"}
                or mapping(token.content).get("okf_schema") != schema):
            continue
        start, stop = token.map
        replacement = rename_key(text, offset + start + 1, offset + stop - 1, 4, source, target)
        if list(declarations(replacement)) != expected:
            raise Refused("The declaration rename would change unrelated schema metadata.")
        return replacement
    raise Refused("Could not locate the Video declaration fence.")


def updated_record(text, data, body, offset, *, source="status", target="video_status"):
    if type(data.get(source)) is not str or data[source] not in LEGACY_VALUES or target in data:
        raise Refused("Expected one unambiguous Video viewing state to rename.")
    replacement = rename_key(text, 1, offset - 1, 0, source, target)
    expected = {(target if key == source else key): value for key, value in data.items()}
    after, after_body, _ = document(replacement)
    if not same(after, expected) or after_body != body:
        raise Refused("The field rename would change unrelated record content.")
    return replacement


def validation_issue(route, data):
    try:
        route.validate(data)
    except Refused as error:
        return str(error)
    return None


def plan_video_status(root):
    writer.require_idle(root)
    indexes, records = {}, []
    for path, file in writer.visible_files(root):
        if file.name == "index.md":
            indexes[path] = read_text(writer.read_file(file))
        elif writer.concept_path(path):
            text = read_text(writer.read_file(file))
            if existing_fields(text, {"type"}).get("type") == "Video":
                records.append((path, text))
    if VIDEO_INDEX not in indexes:
        raise Refused("The expected Video index is missing.")

    directory = str(PurePosixPath(VIDEO_INDEX).parent)
    resolve_schema("Video", directory, indexes, declaring=VIDEO_INDEX)
    replacement = updated_index(indexes[VIDEO_INDEX])
    new_indexes = {**indexes, VIDEO_INDEX: replacement}
    changes = []
    counts = Counter()
    blockers = []
    validation = Counter()
    routes = {}
    ids = set()
    for path, text in sorted(records):
        data, body, offset = document(text)
        identity = data.get("id")
        if type(identity) is not str or not ID.fullmatch(identity) or identity in ids:
            raise Refused("Expected a unique managed ID on every Video.")
        ids.add(identity)
        old, new = data.get("status"), data.get("video_status")
        is_legacy = type(old) is str and old in LEGACY_VALUES
        if "status" in data and not (is_legacy or type(old) is str and old in LIFECYCLE_VALUES):
            blockers.append({"path": path, "reason": "unrecognized status"})
            continue
        if "video_status" in data:
            if is_legacy or type(new) is not str or new not in LEGACY_VALUES:
                blockers.append({"path": path, "reason": "conflicting or invalid video_status"})
            else:
                counts["already_uses_video_status"] += 1
            continue
        if not is_legacy:
            counts["no_legacy_status"] += 1
            continue

        target = PurePosixPath(path).parent.as_posix()
        target = "/" if target == "." else target
        if target not in routes:
            routes[target] = tuple(resolve_schema("Video", target, variant, declaring=VIDEO_INDEX)
                                   for variant in (indexes, new_indexes))
        old_route, new_route = routes[target]
        after = updated_record(text, data, body, offset)
        before_issue = validation_issue(old_route, data)
        after_issue = validation_issue(new_route, document(after)[0])
        if after_issue:
            category = "preexisting" if after_issue == before_issue else "new"
            validation[category] += 1
            blockers.append({"path": path, "reason": f"{category} authoring issue: {after_issue}"})
        changes.append(writer.Change(path, writer.digest(text.encode()), after))

    declaration = writer.Change(VIDEO_INDEX, writer.digest(indexes[VIDEO_INDEX].encode()), replacement)
    raw_log = writer.read_file(writer.safe_target(root, "log.md"))
    audit_before = writer.digest(raw_log)
    writer.require_idle(root)

    def summarize(change):
        return {"path": change.path, "before": change.before, "after": change.revision}

    payload = {"status": "blocked" if blockers else "preview", "videos": len(records),
               "renames": len(changes), "already_uses_video_status": counts["already_uses_video_status"],
               "no_legacy_status": counts["no_legacy_status"], "validation_issues": dict(validation),
               "declaration": summarize(declaration), "records": [summarize(c) for c in changes],
               "audit_before": audit_before, "blockers": blockers}
    return {**payload, "digest": writer.digest(writer.json_bytes(payload))}, [*changes, declaration], raw_log


def preview_video_status(root, successor=None):
    writer.check_authority(root, successor)
    return plan_video_status(root)[0]


def verify_changes(changes):
    if (len(changes) < 2 or changes[-2].path != VIDEO_INDEX or changes[-1].path != "log.md"
            or any(c.before is None or c.after is None or c.before == c.revision for c in changes)):
        raise Refused("Invalid pending Video migration.")
    records, index, audit = changes[:-2], changes[-2], changes[-1]
    paths = [c.path for c in records]
    if paths != sorted(set(paths)) or any(not writer.concept_path(p) for p in paths):
        raise Refused("Invalid pending Video migration paths.")
    ids = set()
    for c in records:
        meta, body, offset = document(c.after)
        identity = meta.get("id")
        if meta.get("type") != "Video" or type(identity) is not str or not ID.fullmatch(identity) or identity in ids:
            raise Refused("The pending migration must contain distinct Video records.")
        ids.add(identity)
        before = updated_record(c.after, meta, body, offset, source="video_status", target="status")
        if c.before != writer.digest(before.encode()):
            raise Refused("A pending Video change is not an exact field rename.")
    before_index = updated_index(index.after, source="video_status", target="status")
    if index.before != writer.digest(before_index.encode()):
        raise Refused("The pending declaration is not an exact field rename.")
    marker = f"[{len(records)} Video records]({VIDEO_INDEX})"
    if not any(line.startswith("* **Video status migration** ") and f"— {marker} · " in line
               for line in audit.after.splitlines()):
        raise Refused("Missing pending Video migration audit entry.")


def verified_checkpoint(root, successor, checkpoint, digest=None):
    if successor is None:
        raise Refused("The stopped checkpoint requires the adopted checkout.")
    writer.check_authority(root, successor)
    snapshot, observed = handover.successor_checkpoint(root, Path(checkpoint).expanduser().absolute(), successor)
    if digest is not None and observed != digest:
        raise Refused("The canonical checkpoint differs from the reviewed digest.")
    return snapshot, observed


def inspect_checkpoint(root, successor, checkpoint):
    writer.require_idle(root)
    snapshot, digest = verified_checkpoint(root, successor, checkpoint)
    handover.compare_checkpoint(root, snapshot)
    return {"status": "verified_canonical_copy", "checkpoint_sha256": digest, "files": len(snapshot["files"])}


def migration_request(expected, actor, request_id, checkpoint_sha256=None):
    if type(expected) is not str or not writer.REVISION.fullmatch(expected):
        raise Refused("Provide the reviewed preview digest.")
    writer.validate_actor(actor)
    request = writer.write_request(request_id, writer.VIDEO_STATUS_OPERATION, expected, actor,
                                   *(() if checkpoint_sha256 is None else (checkpoint_sha256,)))
    if request is None:
        raise Refused("The Video migration requires a durable request ID.")
    return request


def apply_video_status(root, expected, actor, request_id, *, successor=None,
                       checkpoint=None, checkpoint_sha256=None, writers_stopped=False):
    """Publish a frozen Video rename through the shared writer."""
    writer.check_authority(root, successor)
    if successor is not None:
        require_stopped(root, checkpoint, checkpoint_sha256, writers_stopped)
    request = migration_request(expected, actor, request_id, checkpoint_sha256)
    operation = writer.VIDEO_STATUS_OPERATION
    with writer.locked(root, successor) as state:
        writer.require_idle(root)
        retained = writer.replay(root, state, request)
        if retained is not None:
            return retained
        if successor is not None:
            snapshot, _ = verified_checkpoint(root, successor, checkpoint, checkpoint_sha256)
            handover.compare_checkpoint(root, snapshot)
        plan, changes, raw_log = plan_video_status(root)
        if plan["digest"] != expected:
            raise Refused("The Video migration preview changed; review a fresh preview.")
        if plan["blockers"]:
            raise Refused("Resolve the Video migration blockers before applying.")
        audit = writer.edit_log(read_text(raw_log), VIDEO_INDEX, f"{plan['renames']} Video records",
                                actor, datetime.now().astimezone(), action="Video status migration")
        changes.append(writer.Change("log.md", plan["audit_before"], audit))
        for c in changes:
            read_text(c.after.encode())
        verify_changes(changes)
        writer.freeze(root, state, changes, operation=operation, request=request)
        return writer.publish(root, state, changes, operation=operation, request=request,
                              successor=successor, maintenance=successor is not None)


def require_stopped(root, checkpoint, checkpoint_sha256, writers_stopped):
    if (not writers_stopped or checkpoint is None or type(checkpoint_sha256) is not str
            or not writer.REVISION.fullmatch(checkpoint_sha256)):
        raise Refused("Require stopped writers and the reviewed canonical checkpoint digest.")
    writer.validate_state(root, root / writer.STATE)
    handover.owned(root / writer.STATE / "lock", directory=False)


def check_frozen_plan(checkpoint, expected, actor, changes):
    plan, planned, backup_log = plan_video_status(checkpoint)
    if plan["digest"] != expected or plan["blockers"] or changes[:-1] != planned:
        raise Refused("The pending Video migration differs from the reviewed plan.")
    original = read_text(backup_log)
    added = list((Counter(changes[-1].after.splitlines()) - Counter(original.splitlines())).elements())
    stamps = [match[1] for line in added
              if (match := re.match(r"^\* \*\*Video status migration\*\* \(([^)]+)\) — ", line))]
    if len(stamps) != 1:
        raise Refused("The pending audit lacks the original Video migration entry.")
    try:
        when = datetime.fromisoformat(stamps[0])
    except ValueError:
        raise Refused("The pending Video migration has an invalid audit timestamp.") from None
    audit = writer.edit_log(original, VIDEO_INDEX, f"{plan['renames']} Video records", actor, when,
                            action="Video status migration")
    if when.utcoffset() is None or changes[-1] != writer.Change("log.md", plan["audit_before"], audit):
        raise Refused("The pending audit differs from the reviewed Video migration.")


def recover_video_status(root, expected, actor, request_id, *, successor, checkpoint,
                         checkpoint_sha256, writers_stopped):
    if successor is None:
        raise Refused("Stopped-checkpoint recovery requires the adopted checkout.")
    writer.check_authority(root, successor)
    require_stopped(root, checkpoint, checkpoint_sha256, writers_stopped)
    request = migration_request(expected, actor, request_id, checkpoint_sha256)
    with writer.locked(root, successor) as state:
        changes, operation, _, _, saved, _, _ = writer.read_changes(root, state)
        if operation != writer.VIDEO_STATUS_OPERATION or saved != request:
            raise Refused("Recovery requires the original Video migration request.")
        snapshot, _ = verified_checkpoint(root, successor, checkpoint, checkpoint_sha256)
        check_frozen_plan(Path(checkpoint).expanduser().absolute(), expected, actor, changes)
        files = snapshot["files"]
        for change in changes:
            if files.get(change.path, {}).get("sha256") != change.before:
                raise Refused("A frozen target is not in the approved checkpoint.")
            raw = writer.read_file(writer.safe_target(root, change.path))
            observed = writer.digest(raw)
            if observed not in {change.before, change.revision}:
                raise Refused("A target changed; retain the original migration journal.")
            files[change.path] = {"size": len(raw), "sha256": observed}
        pending = writer.read_file(state / writer.PENDING, limit=writer.PLAN_LIMIT)
        files[f"{writer.STATE}/{writer.PENDING}"] = {"size": len(pending), "sha256": writer.digest(pending)}
        receipt = writer.receipt_path(state, request_id)
        if writer.present(receipt):
            retained = writer.replay(root, state, request)
            raw = writer.receipt_bytes(root, request, retained)
            files[f"{writer.STATE}/{receipt.name}"] = {"size": len(raw), "sha256": writer.digest(raw)}
        handover.compare_checkpoint(root, snapshot)
        return writer.publish(root, state, changes, recovering=True, operation=operation, request=request,
                              successor=successor, maintenance=True)
