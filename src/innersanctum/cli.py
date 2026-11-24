"""Guarded concept and personal journal commands for an OKF bundle."""

import argparse
from contextlib import nullcontext
import json
from pathlib import Path
import sys

from .schema import LIMIT, Refused, read_text, resolve_route
from .handover import adopt, live_checkout
from .writer import create, inventory, open_bundle, read_file, recover
from . import journal


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
    ledger = groups.add_parser("journal", help="Add a personal journal entry")
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
    journal_recovery = journal_actions.add_parser("recover", help="Finish the bundle's pending write")
    for action in (template, new, recovery, entry, journal_recovery):
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
                elif args.action == "journal-add":
                    raw = (sys.stdin.buffer.read(journal.MAX_ENTRY + 1) if args.source == "-"
                           else read_file(Path(args.source).expanduser(), limit=journal.MAX_ENTRY))
                    result = journal.add(root, raw, args.actor, day=args.date, at=args.at,
                                         subject=args.subject, category=args.category,
                                         dry_run=args.dry_run, successor=successor)
                else:
                    routes = read_text(read_file(Path(args.routes).expanduser()))
                    if args.action == "template":
                        indexes, _ = inventory(root, collect_ids=False)
                        print(resolve_route(args.type, routes, indexes).template(), end="")
                        return 0
                    raw = (sys.stdin.buffer.read(LIMIT + 1) if args.source == "-"
                           else read_file(Path(args.source).expanduser()))
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
