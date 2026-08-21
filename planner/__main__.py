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
    cmd_review,
    cmd_show,
)
from planner.engine.results import ResearchStateResult, ReviewResult, ShowResult

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
            "  python -m planner groom                  — show the next grooming card\n"
            "\n"
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

    sub.add_parser("groom", help="show the next priority grooming card")


    if len(sys.argv) == 1:
        _exit_with_result(cmd_show(data_root=data_root))

    args = parser.parse_args()
    command = cast(str | None, args.cmd)
    handlers: dict[str, CommandHandler] = {
        "audit": _run_audit,
        "check": _run_check,
        "find": _run_find,
        "groom": _run_grooming,
        "review": _run_review,
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
    del args
    return _print_result(cmd_grooming_next(data_root=data_root))


def _run_review(_args: argparse.Namespace, data_root: Path | None) -> int:
    return _print_result(cmd_review(data_root=data_root))


def _exit_with_result(result: ReviewResult | ShowResult) -> None:
    sys.exit(_print_result(result))


def _print_result(result: ReviewResult | ShowResult | ResearchStateResult) -> int:
    if result.output:
        print(result.output, end="")
    if isinstance(result, (ReviewResult, ResearchStateResult)) and result.stderr:
        print(result.stderr, end="", file=sys.stderr)
    return result.exit_code


if __name__ == "__main__":
    main()
