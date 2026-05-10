"""CLI entry point: argparse dispatch for `python -m planner <cmd>`."""

from __future__ import annotations

import argparse
import sys

from planner.engine import (
    cmd_check,
    cmd_doctor,
    cmd_find,
    cmd_plan,
    cmd_review_substance,
    cmd_show,
)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Supplement Slot Planner",
        epilog=(
            "Agent workflows:\n"
            "  Data-only YAML edits:\n"
            "    uv run python -m planner find \"<name form brand>\"\n"
            "    uv run python -m planner review-substance data/substances/<card>.yaml\n"
            "    # edit substance-to-substance links in data/relations.yaml\n"
            "    uv run python -m planner check\n"
            "    uv run python -m planner doctor\n\n"
            "  Schedule-affecting edits:\n"
            "    uv run python -m planner plan\n"
            "    uv run python -m planner doctor\n\n"
            "  Planner, schema, or test changes:\n"
            "    uv run python -m planner plan\n"
            "    uv run python -m planner doctor\n"
            "    uv run pytest\n"
            "    uv run python -m planner plan\n\n"
            "Notes:\n"
            "  check, plan, and doctor automatically generate missing product/substance\n"
            "  ids and rename product/substance files when that fix is deterministic.\n"
            "  plan runs check first and rewrites schedule.yaml."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = parser.add_subparsers(dest="cmd", required=False)

    sub.add_parser("check", help="validate all YAML data files")

    sub.add_parser("plan", help="generate schedule.yaml from non-inactive stacks")
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

    if args.cmd == "check":
        sys.exit(cmd_check())
    elif args.cmd == "find":
        sys.exit(cmd_find(args.query, args.limit))
    elif args.cmd == "plan":
        sys.exit(cmd_plan())
    elif args.cmd == "doctor":
        sys.exit(cmd_doctor())
    elif args.cmd == "review-substance":
        sys.exit(cmd_review_substance(args.path))


if __name__ == "__main__":
    main()
