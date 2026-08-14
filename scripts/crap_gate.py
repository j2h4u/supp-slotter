from __future__ import annotations

import argparse
from collections.abc import Iterable
from pathlib import Path
from typing import Protocol, cast

from coverage import CoverageData
from pytest_crap.calculator import FunctionScore, calculate_crap

DEFAULT_THRESHOLD = 30.0
DEFAULT_SOURCE_ROOT = Path("planner")


class _GateArgs(Protocol):
    coverage: Path
    src: Path
    threshold: float


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Fail if any function exceeds the configured CRAP threshold.")
    parser.add_argument("--coverage", type=Path, required=True, help="coverage.py data file")
    parser.add_argument("--src", type=Path, default=DEFAULT_SOURCE_ROOT, help="source root to scan")
    parser.add_argument("--threshold", type=float, default=DEFAULT_THRESHOLD, help="maximum allowed CRAP per function")
    return parser


def _parse_args(argv: list[str] | None) -> _GateArgs:
    return cast(_GateArgs, _build_parser().parse_args(argv))


def _coverage_data(path: Path) -> CoverageData:
    data = CoverageData(basename=str(path))
    data.read()
    return data


def _is_under_source_root(file_path: Path, source_root: Path) -> bool:
    resolved_file = file_path.resolve()
    resolved_source = source_root.resolve()
    return resolved_file == resolved_source or resolved_source in resolved_file.parents


def _function_scores(data: CoverageData, source_root: Path) -> list[FunctionScore]:
    scores: list[FunctionScore] = []
    for raw_path in sorted(data.measured_files()):
        file_path = Path(raw_path)
        if not _is_under_source_root(file_path, source_root):
            continue

        covered_lines = set(data.lines(raw_path) or [])
        scores.extend(calculate_crap(str(file_path), covered_lines))
    return scores


def _format_offender(score: FunctionScore) -> str:
    relative_path = Path(score.file_path).resolve().relative_to(Path.cwd())
    return (
        f"{relative_path}::{score.name}:{score.start_line} "
        f"CRAP {score.crap:.2f}, complexity {score.cc}, coverage {score.coverage_percent:.1f}%"
    )


def _top_offenders(scores: Iterable[FunctionScore], threshold: float) -> list[FunctionScore]:
    return sorted(
        (score for score in scores if score.crap > threshold),
        key=lambda score: (-score.crap, score.file_path, score.start_line, score.name),
    )


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    scores = _function_scores(_coverage_data(args.coverage), args.src)
    offenders = _top_offenders(scores, args.threshold)
    if offenders:
        print(f"CRAP gate failed: {len(offenders)} function(s) exceed {args.threshold:.2f}")
        for score in offenders[:20]:
            print(f"  {_format_offender(score)}")
        return 1

    print(f"CRAP gate passed: {len(scores)} function(s), threshold {args.threshold:.2f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
