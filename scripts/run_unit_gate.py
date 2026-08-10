"""Run planner validation and a selected bounded pytest suite."""

from __future__ import annotations

import json
import subprocess
import sys
from argparse import ArgumentParser
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Literal, cast

DEFAULT_TEST_ROOT = Path("tests")
PYTEST_MARKERS = "not integration and not slow"
Suite = Literal["smoke", "fast-unit", "ontology-contract", "coverage", "all"]

# Keep the first development loop small while named suites remain ordinary
# pytest invocations over a curated set of modules.
SMOKE_NODE_IDS = (
    "tests/test_scheduler_reviewer_authority.py::test_reviewer_only_knowledge_does_not_change_slot_assignment",
    "tests/test_plan_search.py::test_plan_search_returns_none_when_hard_constraint_blocks_all_assignments",
    "tests/test_plan_search.py::test_advisory_penalty_prefers_separate_slot",
)
FAST_UNIT_MODULES = frozenset({
    Path("tests/test_plan_relation_scheduling.py"),
    Path("tests/test_plan_search.py"),
    Path("tests/test_product_validation.py"),
    Path("tests/test_read_model_relations.py"),
    Path("tests/test_relation_conflicts.py"),
    Path("tests/test_run_unit_gate.py"),
    Path("tests/test_scheduling_constraint_runtime.py"),
    Path("tests/test_scheduling_units.py"),
    Path("tests/test_schemas.py"),
    Path("tests/test_warning_humanization.py"),
})
ONTOLOGY_CONTRACT_MODULES = frozenset({
    Path("tests/test_ontology_artifacts.py"),
    Path("tests/test_ontology_assertion_runtime.py"),
    Path("tests/test_ontology_compiler_outputs.py"),
    Path("tests/test_ontology_formal_runtime_assertions.py"),
    Path("tests/test_ontology_ontoclean_contract.py"),
    Path("tests/test_ontology_repository_contract.py"),
    Path("tests/test_ontology_repository_projection.py"),
    Path("tests/test_ontology_runtime_loader.py"),
    Path("tests/test_ontology_shacl_fixtures.py"),
})
ONTOLOGY_CONTRACT_GROUPS: tuple[tuple[str, frozenset[Path]], ...] = (
    ("A compiler-heavy", frozenset({Path("tests/test_ontology_compiler_outputs.py")})),
    (
        "B formal source contracts",
        frozenset({
            Path("tests/test_ontology_formal_runtime_assertions.py"),
            Path("tests/test_ontology_ontoclean_contract.py"),
            Path("tests/test_ontology_repository_contract.py"),
        }),
    ),
    (
        "C runtime/artifacts/projection/SHACL",
        frozenset({
            Path("tests/test_ontology_artifacts.py"),
            Path("tests/test_ontology_assertion_runtime.py"),
            Path("tests/test_ontology_repository_projection.py"),
            Path("tests/test_ontology_runtime_loader.py"),
            Path("tests/test_ontology_shacl_fixtures.py"),
        }),
    ),
)
SUITE_INVENTORY_SCHEMA_VERSION = 1
Command = Sequence[str]
CommandRunner = Callable[[Command], int]


def _coverage_inventory_items() -> list[str]:
    """Return curated coverage targets without repeating full-module smoke nodes."""

    fast_unit_items = sorted(path.as_posix() for path in FAST_UNIT_MODULES)
    fast_unit_paths = {Path(item) for item in fast_unit_items}
    unique_smoke_nodes = [
        node_id for node_id in SMOKE_NODE_IDS if Path(node_id.split("::", 1)[0]) not in fast_unit_paths
    ]
    return [*fast_unit_items, *unique_smoke_nodes]


def suite_inventory() -> dict[str, object]:
    """Return stable, machine-readable boundaries of each named suite."""

    return {
        "schema_version": SUITE_INVENTORY_SCHEMA_VERSION,
        "suites": {
            "smoke": {
                "selection": "fixed-node-ids",
                "items": list(SMOKE_NODE_IDS),
            },
            "fast-unit": {
                "selection": "curated-module-list",
                "items": sorted(path.as_posix() for path in FAST_UNIT_MODULES),
            },
            "coverage": {
                "selection": "fast-unit-modules-plus-unique-smoke-nodes",
                "items": _coverage_inventory_items(),
                "pytest_flags": ["--cov=planner", "--cov-report="],
            },
            "ontology-contract": {
                "selection": "three-curated-module-groups",
                "groups": [
                    {"name": name, "items": sorted(path.as_posix() for path in paths)}
                    for name, paths in ONTOLOGY_CONTRACT_GROUPS
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
                "selection": "just-recipe",
                "components": [
                    "check",
                    "smoke",
                    "fast-unit",
                    "ontology-contract",
                    "corpus-projection",
                    "coverage-check",
                ],
                "policy": "rare full release-candidate gate; do not use for small edits",
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


def _pytest_command(targets: Sequence[str | Path], *, coverage: bool = False) -> list[str]:
    command = [sys.executable, "-m", "pytest", "-q", "-m", PYTEST_MARKERS]
    command.extend(str(target) for target in targets)
    if coverage:
        command.extend(("--cov=planner", "--cov-report="))
    return command


def _suite_modules(modules: list[Path], suite: Suite, test_root: Path = DEFAULT_TEST_ROOT) -> list[Path]:
    if suite == "all":
        return modules

    selected_paths = FAST_UNIT_MODULES if suite in ("fast-unit", "coverage") else ONTOLOGY_CONTRACT_MODULES
    repository_root = test_root.parent.resolve()
    selected_modules: list[Path] = []
    for module in modules:
        repository_relative_module = module.resolve().relative_to(repository_root) if module.is_absolute() else module
        if repository_relative_module in selected_paths:
            selected_modules.append(module)
    return selected_modules


def _select_targets(test_root: Path, suite: Suite) -> list[str | Path] | None:
    if suite == "smoke":
        targets: list[str | Path] = []
        targets.extend(SMOKE_NODE_IDS)
        return targets

    modules = discover_test_modules(test_root)
    if not modules:
        print(f"No unit test modules discovered under {test_root}.", file=sys.stderr, flush=True)
        return None

    selected_modules = _suite_modules(modules, suite, test_root)
    if suite == "coverage":
        selected_modules = _suite_modules(modules, "fast-unit", test_root)
        selected_module_paths = {
            module.resolve().relative_to(test_root.parent.resolve()) if module.is_absolute() else module
            for module in selected_modules
        }
        targets = list(selected_modules)
        targets.extend(
            node_id for node_id in SMOKE_NODE_IDS if Path(node_id.split("::", 1)[0]) not in selected_module_paths
        )
        if not targets:
            print(f"No {suite} test modules selected under {test_root}.", file=sys.stderr, flush=True)
            return None
        return targets
    if not selected_modules:
        print(f"No {suite} test modules selected under {test_root}.", file=sys.stderr, flush=True)
        return None
    targets = []
    targets.extend(selected_modules)
    return targets


def run_unit_gate(
    test_root: Path = DEFAULT_TEST_ROOT,
    *,
    command_runner: CommandRunner = _run_command,
    suite: Suite = "all",
) -> int:
    """Run planner validation, then the selected bounded pytest invocation(s)."""

    planner_status = _normalize_status(command_runner([sys.executable, "-m", "planner", "check"]))
    if planner_status != 0:
        return planner_status

    targets = _select_targets(test_root, suite)
    if targets is None:
        return 5

    if suite != "ontology-contract":
        print(f"Running {suite} suite ({len(targets)} targets)", flush=True)
        return _normalize_status(command_runner(_pytest_command(targets, coverage=suite == "coverage")))

    print(f"Running {suite} suite in {len(ONTOLOGY_CONTRACT_GROUPS)} groups", flush=True)
    for name, group in ONTOLOGY_CONTRACT_GROUPS:
        group_targets: list[Path] = []
        for module in targets:
            module_path = Path(module)
            repository_relative_module = (
                module_path.resolve().relative_to(test_root.parent.resolve())
                if module_path.is_absolute()
                else module_path
            )
            if repository_relative_module in group:
                group_targets.append(module_path)
        if not group_targets:
            continue
        print(f"Running {name} group ({len(group_targets)} targets)", flush=True)
        status = _normalize_status(command_runner(_pytest_command(group_targets)))
        if status != 0:
            return status
    return 0


def main() -> int:
    parser = ArgumentParser(description="Run supp-slotter bounded pytest suites.")
    parser.add_argument(
        "--list-suites",
        action="store_true",
        help="print the machine-readable suite inventory and exit without running tests",
    )
    parser.add_argument(
        "--suite",
        choices=("smoke", "fast-unit", "ontology-contract", "coverage", "all"),
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
