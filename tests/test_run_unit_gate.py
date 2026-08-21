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
    output = capsys.readouterr().out
    assert "Running fast-unit suite (2 targets)\n" in output
    assert output.count("elapsed=") == 2


def test_runtime_scenarios_selects_exact_modules_and_nodes_in_order(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    tests_root = _make_modules(
        tmp_path,
        [path.relative_to(Path("tests")).as_posix() for path in run_unit_gate.RUNTIME_SCENARIOS_MODULES],
    )
    calls: list[list[str]] = []

    def runner(command: run_unit_gate.Command) -> int:
        calls.append(list(command))
        return 0

    assert run_unit_gate.run_unit_gate(tests_root, command_runner=runner, suite="runtime-scenarios") == 0
    assert len(calls) == 2
    pytest_command = calls[1]
    expected_modules = [
        str(tests_root / path.relative_to(Path("tests"))) for path in run_unit_gate.RUNTIME_SCENARIOS_MODULES
    ]
    expected_targets = [*expected_modules, *run_unit_gate.RUNTIME_SCENARIOS_NODE_IDS]
    assert pytest_command == [
        run_unit_gate.sys.executable,
        "-m",
        "pytest",
        "-q",
        "-m",
        run_unit_gate.PYTEST_MARKERS,
        *expected_targets,
    ]
    assert expected_targets == list(dict.fromkeys(expected_targets))
    assert "-n" not in pytest_command
    assert "--dist" not in pytest_command
    output = capsys.readouterr().out
    assert "Running runtime-scenarios suite (18 targets)\n" in output
    assert output.count("elapsed=") == 2


def test_runtime_scenarios_propagate_pytest_failure_without_followup_process(tmp_path: Path) -> None:
    tests_root = _make_modules(
        tmp_path,
        [path.relative_to(Path("tests")).as_posix() for path in run_unit_gate.RUNTIME_SCENARIOS_MODULES],
    )
    calls: list[list[str]] = []

    def runner(command: run_unit_gate.Command) -> int:
        calls.append(list(command))
        return 0 if len(calls) == 1 else 23

    assert run_unit_gate.run_unit_gate(tests_root, command_runner=runner, suite="runtime-scenarios") == 23
    assert len(calls) == 2


def test_runtime_scenarios_inventory_and_coverage_boundaries() -> None:
    suites = cast(dict[str, object], run_unit_gate.suite_inventory()["suites"])
    runtime_inventory = cast(dict[str, object], suites["runtime-scenarios"])
    assert runtime_inventory == {
        "selection": "curated-module-list-plus-fixed-node-ids",
        "items": [
            *(path.as_posix() for path in run_unit_gate.RUNTIME_SCENARIOS_MODULES),
            *run_unit_gate.RUNTIME_SCENARIOS_NODE_IDS,
        ],
    }
    release_inventory = cast(dict[str, object], suites["release"])
    release_components = cast(list[str], release_inventory["components"])
    assert release_components == ["check", "smoke", "ontology-contract", "runtime-scenarios", "coverage"]
    assert "fast-unit" not in release_components
    coverage_inventory = set(run_unit_gate._coverage_inventory_items())
    preexisting_module_overlaps = set(run_unit_gate.RUNTIME_SCENARIOS_MODULES) & (
        run_unit_gate.FAST_UNIT_MODULES | set(run_unit_gate.COVERAGE_ONLY_MODULES)
    )
    runtime_only_modules = set(run_unit_gate.RUNTIME_SCENARIOS_MODULES) - preexisting_module_overlaps
    assert not {path.as_posix() for path in runtime_only_modules} & coverage_inventory
    assert not set(run_unit_gate.RUNTIME_SCENARIOS_NODE_IDS) & coverage_inventory


def test_coverage_suite_selects_fast_modules_and_only_unique_smoke_nodes(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    tests_root = _make_modules(
        tmp_path,
        [
            *(path.relative_to(Path("tests")).as_posix() for path in run_unit_gate.FAST_UNIT_MODULES),
            *(path.relative_to(Path("tests")).as_posix() for path in run_unit_gate.COVERAGE_ONLY_MODULES),
            "test_scheduler_reviewer_authority.py",
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
        "tests/test_cli_surface.py",
        "tests/test_dashboard_review.py",
        "tests/test_dashboard_schema.py",
        "tests/test_fact_labels.py",
        "tests/test_formal_uniqueness.py",
        "tests/test_grooming_command.py",
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
    smoke_node = (
        "tests/test_scheduler_reviewer_authority.py::test_reviewer_only_knowledge_does_not_change_slot_assignment"
    )
    assert calls[1].count(smoke_node) == 1
    assert len(calls[1][6:-3]) == len(set(calls[1][6:-3]))
    assert run_unit_gate._coverage_inventory_items() == expected_inventory
    assert not set(expected_inventory) & {path.as_posix() for path in run_unit_gate.ONTOLOGY_CONTRACT_MODULES}
    output = capsys.readouterr().out
    assert "Running coverage suite (23 targets)\n" in output
    assert output.count("elapsed=") == 2


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
            "test_ontology_presentation_cache.py",
            "test_ontology_compiler_outputs.py",
            "test_linkml_core_schema.py",
            "test_architecture_contracts.py",
            "test_canonical_scheduling_policies.py",
            "test_ontology_formal_runtime_assertions.py",
            "test_ontology_ontoclean_contract.py",
            "test_ontology_repository_contract.py",
            "test_ontology_repository_projection.py",
            "test_ontology_runtime_loader.py",
            "test_ontology_shacl_fixtures.py",
            "test_yaml_duplicate_keys.py",
        ],
    )
    calls: list[list[str]] = []

    def runner(command: run_unit_gate.Command) -> int:
        calls.append(list(command))
        return 0

    assert run_unit_gate.run_unit_gate(tests_root, command_runner=runner, suite="ontology-contract") == 0
    assert len(calls) == 4

    def target_name(target: str) -> str:
        return target if "::" in target else Path(target).name

    assert [[target_name(target) for target in call[6:]] for call in calls[1:]] == [
        [
            "test_linkml_core_schema.py",
            "test_ontology_compiler_outputs.py",
            "tests/test_runtime_axis_cardinality.py::test_compiler_rejects_unknown_projection_target",
        ],
        [
            "test_architecture_contracts.py",
            "test_canonical_scheduling_policies.py",
            "test_ontology_formal_runtime_assertions.py",
            "test_ontology_ontoclean_contract.py",
            "test_ontology_repository_contract.py",
        ],
        [
            "test_ontology_artifacts.py",
            "test_ontology_assertion_runtime.py",
            "test_ontology_presentation_cache.py",
            "test_ontology_repository_projection.py",
            "test_ontology_runtime_loader.py",
            "test_ontology_shacl_fixtures.py",
            "test_yaml_duplicate_keys.py",
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


def _make_release_test_root(tmp_path: Path) -> Path:
    module_paths = (
        set(run_unit_gate.FAST_UNIT_MODULES)
        | set(run_unit_gate.COVERAGE_ONLY_MODULES)
        | set(run_unit_gate.ONTOLOGY_CONTRACT_MODULES)
        | set(run_unit_gate.RUNTIME_SCENARIOS_MODULES)
        | {Path(node_id.split("::", 1)[0]) for node_id in run_unit_gate.RELEASE_EXACT_NODE_IDS}
    )
    return _make_modules(tmp_path, [path.relative_to(Path("tests")).as_posix() for path in sorted(module_paths)])


def test_release_suite_runs_six_ordered_pytest_stages_without_fast_unit(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    tests_root = _make_release_test_root(tmp_path)
    calls: list[list[str]] = []

    def runner(command: run_unit_gate.Command) -> int:
        calls.append(list(command))
        return 0

    assert run_unit_gate.run_unit_gate(tests_root, command_runner=runner, suite="release") == 0
    pytest_calls = [call for call in calls if len(call) > 2 and call[2:4] == ["pytest", "-q"]]
    assert len(calls) == 7
    assert calls[0] == [run_unit_gate.sys.executable, "-m", "planner", "check"]
    assert len(pytest_calls) == 6
    assert pytest_calls[0][6:] == list(run_unit_gate.SMOKE_NODE_IDS)

    def target_name(target: str) -> str:
        return target if "::" in target else Path(target).name

    assert [[target_name(target) for target in call[6:]] for call in pytest_calls[1:4]] == [
        [
            "test_linkml_core_schema.py",
            "test_ontology_compiler_outputs.py",
            "tests/test_runtime_axis_cardinality.py::test_compiler_rejects_unknown_projection_target",
        ],
        [
            "test_architecture_contracts.py",
            "test_canonical_scheduling_policies.py",
            "test_ontology_formal_runtime_assertions.py",
            "test_ontology_ontoclean_contract.py",
            "test_ontology_repository_contract.py",
        ],
        [
            "test_ontology_artifacts.py",
            "test_ontology_assertion_runtime.py",
            "test_ontology_presentation_cache.py",
            "test_ontology_repository_projection.py",
            "test_ontology_runtime_loader.py",
            "test_ontology_shacl_fixtures.py",
            "test_yaml_duplicate_keys.py",
        ],
    ]
    runtime_targets = [
        *(str(tests_root / path.relative_to(Path("tests"))) for path in run_unit_gate.RUNTIME_SCENARIOS_MODULES),
        *run_unit_gate.RUNTIME_SCENARIOS_NODE_IDS,
    ]
    assert pytest_calls[4][6:] == runtime_targets
    assert pytest_calls[5][-3:] == ["--cov=planner", "--cov-report=", "--cov-fail-under=0"]
    assert pytest_calls[5].count("--cov=planner") == 1
    assert pytest_calls[5].count("--cov-report=") == 1
    assert pytest_calls[5].count("--cov-fail-under=0") == 1
    assert not any("fast-unit" in target for target in pytest_calls[1][6:])
    output = capsys.readouterr().out
    assert output.count("elapsed=") == 7
    assert "Running release suite in 6 stages\n" in output


@pytest.mark.parametrize("failure_call", range(2, 8))
def test_release_suite_fails_fast_at_each_pytest_stage(tmp_path: Path, *, failure_call: int) -> None:
    tests_root = _make_release_test_root(tmp_path)
    calls: list[list[str]] = []

    def runner(command: run_unit_gate.Command) -> int:
        calls.append(list(command))
        return 29 if len(calls) == failure_call else 0

    assert run_unit_gate.run_unit_gate(tests_root, command_runner=runner, suite="release") == 29
    assert len(calls) == failure_call


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


def test_release_inventory_represents_every_discovered_test_module() -> None:
    repository_root = Path(__file__).resolve().parents[1]
    discovered = {
        path.relative_to(repository_root) for path in run_unit_gate.discover_test_modules(repository_root / "tests")
    }
    full_module_inventories = (
        set(run_unit_gate.FAST_UNIT_MODULES)
        | set(run_unit_gate.COVERAGE_ONLY_MODULES)
        | set(run_unit_gate.ONTOLOGY_CONTRACT_MODULES)
        | set(run_unit_gate.RUNTIME_SCENARIOS_MODULES)
    )
    exact_node_modules = {Path(node_id.split("::", 1)[0]) for node_id in run_unit_gate.RELEASE_EXACT_NODE_IDS}
    represented = full_module_inventories | exact_node_modules
    assert not discovered - represented
