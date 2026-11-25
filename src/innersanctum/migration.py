"""Plan and rehearse the Personal Video field rename."""

from collections import Counter
from datetime import datetime
from pathlib import PurePosixPath

from . import writer
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


def apply_video_status(root, expected, actor, request_id):
    """Publish only to an unadopted disposable bundle through the shared writer."""
    writer.check_authority(root)
    if type(expected) is not str or not writer.REVISION.fullmatch(expected):
        raise Refused("Provide the reviewed preview digest.")
    writer.validate_actor(actor)
    operation = writer.VIDEO_STATUS_OPERATION
    request = writer.write_request(request_id, operation, expected, actor)
    if request is None:
        raise Refused("The Video migration requires a durable request ID.")
    with writer.locked(root) as state:
        writer.require_idle(root)
        retained = writer.replay(root, state, request)
        if retained is not None:
            return retained
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
        return writer.publish(root, state, changes, operation=operation, request=request)
