"""Guarded concept and personal journal commands for an OKF bundle."""

import argparse
from contextlib import nullcontext
import json
from pathlib import Path
import sys

from .schema import LIMIT, Refused, read_text, resolve_route
from .handover import SUCCESSOR, adopt, live_checkout
from .writer import create, inventory, open_bundle, read_file, receipt_status, recover
from . import clerk_archive, concept, journal, migration, timestamp_cleanup, version_declaration


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
    receipt = actions.add_parser("receipt", help="Observe a request receipt without recovering or publishing")
    receipt.add_argument("request_id")
    read = actions.add_parser("read", help="Read one concept's Markdown and revision as JSON")
    update = actions.add_parser("update", help="Replace an existing concept without changing its identity")
    delete = actions.add_parser("delete", help="Remove one concept and its parent listing")
    for action in (read, update, delete):
        action.add_argument("selector", metavar="PATH_OR_ID", help="Exact bundle-relative path or bho: ID")
    update.add_argument("--from", dest="source", required=True, help="Full replacement Markdown file or - for stdin")
    update.add_argument("--expect-path", help="For ID selection, require this exact bundle-relative path")
    update.add_argument("--clerk-session", help="Archived Clerk snapshot for a body-only edit")
    for action in (receipt, update, recovery):
        action.add_argument("--expect-adoption", help="Require the adopted checkpoint's exact receipt SHA-256")
    for action in (update, recovery):
        action.add_argument("--expect-archive", help="Require the original adopted archive binding SHA-256")
    ledger = groups.add_parser("journal", help="Read and manage personal journal entries")
    journal_actions = ledger.add_subparsers(dest="action", required=True)
    entry = journal_actions.add_parser("add", help="Add an entry to a date-named Journal concept")
    entry.set_defaults(action="journal-add")
    entry.add_argument("--from", dest="source", default="-", help="Entry file or - for stdin (default)")
    entry.add_argument("--actor", required=True, help="Actual author for the entry and audit")
    entry.add_argument("--date", help="YYYY-MM-DD; defaults to the date of the entry timestamp")
    entry.add_argument("--at", help="ISO timestamp with seconds and UTC offset; defaults to local now")
    entry.add_argument("--revision", help="Require an existing day at this exact revision")
    entry.add_argument("--category", choices=("Personal", "Work"), default="Personal")
    entry.add_argument("--subject", help="Optional one-line subject")
    entry.add_argument("--entry-json", action="store_true",
                       help="Read an object with markdown and subject from --from instead of raw Markdown")
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
    for action in (new, update, delete, entry, journal_update, journal_delete):
        action.add_argument("--request-id", help="Client-assigned ID for a durable write receipt")
    journal_recovery = journal_actions.add_parser("recover", help="Finish the bundle's pending write")
    for action in (template, new, recovery, receipt, read, update, delete,
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
    migrations = groups.add_parser("migration")
    migration_actions = migrations.add_subparsers(required=True)
    video = migration_actions.add_parser("video-status-preview", help="Inspect the Video field rename without writing")
    video.set_defaults(action="video-status-preview")
    target = video.add_mutually_exclusive_group(required=True)
    target.add_argument("--bundle", help="Explicit standalone bundle directory")
    target.add_argument("--live-checkout", help="Exact adopted InnerSanctum checkout")
    version = migration_actions.add_parser("version-preview", help="Preview declaring OKF 0.3")
    version.set_defaults(action="version-preview")
    target = version.add_mutually_exclusive_group(required=True)
    target.add_argument("--bundle", help="Explicit standalone bundle directory")
    target.add_argument("--live-checkout", help="Exact adopted InnerSanctum checkout")
    version_rehearsal = migration_actions.add_parser("version-rehearse",
                                                     help="Declare OKF 0.3 on a disposable bundle")
    version_rehearsal.set_defaults(action="version-rehearse")
    version_rehearsal.add_argument("--bundle", required=True)
    version_rehearsal.add_argument("--expect-digest", required=True)
    version_rehearsal.add_argument("--actor", required=True)
    version_rehearsal.add_argument("--request-id", required=True)
    stamps = migration_actions.add_parser("timestamp-preview", help="Preview format-only timestamp cleanup")
    stamps.set_defaults(action="timestamp-preview")
    target = stamps.add_mutually_exclusive_group(required=True)
    target.add_argument("--bundle", help="Explicit standalone bundle directory")
    target.add_argument("--live-checkout", help="Exact adopted InnerSanctum checkout")
    stamps_rehearsal = migration_actions.add_parser("timestamp-rehearse",
                                                   help="Apply reviewed timestamp cleanup on a disposable bundle")
    stamps_rehearsal.set_defaults(action="timestamp-rehearse")
    stamps_rehearsal.add_argument("--bundle", required=True)
    stamps_rehearsal.add_argument("--expect-digest", required=True)
    stamps_rehearsal.add_argument("--actor", required=True)
    stamps_rehearsal.add_argument("--request-id", required=True)
    rehearsal = migration_actions.add_parser("video-status-rehearse", help="Apply the reviewed rename on a disposable bundle")
    rehearsal.set_defaults(action="video-status-rehearse")
    rehearsal.add_argument("--bundle", required=True, help="Explicit standalone bundle directory")
    rehearsal.add_argument("--expect-digest", required=True, help="Digest from the reviewed preview")
    rehearsal.add_argument("--actor", required=True, help="Actual editor for the audit")
    rehearsal.add_argument("--request-id", required=True, help="Stable ID for this rehearsal")
    evidence = migration_actions.add_parser("video-status-checkpoint", aliases=["timestamp-checkpoint", "version-checkpoint"],
                                            help="Verify an existing stopped canonical copy")
    evidence.set_defaults(action="migration-checkpoint")
    evidence.add_argument("--live-checkout", required=True)
    evidence.add_argument("--canonical-checkpoint", required=True)
    evidence.add_argument("--expect-adoption", required=True)
    for family, name in ((f, n) for f in ("video-status", "timestamp", "version") for n in ("apply", "recover")):
        live = migration_actions.add_parser(f"{family}-{name}",
                                            help=f"{name.capitalize()} {family} on an adopted, stopped checkout")
        live.set_defaults(action=f"{family}-{name}")
        live.add_argument("--live-checkout", required=True)
        live.add_argument("--canonical-checkpoint", required=True)
        live.add_argument("--checkpoint-sha256", required=True)
        live.add_argument("--expect-adoption", required=True)
        live.add_argument("--expect-digest", required=True)
        live.add_argument("--actor", required=True)
        live.add_argument("--request-id", required=True)
        live.add_argument("--writers-stopped", required=True, action="store_true",
                          help="Assert writer exclusion and independent stopped-pair verification")
    archive = groups.add_parser("clerk-archive", help="Keep or reopen a private Clerk snapshot outside OKF")
    archive_actions = archive.add_subparsers(required=True)
    store = archive_actions.add_parser("store", help="Store an immutable UTF-8 conversation export")
    store.set_defaults(action="clerk-store")
    store.add_argument("--session", required=True, help="Stable opaque session ID (32 lowercase hex digits)")
    store.add_argument("--from", dest="source", required=True, help="Private Markdown export, or - for stdin")
    archived = archive_actions.add_parser("read", help="Resolve a retained archive reference to exact source bytes")
    archived.set_defaults(action="clerk-read")
    archived.add_argument("reference")
    bind = archive_actions.add_parser("bind", help="Provision one owner-bound archive on an adopted checkout")
    bind.set_defaults(action="clerk-bind")
    bind.add_argument("--owner", required=True)
    bind.add_argument("--namespace", required=True)
    info = archive_actions.add_parser("binding", help="Read back the pinned adopted owner binding")
    info.set_defaults(action="clerk-binding")
    for action in (bind, info):
        action.add_argument("--live-checkout", required=True)
    for action in (store, archived):
        target = action.add_mutually_exclusive_group(required=True)
        target.add_argument("--bundle", help="Disposable standalone OKF next to SourceFiles")
        target.add_argument("--live-checkout", help="Exact adopted InnerSanctum checkout")
    for action in (store, archived, info):
        action.add_argument("--expect-archive")
    for action in (store, archived, info, bind):
        action.add_argument("--expect-adoption")
    return command


def input_bytes(source, *, limit=LIMIT):
    return (sys.stdin.buffer.read(limit + 1) if source == "-"
             else read_file(Path(source).expanduser(), limit=limit))


def journal_input(args):
    if not args.entry_json:
        return input_bytes(args.source, limit=journal.MAX_ENTRY), args.subject
    limit = 6 * journal.MAX_ENTRY + 4096
    try:
        raw = input_bytes(args.source, limit=limit)
        if len(raw) > limit:
            raise ValueError
        pairs = json.loads(raw.decode("utf-8"), object_pairs_hook=tuple)
        if type(pairs) is not tuple or len(pairs) != 2:
            raise ValueError
        data = dict(pairs)
        if (args.subject is not None or type(data) is not dict or set(data) != {"markdown", "subject"}
                or type(data["markdown"]) is not str or type(data["subject"]) not in {str, type(None)}):
            raise ValueError
        return data["markdown"].encode(), data["subject"]
    except (ValueError, RecursionError):
        raise Refused("Expected UTF-8 JSON with markdown and subject, without --subject.") from None


def main(argv=None):
    args = parser().parse_args(argv)
    checkout = Path(__file__).resolve().parents[2]
    try:
        if args.action == "adopt":
            result = adopt(Path(args.live_checkout).expanduser().absolute(), args.checkpoint,
                           args.sha256, writers_stopped=args.writers_stopped)
        else:
            target = (live_checkout(Path(args.live_checkout).expanduser().absolute()) if getattr(args, "live_checkout", None)
                      else nullcontext((open_bundle(args.bundle, checkout), None)))
            with target as (root, successor):
                expected = getattr(args, "expect_adoption", None)
                archive_pin = getattr(args, "expect_archive", None)
                if expected is not None and (successor is None or SUCCESSOR.fullmatch(successor)[2].decode() != expected):
                    raise Refused("The adopted checkout does not match the expected checkpoint receipt.")
                if successor is not None and (args.action.startswith("clerk-") or archive_pin is not None) and expected is None:
                    raise Refused("Pin the exact adoption checkpoint for an adopted Clerk operation.")
                if args.action == "clerk-bind":
                    result = clerk_archive.bind(root, successor, args.owner, args.namespace)
                elif args.action == "clerk-binding":
                    result = clerk_archive.inspect(root, successor, archive_pin)
                elif args.action == "clerk-store":
                    raw = input_bytes(args.source, limit=clerk_archive.LIMIT)
                    result = clerk_archive.store(root, args.session, raw, successor=successor, pin=archive_pin)
                elif args.action == "clerk-read":
                    sys.stdout.buffer.write(clerk_archive.read(root, args.reference, successor=successor, pin=archive_pin))
                    return 0
                elif args.action == "recover":
                    result = recover(root, successor=successor, archive_pin=archive_pin)
                elif args.action == "receipt":
                    result = receipt_status(root, args.request_id, successor=successor)
                elif args.action == "read":
                    result = concept.read(root, args.selector, successor=successor)
                elif args.action == "video-status-preview":
                    result = migration.preview_video_status(root, successor)
                elif args.action == "timestamp-preview":
                    result = timestamp_cleanup.preview(root, successor)
                elif args.action == "version-preview":
                    result = version_declaration.preview(root, successor)
                elif args.action == "version-rehearse":
                    result = version_declaration.rehearse(root, args.expect_digest, args.actor, args.request_id)
                elif args.action == "timestamp-rehearse":
                    result = timestamp_cleanup.rehearse(root, args.expect_digest, args.actor, args.request_id)
                elif args.action == "video-status-rehearse":
                    result = migration.apply_video_status(root, args.expect_digest, args.actor, args.request_id)
                elif args.action == "migration-checkpoint":
                    result = migration.inspect_checkpoint(root, successor, args.canonical_checkpoint)
                elif args.action in {"video-status-apply", "video-status-recover"}:
                    command = (migration.apply_video_status if args.action == "video-status-apply"
                               else migration.recover_video_status)
                    result = command(root, args.expect_digest, args.actor, args.request_id, successor=successor,
                                     checkpoint=args.canonical_checkpoint, checkpoint_sha256=args.checkpoint_sha256,
                                     writers_stopped=args.writers_stopped)
                elif args.action in {"timestamp-apply", "timestamp-recover"}:
                    command = timestamp_cleanup.apply if args.action == "timestamp-apply" else timestamp_cleanup.recover
                    result = command(root, args.expect_digest, args.actor, args.request_id, successor=successor,
                                     checkpoint=args.canonical_checkpoint, checkpoint_sha256=args.checkpoint_sha256,
                                     writers_stopped=args.writers_stopped)
                elif args.action in {"version-apply", "version-recover"}:
                    command = version_declaration.apply if args.action == "version-apply" else version_declaration.recover
                    result = command(root, args.expect_digest, args.actor, args.request_id, successor=successor,
                                     checkpoint=args.canonical_checkpoint, checkpoint_sha256=args.checkpoint_sha256,
                                     writers_stopped=args.writers_stopped)
                elif args.action in {"update", "delete"}:
                    replacement = input_bytes(args.source) if args.action == "update" else None
                    result = concept.change(root, args.selector, args.revision, args.actor,
                                            replacement=replacement, dry_run=args.dry_run, successor=successor,
                                            request_id=args.request_id,
                                             expected_path=getattr(args, "expect_path", None),
                                              clerk_session=getattr(args, "clerk_session", None), archive_pin=archive_pin)
                elif args.action == "journal-read":
                    result = journal.read(root, args.day, successor=successor)
                elif args.action in {"journal-update", "journal-delete"}:
                    edits = {}
                    if args.action == "journal-update":
                        edits = dict(replacement=input_bytes(args.source, limit=journal.MAX_ENTRY),
                                     category=args.category, subject=args.subject, clear_subject=args.clear_subject)
                    result = journal.change(root, args.day, args.entry, args.revision, args.actor,
                                            dry_run=args.dry_run, successor=successor,
                                            request_id=args.request_id, **edits)
                elif args.action == "journal-add":
                    raw, subject = journal_input(args)
                    result = journal.add(root, raw, args.actor, day=args.date, at=args.at,
                                         subject=subject, category=args.category,
                                         dry_run=args.dry_run, successor=successor, request_id=args.request_id,
                                         revision=args.revision)
                else:
                    routes = read_text(read_file(Path(args.routes).expanduser()))
                    if args.action == "template":
                        indexes, _ = inventory(root, collect_ids=False)
                        print(resolve_route(args.type, routes, indexes).template(), end="")
                        return 0
                    raw = input_bytes(args.source)
                    result = create(root, routes, raw, args.actor, dry_run=args.dry_run, successor=successor,
                                    request_id=args.request_id)
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
