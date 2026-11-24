"""Read and revise existing concepts without moving or reidentifying them."""

from datetime import datetime
from pathlib import PurePosixPath
import re

from . import writer
from .schema import ID, MANAGED, MD, Refused, document, existing_fields, read_text, resolve_schema, same


LISTING_LINK = re.compile(r"^( {0,3}[*+-][ \t]+\[)((?:\\.|[^\[\]\\])*)(\]\(.*)$")


def load(root, selector):
    if ID.fullmatch(selector):
        matches = [relative for relative, path in writer.visible_files(root)
                   if writer.concept_path(relative)
                   and existing_fields(read_text(writer.read_file(path)), {"id"}).get("id") == selector]
        if len(matches) != 1:
            raise Refused("Concept ID was not found or is ambiguous.")
        path = matches[0]
    else:
        path = selector
    if not writer.concept_path(path):
        raise Refused("Select a concept Markdown path, not a structural file.")
    if writer.in_journal(path):
        raise Refused("Use journal commands for Journal records.")
    raw = writer.read_file(writer.safe_target(root, path))
    text = read_text(raw)
    fields = existing_fields(text, {"id", "type"}, required=True)
    identity, kind = fields.get("id", ""), fields.get("type")
    if not ID.fullmatch(identity) or kind is None:
        raise Refused("Expected an identified concept with a type.")
    if kind == "Journal":
        raise Refused("Use journal commands for Journal records.")
    if ID.fullmatch(selector) and identity != selector:
        raise Refused("Concept changed during lookup; read it again.")
    return {"path": path, "id": identity, "type": kind, "revision": writer.digest(raw), "markdown": text}


def read(root, selector, *, successor=None):
    writer.check_authority(root, successor)
    writer.require_idle(root)
    result = load(root, selector)
    writer.require_idle(root)
    return result


def revise_listing(text, index, path, title):
    """Edit only one unambiguous, single-line parent listing item."""
    _, body, offset = document(text, required=False)
    headings = writer.headings(body)
    starts = [(line, mark) for tag, label, line, mark in headings
              if tag == "h2" and label == "Directory Listing"]
    if len(starts) != 1 or starts[0][1] != "##":
        raise Refused("Parent index needs one ## Directory Listing section.")
    start = starts[0][0]
    stop = next((line for tag, _, line, _ in headings if line > start and tag in {"h1", "h2"}), None)

    tokens = MD.parse(body)
    matches = []
    for token in tokens:
        for child in token.children or []:
            if child.type != "link_open":
                continue
            destination = writer.link_destination(child.attrGet("href") or "", index)
            if destination is not None and writer.folded(destination) == writer.folded(path):
                matches.append(token)
    if len(matches) != 1 or matches[0].map is None:
        raise Refused("Parent index needs exactly one link to the concept.")
    first, end = matches[0].map
    lines, newline = writer.lines_for(text)
    listing = lines[first + offset]
    item = LISTING_LINK.fullmatch(listing)
    bullet = next((t for t in tokens if t.type == "list_item_open" and t.level == 1 and t.map[0] == first), None)
    def leads_to_target(children):
        if not children or children[0].type != "link_open":
            return False
        destination = writer.link_destination(children[0].attrGet("href") or "", index)
        return destination is not None and writer.folded(destination) == writer.folded(path)

    # Reparse with no reference definitions so we only touch actual inline links.
    inline = next((t for t in MD.parse(listing) if t.type == "inline"), None)
    if (not start < first or stop is not None and first >= stop or end != first + 1
            or not item or not bullet or not inline
            or not leads_to_target(matches[0].children) or not leads_to_target(inline.children)
            or title is None and sum(child.type == "link_open" for child in matches[0].children) != 1
            or any(line.strip() for line in lines[end + offset:bullet.map[1] + offset])):
        raise Refused("Parent index link is not a standalone Directory Listing bullet.")
    if title is None:
        del lines[first + offset]
    else:
        lines[first + offset] = item[1] + writer.escape_label(title) + item[3]
    return newline.join(lines)


def change(root, selector, revision, actor, *, replacement=None, dry_run=False, successor=None,
           request_id=None, expected_path=None):
    writer.validate_actor(actor)
    operation = "concept-delete" if replacement is None else "concept-update"
    request = writer.write_request(request_id, operation, selector, revision, actor,
                                   None if replacement is None else writer.digest(replacement),
                                   *(() if expected_path is None else (expected_path,)))

    def prepare():
        old = load(root, selector)
        writer.require_revision(revision, old["revision"])
        path, identity = old["path"], old["id"]
        if expected_path is not None and (not ID.fullmatch(selector) or path != expected_path):
            raise Refused("The selected ID is not at the expected path.")
        index = str(PurePosixPath(path).with_name("index.md"))
        title = None
        after = None
        edit_index = True
        if replacement is not None:
            after = read_text(replacement)
            writer.lines_for(after)
            previous = document(old["markdown"])[0]
            fields = document(after)[0]
            keys = MANAGED.intersection(previous.keys() | fields.keys()) | {"type"}
            if any(key not in previous or key not in fields or not same(previous[key], fields[key]) for key in keys):
                raise Refused("Keep the existing type and all managed fields (id, generated, verified, owner, scope).")
            indexes, _ = writer.inventory(root, collect_ids=False)
            directory = "/" if index == "index.md" else str(PurePosixPath(index).parent)
            route = resolve_schema(old["type"], directory, indexes)
            route.validate(fields)
            title = fields["title"]
            edit_index = title != previous.get("title")
            if after == old["markdown"]:
                raise Refused("The replacement is unchanged.")
        changes = [writer.Change(path, revision, after)]
        if edit_index:
            raw = writer.read_file(writer.safe_target(root, index))
            changed = revise_listing(read_text(raw), index, path, title)
            if changed.encode() != raw:
                changes.append(writer.Change(index, writer.digest(raw), changed))
        log = writer.read_file(writer.safe_target(root, "log.md"))
        audit = writer.edit_log(read_text(log), path, title if title is not None else identity, actor,
                                datetime.now().astimezone(), action="Delete" if after is None else "Update",
                                link=after is not None)
        return [*changes, writer.Change("log.md", writer.digest(log), audit)], identity

    return writer.edit(root, operation, prepare, dry_run=dry_run, successor=successor, request=request)
