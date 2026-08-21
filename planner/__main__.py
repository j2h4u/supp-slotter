"""CLI entry point: argparse dispatch for `python -m planner <cmd>`."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Callable
from pathlib import Path
from typing import cast

from planner.engine import (
    cmd_audit,
    cmd_check,
    cmd_find,
    cmd_grooming_next,
    cmd_grooming_research,
    cmd_review,
    cmd_review_substance,
    cmd_show,
)
from planner.engine.results import GroomingResult, ResearchStateResult, ReviewResult, ShowResult

CommandHandler = Callable[[argparse.Namespace, Path | None], int]


def main(data_root: Path | None = None) -> None:
    parser = argparse.ArgumentParser(
        description="Supplement Slot Planner",
        epilog=(
            "Usage:\n"
            "  python -m planner                        — show schedule (default)\n"
            "  python -m planner check                  — validate data files only\n"
            "  python -m planner review                 — concerns, relations, fact memberships\n"
            "  python -m planner audit                  — diagnostics and card-quality checks\n"
            "  python -m planner find <words>           — search cards\n"
            "  python -m planner grooming next          — show the next enrichment batch\n"
            "  python -m planner review-substance <path> — single-card trait checklist\n\n"
            "Notes:\n"
            "  check and the default command automatically generate missing\n"
            "  product/substance ids and rename files when the fix is deterministic."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = parser.add_subparsers(dest="cmd", required=False)

    sub.add_parser("check", help="validate all YAML data files")

    audit_parser = sub.add_parser("audit", help="diagnostics and card-quality checks")
    audit_parser.add_argument(
        "--full",
        action="store_true",
        help="also include the generic full-audit diagnostics",
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
        help="knowledge-section review of active stack (concerns, relations, fact memberships)",
    )

    grooming = sub.add_parser("grooming", help="read-only enrichment queue")
    grooming_sub = grooming.add_subparsers(dest="grooming_cmd", required=True)
    grooming_next = grooming_sub.add_parser("next", help="show active cards never attempted")
    grooming_next.add_argument(
        "--limit",
        type=int,
        default=None,
        help="positive maximum number of cards (default: 1)",
    )
    grooming_research = grooming_sub.add_parser("research", help="list active substance cards by research state")
    grooming_research.add_argument("--state", required=True, help="research state enum value")
    grooming_research.add_argument(
        "--limit", type=int, default=None, help="positive maximum number of cards (default: 1)"
    )

    review_substance = sub.add_parser(
        "review-substance",
        help="show a grouped trait checklist for one substance card",
    )
    review_substance.add_argument("path", help="path to data/substances/*.yaml")
    review_substance.add_argument(
        "--compact",
        action="store_true",
        help="show only current traits, relation matches, and concerns",
    )

    if len(sys.argv) == 1:
        _exit_with_result(cmd_show(data_root=data_root))

    args = parser.parse_args()
    command = cast(str | None, args.cmd)
    handlers: dict[str, CommandHandler] = {
        "audit": _run_audit,
        "check": _run_check,
        "find": _run_find,
        "grooming": _run_grooming,
        "review": _run_review,
        "review-substance": _run_review_substance,
    }
    if command is None:
        parser.print_help()
        sys.exit(2)
    handler = handlers.get(command)
    if handler is not None:
        sys.exit(handler(args, data_root))


def _run_audit(args: argparse.Namespace, data_root: Path | None) -> int:
    return cmd_audit(data_root=data_root, full=cast(bool, args.full)).exit_code


def _run_check(_args: argparse.Namespace, data_root: Path | None) -> int:
    return cmd_check(data_root=data_root).exit_code


def _run_find(args: argparse.Namespace, data_root: Path | None) -> int:
    return cmd_find(cast(list[str], args.query), cast(int, args.limit), data_root=data_root).exit_code


def _run_grooming(args: argparse.Namespace, data_root: Path | None) -> int:
    if cast(str, args.grooming_cmd) == "next":
        return _print_result(cmd_grooming_next(cast(int, args.limit), data_root=data_root))
    if cast(str, args.grooming_cmd) == "research":
        return _print_result(
            cmd_grooming_research(cast(str, args.state), cast(int | None, args.limit), data_root=data_root)
        )
    return 2


def _run_review(_args: argparse.Namespace, data_root: Path | None) -> int:
    return _print_result(cmd_review(data_root=data_root))


def _run_review_substance(args: argparse.Namespace, data_root: Path | None) -> int:
    return _print_result(
        cmd_review_substance(
            cast(str, args.path),
            data_root=data_root,
            compact=cast(bool, args.compact),
        )
    )


def _exit_with_result(result: ReviewResult | ShowResult) -> None:
    sys.exit(_print_result(result))


def _print_result(result: ReviewResult | ShowResult | GroomingResult | ResearchStateResult) -> int:
    if result.output:
        print(result.output, end="")
    if isinstance(result, (ReviewResult, GroomingResult, ResearchStateResult)) and result.stderr:
        print(result.stderr, end="", file=sys.stderr)
    return result.exit_code


if __name__ == "__main__":
    main()
