"""Schema-driven Create commands for a standalone OKF bundle."""

import argparse
import json
from pathlib import Path
import sys

from .schema import LIMIT, Refused, read_text, resolve_route
from .writer import create, inventory, open_bundle, read_file, recover


def parser():
    command = argparse.ArgumentParser(prog="innersanctum", description=__doc__)
    concepts = command.add_subparsers(required=True).add_parser("concept")
    actions = concepts.add_subparsers(dest="action", required=True)
    template = actions.add_parser("template", help="Print a draft from a declared type schema")
    template.add_argument("type")
    new = actions.add_parser("create", help="Create one concept and update its index and log")
    new.add_argument("--from", dest="source", required=True, help="UTF-8 draft file, or - for stdin")
    new.add_argument("--actor", required=True, help="Actual producer for provenance and audit")
    new.add_argument("--dry-run", action="store_true", help="Validate and preview without writing")
    recovery = actions.add_parser("recover", help="Finish an interrupted Create without replanning")
    for action in (template, new, recovery):
        action.add_argument("--bundle", required=True, help="Explicit standalone bundle directory")
    for action in (template, new):
        action.add_argument("--routes", required=True, help="TOML map of authoring destinations")
    return command


def main(argv=None):
    args = parser().parse_args(argv)
    checkout = Path(__file__).resolve().parents[2]
    try:
        root = open_bundle(args.bundle, checkout)
        if args.action == "recover":
            result = recover(root)
        else:
            routes = read_text(read_file(Path(args.routes).expanduser()))
            if args.action == "template":
                indexes, _ = inventory(root, collect_ids=False)
                print(resolve_route(args.type, routes, indexes).template(), end="")
                return 0
            raw = (sys.stdin.buffer.read(LIMIT + 1) if args.source == "-"
                   else read_file(Path(args.source).expanduser()))
            result = create(root, routes, raw, args.actor, dry_run=args.dry_run)
        print(json.dumps(result, sort_keys=True))
    except Refused as error:
        print(f"innersanctum: {error}", file=sys.stderr)
        return 2
    except (OSError, UnicodeError):
        print("innersanctum: I/O failed. If a Create is pending, recover it before retrying.",
              file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        print("innersanctum: interrupted. If a Create is pending, recover it before retrying.",
              file=sys.stderr)
        return 130
    return 0


if __name__ == "__main__":
    sys.exit(main())
