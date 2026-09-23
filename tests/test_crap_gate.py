"""Focused tests for repository quality gates."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from coverage import CoverageData
from pytest_crap.calculator import FunctionScore
from scripts.check_mutation_gate import check_mutation_gate
from scripts.check_supply_chain_pins import _check_action_refs
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


def test_violations_block_the_threshold_boundary() -> None:
    score = FunctionScore("boundary", "planner/boundary.py", 1, 2, 5, 0.0, DEFAULT_THRESHOLD)

    assert violations([score]) == [score]


def test_supply_chain_pin_check_rejects_dash_uses_steps(tmp_path: Path) -> None:
    workflow_dir = tmp_path / ".github" / "workflows"
    workflow_dir.mkdir(parents=True)
    workflow_dir.joinpath("ci.yml").write_text(
        "name: CI\njobs:\n  test:\n    steps:\n      - uses: example/action@main\n",
        encoding="utf-8",
    )

    assert any("example/action@main" in error for error in _check_action_refs(tmp_path))


def test_supply_chain_pin_check_rejects_quoted_uses_value(tmp_path: Path) -> None:
    workflow_dir = tmp_path / ".github" / "workflows"
    workflow_dir.mkdir(parents=True)
    workflow_dir.joinpath("ci.yml").write_text(
        'jobs:\n  test:\n    steps:\n      uses: "example/action@v2" # floating major tag\n',
        encoding="utf-8",
    )

    assert any("example/action@v2" in error for error in _check_action_refs(tmp_path))


def test_mutation_gate_rejects_incomplete_totals(tmp_path: Path) -> None:
    stats = tmp_path / "stats.json"
    stats.write_text(
        json.dumps({
            "total": 10,
            "killed": 1,
            "survived": 0,
            "no_tests": 0,
            "suspicious": 0,
            "timeout": 0,
            "check_was_interrupted_by_user": 0,
            "segfault": 0,
            "not_checked": 0,
        }),
        encoding="utf-8",
    )

    with pytest.raises(SystemExit, match="classified mutants"):
        check_mutation_gate(stats)


def test_mutation_gate_ratchets_known_survivors(tmp_path: Path) -> None:
    stats = tmp_path / "stats.json"
    stats.write_text(
        json.dumps({
            "total": 1,
            "killed": 0,
            "survived": 1,
            "no_tests": 0,
            "suspicious": 0,
            "timeout": 0,
            "check_was_interrupted_by_user": 0,
            "segfault": 0,
            "not_checked": 0,
        }),
        encoding="utf-8",
    )
    results = tmp_path / "results.txt"
    results.write_text("    known: survived\n", encoding="utf-8")
    baseline = tmp_path / "baseline.txt"
    baseline.write_text("known\n", encoding="utf-8")

    assert check_mutation_gate(stats, results_path=results, baseline_path=baseline) == 0

    results.write_text("    new: survived\n", encoding="utf-8")
    assert check_mutation_gate(stats, results_path=results, baseline_path=baseline) == 1
