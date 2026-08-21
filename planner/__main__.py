"""CLI entry point: argparse dispatch for `python -m planner <cmd>`."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Callable
from pathlib import Path
from typing import cast

from planner.engine import (
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
        description="Supplement Slot Planner (no command prints the schedule)",
        epilog=(
            "Usage:\n"
            "Commands:\n"
            "  (none)                         — print the schedule\n"
            "  check                          — normalize deterministic refs, then validate\n"
            "  find WORDS...                  — search cards\n"
            "  review                         — active-stack health and review\n"
            "  groom                          — next priority grooming card"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = parser.add_subparsers(dest="cmd", required=False)

    check_parser = sub.add_parser("check", help="normalize deterministic refs, then validate all YAML data files")
    check_parser.epilog = (
        "check first applies deterministic maintenance (IDs, filenames, and refs), then validates data."
    )

    find_parser = sub.add_parser(
        "find",
        help="search existing product/substance cards by multiple words",
    )
    find_parser.add_argument("query", nargs="+", help="search words")
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


def _run_check(_args: argparse.Namespace, data_root: Path | None) -> int:
    return cmd_check(data_root=data_root).exit_code


def _run_find(args: argparse.Namespace, data_root: Path | None) -> int:
    return cmd_find(cast(list[str], args.query), 8, data_root=data_root).exit_code


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
