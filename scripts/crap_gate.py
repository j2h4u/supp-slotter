"""Enforce the default CRAP threshold over a bounded coverage run."""

from __future__ import annotations

from argparse import ArgumentParser
from collections.abc import Sequence
from pathlib import Path
from typing import Protocol, cast

from coverage import CoverageData
from pytest_crap.calculator import FunctionScore, calculate_crap

DEFAULT_THRESHOLD = 30.0
DEFAULT_SOURCE_ROOT = Path("planner")


class _GateArguments(Protocol):
    coverage: Path
    src: Path


def collect_scores(source_root: Path, coverage_file: Path) -> list[FunctionScore]:
    """Calculate CRAP scores for every production function in *source_root*."""

    data = CoverageData(basename=coverage_file)
    data.read()
    covered_by_path = {Path(filename).resolve(): set(data.lines(filename) or ()) for filename in data.measured_files()}
    scores: list[FunctionScore] = []
    for source_file in sorted(source_root.rglob("*.py")):
        scores.extend(calculate_crap(str(source_file), covered_by_path.get(source_file.resolve(), set())))
    return scores


def violations(scores: Sequence[FunctionScore], threshold: float = DEFAULT_THRESHOLD) -> list[FunctionScore]:
    """Return scores strictly above the standard CRAP threshold."""

    return sorted(
        (score for score in scores if score.crap > threshold),
        key=lambda score: (-score.crap, score.file_path, score.start_line, score.name),
    )


def _build_parser() -> ArgumentParser:
    parser = ArgumentParser(description="Enforce the default CRAP threshold.")
    parser.add_argument("--coverage", type=Path, required=True, help="coverage.py data file from the bounded test run")
    parser.add_argument("--src", type=Path, default=DEFAULT_SOURCE_ROOT, help="production source root to inspect")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = cast(_GateArguments, _build_parser().parse_args(argv))
    coverage_file = args.coverage.resolve()
    source_root = args.src.resolve()
    if not coverage_file.is_file():
        print(f"CRAP gate failed: coverage data not found: {coverage_file}")
        return 2
    if not source_root.is_dir():
        print(f"CRAP gate failed: source root not found: {source_root}")
        return 2

    scores = collect_scores(source_root, coverage_file)
    failed = violations(scores)
    if failed:
        print(f"CRAP gate failed: {len(failed)} function(s) exceed threshold {DEFAULT_THRESHOLD:.0f}")
        for score in failed:
            print(
                f"  {score.file_path}:{score.start_line} {score.name} "
                f"CRAP={score.crap:.2f} CC={score.cc} coverage={score.coverage_percent:.1f}%"
            )
        return 1

    print(f"CRAP gate passed: {len(scores)} function(s), threshold {DEFAULT_THRESHOLD:.0f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
