"""Stopped operator operation, separate from serve. Requires both approved baseline pins."""

import argparse
from pathlib import Path

from innersanctum import handover, reaction_filing as filing
from innersanctum.schema import Refused


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live-checkout", type=Path, required=True)
    parser.add_argument("--expect-adoption", required=True)
    parser.add_argument("--expect-source-catalog", required=True)
    parser.add_argument("--writers-stopped", action="store_true", required=True)
    args = parser.parse_args()
    if args.live_checkout.absolute() != filing.CHECKOUT:
        parser.error("Select this tool’s exact checkout.")
    try:
        with handover.live_checkout(filing.CHECKOUT) as (root, successor):
            if handover.SUCCESSOR.fullmatch(successor)[2].decode() != args.expect_adoption:
                raise Refused("Unexpected Personal adoption.")
            print(filing.prepare_personal(root, successor, args.expect_source_catalog))
    except (OSError, ValueError, Refused) as err:
        parser.exit(2, f"Not prepared: {err}\n")


if __name__ == "__main__":
    main()
