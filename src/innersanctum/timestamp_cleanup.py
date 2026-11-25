"""Preview format-only timestamp changes without rewriting YAML or Markdown."""

from collections import Counter
import re

from ruamel.yaml.error import YAMLError
from ruamel.yaml.nodes import MappingNode, ScalarNode, SequenceNode
from ruamel.yaml.tokens import ScalarToken, TagToken

from . import writer
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


def preview(root, successor=None):
    writer.check_authority(root, successor)
    writer.require_idle(root)
    counts = Counter()
    edits, blockers = [], []
    for relative, path in writer.visible_files(root):
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
            edits.append({"path": relative, "before": writer.digest(original.encode()),
                          "after": writer.digest(replacement.encode()), "changes": dict(local)})
            counts.update(local)
    writer.require_idle(root)
    result = {"status": "blocked" if blockers else "preview", "records": edits, "blockers": blockers,
              "provenance_timestamps": counts["provenance_timestamps"], "explicit_tags": counts["explicit_tags"]}
    return {**result, "digest": writer.digest(writer.json_bytes(result))}
