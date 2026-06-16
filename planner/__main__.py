"""CLI entry point: argparse dispatch for `python -m planner <cmd>`."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

from planner.engine import (
    cmd_audit,
    cmd_check,
    cmd_find,
    cmd_review,
    cmd_review_substance,
    cmd_show,
)

CommandHandler = Callable[[argparse.Namespace, Path | None], int]


def main(data_root: Path | None = None) -> None:
    parser = argparse.ArgumentParser(
        description="Supplement Slot Planner",
        epilog=(
            "Usage:\n"
            "  python -m planner                        — show schedule (default)\n"
            "  python -m planner check                  — validate data files only\n"
            "  python -m planner review                 — concerns, relations, risk flags, pathways\n"
            "  python -m planner audit                  — diagnostics and card-quality checks\n"
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

    audit_parser = sub.add_parser("audit", help="diagnostics and card-quality checks")
    audit_parser.add_argument(
        "--full",
        action="store_true",
        help=(
            "also run deep card quality checks: no-form variants, missing fields, "
            "intake review, active product source gaps"
        ),
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
    review_substance.add_argument(
        "--compact",
        action="store_true",
        help="show only current traits, relation matches, and concerns",
    )

    if len(sys.argv) == 1:
        _exit_with_result(cmd_show(data_root=data_root))

    args = parser.parse_args()
    handlers: dict[str, CommandHandler] = {
        "audit": _run_audit,
        "check": _run_check,
        "find": _run_find,
        "review": _run_review,
        "review-substance": _run_review_substance,
    }
    handler = handlers.get(args.cmd)
    if handler is not None:
        sys.exit(handler(args, data_root))


def _run_audit(args: argparse.Namespace, data_root: Path | None) -> int:
    return cmd_audit(data_root=data_root, full=args.full).exit_code


def _run_check(_args: argparse.Namespace, data_root: Path | None) -> int:
    return cmd_check(data_root=data_root).exit_code


def _run_find(args: argparse.Namespace, data_root: Path | None) -> int:
    return cmd_find(args.query, args.limit, data_root=data_root).exit_code


def _run_review(_args: argparse.Namespace, data_root: Path | None) -> int:
    return _print_result(cmd_review(data_root=data_root))


def _run_review_substance(args: argparse.Namespace, data_root: Path | None) -> int:
    return _print_result(
        cmd_review_substance(
            args.path,
            data_root=data_root,
            compact=args.compact,
        )
    )


def _exit_with_result(result: Any) -> None:
    sys.exit(_print_result(result))


def _print_result(result: Any) -> int:
    if result.output:
        print(result.output, end="")
    if result.stderr:
        print(result.stderr, end="", file=sys.stderr)
    return result.exit_code


if __name__ == "__main__":
    main()
