"""Focused tests for the blocking CRAP quality gate."""

from __future__ import annotations

from pathlib import Path

from coverage import CoverageData
from pytest_crap.calculator import FunctionScore
from scripts.crap_gate import DEFAULT_THRESHOLD, collect_scores, violations


def _coverage_file(tmp_path: Path, source_file: Path, lines: list[int]) -> Path:
    coverage_file = tmp_path / ".coverage"
    data = CoverageData(basename=coverage_file)
    data.add_lines({str(source_file.resolve()): lines})
    data.write()
    return coverage_file


def test_collect_scores_treats_unmeasured_functions_as_uncovered(tmp_path: Path) -> None:
    source_file = tmp_path / "sample.py"
    source_file.write_text(
        "def complex_function(value):\n"
        "    if value == 0:\n"
        "        return 0\n"
        "    elif value == 1:\n"
        "        return 1\n"
        "    elif value == 2:\n"
        "        return 2\n"
        "    elif value == 3:\n"
        "        return 3\n"
        "    elif value == 4:\n"
        "        return 4\n"
        "    else:\n"
        "        return 5\n"
    )
    scores = collect_scores(tmp_path, _coverage_file(tmp_path, source_file, []))

    assert len(scores) == 1
    assert violations(scores)
    assert scores[0].crap > DEFAULT_THRESHOLD


def test_violations_allow_simple_uncovered_glue() -> None:
    score = FunctionScore("glue", "planner/glue.py", 1, 2, 1, 0.0, 2.0)

    assert violations([score]) == []
