"""Read and edit date-addressed entries using the bundle's shared writer."""

from dataclasses import dataclass
from datetime import date, datetime
import json
import re

from . import writer
from .schema import (
    ID, MD, Refused, date_value, datetime_value, document, existing_fields, read_text, resolve_route,
    split_document,
)


ROOT = writer.JOURNAL_ROOT
ROUTE = f'[types.Journal]\nschema = "{ROOT}/index.md"\ndirectory = "{ROOT}"\n'
LEDGER = {"Journal Entries", "Entries"}
TIME = re.compile(r"^ {0,3}[*+-][ \t]+\*\*(?:Time|Timestamp)(?::\*\*|\*\*:)[ \t]+(\S+)[ \t]*$")
ENTRY = re.compile(r"^( {2,4})\*\*Entry(?::\*\*|\*\*:)(?=[ \t]|$)")
MARKER = re.compile(r"(?<!\\)\*\*(?:Time|Timestamp|Entry)(?::\*\*|\*\*:)", re.I)
MAX_ENTRY = 32 * 1024


@dataclass(frozen=True)
class Item:
    stamp: str
    first: int
    last: int
    entry: int

    @property
    def time(self):
        return datetime.fromisoformat(self.stamp)


def local_times(now, day, at):
    if day is not None and not date_value(day):
        raise Refused("Journal date must be YYYY-MM-DD.")
    if at is not None and not datetime_value(at):
        raise Refused("Journal time must be an ISO timestamp with seconds and a UTC offset.")
    entry_time = datetime.fromisoformat(at) if at is not None else now.replace(microsecond=0)
    if day is not None and entry_time.date() != date.fromisoformat(day):
        raise Refused("The timestamp must fall on the journal date. Use --at for a different day.")
    return entry_time


def entry_paragraphs(raw):
    if len(raw) > MAX_ENTRY:
        raise Refused("Journal entry exceeds 32 KiB.")
    text = read_text(raw)
    lines, _ = writer.lines_for(text)
    if any(not (char.isprintable() or char == "\t") for line in lines for char in line):
        raise Refused("Journal entry contains a control character.")
    paragraphs = [" ".join(p.split()) for p in re.split(r"\n[ \t]*\n", "\n".join(lines).strip())]
    if not paragraphs or not paragraphs[0]:
        raise Refused("Provide a nonblank journal entry.")
    for paragraph in paragraphs:
        tokens = MD.parse(paragraph)
        if ([token.type for token in tokens] != ["paragraph_open", "inline", "paragraph_close"]
                or any(token.type == "html_inline" for token in tokens[1].children or [])
                or MARKER.search(paragraph)):
            raise Refused("Use paragraphs with inline Markdown, not block markup or journal field markers.")
    return paragraphs


def entry_body(paragraphs, marker, indent):
    result = [f"{marker} {paragraphs[0]}"]
    for paragraph in paragraphs[1:]:
        result.extend(("", f"{indent}{paragraph}"))
    return result


def category_label(category):
    if category not in {"Personal", "Work"}:
        raise Refused("Journal category must be Personal or Work.")
    return f"**Category:** {category}  "


def subject_label(subject):
    if not subject.strip() or not subject.isprintable() or len(subject) > 256:
        raise Refused("Journal subject must be a nonblank single line of at most 256 characters.")
    return f"**Subject:** {writer.escape_label(subject)}  "


def entry_lines(raw, actor, category, subject, at):
    paragraphs = entry_paragraphs(raw)
    literal_actor = re.sub(r"([\\`*_\[\]<>~&])", r"\\\1", actor)
    result = [f"* **Time:** {at.isoformat()}  ",
              f"  **Author:** {literal_actor}  ", f"  {category_label(category)}"]
    if subject is not None:
        result.append(f"  {subject_label(subject)}")
    return [*result, *entry_body(paragraphs, "  **Entry:**", "  ")]


def ledger_items(body):
    headings = writer.headings(body)
    ledgers = [pos for tag, heading, pos, markup in headings
               if tag == "h2" and markup == "##" and heading in LEDGER]
    ambiguous = [1 for _, heading, _, _ in headings if heading in LEDGER]
    if len(ledgers) != 1 or len(ambiguous) != 1:
        raise Refused("Journal day needs exactly one top-level ## Journal Entries or ## Entries heading.")
    start = ledgers[0] + 1
    body_lines, _ = writer.lines_for(body)
    stop = next((pos for tag, _, pos, _ in headings if pos >= start and tag in {"h1", "h2"}), len(body_lines))
    items = []
    for token in MD.parse(body):
        if token.type != "list_item_open" or token.level != 1 or not start <= token.map[0] < stop:
            continue
        first, last = token.map
        match = TIME.fullmatch(body_lines[first])
        markers = [i for i in range(first + 1, last) if ENTRY.match(body_lines[i])]
        if not match or not datetime_value(match[1]) or len(markers) != 1:
            raise Refused("An existing journal entry could not be placed safely.")
        while last > markers[0] + 1 and not body_lines[last - 1].strip():
            last -= 1
        item = Item(match[1], first, last, markers[0])
        if items and item.time > items[-1].time:
            raise Refused("Existing journal entries are not newest first.")
        items.append(item)
    by_line = {item.first for item in items}
    if any(TIME.fullmatch(body_lines[i]) and i not in by_line for i in range(start, stop)):
        raise Refused("Journal ledger contains an ambiguous timestamp marker.")
    return start, items


def add_to_ledger(text, body, offset, entries, at):
    start, items = ledger_items(body)
    position = (next((item.first for item in items if at >= item.time), items[-1].last)
                if items else start)
    lines, newline = writer.lines_for(text)
    position += offset
    leading = [""] if position and lines[position - 1] else []
    trailing = [""] if position == len(lines) or lines[position] else []
    lines[position:position] = [*leading, *entries, *trailing]
    return newline.join(lines)


def ensure_links(text, index, links):
    _, body, offset = document(text, required=False)
    linked = {writer.link_destination(child.attrGet("href") or "", index)
              for token in MD.parse(body) for child in token.children or [] if child.type == "link_open"}
    additions = [f"* [{writer.escape_label(label)}]({href})"
                 for label, href in links if writer.link_destination(href, index) not in linked]
    if not additions:
        return text
    headings = [(position, markup) for tag, heading, position, markup in writer.headings(body)
                if tag == "h2" and heading == "Directory Listing"]
    if len(headings) != 1 or headings[0][1] != "##":
        raise Refused("Journal index needs one top-level ## Directory Listing heading.")
    lines, newline = writer.lines_for(text)
    position = offset + headings[0][0] + 1
    lines[position:position] = ["", *additions]
    position += len(additions) + 1
    if position == len(lines) or lines[position]:
        lines.insert(position, "")
    return newline.join(lines)


def plan_add(root, raw, actor, *, day=None, at=None, subject=None, category="Personal", now=None,
             revision=None):
    writer.validate_actor(actor)
    now = now or datetime.now().astimezone()
    entry_time = local_times(now, day, at)
    day = entry_time.date().isoformat()
    entries = entry_lines(raw, actor, category, subject, entry_time)
    month = f"{ROOT}/{day[:7]}"
    directory = writer.safe_target(root, month, missing=True)
    new_month = not writer.present(directory)
    if not new_month and (directory.is_symlink() or not directory.is_dir()):
        raise Refused("Journal month is not a physical directory.")
    path = writer.journal_path(day)
    monthly, parent = f"{month}/index.md", f"{ROOT}/index.md"
    indexes, identities = writer.inventory(root, collect_ids=True)
    route = resolve_route("Journal", ROUTE, indexes)
    if not new_month and monthly not in indexes:
        raise Refused("Existing journal month needs an index.md before it can be updated.")
    target = root / path if new_month else writer.safe_target(root, path, missing=True)
    log = read_text(writer.read_file(root / "log.md"))
    title = f"Journal for {day}"
    audit = writer.Change("log.md", writer.digest(log.encode()),
                          writer.edit_log(log, path, title, actor, now, action="Journal entry"))
    if writer.present(target):
        old = writer.read_file(target)
        if revision is not None:
            writer.require_revision(revision, writer.digest(old))
        text = read_text(old)
        metadata, body, offset = document(text)
        if (metadata.get("type") != "Journal" or type(metadata.get("id")) is not str
                or not ID.fullmatch(metadata["id"])):
            raise Refused("Existing day is not an identified Journal concept.")
        route.validate(metadata)
        after = add_to_ledger(text, body, offset, entries, entry_time)
        return [writer.Change(path, writer.digest(old), after), audit], None

    if revision is not None:
        raise Refused("The day no longer exists; read the current journal before retrying.")
    identity = writer.allocate_id(identities | writer.retired_ids(log))
    initial = "\n".join(("---", f'id: "{identity}"', "type: Journal", f'title: "{title}"',
                         "generated:", f"  by: {json.dumps(actor, ensure_ascii=False)}",
                         f'  at: "{now.isoformat(timespec="seconds")}"', "---", "",
                         "## Journal Entries", "", *entries, ""))
    route.validate(document(initial)[0])
    changes = [writer.Change(path, None, initial)]
    for index, links in ((monthly, [(title, day + ".md")]),
                         (parent, [(day[:7], f"{day[:7]}/index.md"), (title, f"/{path}")])):
        old = indexes.get(index)
        after = ensure_links(old if old is not None else f"# Journal for {day[:7]}\n\n## Directory Listing\n",
                             index, links)
        if after != old:
            changes.append(writer.Change(index, None if old is None else writer.digest(old.encode()), after))
    return [*changes, audit], month if new_month else None


def add(root, raw, actor, *, day=None, at=None, subject=None, category="Personal", dry_run=False,
        successor=None, request_id=None, revision=None):
    writer.check_authority(root, successor)
    arguments = (writer.digest(raw), actor, day, at, subject, category)
    request = writer.write_request(request_id, "journal-add", *arguments,
                                   *(() if revision is None else (revision,)))

    def prepare():
        changes, directory = plan_add(root, raw, actor, day=day, at=at, subject=subject, category=category,
                                      revision=revision)
        for change in changes:
            read_text(change.after.encode())
        writer.verify_journal_changes(changes, directory)
        return changes, directory

    if dry_run:
        if writer.present(root / writer.STATE / writer.PENDING):
            raise Refused("A write is pending; recover it before planning another.")
        changes, directory = prepare()
        return writer.describe(changes, "planned", operation="journal-add", directory=directory)
    with writer.locked(root, successor) as state:
        if writer.present(state / writer.PENDING):
            raise Refused("A write is pending; run journal recover before trying another.")
        retained = writer.replay(root, state, request)
        if retained is not None:
            return retained
        changes, directory = prepare()
        writer.freeze(root, state, changes, operation="journal-add", directory=directory, request=request)
        return writer.publish(root, state, changes, operation="journal-add", directory=directory, request=request)


def load(root, day):
    path = writer.journal_path(day)
    raw = writer.read_file(writer.safe_target(root, path))
    text = read_text(raw)
    fields = existing_fields(text, {"id", "type"}, required=True)
    identity = fields.get("id", "")
    if fields.get("type") != "Journal" or not ID.fullmatch(identity):
        raise Refused("Existing day is not an identified Journal concept.")
    return {"path": path, "id": identity, "date": day, "revision": writer.digest(raw)}, text


def ledger_source(text):
    _, body, offset = split_document(text)
    _, items = ledger_items(body)
    lines, newline = writer.lines_for(text)
    return lines, newline, offset, items


def read(root, day, *, successor=None):
    writer.check_authority(root, successor)
    writer.require_idle(root)
    result, text = load(root, day)
    lines, newline, offset, items = ledger_source(text)
    result["entries"] = [{"entry": index, "at": item.stamp,
                          "markdown": newline.join(lines[offset + item.first:offset + item.last])}
                         for index, item in enumerate(items, 1)]
    writer.require_idle(root)
    return result


def set_label(lines, field, label, indent):
    marker = re.compile(rf"^( {{2,4}})\*\*{field}(?::\*\*|\*\*:)(?=[ \t]|$)")
    matches = [(i, match[1]) for i, line in enumerate(lines) if (match := marker.match(line))]
    if len(matches) > 1:
        raise Refused(f"Journal entry has more than one {field} field.")
    if matches:
        index, padding = matches[0]
        lines[index:index + 1] = [] if label is None else [padding + label]
    elif label is not None:
        lines.append(indent + label)


def change(root, day, entry, revision, actor, *, replacement=None, category=None, subject=None,
           clear_subject=False, dry_run=False, successor=None, request_id=None):
    writer.validate_actor(actor)
    operation = "journal-delete" if replacement is None else "journal-update"
    request = writer.write_request(request_id, operation, day, entry, revision, actor,
                                   None if replacement is None else writer.digest(replacement),
                                   category, subject, clear_subject)

    def prepare():
        record, old = load(root, day)
        writer.require_revision(revision, record["revision"])
        lines, newline, offset, items = ledger_source(old)
        if not 1 <= entry <= len(items):
            raise Refused("Select an entry number from journal read.")
        item = items[entry - 1]
        first, last = offset + item.first, offset + item.last
        expected = [lines[offset + i.first:offset + i.last] for i in items]
        replaced = []
        if replacement is not None:
            marker = ENTRY.match(lines[offset + item.entry])
            indent = marker[1]
            headers = lines[first + 1:offset + item.entry]
            if category is not None:
                set_label(headers, "Category", category_label(category), indent)
            if subject is not None or clear_subject:
                set_label(headers, "Subject", None if clear_subject else subject_label(subject), indent)
            replaced = [lines[first], *headers, *entry_body(entry_paragraphs(replacement), marker[0], indent)]
        lines[first:last] = replaced
        expected[entry - 1:entry] = [replaced] if replaced else []
        after = newline.join(lines)
        if old == after:
            raise Refused("The replacement is unchanged.")
        new_lines, _, new_offset, new_items = ledger_source(after)
        if [new_lines[new_offset + i.first:new_offset + i.last] for i in new_items] != expected:
            raise Refused("The edit would change how other journal content is parsed.")
        path = record["path"]
        log = writer.read_file(writer.safe_target(root, "log.md"))
        audit = writer.edit_log(read_text(log), path, f"Journal for {day}", actor,
                                datetime.now().astimezone(),
                                action="Journal entry delete" if replacement is None else "Journal entry update")
        return [writer.Change(path, revision, after), writer.Change("log.md", writer.digest(log), audit)], record["id"]

    return writer.edit(root, operation, prepare, dry_run=dry_run, successor=successor, request=request)
