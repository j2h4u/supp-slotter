"""Run planner validation and isolated tests for a selected harness layer.

The enclosing ``run_bounded.sh`` process owns the cgroup and checkout lock.
Each pytest module is then given a fresh Python process so module-level state
and anonymous Python heap cannot accumulate across the suite.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from argparse import ArgumentParser
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Literal, cast

DEFAULT_TEST_ROOT = Path("tests")
PYTEST_MARKERS = "not integration and not slow"
# `all` remains an explicit escape hatch for diagnostics; the named full gate
# is `just release`, never the compatibility `unit` alias.
Suite = Literal["smoke", "fast-unit", "unit", "ontology-contract", "all"]
# Keep this list short and stable: smoke is the first development feedback
# loop, while the curated module suites make ontology-heavy work explicit.
SMOKE_NODE_IDS = (
    "tests/test_scheduler_reviewer_authority.py::test_reviewer_only_knowledge_does_not_change_slot_assignment",
    "tests/test_plan_search.py::test_plan_search_returns_none_when_hard_constraint_blocks_all_assignments",
    "tests/test_plan_search.py::test_advisory_penalty_prefers_separate_slot",
    "tests/test_schedule_fact_index.py::test_schedule_excludes_reviewer_only_facts_from_active_fact_index",
)
FAST_UNIT_MODULES = frozenset({
    Path("tests/test_governed_assignment_scoring.py"),
    Path("tests/test_plan_relation_scheduling.py"),
    Path("tests/test_plan_search.py"),
    Path("tests/test_product_validation.py"),
    Path("tests/test_read_model_relations.py"),
    Path("tests/test_relation_conflicts.py"),
    Path("tests/test_run_unit_gate.py"),
    Path("tests/test_schedule_fact_index.py"),
    Path("tests/test_scheduling_constraint_runtime.py"),
    Path("tests/test_scheduling_trait_projection.py"),
    Path("tests/test_scheduling_units.py"),
    Path("tests/test_schemas.py"),
    Path("tests/test_warning_humanization.py"),
})
ONTOLOGY_CONTRACT_MODULES = frozenset({
    Path("tests/test_enzyme_governance_acceptance.py"),
    Path("tests/test_ontology_artifacts.py"),
    Path("tests/test_ontology_assertion_runtime.py"),
    Path("tests/test_ontology_compiler_outputs.py"),
    Path("tests/test_ontology_formal_runtime_assertions.py"),
    Path("tests/test_ontology_generated_contract.py"),
    Path("tests/test_ontology_repository_contract.py"),
    Path("tests/test_ontology_repository_projection.py"),
    Path("tests/test_ontology_runtime_loader.py"),
    Path("tests/test_ontology_shacl_fixtures.py"),
})
SPLIT_MODULES = frozenset({
    Path("tests/test_enzyme_governance_acceptance.py"),
    Path("tests/test_ontology_artifacts.py"),
    Path("tests/test_ontology_compiler_outputs.py"),
    Path("tests/test_ontology_formal_runtime_assertions.py"),
    Path("tests/test_ontology_repository_contract.py"),
})
SUITE_INVENTORY_SCHEMA_VERSION = 1
_COLLECTION_SUMMARY = re.compile(
    r"(?:no tests collected|\d+ tests? collected|\d+/\d+ tests? collected \(\d+ deselected\))"
    r"(?: in \d+(?:\.\d+)?s)?"
)
Command = Sequence[str]
CommandRunner = Callable[[Command], int]
CollectionRunner = Callable[[Command], subprocess.CompletedProcess[str]]


def suite_inventory() -> dict[str, object]:
    """Return the stable, machine-readable boundaries of each named suite."""

    return {
        "schema_version": SUITE_INVENTORY_SCHEMA_VERSION,
        "aliases": {"unit": "fast-unit"},
        "suites": {
            "smoke": {
                "selection": "fixed-node-ids",
                "items": list(SMOKE_NODE_IDS),
            },
            "fast-unit": {
                "selection": "curated-module-list",
                "items": sorted(path.as_posix() for path in FAST_UNIT_MODULES),
            },
            "ontology-contract": {
                "selection": "curated-module-list",
                "items": sorted(path.as_posix() for path in ONTOLOGY_CONTRACT_MODULES),
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
                    "crap-check",
                ],
                "policy": "rare full release-candidate gate; do not use for small edits",
            },
        },
    }


def discover_test_modules(test_root: Path = DEFAULT_TEST_ROOT) -> list[Path]:
    """Return all unit-test module paths in deterministic lexical order."""

    modules = {path for pattern in ("test_*.py", "*_test.py") for path in test_root.rglob(pattern) if path.is_file()}
    return sorted(modules, key=lambda path: path.as_posix())


def _run_command(command: Command) -> int:
    return subprocess.run(command, check=False).returncode


def _run_collection_command(command: Command) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        check=False,
        capture_output=True,
        text=True,
        shell=False,
    )


def _normalize_status(status: int) -> int:
    """Convert Python's negative signal return code to shell's 128+signal form."""

    return 128 + -status if status < 0 else status


def _pytest_command(module: Path) -> list[str]:
    return [sys.executable, "-m", "pytest", "-q", "-m", PYTEST_MARKERS, str(module)]


def _pytest_node_command(node_id: str) -> list[str]:
    return [sys.executable, "-m", "pytest", "-q", "-m", PYTEST_MARKERS, node_id]


def _collection_command(module: Path) -> list[str]:
    return [sys.executable, "-m", "pytest", "-q", "-m", PYTEST_MARKERS, "--collect-only", str(module)]


def parse_collected_node_ids(stdout: str, module: Path) -> list[str]:
    """Parse exact leaf node IDs from quiet pytest collection output."""

    records = [line for line in stdout.splitlines() if line.strip()]
    if records and _COLLECTION_SUMMARY.fullmatch(records[-1]):
        records.pop()

    prefix = f"{module.as_posix()}::"
    node_ids: list[str] = []
    seen: set[str] = set()
    for record in records:
        if not record.startswith(prefix):
            kind = "foreign" if "::" in record else "malformed"
            raise ValueError(f"{kind} collection record: {record!r}")
        suffix = record.removeprefix(prefix)
        if not suffix.strip() or "\x00" in suffix:
            raise ValueError(f"malformed collection record: {record!r}")
        if record in seen:
            raise ValueError(f"duplicate collection record: {record!r}")
        seen.add(record)
        node_ids.append(record)

    if not node_ids:
        raise ValueError("collection produced no test node IDs")
    return node_ids


def _surface_collection_stderr(stderr: str) -> None:
    if stderr:
        print(stderr, file=sys.stderr, end="" if stderr.endswith("\n") else "\n", flush=True)


def _collect_module_node_ids(
    module: Path,
    collection_runner: CollectionRunner,
) -> tuple[int, list[str]]:
    result = collection_runner(_collection_command(module))
    status = _normalize_status(result.returncode)
    if status != 0:
        _surface_collection_stderr(result.stderr)
        return status, []
    try:
        return 0, parse_collected_node_ids(result.stdout, module)
    except ValueError as error:
        print(f"Invalid collection output for {module.as_posix()}: {error}", file=sys.stderr, flush=True)
        return 5, []


def _run_split_module(
    module: Path,
    *,
    command_runner: CommandRunner,
    collection_runner: CollectionRunner,
) -> tuple[int, list[str]]:
    collection_status, node_ids = _collect_module_node_ids(module, collection_runner)
    if collection_status != 0:
        return collection_status, []

    failed_leaves: list[str] = []
    leaf_total = len(node_ids)
    for leaf_index, node_id in enumerate(node_ids, start=1):
        print(f"  [{leaf_index}/{leaf_total}] {node_id}", flush=True)
        status = _normalize_status(command_runner(_pytest_node_command(node_id)))
        if status == 0:
            continue
        if status == 1:
            failed_leaves.append(node_id)
            continue
        return status, failed_leaves
    return (1 if failed_leaves else 0), failed_leaves


def _validate_discovered_modules(test_root: Path, modules: list[Path], split_modules: frozenset[Path]) -> int:
    if not modules:
        print(f"No unit test modules discovered under {test_root}.", file=sys.stderr, flush=True)
        return 5

    missing_split_modules = sorted(split_modules.difference(modules), key=lambda path: path.as_posix())
    if not missing_split_modules:
        return 0

    print("Configured split unit test modules were not discovered:", file=sys.stderr, flush=True)
    for module in missing_split_modules:
        print(f"- {module.as_posix()}", file=sys.stderr, flush=True)
    return 5


def _suite_modules(modules: list[Path], suite: Suite, test_root: Path = DEFAULT_TEST_ROOT) -> list[Path]:
    if suite == "all":
        return modules
    selected_paths = FAST_UNIT_MODULES if suite in {"fast-unit", "unit"} else ONTOLOGY_CONTRACT_MODULES
    repository_root = test_root.parent.resolve()
    selected_modules: list[Path] = []
    for module in modules:
        repository_relative_module = module.resolve().relative_to(repository_root) if module.is_absolute() else module
        if repository_relative_module in selected_paths:
            selected_modules.append(module)
    return selected_modules


def _run_smoke_nodes(command_runner: CommandRunner) -> int:
    failed_nodes: list[str] = []
    total = len(SMOKE_NODE_IDS)
    for index, node_id in enumerate(SMOKE_NODE_IDS, start=1):
        print(f"[{index}/{total}] {node_id}", flush=True)
        status = _normalize_status(command_runner(_pytest_node_command(node_id)))
        if status == 0:
            continue
        if status == 1:
            failed_nodes.append(node_id)
            continue
        return status
    if not failed_nodes:
        return 0
    print("Failed smoke test nodes:")
    for node_id in failed_nodes:
        print(f"- {node_id}")
    return 1


def _run_test_module(
    module: Path,
    *,
    is_split: bool,
    command_runner: CommandRunner,
    collection_runner: CollectionRunner,
) -> tuple[int, list[str]]:
    if is_split:
        return _run_split_module(
            module,
            command_runner=command_runner,
            collection_runner=collection_runner,
        )
    return _normalize_status(command_runner(_pytest_command(module))), []


def _report_failures(failed_modules: list[Path], failed_split_leaves: list[str]) -> int:
    if not failed_modules:
        return 0

    print("Failed unit test modules:")
    for module in failed_modules:
        print(f"- {module.as_posix()}")
    if failed_split_leaves:
        print("Failed split unit test leaves:")
        for node_id in failed_split_leaves:
            print(f"- {node_id}")
    return 1


def run_unit_gate(
    test_root: Path = DEFAULT_TEST_ROOT,
    *,
    command_runner: CommandRunner = _run_command,
    collection_runner: CollectionRunner = _run_collection_command,
    split_modules: frozenset[Path] = SPLIT_MODULES,
    suite: Suite = "all",
) -> int:
    """Run planner validation, then each discovered test module in isolation."""

    planner_status = _normalize_status(command_runner([sys.executable, "-m", "planner", "check"]))
    if planner_status != 0:
        return planner_status

    if suite == "smoke":
        return _run_smoke_nodes(command_runner)

    modules = discover_test_modules(test_root)
    discovery_status = _validate_discovered_modules(test_root, modules, split_modules)
    if discovery_status != 0:
        return discovery_status

    selected_modules = _suite_modules(modules, suite, test_root)
    if not selected_modules:
        print(f"No {suite} test modules selected under {test_root}.", file=sys.stderr, flush=True)
        return 5

    selected_split_modules = frozenset(module for module in split_modules if module in selected_modules)
    failed_modules: list[Path] = []
    failed_split_leaves: list[str] = []
    total = len(selected_modules)
    for index, module in enumerate(selected_modules, start=1):
        print(f"[{index}/{total}] {module.as_posix()}", flush=True)
        is_split = module in selected_split_modules
        status, failed_leaves = _run_test_module(
            module,
            is_split=is_split,
            command_runner=command_runner,
            collection_runner=collection_runner,
        )
        if status == 0:
            continue
        if status != 1 or (is_split and not failed_leaves):
            return status
        failed_modules.append(module)
        failed_split_leaves.extend(failed_leaves)

    return _report_failures(failed_modules, failed_split_leaves)


def main() -> int:
    parser = ArgumentParser(description="Run supp-slotter bounded pytest suites.")
    parser.add_argument(
        "--list-suites",
        action="store_true",
        help="print the machine-readable suite inventory and exit without running tests",
    )
    parser.add_argument(
        "--suite",
        choices=("smoke", "fast-unit", "unit", "ontology-contract", "all"),
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
