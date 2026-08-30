"""Run planner validation and a selected bounded pytest suite."""

from __future__ import annotations

import ast
import json
import subprocess
import sys
import time
from argparse import ArgumentParser
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Literal, cast

DEFAULT_TEST_ROOT = Path("tests")
PYTEST_MARKERS = "not integration and not slow"
Suite = Literal[
    "smoke",
    "fast-unit",
    "fast-unit-tests",
    "canonical-runtime",
    "ontology-contract",
    "runtime-scenarios",
    "coverage",
    "all",
    "release",
]

# Keep the first development loop small while named suites remain ordinary
# pytest invocations over curated, complete modules.  Full-module selection
# means a new test added to one of these modules cannot silently evade release.
SMOKE_MODULES = (
    Path("tests/test_canonical_optimizer_plan_integration.py"),
    Path("tests/test_canonical_publication.py"),
    Path("tests/test_cutover_vertical_scenarios.py"),
)
FAST_UNIT_MODULES = frozenset({
    Path("tests/test_cli_surface.py"),
    Path("tests/test_crap_gate.py"),
    Path("tests/test_dashboard_schema.py"),
    Path("tests/test_logical_slot_topology.py"),
    Path("tests/test_canonical_fact_catalog_integration.py"),
    Path("tests/test_canonical_inference.py"),
    Path("tests/test_canonical_inference_plan_integration.py"),
    Path("tests/test_canonical_optimizer.py"),
    Path("tests/test_canonical_optimizer_plan_integration.py"),
    Path("tests/test_canonical_publication.py"),
    Path("tests/test_product_validation.py"),
    Path("tests/test_read_model_relations.py"),
    Path("tests/test_run_unit_gate.py"),
    Path("tests/test_scheduler_reviewer_authority.py"),
    Path("tests/test_schemas.py"),
    Path("tests/test_substance_similarity.py"),
})
# Runtime-only scenario coverage.  These modules load committed artifacts but
# do not invoke ontology generation, compiler, SHACL, or other heavy gates.
COVERAGE_ONLY_MODULES = (
    Path("tests/test_dashboard_review.py"),
    Path("tests/test_loader_fail_closed.py"),
    Path("tests/test_maintenance.py"),
    Path("tests/test_review_command.py"),
    Path("tests/test_card_reference_integrity.py"),
    Path("tests/test_pillbox_loader_contract.py"),
    Path("tests/test_formal_uniqueness.py"),
)
RUNTIME_SCENARIOS_MODULES = (
    Path("tests/test_canonical_inference_plan_integration.py"),
    Path("tests/test_canonical_optimizer.py"),
    Path("tests/test_canonical_optimizer_plan_integration.py"),
    Path("tests/test_canonical_publication.py"),
    Path("tests/test_cutover_vertical_scenarios.py"),
    Path("tests/test_find_command.py"),
    Path("tests/test_non_daily_presentation.py"),
    Path("tests/test_relation_review.py"),
    Path("tests/test_scheduler_reviewer_authority.py"),
    Path("tests/test_grooming.py"),
    Path("tests/test_stack_validation.py"),
)
CANONICAL_RUNTIME_REQUIRED_CAPABILITIES = frozenset({
    "applicability_and_proofs",
    "contradiction",
    "exact_objective_stages",
    "exhaustive_oracle",
    "finite_law_table",
    "no_publication_failures",
    "normalization",
    "stable_tie_break",
})
# This is deliberately exact-node rather than module inventory: each capability
# has an identified acceptance witness and the release gate still runs its full
# owning module.
CANONICAL_RUNTIME_CAPABILITY_NODES: dict[str, tuple[str, ...]] = {
    "finite_law_table": ("tests/test_canonical_inference.py::test_every_admitted_value_maps_to_one_pressure",),
    "applicability_and_proofs": (
        "tests/test_canonical_inference.py::test_wrong_or_unselected_applicability_does_not_emit_pressure",
        "tests/test_canonical_inference.py::test_substance_applicability_reaches_each_exact_matching_role",
        "tests/test_canonical_inference.py::test_proof_contains_law_fact_subject_path_and_provenance",
        "tests/test_cutover_authored_vertical_scenarios.py::test_authored_vertical_fixture_compiles_loads_and_routes_all_runtime_anchors",
    ),
    "normalization": (
        "tests/test_canonical_inference.py::test_duplicate_witnesses_facts_components_and_paths_normalize_to_one_pressure",
    ),
    "contradiction": ("tests/test_canonical_inference.py::test_same_dimension_values_are_layout_free_conflict",),
    "exact_objective_stages": (
        "tests/test_canonical_optimizer.py::test_pressure_maximum_precedes_balance_and_keeps_only_maximum_slots",
        "tests/test_canonical_optimizer.py::test_exact_squared_load_balance_is_unbounded_and_stable_by_item_id",
    ),
    "stable_tie_break": (
        "tests/test_canonical_optimizer.py::test_tie_break_uses_slot_id_after_order_and_is_domain_independent",
    ),
    "exhaustive_oracle": (
        "tests/test_canonical_optimizer.py::test_bounded_randomized_results_match_independent_cartesian_oracle",
    ),
    "no_publication_failures": (
        "tests/test_canonical_optimizer.py::test_conflicts_and_invalid_inputs_are_layout_free_indeterminate",
        "tests/test_canonical_optimizer.py::test_abort_during_final_expansion_or_pre_return_cannot_publish",
        "tests/test_canonical_publication.py::test_invalid_source_mapping_product_domain_or_slot_publishes_nothing",
        "tests/test_canonical_publication.py::test_failed_or_interrupted_write_removes_stale_lease",
    ),
}
ONTOLOGY_CONTRACT_GROUPS: tuple[tuple[str, tuple[Path, ...]], ...] = (
    (
        "A compiler-heavy",
        (
            Path("tests/test_composition_role_identity.py"),
            Path("tests/test_linkml_core_schema.py"),
            Path("tests/test_canonical_fact_catalog_runtime.py"),
            Path("tests/test_canonical_law_catalog.py"),
            Path("tests/test_ontology_compiler_outputs.py"),
            Path("tests/test_real_canonical_catalog.py"),
        ),
    ),
    (
        "B formal source contracts",
        (
            Path("tests/test_architecture_contracts.py"),
            Path("tests/test_canonical_scheduling_migration.py"),
            Path("tests/test_cluster1_vright_contract.py"),
            Path("tests/test_ontology_formal_runtime_assertions.py"),
            Path("tests/test_ontology_ontoclean_contract.py"),
            Path("tests/test_ontology_repository_contract.py"),
        ),
    ),
    (
        "C runtime/artifacts/projection/SHACL",
        (
            Path("tests/test_ontology_artifacts.py"),
            Path("tests/test_ontology_assertion_runtime.py"),
            Path("tests/test_ontology_repository_projection.py"),
            Path("tests/test_ontology_runtime_loader.py"),
            Path("tests/test_ontology_presentation_cache.py"),
            Path("tests/test_ontology_shacl_fixtures.py"),
            Path("tests/test_runtime_contract_v2.py"),
            Path("tests/test_yaml_duplicate_keys.py"),
        ),
    ),
)
ONTOLOGY_CONTRACT_MODULES = frozenset(target for _, targets in ONTOLOGY_CONTRACT_GROUPS for target in targets)
# Release selection is module-based, so every canonical runtime node is covered
# by its owning complete module rather than a brittle second node-only run.
RELEASE_EXACT_NODE_IDS: tuple[str, ...] = tuple(
    sorted(node for nodes in CANONICAL_RUNTIME_CAPABILITY_NODES.values() for node in nodes)
)
EXPLICITLY_EXCLUDED_RELEASE_MODULES: dict[Path, str] = {}
SUITE_INVENTORY_SCHEMA_VERSION = 2
Command = Sequence[str]
CommandRunner = Callable[[Command], int]


def _coverage_inventory_items() -> list[str]:
    """Return curated coverage modules."""

    coverage_modules = FAST_UNIT_MODULES | set(COVERAGE_ONLY_MODULES)
    return sorted(path.as_posix() for path in coverage_modules)


def canonical_runtime_nodes() -> tuple[str, ...]:
    """Flatten the exact canonical-runtime acceptance nodes stably."""

    return tuple(sorted(node for nodes in CANONICAL_RUNTIME_CAPABILITY_NODES.values() for node in nodes))


def canonical_runtime_inventory_errors(test_root: Path = DEFAULT_TEST_ROOT) -> list[str]:
    """Validate the finite runtime capability-to-test-node contract."""

    errors: list[str] = []
    if set(CANONICAL_RUNTIME_CAPABILITY_NODES) != CANONICAL_RUNTIME_REQUIRED_CAPABILITIES:
        errors.append("canonical runtime inventory capability set is not exact")
    nodes = canonical_runtime_nodes()
    if not nodes or len(nodes) != len(set(nodes)):
        errors.append("canonical runtime inventory nodes must be non-empty and unique")
    if nodes != tuple(sorted(nodes)):
        errors.append("canonical runtime inventory flattening is not stable")
    repository_root = test_root.parent.resolve()
    for node in nodes:
        if "::" not in node:
            errors.append(f"canonical runtime inventory node lacks test name: {node}")
            continue
        module_name, test_name = node.split("::", 1)
        module = repository_root / module_name
        if not module.is_file():
            errors.append(f"canonical runtime inventory names missing module: {module_name}")
            continue
        parsed = ast.parse(module.read_text(encoding="utf-8"), filename=str(module))
        if not any(isinstance(item, ast.FunctionDef) and item.name == test_name for item in parsed.body):
            errors.append(f"canonical runtime inventory names missing node: {node}")
        if Path(module_name) not in release_module_inventory():
            errors.append(f"canonical runtime inventory node is not included in release: {node}")
    return errors


def release_module_inventory() -> frozenset[Path]:
    """Return every module represented by the release gate."""

    return frozenset(
        set(SMOKE_MODULES)
        | FAST_UNIT_MODULES
        | set(COVERAGE_ONLY_MODULES)
        | ONTOLOGY_CONTRACT_MODULES
        | set(RUNTIME_SCENARIOS_MODULES)
        | {Path(node_id.split("::", 1)[0]) for node_id in RELEASE_EXACT_NODE_IDS}
    )


def release_inventory_errors(test_root: Path = DEFAULT_TEST_ROOT) -> list[str]:
    """Return deterministic completeness errors for the release test inventory."""

    discovered = {
        module.resolve().relative_to(test_root.parent.resolve()) if module.is_absolute() else module
        for module in discover_test_modules(test_root)
    }
    represented = release_module_inventory()
    excluded = set(EXPLICITLY_EXCLUDED_RELEASE_MODULES)
    errors: list[str] = []
    blank_reasons = sorted(
        path.as_posix() for path, reason in EXPLICITLY_EXCLUDED_RELEASE_MODULES.items() if not reason.strip()
    )
    if blank_reasons:
        errors.append("release inventory exclusions require non-empty reasons: " + ", ".join(blank_reasons))
    overlap = sorted(path.as_posix() for path in represented & excluded)
    if overlap:
        errors.append("release inventory modules cannot be both represented and excluded: " + ", ".join(overlap))
    missing = sorted(path.as_posix() for path in discovered - represented - excluded)
    if missing:
        errors.append("release inventory omits discovered modules: " + ", ".join(missing))
    stale = sorted(path.as_posix() for path in represented - discovered)
    if stale:
        errors.append("release inventory names missing modules: " + ", ".join(stale))
    unknown_exclusions = sorted(path.as_posix() for path in excluded - discovered)
    if unknown_exclusions:
        errors.append("release inventory excludes missing modules: " + ", ".join(unknown_exclusions))
    return errors


def suite_inventory() -> dict[str, object]:
    """Return stable, machine-readable boundaries of each named suite."""

    return {
        "schema_version": SUITE_INVENTORY_SCHEMA_VERSION,
        "suites": {
            "smoke": {
                "selection": "curated-module-list",
                "items": [path.as_posix() for path in SMOKE_MODULES],
            },
            "fast-unit": {
                "selection": "curated-module-list",
                "items": sorted(path.as_posix() for path in FAST_UNIT_MODULES),
            },
            "canonical-runtime": {
                "selection": "capability-to-exact-test-node-inventory",
                "capabilities": {
                    capability: list(CANONICAL_RUNTIME_CAPABILITY_NODES[capability])
                    for capability in sorted(CANONICAL_RUNTIME_CAPABILITY_NODES)
                },
                "items": list(canonical_runtime_nodes()),
            },
            "coverage": {
                "selection": "fast-unit-plus-coverage-only-modules",
                "items": _coverage_inventory_items(),
                "pytest_flags": ["--cov=planner", "--cov-report=", "--crap"],
            },
            "runtime-scenarios": {
                "selection": "curated-module-list",
                "items": [path.as_posix() for path in RUNTIME_SCENARIOS_MODULES],
            },
            "ontology-contract": {
                "selection": "three-curated-module-groups",
                "groups": [
                    {
                        "name": name,
                        "items": [target.as_posix() for target in targets],
                    }
                    for name, targets in ONTOLOGY_CONTRACT_GROUPS
                ],
            },
            "all": {
                "selection": "all-discovered-modules",
                "policy": "explicit-heavy-suite; use release for the full release gate",
            },
            "corpus-projection": {
                "selection": "just-recipe",
                "command": "just corpus-projection",
                "policy": "explicit repository RDF/SHACL projection gate",
            },
            "release": {
                "selection": "fixed-release-stage-order",
                "components": [
                    "check",
                    "smoke",
                    "ontology-contract",
                    "runtime-scenarios",
                    "coverage",
                ],
                "module_inventory": sorted(path.as_posix() for path in release_module_inventory()),
                "explicitly_excluded_modules": {
                    path.as_posix(): reason for path, reason in sorted(EXPLICITLY_EXCLUDED_RELEASE_MODULES.items())
                },
                "policy": "rare full release-candidate gate with blocking CRAP quality check; do not use for small edits",
            },
        },
    }


def discover_test_modules(test_root: Path = DEFAULT_TEST_ROOT) -> list[Path]:
    """Return unit-test modules in deterministic lexical order."""

    modules = {path for pattern in ("test_*.py", "*_test.py") for path in test_root.rglob(pattern) if path.is_file()}
    return sorted(modules, key=lambda path: path.as_posix())


def _run_command(command: Command) -> int:
    return subprocess.run(command, check=False).returncode


def _normalize_status(status: int) -> int:
    """Convert Python's negative signal return code to shell's 128+signal form."""

    return 128 + -status if status < 0 else status


def _run_timed(command: Command, *, label: str, command_runner: CommandRunner) -> int:
    """Run one command and report its bounded monotonic elapsed time."""

    started = time.monotonic()
    try:
        status = _normalize_status(command_runner(command))
    finally:
        elapsed = max(0.0, time.monotonic() - started)
        print(f"{label}: elapsed={elapsed:.3f}s", flush=True)
    return status


def _pytest_command(
    targets: Sequence[str | Path], *, coverage: bool = False, crap: bool = False, append: bool = False
) -> list[str]:
    command = [sys.executable, "-m", "pytest", "-q", "-m", PYTEST_MARKERS]
    command.extend(str(target) for target in targets)
    if coverage:
        command.extend(("--cov=planner", "--cov-report="))
        if append:
            command.append("--cov-append")
    if crap:
        command.append("--crap")
    return command


def _suite_modules(modules: list[Path], suite: Suite, test_root: Path = DEFAULT_TEST_ROOT) -> list[Path]:
    if suite == "all":
        return modules

    if suite == "runtime-scenarios":
        return [
            module
            for expected_path in RUNTIME_SCENARIOS_MODULES
            for module in modules
            if (module.resolve().relative_to(test_root.parent.resolve()) if module.is_absolute() else module)
            == expected_path
        ]
    selected_paths = (
        SMOKE_MODULES
        if suite == "smoke"
        else FAST_UNIT_MODULES
        if suite in ("fast-unit", "fast-unit-tests", "coverage")
        else ONTOLOGY_CONTRACT_MODULES
    )
    repository_root = test_root.parent.resolve()
    selected_modules: list[Path] = []
    for module in modules:
        repository_relative_module = module.resolve().relative_to(repository_root) if module.is_absolute() else module
        if repository_relative_module in selected_paths:
            selected_modules.append(module)
    return selected_modules


def _select_targets(test_root: Path, suite: Suite) -> list[str | Path] | None:
    targets: list[str | Path] | None = None
    modules = discover_test_modules(test_root)
    if not modules:
        print(f"No unit test modules discovered under {test_root}.", file=sys.stderr, flush=True)
        return None

    selected_modules = _suite_modules(modules, suite, test_root)
    if suite == "canonical-runtime":
        errors = canonical_runtime_inventory_errors(test_root)
        if errors:
            print("\n".join(errors), file=sys.stderr, flush=True)
            return None
        return [
            f"{test_root / Path(node.split('::', 1)[0]).relative_to('tests')}::{node.split('::', 1)[1]}"
            for node in canonical_runtime_nodes()
        ]
    if suite == "coverage":
        coverage_paths = FAST_UNIT_MODULES | set(COVERAGE_ONLY_MODULES)
        targets = [
            module
            for module in modules
            if (module.resolve().relative_to(test_root.parent.resolve()) if module.is_absolute() else module)
            in coverage_paths
        ]
    elif selected_modules:
        targets = list(selected_modules)
    else:
        if suite != "all":
            print(f"No {suite} test modules selected under {test_root}.", file=sys.stderr, flush=True)
        targets = None
    if targets is None:
        return None
    return targets


def _run_ontology_groups(
    test_root: Path,
    targets: list[str | Path],
    *,
    command_runner: CommandRunner,
    timing_prefix: str,
    coverage: bool = False,
) -> int:
    print(f"Running ontology-contract suite in {len(ONTOLOGY_CONTRACT_GROUPS)} groups", flush=True)
    for name, group in ONTOLOGY_CONTRACT_GROUPS:
        by_repository_path: dict[Path, Path] = {}
        for target in targets:
            module_path = Path(target)
            repository_relative_module = (
                module_path.resolve().relative_to(test_root.parent.resolve())
                if module_path.is_absolute()
                else module_path
            )
            by_repository_path[repository_relative_module] = module_path
        group_targets = [by_repository_path[module] for module in group if module in by_repository_path]
        if not group_targets:
            continue
        print(f"Running {name} group ({len(group_targets)} targets)", flush=True)
        status = _run_timed(
            _pytest_command(group_targets, coverage=coverage, append=coverage),
            label=f"{timing_prefix + ' ' if timing_prefix else ''}ontology {name.split(maxsplit=1)[0]} pytest",
            command_runner=command_runner,
        )
        if status != 0:
            return status
    return 0


def _run_release_suite(
    test_root: Path,
    *,
    command_runner: CommandRunner,
) -> int:
    inventory_errors = release_inventory_errors(test_root)
    if inventory_errors:
        print("\n".join(inventory_errors), file=sys.stderr, flush=True)
        return 5
    stage_targets = {
        suite: _select_targets(test_root, suite)
        for suite in ("smoke", "ontology-contract", "runtime-scenarios", "coverage")
    }
    if any(targets is None for targets in stage_targets.values()):
        return 5

    smoke_targets = cast(list[str | Path], stage_targets["smoke"])
    ontology_targets = cast(list[str | Path], stage_targets["ontology-contract"])
    runtime_targets = cast(list[str | Path], stage_targets["runtime-scenarios"])
    coverage_targets = cast(list[str | Path], stage_targets["coverage"])
    print("Running release suite in 6 stages", flush=True)
    print(f"Running smoke stage ({len(smoke_targets)} targets)", flush=True)
    status = _run_timed(
        _pytest_command(smoke_targets, coverage=True, append=True),
        label="release smoke pytest",
        command_runner=command_runner,
    )
    if status != 0:
        return status

    status = _run_ontology_groups(
        test_root,
        ontology_targets,
        command_runner=command_runner,
        timing_prefix="release",
        coverage=True,
    )
    if status != 0:
        return status

    print(f"Running runtime-scenarios stage ({len(runtime_targets)} targets)", flush=True)
    status = _run_timed(
        _pytest_command(runtime_targets, coverage=True, append=True),
        label="release runtime-scenarios pytest",
        command_runner=command_runner,
    )
    if status != 0:
        return status

    print(f"Running CRAP stage ({len(coverage_targets)} targets)", flush=True)
    return _run_timed(
        _pytest_command(coverage_targets, coverage=True, crap=True, append=True),
        label="release CRAP pytest",
        command_runner=command_runner,
    )


def run_unit_gate(
    test_root: Path = DEFAULT_TEST_ROOT,
    *,
    command_runner: CommandRunner = _run_command,
    suite: Suite = "all",
) -> int:
    """Run planner validation, then the selected bounded pytest invocation(s)."""

    if suite != "fast-unit-tests":
        planner_status = _run_timed(
            [sys.executable, "-m", "planner", "check"],
            label="planner check",
            command_runner=command_runner,
        )
        if planner_status != 0:
            return planner_status

    if suite == "release":
        return _run_release_suite(test_root, command_runner=command_runner)

    targets = _select_targets(test_root, suite)
    if targets is None:
        return 5

    if suite != "ontology-contract":
        print(f"Running {suite} suite ({len(targets)} targets)", flush=True)
        return _run_timed(
            _pytest_command(targets, coverage=suite == "coverage", crap=suite == "coverage"),
            label=f"{suite} pytest",
            command_runner=command_runner,
        )

    return _run_ontology_groups(
        test_root,
        targets,
        command_runner=command_runner,
        timing_prefix="",
    )


def main() -> int:
    parser = ArgumentParser(description="Run supp-slotter bounded pytest suites.")
    parser.add_argument(
        "--list-suites",
        action="store_true",
        help="print the machine-readable suite inventory and exit without running tests",
    )
    parser.add_argument(
        "--suite",
        choices=(
            "smoke",
            "fast-unit",
            "fast-unit-tests",
            "canonical-runtime",
            "ontology-contract",
            "runtime-scenarios",
            "coverage",
            "all",
            "release",
        ),
        default="fast-unit",
        help="test suite to run; default is the fast development unit suite",
    )
    args = parser.parse_args()
    if cast(bool, args.list_suites):
        print(json.dumps(suite_inventory(), indent=2, sort_keys=True))
        return 0
    return run_unit_gate(suite=cast(Suite, args.suite))


if __name__ == "__main__":
    raise SystemExit(main())
