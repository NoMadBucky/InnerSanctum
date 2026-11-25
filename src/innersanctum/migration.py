"""Read-only preview of the Personal Video field rename."""

from collections import Counter
import json
from pathlib import PurePosixPath
import re

from . import writer
from .schema import ID, MD, Refused, declarations, document, existing_fields, mapping, read_text, resolve_schema


VIDEO_INDEX = "Resources/videos/index.md"
LEGACY_VALUES = frozenset({"watched", "watchlist", "unread", "to-read", "reading", "read"})
LIFECYCLE_VALUES = frozenset({"draft", "stable", "deprecated"})


def rename_key(lines, start, stop, indent):
    """Only touch a single plain key; callers verify the resulting YAML."""
    prefix = " " * indent
    matches = [i for i in range(start, stop) if lines[i].startswith(prefix + "status:")]
    if len(matches) != 1:
        raise Refused("Expected one plain status key at the supported indentation.")
    i = matches[0]
    lines[i] = prefix + "video_" + lines[i][len(prefix):]
    return "".join(lines)


def updated_index(text):
    original = list(declarations(text))
    video = [schema for kind, schema in original if kind == "Video"]
    if len(video) != 1:
        raise Refused("The Video index must contain one Video declaration.")
    schema = video[0]
    fields = schema.get("fields", {})
    rule = fields.get("status")
    if (type(rule) is not dict or rule.get("type") != "enum"
            or type(rule.get("values")) is not list
            or len(rule["values"]) != len(LEGACY_VALUES)
            or not all(type(value) is str and value in LEGACY_VALUES for value in rule["values"])
            or len(set(rule["values"])) != len(LEGACY_VALUES)
            or "video_status" in fields
            or any("status" in schema.get(k, ()) or "video_status" in schema.get(k, ())
                   for k in ("required", "variants", "legacy", "never"))):
        raise Refused("Expected the optional six-value legacy Video status declaration.")
    expected_fields = {("video_status" if key == "status" else key): value
                       for key, value in fields.items()}
    expected = [(kind, {**decl, "fields": expected_fields} if kind == "Video" else decl)
                for kind, decl in original]
    _, body, offset = document(text, required=False)
    for token in MD.parse(body):
        if (token.level or token.type != "fence" or token.info.strip().lower() not in {"yaml", "yml"}
                or mapping(token.content).get("okf_schema") != schema):
            continue
        start, stop = token.map
        replacement = rename_key(text.splitlines(keepends=True), offset + start + 1,
                                 offset + stop - 1, indent=4)
        if list(declarations(replacement)) != expected:
            raise Refused("The declaration rename would change unrelated schema metadata.")
        return replacement
    raise Refused("Could not locate the Video declaration fence.")


def updated_record(text, data, body, offset):
    replacement = rename_key(text.splitlines(keepends=True), 1, offset - 1, indent=0)
    expected = {("video_status" if key == "status" else key): value for key, value in data.items()}
    after, after_body, _ = document(replacement)
    if after != expected or after_body != body:
        raise Refused("The field rename would change unrelated record content.")
    return replacement


def validation_issue(route, data):
    try:
        route.validate(data)
    except Refused as error:
        return str(error)
    return None


def preview_video_status(root, successor=None):
    writer.check_authority(root, successor)
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
    entries = []
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
        entries.append({"path": path, "before": writer.digest(text.encode()),
                        "after": writer.digest(after.encode())})

    declaration = {"path": VIDEO_INDEX, "before": writer.digest(indexes[VIDEO_INDEX].encode()),
                   "after": writer.digest(replacement.encode())}
    payload = {"declaration": declaration, "records": entries, "blockers": blockers}
    writer.require_idle(root)
    return {"status": "blocked" if blockers else "preview", "videos": len(records),
            "renames": len(entries), "already_uses_video_status": counts["already_uses_video_status"],
            "no_legacy_status": counts["no_legacy_status"], "validation_issues": dict(validation),
            "digest": writer.digest(json.dumps(payload, sort_keys=True).encode()),
            **payload}
