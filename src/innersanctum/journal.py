"""Add one date-addressed entry using the bundle's shared writer."""

from datetime import date, datetime
from pathlib import PurePosixPath
import json
import posixpath
import re
from urllib.parse import unquote, urlsplit

from . import writer
from .schema import ID, MD, Refused, date_value, datetime_value, document, read_text, resolve_route


ROOT = writer.JOURNAL_ROOT
ROUTE = f'[types.Journal]\nschema = "{ROOT}/index.md"\ndirectory = "{ROOT}"\n'
LEDGER = {"Journal Entries", "Entries"}
TIME = re.compile(r"^ {0,3}[*+-][ \t]+\*\*(?:Time|Timestamp)(?::\*\*|\*\*:)[ \t]+(\S+)[ \t]*$")
ENTRY = re.compile(r"^ {2,4}\*\*Entry(?::\*\*|\*\*:)(?:[ \t]|$)")
MARKER = re.compile(r"(?<!\\)\*\*(?:Time|Timestamp|Entry)(?::\*\*|\*\*:)", re.I)
MAX_ENTRY = 32 * 1024


def local_times(now, day, at):
    if day is not None and not date_value(day):
        raise Refused("Journal date must be YYYY-MM-DD.")
    if at is not None and not datetime_value(at):
        raise Refused("Journal time must be an ISO timestamp with seconds and a UTC offset.")
    entry_time = datetime.fromisoformat(at) if at is not None else now.replace(microsecond=0)
    if day is not None and entry_time.date() != date.fromisoformat(day):
        raise Refused("The timestamp must fall on the journal date. Use --at for a different day.")
    return entry_time


def entry_lines(raw, actor, category, subject, at):
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
    if category not in {"Personal", "Work"}:
        raise Refused("Journal category must be Personal or Work.")
    literal_actor = re.sub(r"([\\`*_\[\]<>~&])", r"\\\1", actor)
    result = [f"* **Time:** {at.isoformat()}  ",
              f"  **Author:** {literal_actor}  ", f"  **Category:** {category}  "]
    if subject is not None:
        if not subject.strip() or not subject.isprintable() or len(subject) > 256:
            raise Refused("Journal subject must be a nonblank single line of at most 256 characters.")
        result.append(f"  **Subject:** {writer.escape_label(subject)}  ")
    result.append(f"  **Entry:** {paragraphs[0]}")
    for paragraph in paragraphs[1:]:
        result.extend(("", f"  {paragraph}"))
    return result


def add_to_ledger(text, body, offset, entries, at):
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
        if (not match or not datetime_value(match[1])
                or not any(ENTRY.match(line) for line in body_lines[first + 1:last])):
            raise Refused("An existing journal entry could not be placed safely.")
        stamp = datetime.fromisoformat(match[1])
        if items and stamp > items[-1][0]:
            raise Refused("Existing journal entries are not newest first.")
        items.append((stamp, first, last))
    by_line = {first for _, first, _ in items}
    if any(TIME.fullmatch(body_lines[i]) and i not in by_line for i in range(start, stop)):
        raise Refused("Journal ledger contains an ambiguous timestamp marker.")
    position = (next((first for stamp, first, _ in items if at >= stamp), items[-1][2])
                if items else start)
    lines, newline = writer.lines_for(text)
    position += offset
    leading = [""] if position and lines[position - 1] else []
    trailing = [""] if position == len(lines) or lines[position] else []
    lines[position:position] = [*leading, *entries, *trailing]
    return newline.join(lines)


def link_destination(href, index):
    try:
        value = urlsplit(href)
    except ValueError:
        return None
    if value.scheme or value.netloc or not value.path:
        return None
    clean = unquote(value.path)
    return (posixpath.normpath(clean.lstrip("/")) if clean.startswith("/") else
            posixpath.normpath(str(PurePosixPath(index).parent / clean)))


def ensure_links(text, index, links):
    _, body, offset = document(text, required=False)
    linked = {link_destination(child.attrGet("href") or "", index)
              for token in MD.parse(body) for child in token.children or [] if child.type == "link_open"}
    additions = [f"* [{writer.escape_label(label)}]({href})"
                 for label, href in links if link_destination(href, index) not in linked]
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


def plan_add(root, raw, actor, *, day=None, at=None, subject=None, category="Personal", now=None):
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
    path = f"{month}/{day}.md"
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
        text = read_text(old)
        metadata, body, offset = document(text)
        if (metadata.get("type") != "Journal" or type(metadata.get("id")) is not str
                or not ID.fullmatch(metadata["id"])):
            raise Refused("Existing day is not an identified Journal concept.")
        route.validate(metadata)
        after = add_to_ledger(text, body, offset, entries, entry_time)
        return [writer.Change(path, writer.digest(old), after), audit], None

    identity = writer.allocate_id(identities)
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


def add(root, raw, actor, *, day=None, at=None, subject=None, category="Personal", dry_run=False, successor=None):
    writer.check_authority(root, successor)

    def prepare():
        changes, directory = plan_add(root, raw, actor, day=day, at=at, subject=subject, category=category)
        for change in changes:
            read_text(change.after.encode())
        writer.verify_journal_changes(changes, directory)
        return changes, directory

    if dry_run:
        if writer.present(root / writer.STATE / writer.PENDING):
            raise Refused("A write is pending; recover it before planning another.")
        changes, directory = prepare()
        return writer.describe(changes, "planned", journal=True, directory=directory)
    with writer.locked(root, successor) as state:
        if writer.present(state / writer.PENDING):
            raise Refused("A write is pending; run journal recover before trying another.")
        changes, directory = prepare()
        writer.freeze(root, state, changes, journal=True, directory=directory)
        return writer.publish(root, state, changes, journal=True, directory=directory)
