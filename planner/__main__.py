"""CLI entry point: argparse dispatch for `python -m planner <cmd>`."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from planner.engine import (
    cmd_audit,
    cmd_check,
    cmd_find,
    cmd_review,
    cmd_review_substance,
    cmd_show,
)


def main(data_root: Path | None = None) -> None:
    parser = argparse.ArgumentParser(
        description="Supplement Slot Planner",
        epilog=(
            "Usage:\n"
            "  python -m planner                        — show schedule (default)\n"
            "  python -m planner check                  — validate data files only\n"
            "  python -m planner review                 — concerns, relations, risk flags, pathways\n"
            "  python -m planner audit                  — cleanup candidates and card-quality checks\n"
            "  python -m planner find <words>           — search cards\n"
            "  python -m planner review-substance <path> — single-card trait checklist\n\n"
            "Notes:\n"
            "  check and the default command automatically generate missing\n"
            "  product/substance ids and rename files when the fix is deterministic."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = parser.add_subparsers(dest="cmd", required=False)

    sub.add_parser("check", help="validate all YAML data files")

    audit_parser = sub.add_parser("audit", help="concerns, relations status, and cleanup candidates")
    audit_parser.add_argument(
        "--full",
        action="store_true",
        help="also run deep card quality checks: stub detection, missing fields, intake review",
    )

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
    sub.add_parser(
        "review",
        help="knowledge-section review of active stack (concerns, relations, risk flags, pathways)",
    )

    review_substance = sub.add_parser(
        "review-substance",
        help="show a grouped trait checklist for one substance card",
    )
    review_substance.add_argument("path", help="path to data/substances/*.yaml")

    if len(sys.argv) == 1:
        sys.exit(cmd_show(data_root=data_root).exit_code)

    args = parser.parse_args()

    if args.cmd == "audit":
        sys.exit(cmd_audit(data_root=data_root, full=args.full).exit_code)
    elif args.cmd == "check":
        sys.exit(cmd_check(data_root=data_root).exit_code)
    elif args.cmd == "find":
        sys.exit(cmd_find(args.query, args.limit, data_root=data_root).exit_code)
    elif args.cmd == "review":
        sys.exit(cmd_review(data_root=data_root).exit_code)
    elif args.cmd == "review-substance":
        sys.exit(cmd_review_substance(args.path, data_root=data_root).exit_code)


if __name__ == "__main__":
    main()
