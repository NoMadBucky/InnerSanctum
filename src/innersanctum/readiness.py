"""Read-only Personal OKF 0.3 checks over an explicit offline snapshot."""

from collections import Counter
from datetime import date
from pathlib import PurePosixPath
import posixpath
import re
import stat
from urllib.parse import unquote, urlsplit

from ruamel.yaml.constructor import ConstructorError, DuplicateKeyError
from ruamel.yaml.error import YAMLError

from . import handover, migration, timestamp_cleanup, writer
from .schema import MD, Refused, declarations, read_text, split_document, yaml_reader


MAX_ENTRIES = 10_000
MAX_MARKDOWN_BYTES = 64 * 1024 * 1024
MAX_FINDINGS = 1_000


def inventory(root):
    entries = {}
    for relative, path in writer.visible_files(root, include_entries=True):
        info = path.lstat()
        if not (stat.S_ISDIR(info.st_mode) or stat.S_ISREG(info.st_mode)):
            raise Refused("Snapshot contains a visible nonregular entry.")
        entries[relative] = (stat.S_ISDIR(info.st_mode), handover.stamp(info))
        if len(entries) > MAX_ENTRIES:
            raise Refused("Snapshot exceeds the readiness entry limit.")
    return entries


def frontmatter(text, reserved, report):
    if reserved and text.split("\n", 1)[0] in {"---", "---\r"}:
        report("conformance", "reserved-frontmatter")
        return None
    try:
        fm, body, _ = split_document(text, required=False)
    except Refused:
        report("conformance", "unclosed-frontmatter")
        return None
    if fm is None:
        return {}, body
    try:
        data = yaml_reader(fm, allow_opaque_tags=True).load(fm)
    except DuplicateKeyError:
        report("conformance", "duplicate-yaml-key")
        return None
    except (ConstructorError, Refused, RecursionError, OverflowError):
        report("inspection", "unsupported-yaml")
        return None
    except (YAMLError, ValueError, TypeError):
        report("conformance", "invalid-yaml")
        return None
    if type(data) is not dict:
        report("conformance", "nonmapping-frontmatter")
        return None
    if any(type(key) is not str for key in data):
        report("inspection", "unsupported-yaml-keys")
        return None
    return data, body


def check_index(body, has_contents, report):
    heading = listing = False
    list_depth = 0
    for token in MD.parse(body):
        if token.type == "heading_open" and token.level == 0:
            heading = True
        elif token.type == "list_item_open":
            list_depth += 1
        elif token.type == "list_item_close":
            list_depth -= 1
        elif heading and list_depth and token.type == "inline":
            listing |= any(child.type == "link_open" for child in token.children or ())
    if not heading:
        report("conformance", "index-without-heading")
    elif not listing and has_contents:
        report("conformance", "index-without-listing")


def check_log(body, report):
    previous = None
    # Fences and quoted examples do not supply date groups or log entries.
    tokens = MD.parse(body)
    dated = False
    for i, token in enumerate(tokens):
        if token.level != 0:
            continue
        if token.type == "heading_open" and token.tag == "h2":
            label = tokens[i + 1].content
            try:
                if not re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", label):
                    raise ValueError
                current = date.fromisoformat(label)
            except ValueError:
                report("conformance", "invalid-log-date", line=token.map[0] + 1)
                dated = False
                continue
            if previous is not None and current > previous:
                report("conformance", "log-not-newest-first", line=token.map[0] + 1)
            previous, dated = current, True
        elif token.type in {"ordered_list_open", "bullet_list_open"} and not dated:
            report("conformance", "log-entries-without-date", line=token.map[0] + 1)


def path_fields(data):
    for key in ("resource", "computation", "superseded_by"):
        yield key, data.get(key)
    for key in ("executor", "attester"):
        if type(data.get(key)) is dict:
            yield f"{key}.resource", data[key].get("resource")
    sources = data.get("sources")
    if type(sources) is dict:
        sources = [sources]
    if type(sources) is list:
        for i, source in enumerate(sources):
            if type(source) is dict:
                yield f"sources[{i}].resource", source.get("resource")


def fallback_only(value, parent, entries):
    if type(value) is not str or not value or not value.isprintable() or any(c.isspace() for c in value):
        return False
    try:
        uri = urlsplit(value)
        if uri.scheme or uri.netloc or not uri.path or value.startswith("/"):
            return False
        if re.search(r"%(?![0-9a-fA-F]{2})|%2f|%5c", uri.path, re.I):
            return False
        path = unquote(uri.path, errors="strict")
    except ValueError:
        return False
    if "\\" in path or not path.isprintable():
        return False

    def resolves(relative):
        return relative == "." or relative in entries and (not path.endswith("/") or entries[relative][0])

    local = posixpath.normpath(posixpath.join(parent, path))
    fallback = posixpath.normpath(path)
    return local != fallback and not resolves(local) and resolves(fallback)


def check_video_index(text, report):
    try:
        video = [schema for kind, schema in declarations(text) if kind == "Video"]
    except Refused:
        video = []
    fields = video[0].get("fields") if len(video) == 1 else None

    def viewing_enum(key):
        rule = fields.get(key)
        values = rule.get("values") if type(rule) is dict and rule.get("type") == "enum" else None
        return (type(values) is list and len(values) == len(migration.LEGACY_VALUES)
                and all(type(value) is str for value in values) and set(values) == migration.LEGACY_VALUES)

    if type(fields) is dict and viewing_enum("status"):
        report("migration", "legacy-video-declaration")
    elif type(fields) is not dict or not viewing_enum("video_status"):
        report("migration", "unrecognized-video-declaration")


def check_concept(path, text, data, entries, report):
    kind = data.get("type")
    if kind is None or kind == "" or kind == []:
        return
    if type(kind) is not str or not kind.strip():
        report("conformance", "invalid-concept-type")
        return
    if kind == "Video":
        status = data.get("status")
        legacy = type(status) is str and status in migration.LEGACY_VALUES
        if legacy:
            report("migration", "conflicting-video-state" if "video_status" in data else "legacy-video-state")
        elif "status" in data and (type(status) is not str or status not in migration.LIFECYCLE_VALUES):
            report("migration", "unrecognized-video-status")
        current = data.get("video_status")
        if "video_status" in data and (type(current) is not str or current not in migration.LEGACY_VALUES):
            report("migration", "invalid-video-state")
    if writer.concept_path(path):
        try:
            _, timestamps = timestamp_cleanup.plan_record(text)
        except Refused:
            report("migration", "unsupported-timestamp-cleanup")
        else:
            if timestamps:
                report("migration", "timestamp-cleanup-needed")
    parent = posixpath.dirname(path)
    for field, value in path_fields(data):
        if fallback_only(value, parent, entries):
            report("migration", "v02-path-fallback", field=field)


def require_idle(root):
    state = root / writer.STATE
    if writer.present(state) and not stat.S_ISDIR(state.lstat().st_mode):
        raise Refused("Snapshot writer state is not a physical directory.")
    if writer.present(state / writer.PENDING):
        raise Refused("Snapshot contains a pending write; select a settled copy.")


def inspect(path, checkout):
    # A stopped copy may retain its writer marker. This selector grants no writer
    # authority or access to a repository, registry, or running checkout.
    root = writer.external_root(path, checkout)
    require_idle(root)
    entries = inventory(root)
    contents = Counter(posixpath.dirname(path) for path in entries)
    manifest, findings = {}, []
    total = 0
    version = None

    def issue(group, code, path, **context):
        if len(findings) >= MAX_FINDINGS:
            raise Refused("Snapshot exceeds the readiness findings limit.")
        findings.append({"group": group, "code": code, "path": path, **context})

    for required in ("index.md", "log.md", migration.VIDEO_INDEX):
        if required not in entries or entries[required][0]:
            issue("migration", "missing-personal-file", required)
    for relative, (directory, evidence) in sorted(entries.items()):
        if directory or not relative.endswith(".md"):
            manifest[relative] = "directory" if directory else "asset"
            continue

        def report(group, code, **context):
            issue(group, code, relative, **context)

        raw = writer.read_file(root / relative)
        total += len(raw)
        if total > MAX_MARKDOWN_BYTES:
            raise Refused("Snapshot exceeds the readiness Markdown byte limit.")
        if handover.stamp((root / relative).lstat()) != evidence:
            raise Refused("Snapshot changed during readiness inspection.")
        manifest[relative] = writer.digest(raw)
        try:
            text = read_text(raw)
        except Refused:
            report("conformance", "invalid-utf8")
            continue
        name = PurePosixPath(relative).name
        parsed = frontmatter(text, relative != "index.md" and name in {"index.md", "log.md"}, report)
        if parsed is None:
            continue
        data, body = parsed
        if relative == "index.md" and "okf_version" in data:
            declared = data["okf_version"]
            version = declared if declared in ("0.2", "0.3") else "other"
            if type(declared) is not str or not re.fullmatch(r"[0-9]+\.[0-9]+", declared):
                report("conformance", "invalid-version")
            elif declared != "0.3":
                report("migration", "existing-version-blocks-declaration")
        if name == "index.md":
            check_index(body, contents[posixpath.dirname(relative)] > 1, report)
            if relative == migration.VIDEO_INDEX:
                check_video_index(text, report)
        elif name == "log.md":
            check_log(body, report)
        else:
            check_concept(relative, text, data, entries, report)
    if inventory(root) != entries:
        raise Refused("Snapshot changed during readiness inspection.")
    require_idle(root)
    return {"status": "blocked" if findings else "ready", "target_version": "0.3", "declared_version": version,
            "inventory_sha256": writer.digest(writer.json_bytes(manifest)), "findings": findings,
            "unchecked": ["reader-compatibility", "trust-tiers", "body-link-targets", "attachment-contents",
                          "workspace-schema-and-catalog", "timestamp-semantics"]}
