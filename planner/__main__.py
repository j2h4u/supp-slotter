"""CLI entry point: argparse dispatch for `python -m planner <cmd>`."""

from __future__ import annotations

import argparse
import sys

from planner.engine import (
    cmd_audit,
    cmd_check,
    cmd_doctor,
    cmd_find,
    cmd_review_substance,
    cmd_show,
)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Supplement Slot Planner",
        epilog=(
            "Usage:\n"
            "  python -m planner               — show schedule (default)\n"
            "  python -m planner check         — validate data files only\n"
            "  python -m planner audit         — show all concerns by kind (safety / data_quality / model_gap)\n"
            "  python -m planner doctor        — list cleanup candidates\n"
            "  python -m planner find <words>  — search cards\n\n"
            "Notes:\n"
            "  check, doctor, and the default command automatically generate missing\n"
            "  product/substance ids and rename files when the fix is deterministic."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = parser.add_subparsers(dest="cmd", required=False)

    sub.add_parser("check", help="validate all YAML data files")

    sub.add_parser("audit", help="show all concerns grouped by kind (safety / data_quality / model_gap)")

    sub.add_parser("doctor", help="list cleanup and refactor candidates")
    find_parser = sub.add_parser(
        "find",
        help="search existing product/substance cards by multiple words",
    )
    find_parser.add_argument("query", nargs="+", help="search words")
    find_parser.add_argument(
        "--limit",
        type=int,
        default=8,
        help="maximum results per section",
    )
    review_substance = sub.add_parser(
        "review-substance",
        help="show a grouped trait checklist for one substance card",
    )
    review_substance.add_argument("path", help="path to data/substances/*.yaml")

    if len(sys.argv) == 1:
        sys.exit(cmd_show())

    args = parser.parse_args()

    if args.cmd == "audit":
        sys.exit(cmd_audit())
    elif args.cmd == "check":
        sys.exit(cmd_check())
    elif args.cmd == "find":
        sys.exit(cmd_find(args.query, args.limit))
    elif args.cmd == "doctor":
        sys.exit(cmd_doctor())
    elif args.cmd == "review-substance":
        sys.exit(cmd_review_substance(args.path))


if __name__ == "__main__":
    main()
