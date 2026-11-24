"""Guarded concept and personal journal commands for an OKF bundle."""

import argparse
from contextlib import nullcontext
import json
from pathlib import Path
import sys

from .schema import LIMIT, Refused, read_text, resolve_route
from .handover import adopt, live_checkout
from .writer import create, inventory, open_bundle, read_file, recover
from . import concept, journal


def parser():
    command = argparse.ArgumentParser(prog="innersanctum", description=__doc__)
    groups = command.add_subparsers(required=True)
    concepts = groups.add_parser("concept")
    actions = concepts.add_subparsers(dest="action", required=True)
    template = actions.add_parser("template", help="Print a draft from a declared type schema")
    template.add_argument("type")
    new = actions.add_parser("create", help="Create one concept and update its index and log")
    new.add_argument("--from", dest="source", required=True, help="UTF-8 draft file, or - for stdin")
    new.add_argument("--actor", required=True, help="Actual producer for provenance and audit")
    new.add_argument("--dry-run", action="store_true", help="Validate and preview without writing")
    recovery = actions.add_parser("recover", help="Finish an interrupted write without replanning")
    read = actions.add_parser("read", help="Read one concept's Markdown and revision as JSON")
    update = actions.add_parser("update", help="Replace an existing concept without changing its identity")
    delete = actions.add_parser("delete", help="Remove one concept and its parent listing")
    for action in (read, update, delete):
        action.add_argument("selector", metavar="PATH_OR_ID", help="Exact bundle-relative path or bho: ID")
    update.add_argument("--from", dest="source", required=True, help="Full replacement Markdown file or - for stdin")
    ledger = groups.add_parser("journal", help="Read and manage personal journal entries")
    journal_actions = ledger.add_subparsers(dest="action", required=True)
    entry = journal_actions.add_parser("add", help="Add an entry to a date-named Journal concept")
    entry.set_defaults(action="journal-add")
    entry.add_argument("--from", dest="source", default="-", help="Entry file or - for stdin (default)")
    entry.add_argument("--actor", required=True, help="Actual author for the entry and audit")
    entry.add_argument("--date", help="YYYY-MM-DD; defaults to the date of the entry timestamp")
    entry.add_argument("--at", help="ISO timestamp with seconds and UTC offset; defaults to local now")
    entry.add_argument("--category", choices=("Personal", "Work"), default="Personal")
    entry.add_argument("--subject", help="Optional one-line subject")
    entry.add_argument("--dry-run", action="store_true", help="Validate and preview without writing")
    journal_read = journal_actions.add_parser("read", help="Read a day's numbered entries and revision as JSON")
    journal_update = journal_actions.add_parser("update", help="Replace one entry's text, keeping its time and author")
    journal_delete = journal_actions.add_parser("delete", help="Remove one entry without removing its day")
    for action, name in ((journal_read, "read"), (journal_update, "update"), (journal_delete, "delete")):
        action.set_defaults(action=f"journal-{name}")
        action.add_argument("day", metavar="DATE", help="Journal day (YYYY-MM-DD)")
    for action in (journal_update, journal_delete):
        action.add_argument("--entry", type=int, required=True, help="Entry number returned by journal read")
    journal_update.add_argument("--from", dest="source", required=True, help="Entry text file or - for stdin")
    journal_update.add_argument("--category", choices=("Personal", "Work"), help="Replace the entry's category")
    subject = journal_update.add_mutually_exclusive_group()
    subject.add_argument("--subject", help="Replace the entry's subject")
    subject.add_argument("--clear-subject", action="store_true", help="Remove the entry's subject")
    for action in (update, delete, journal_update, journal_delete):
        action.add_argument("--revision", required=True, help="Exact SHA-256 revision returned by read")
        action.add_argument("--actor", required=True, help="Actual editor for the audit")
        action.add_argument("--dry-run", action="store_true", help="Validate and preview without writing")
    journal_recovery = journal_actions.add_parser("recover", help="Finish the bundle's pending write")
    for action in (template, new, recovery, read, update, delete,
                   entry, journal_read, journal_update, journal_delete, journal_recovery):
        target = action.add_mutually_exclusive_group(required=True)
        target.add_argument("--bundle", help="Explicit standalone bundle directory")
        target.add_argument("--live-checkout", help="Exact adopted InnerSanctum checkout")
    for action in (template, new):
        action.add_argument("--routes", required=True, help="TOML map of authoring destinations")
    transfer = actions.add_parser("adopt", help="Transfer one stopped, checkpointed checkout")
    transfer.add_argument("--live-checkout", required=True, help="Exact InnerSanctum checkout")
    transfer.add_argument("--checkpoint", required=True, help="Independently verified stopped Personal checkpoint")
    transfer.add_argument("--sha256", required=True, help="Retained approval digest for the checkpoint receipt")
    transfer.add_argument("--writers-stopped", action="store_true", required=True,
                          help="Assert writers and publishers are excluded; this does not stop them")
    return command


def input_bytes(source, *, limit=LIMIT):
    return (sys.stdin.buffer.read(limit + 1) if source == "-"
            else read_file(Path(source).expanduser(), limit=limit))


def main(argv=None):
    args = parser().parse_args(argv)
    checkout = Path(__file__).resolve().parents[2]
    try:
        if args.action == "adopt":
            result = adopt(Path(args.live_checkout).expanduser().absolute(), args.checkpoint,
                           args.sha256, writers_stopped=args.writers_stopped)
        else:
            target = (live_checkout(Path(args.live_checkout).expanduser().absolute()) if args.live_checkout
                      else nullcontext((open_bundle(args.bundle, checkout), None)))
            with target as (root, successor):
                if args.action == "recover":
                    result = recover(root, successor=successor)
                elif args.action == "read":
                    result = concept.read(root, args.selector, successor=successor)
                elif args.action in {"update", "delete"}:
                    replacement = input_bytes(args.source) if args.action == "update" else None
                    result = concept.change(root, args.selector, args.revision, args.actor,
                                            replacement=replacement, dry_run=args.dry_run, successor=successor)
                elif args.action == "journal-read":
                    result = journal.read(root, args.day, successor=successor)
                elif args.action in {"journal-update", "journal-delete"}:
                    edits = {}
                    if args.action == "journal-update":
                        edits = dict(replacement=input_bytes(args.source, limit=journal.MAX_ENTRY),
                                     category=args.category, subject=args.subject, clear_subject=args.clear_subject)
                    result = journal.change(root, args.day, args.entry, args.revision, args.actor,
                                            dry_run=args.dry_run, successor=successor, **edits)
                elif args.action == "journal-add":
                    raw = input_bytes(args.source, limit=journal.MAX_ENTRY)
                    result = journal.add(root, raw, args.actor, day=args.date, at=args.at,
                                         subject=args.subject, category=args.category,
                                         dry_run=args.dry_run, successor=successor)
                else:
                    routes = read_text(read_file(Path(args.routes).expanduser()))
                    if args.action == "template":
                        indexes, _ = inventory(root, collect_ids=False)
                        print(resolve_route(args.type, routes, indexes).template(), end="")
                        return 0
                    raw = input_bytes(args.source)
                    result = create(root, routes, raw, args.actor, dry_run=args.dry_run, successor=successor)
        print(json.dumps(result, sort_keys=True))
    except Refused as error:
        print(f"innersanctum: {error}", file=sys.stderr)
        return 2
    except (OSError, UnicodeError):
        print("innersanctum: I/O failed. If a write is pending, recover it before retrying.",
              file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        print("innersanctum: interrupted. If a write is pending, recover it before retrying.",
              file=sys.stderr)
        return 130
    return 0


if __name__ == "__main__":
    sys.exit(main())
