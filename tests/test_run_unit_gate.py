from __future__ import annotations

import json
from pathlib import Path
from typing import cast

import pytest
from scripts import run_unit_gate


def _make_modules(tmp_path: Path, names: list[str]) -> Path:
    tests_root = tmp_path / "tests"
    for name in names:
        path = tests_root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("# fixture\n")
    return tests_root


def test_discovery_matches_both_patterns_recursively_and_sorts(tmp_path: Path) -> None:
    tests_root = _make_modules(
        tmp_path,
        [
            "z_test.py",
            "test_z.py",
            "nested/test_a.py",
            "nested/a_test.py",
            "nested/not_a_test.txt",
            "nested/test_no.pyc",
            "test_z.py",
        ],
    )

    assert run_unit_gate.discover_test_modules(tests_root) == [
        tests_root / "nested/a_test.py",
        tests_root / "nested/test_a.py",
        tests_root / "test_z.py",
        tests_root / "z_test.py",
    ]


def test_planner_failure_is_fail_fast(tmp_path: Path) -> None:
    tests_root = _make_modules(tmp_path, ["test_one.py"])
    calls: list[list[str]] = []

    def runner(command: run_unit_gate.Command) -> int:
        calls.append(list(command))
        return 3

    assert run_unit_gate.run_unit_gate(tests_root, command_runner=runner) == 3
    assert calls == [[run_unit_gate.sys.executable, "-m", "planner", "check"]]


@pytest.mark.parametrize("test_root_exists", [False, True])
def test_missing_or_empty_discovery_fails_closed_without_pytest(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    *,
    test_root_exists: bool,
) -> None:
    tests_root = tmp_path / "tests"
    if test_root_exists:
        tests_root.mkdir()
    calls: list[list[str]] = []

    def runner(command: run_unit_gate.Command) -> int:
        calls.append(list(command))
        return 0

    assert run_unit_gate.run_unit_gate(tests_root, command_runner=runner) == 5
    assert calls == [[run_unit_gate.sys.executable, "-m", "planner", "check"]]
    assert capsys.readouterr().err == f"No unit test modules discovered under {tests_root}.\n"


def test_fast_unit_suite_selects_curated_modules_in_one_invocation(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    tests_root = _make_modules(
        tmp_path,
        [
            "test_plan_search.py",
            "test_warning_humanization.py",
            "test_audit_command.py",
            "test_ontology_artifacts.py",
        ],
    )
    calls: list[list[str]] = []

    def runner(command: run_unit_gate.Command) -> int:
        calls.append(list(command))
        return 0

    assert run_unit_gate.run_unit_gate(tests_root, command_runner=runner, suite="fast-unit") == 0
    assert len(calls) == 2
    assert calls[1] == [
        run_unit_gate.sys.executable,
        "-m",
        "pytest",
        "-q",
        "-m",
        run_unit_gate.PYTEST_MARKERS,
        str(tests_root / "test_plan_search.py"),
        str(tests_root / "test_warning_humanization.py"),
    ]
    assert capsys.readouterr().out == "Running fast-unit suite (2 targets)\n"


def test_coverage_suite_selects_fast_modules_and_only_unique_smoke_nodes(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    tests_root = _make_modules(
        tmp_path,
        [
            *(path.relative_to(Path("tests")).as_posix() for path in run_unit_gate.FAST_UNIT_MODULES),
            *(path.relative_to(Path("tests")).as_posix() for path in run_unit_gate.COVERAGE_ONLY_MODULES),
            "test_scheduler_reviewer_authority.py",
            "test_audit_command.py",
        ],
    )
    calls: list[list[str]] = []

    def runner(command: run_unit_gate.Command) -> int:
        calls.append(list(command))
        return 0

    assert run_unit_gate.run_unit_gate(tests_root, command_runner=runner, suite="coverage") == 0
    assert len(calls) == 2
    expected_inventory = [
        "tests/test_card_reference_integrity.py",
        "tests/test_dashboard_review.py",
        "tests/test_formal_uniqueness.py",
        "tests/test_loader_fail_closed.py",
        "tests/test_maintenance.py",
        "tests/test_pillbox_loader_contract.py",
        "tests/test_plan_relation_scheduling.py",
        "tests/test_plan_search.py",
        "tests/test_product_validation.py",
        "tests/test_read_model_relations.py",
        "tests/test_relation_conflicts.py",
        "tests/test_review_command.py",
        "tests/test_review_substance_command.py",
        "tests/test_run_unit_gate.py",
        "tests/test_scheduling_constraint_audit.py",
        "tests/test_scheduling_constraint_runtime.py",
        "tests/test_scheduling_units.py",
        "tests/test_schemas.py",
        "tests/test_warning_humanization.py",
        "tests/test_scheduler_reviewer_authority.py::test_reviewer_only_knowledge_does_not_change_slot_assignment",
    ]
    expected_coverage_modules = [Path(item) for item in expected_inventory if "::" not in item]
    assert calls[1] == [
        run_unit_gate.sys.executable,
        "-m",
        "pytest",
        "-q",
        "-m",
        run_unit_gate.PYTEST_MARKERS,
        *(str(tests_root / path.relative_to(Path("tests"))) for path in expected_coverage_modules),
        "tests/test_scheduler_reviewer_authority.py::test_reviewer_only_knowledge_does_not_change_slot_assignment",
        "--cov=planner",
        "--cov-report=",
        "--cov-fail-under=0",
    ]
    assert calls[1].count("--cov-fail-under=0") == 1
    assert not any(
        argument.startswith("--cov-fail-under=") and argument != "--cov-fail-under=0" for argument in calls[1]
    )
    assert "-n" not in calls[1]
    assert "--dist" not in calls[1]
    smoke_node = expected_inventory[19]
    assert calls[1].count(smoke_node) == 1
    assert len(calls[1][6:-3]) == len(set(calls[1][6:-3]))
    assert run_unit_gate._coverage_inventory_items() == expected_inventory
    assert not set(expected_inventory) & {path.as_posix() for path in run_unit_gate.ONTOLOGY_CONTRACT_MODULES}
    assert capsys.readouterr().out == "Running coverage suite (20 targets)\n"


def test_coverage_suite_propagates_pytest_failure_without_followup_process(tmp_path: Path) -> None:
    tests_root = _make_modules(tmp_path, ["test_plan_search.py"])
    calls: list[list[str]] = []

    def runner(command: run_unit_gate.Command) -> int:
        calls.append(list(command))
        return 0 if len(calls) == 1 else 23

    assert run_unit_gate.run_unit_gate(tests_root, command_runner=runner, suite="coverage") == 23
    assert len(calls) == 2


def test_ontology_contract_suite_runs_three_curated_groups_in_order(tmp_path: Path) -> None:
    tests_root = _make_modules(
        tmp_path,
        [
            "test_ontology_artifacts.py",
            "test_ontology_assertion_runtime.py",
            "test_ontology_compiler_outputs.py",
            "test_ontology_formal_runtime_assertions.py",
            "test_ontology_ontoclean_contract.py",
            "test_ontology_repository_contract.py",
            "test_ontology_repository_projection.py",
            "test_ontology_runtime_loader.py",
            "test_ontology_shacl_fixtures.py",
        ],
    )
    calls: list[list[str]] = []

    def runner(command: run_unit_gate.Command) -> int:
        calls.append(list(command))
        return 0

    assert run_unit_gate.run_unit_gate(tests_root, command_runner=runner, suite="ontology-contract") == 0
    assert len(calls) == 4
    assert [[Path(target).name for target in call[6:]] for call in calls[1:]] == [
        ["test_ontology_compiler_outputs.py"],
        [
            "test_ontology_formal_runtime_assertions.py",
            "test_ontology_ontoclean_contract.py",
            "test_ontology_repository_contract.py",
        ],
        [
            "test_ontology_artifacts.py",
            "test_ontology_assertion_runtime.py",
            "test_ontology_repository_projection.py",
            "test_ontology_runtime_loader.py",
            "test_ontology_shacl_fixtures.py",
        ],
    ]


def test_ontology_contract_group_failure_stops_following_groups(tmp_path: Path) -> None:
    tests_root = _make_modules(
        tmp_path,
        [path.as_posix().removeprefix("tests/") for path in run_unit_gate.ONTOLOGY_CONTRACT_MODULES],
    )
    calls: list[list[str]] = []

    def runner(command: run_unit_gate.Command) -> int:
        calls.append(list(command))
        return 0 if len(calls) == 1 else 17

    assert run_unit_gate.run_unit_gate(tests_root, command_runner=runner, suite="ontology-contract") == 17
    assert len(calls) == 2


def test_smoke_suite_uses_one_short_node_invocation_without_discovery(tmp_path: Path) -> None:
    tests_root = _make_modules(tmp_path, ["test_unused.py"])
    calls: list[list[str]] = []

    def runner(command: run_unit_gate.Command) -> int:
        calls.append(list(command))
        return 0

    assert run_unit_gate.run_unit_gate(tests_root, command_runner=runner, suite="smoke") == 0
    assert calls == [
        [run_unit_gate.sys.executable, "-m", "planner", "check"],
        [
            run_unit_gate.sys.executable,
            "-m",
            "pytest",
            "-q",
            "-m",
            run_unit_gate.PYTEST_MARKERS,
            *run_unit_gate.SMOKE_NODE_IDS,
        ],
    ]


def test_all_suite_runs_discovered_modules_once_in_order(tmp_path: Path) -> None:
    tests_root = _make_modules(tmp_path, ["test_two.py", "nested/test_one.py"])
    calls: list[list[str]] = []

    def runner(command: run_unit_gate.Command) -> int:
        calls.append(list(command))
        return 0

    assert run_unit_gate.run_unit_gate(tests_root, command_runner=runner, suite="all") == 0
    assert len(calls) == 2
    assert calls[1][-2:] == [str(tests_root / "nested/test_one.py"), str(tests_root / "test_two.py")]


@pytest.mark.parametrize(("status", "expected"), [(1, 1), (-9, 137), (2, 2)])
def test_pytest_status_is_returned_and_no_followup_process_is_started(
    tmp_path: Path,
    *,
    status: int,
    expected: int,
) -> None:
    tests_root = _make_modules(tmp_path, ["test_one.py"])
    calls: list[list[str]] = []

    def runner(command: run_unit_gate.Command) -> int:
        calls.append(list(command))
        return 0 if len(calls) == 1 else status

    assert run_unit_gate.run_unit_gate(tests_root, command_runner=runner) == expected
    assert len(calls) == 2


def test_suite_inventory_is_machine_readable_without_running_planner(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(run_unit_gate.sys, "argv", ["run_unit_gate.py", "--list-suites"])

    assert run_unit_gate.main() == 0
    payload = cast(dict[str, object], json.loads(capsys.readouterr().out))
    assert payload == run_unit_gate.suite_inventory()
