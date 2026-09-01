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
    cmd_review,
    cmd_show,
)
from planner.engine.results import ReviewResult, ShowResult
from planner.maintenance import cmd_normalize

CommandHandler = Callable[[argparse.Namespace, Path | None], int]


def main(data_root: Path | None = None) -> None:
    parser = argparse.ArgumentParser(
        description="Supplement Slot Planner; bare invocation prints the schedule",
        epilog=(
            "Usage:\n"
            "Commands:\n"
            "  (bare invocation) or show      — print the schedule\n"
            "  check                          — validate all YAML data files without rewriting\n"
            "  normalize                      — explicitly rewrite card IDs, filenames, and refs\n"
            "  find WORDS...                  — search cards\n"
            "  review                         — active-stack health and review"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = parser.add_subparsers(dest="cmd", required=False)

    sub.add_parser("show", help="regenerate and print the schedule")
    check_parser = sub.add_parser("check", help="validate all YAML data files without rewriting")
    check_parser.epilog = "check validates canonical inputs and reports inconsistencies without rewriting them."
    sub.add_parser("normalize", help="explicitly rewrite card IDs, filenames, and references")

    find_parser = sub.add_parser(
        "find",
        help="search existing product/substance cards by multiple words",
    )
    find_parser.add_argument("query", nargs="+", help="search words")
    sub.add_parser(
        "review",
        help="knowledge-section review of active stack (concerns, relations, fact memberships)",
    )

    if len(sys.argv) == 1:
        _exit_with_result(cmd_show(data_root=data_root))

    args = parser.parse_args()
    command = cast(str | None, args.cmd)
    handlers: dict[str, CommandHandler] = {
        "show": _run_show,
        "check": _run_check,
        "normalize": _run_normalize,
        "find": _run_find,
        "review": _run_review,
    }
    if command is None:
        parser.print_help()
        sys.exit(2)
    handler = handlers.get(command)
    if handler is not None:
        sys.exit(handler(args, data_root))


def _run_show(_args: argparse.Namespace, data_root: Path | None) -> int:
    return _print_result(cmd_show(data_root=data_root))


def _run_check(_args: argparse.Namespace, data_root: Path | None) -> int:
    return cmd_check(data_root=data_root).exit_code


def _run_normalize(_args: argparse.Namespace, data_root: Path | None) -> int:
    return cmd_normalize(data_root=data_root)


def _run_find(args: argparse.Namespace, data_root: Path | None) -> int:
    return cmd_find(cast(list[str], args.query), 8, data_root=data_root).exit_code


def _run_review(_args: argparse.Namespace, data_root: Path | None) -> int:
    return _print_result(cmd_review(data_root=data_root))


def _exit_with_result(result: ReviewResult | ShowResult) -> None:
    sys.exit(_print_result(result))


def _print_result(result: ReviewResult | ShowResult) -> int:
    if result.output:
        print(result.output, end="")
    if isinstance(result, ReviewResult) and result.stderr:
        print(result.stderr, end="", file=sys.stderr)
    return result.exit_code


if __name__ == "__main__":
    main()
