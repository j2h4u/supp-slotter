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
            "test_canonical_optimizer.py",
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
        str(tests_root / "test_canonical_optimizer.py"),
    ]
    output = capsys.readouterr().out
    assert "Running fast-unit suite (1 targets)\n" in output
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
    expected_targets = expected_modules
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
    assert f"Running runtime-scenarios suite ({len(expected_targets)} targets)\n" in output
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
        "selection": "curated-module-list",
        "items": [path.as_posix() for path in run_unit_gate.RUNTIME_SCENARIOS_MODULES],
    }
    coverage_inventory = set(run_unit_gate._coverage_inventory_items())
    preexisting_module_overlaps = set(run_unit_gate.RUNTIME_SCENARIOS_MODULES) & (
        run_unit_gate.FAST_UNIT_MODULES | set(run_unit_gate.COVERAGE_ONLY_MODULES)
    )
    runtime_only_modules = set(run_unit_gate.RUNTIME_SCENARIOS_MODULES) - preexisting_module_overlaps
    assert not {path.as_posix() for path in runtime_only_modules} & coverage_inventory


def test_coverage_suite_selects_fast_modules_and_only_unique_smoke_nodes(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    tests_root = _make_modules(
        tmp_path,
        [
            *(path.relative_to(Path("tests")).as_posix() for path in run_unit_gate.FAST_UNIT_MODULES),
            *(path.relative_to(Path("tests")).as_posix() for path in run_unit_gate.COVERAGE_ONLY_MODULES),
        ],
    )
    calls: list[list[str]] = []

    def runner(command: run_unit_gate.Command) -> int:
        calls.append(list(command))
        return 0

    assert run_unit_gate.run_unit_gate(tests_root, command_runner=runner, suite="coverage") == 0
    assert len(calls) == 2
    expected_inventory = [
        "tests/test_canonical_fact_catalog_integration.py",
        "tests/test_canonical_inference.py",
        "tests/test_canonical_inference_plan_integration.py",
        "tests/test_canonical_optimizer.py",
        "tests/test_canonical_optimizer_plan_integration.py",
        "tests/test_canonical_publication.py",
        "tests/test_card_reference_integrity.py",
        "tests/test_cli_surface.py",
        "tests/test_crap_gate.py",
        "tests/test_dashboard_review.py",
        "tests/test_dashboard_schema.py",
        "tests/test_formal_uniqueness.py",
        "tests/test_loader_fail_closed.py",
        "tests/test_logical_slot_topology.py",
        "tests/test_maintenance.py",
        "tests/test_ontology_repository_contract.py",
        "tests/test_ontology_repository_projection.py",
        "tests/test_ontology_shacl_fixtures.py",
        "tests/test_pillbox_loader_contract.py",
        "tests/test_product_food_instruction.py",
        "tests/test_product_validation.py",
        "tests/test_read_model_relations.py",
        "tests/test_review_command.py",
        "tests/test_run_unit_gate.py",
        "tests/test_scheduler_reviewer_authority.py",
        "tests/test_schemas.py",
        "tests/test_substance_similarity.py",
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
        "--cov=planner",
        "--cov-report=",
        "--crap",
    ]
    assert calls[1].count("--crap") == 1
    assert not any(argument.startswith("--cov-fail-under=") for argument in calls[1])
    assert "-n" not in calls[1]
    assert "--dist" not in calls[1]
    assert len(calls[1][6:-2]) == len(set(calls[1][6:-2]))
    assert run_unit_gate._coverage_inventory_items() == expected_inventory
    assert set(expected_inventory) & {path.as_posix() for path in run_unit_gate.ONTOLOGY_CONTRACT_MODULES} == {
        "tests/test_ontology_repository_contract.py",
        "tests/test_ontology_repository_projection.py",
        "tests/test_ontology_shacl_fixtures.py",
    }
    output = capsys.readouterr().out
    assert f"Running coverage suite ({len(expected_inventory)} targets)\n" in output
    assert output.count("elapsed=") == 2


def test_coverage_suite_propagates_pytest_failure_without_followup_process(tmp_path: Path) -> None:
    tests_root = _make_modules(tmp_path, ["test_canonical_optimizer.py"])
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
            "test_ontology_compiler_outputs.py",
            "test_composition_role_identity.py",
            "test_canonical_fact_catalog_runtime.py",
            "test_canonical_law_catalog.py",
            "test_linkml_core_schema.py",
            "test_real_canonical_catalog.py",
            "test_architecture_contracts.py",
            "test_cluster1_vright_contract.py",
            "test_ontology_formal_runtime_assertions.py",
            "test_ontology_ontoclean_contract.py",
            "test_ontology_repository_contract.py",
            "test_ontology_repository_projection.py",
            "test_ontology_runtime_loader.py",
            "test_ontology_shacl_fixtures.py",
            "test_runtime_contract_v2.py",
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
            "test_composition_role_identity.py",
            "test_linkml_core_schema.py",
            "test_canonical_fact_catalog_runtime.py",
            "test_canonical_law_catalog.py",
            "test_ontology_compiler_outputs.py",
            "test_real_canonical_catalog.py",
        ],
        [
            "test_architecture_contracts.py",
            "test_cluster1_vright_contract.py",
            "test_ontology_formal_runtime_assertions.py",
            "test_ontology_ontoclean_contract.py",
            "test_ontology_repository_contract.py",
        ],
        [
            "test_ontology_artifacts.py",
            "test_ontology_repository_projection.py",
            "test_ontology_runtime_loader.py",
            "test_ontology_shacl_fixtures.py",
            "test_runtime_contract_v2.py",
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


def test_smoke_suite_uses_complete_curated_modules(tmp_path: Path) -> None:
    tests_root = _make_modules(
        tmp_path,
        [path.relative_to(Path("tests")).as_posix() for path in run_unit_gate.SMOKE_MODULES],
    )
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
            *(str(tests_root / path.relative_to(Path("tests"))) for path in run_unit_gate.SMOKE_MODULES),
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


def test_canonical_runtime_inventory_is_exact_and_stable() -> None:
    expected_capabilities = {
        "finite_law_table",
        "applicability_and_proofs",
        "normalization",
        "contradiction",
        "exact_objective_stages",
        "stable_tie_break",
        "exhaustive_oracle",
        "no_publication_failures",
        "fail_fast_command_boundary",
    }
    assert set(run_unit_gate.CANONICAL_RUNTIME_CAPABILITY_NODES) == expected_capabilities
    nodes = run_unit_gate.canonical_runtime_nodes()
    assert nodes == tuple(sorted(nodes))
    assert nodes and len(nodes) == len(set(nodes))
    assert not run_unit_gate.canonical_runtime_inventory_errors(Path(__file__).resolve().parent)


def test_private_fast_unit_tests_suite_skips_planner_validation(tmp_path: Path) -> None:
    tests_root = _make_modules(
        tmp_path,
        [path.relative_to(Path("tests")).as_posix() for path in run_unit_gate.FAST_UNIT_MODULES],
    )
    calls: list[list[str]] = []

    def runner(command: run_unit_gate.Command) -> int:
        calls.append(list(command))
        return 0

    assert run_unit_gate.run_unit_gate(tests_root, command_runner=runner, suite="fast-unit-tests") == 0
    assert len(calls) == 1
    assert calls[0][2:4] == ["pytest", "-q"]


def test_verify_composition_has_one_planner_validation_owner() -> None:
    """Static checks are not planner validation; the shelf scenario owns it once."""

    justfile = Path(__file__).resolve().parents[1] / "justfile"
    text = justfile.read_text(encoding="utf-8")
    assert "verify: check _fast-unit-tests current-shelf-smoke" in text
    assert "check: _fmt-check _lint _preview-complexity-lint _lock-check _typecheck" in text
    assert "check: " in text and "planner" not in next(line for line in text.splitlines() if line.startswith("check: "))
    assert (
        "_fast-unit-tests:\n    scripts/run_bounded.sh -- uv run python scripts/run_unit_gate.py --suite fast-unit-tests"
        in text
    )
    assert (
        'current-shelf-smoke:\n    scripts/run_bounded.sh -- uv run pytest -q -m "not integration and not slow" '
        "tests/test_cutover_vertical_scenarios.py::test_real_shelf_daily_episodic_and_training_products_are_complete"
        in text
    )
    assert "canonical-runtime:\n    scripts/run_bounded.sh -- uv run --group ontology python" in text
    assert "the one planner validation for that composition" in text
    assert "current-shelf-smoke` calls cmd_plan, which owns exactly one check" in text
