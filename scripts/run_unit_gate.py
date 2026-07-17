"""Run the planner check and isolated unit-test modules.

The enclosing ``run_bounded.sh`` process owns the cgroup and checkout lock.
Each pytest module is then given a fresh Python process so module-level state
and anonymous Python heap cannot accumulate across the suite.
"""

from __future__ import annotations

import re
import subprocess
import sys
from collections.abc import Callable, Sequence
from pathlib import Path

DEFAULT_TEST_ROOT = Path("tests")
PYTEST_MARKERS = "not integration and not slow"
SPLIT_MODULES = frozenset({
    Path("tests/test_enzyme_governance_acceptance.py"),
    Path("tests/test_ontology_artifacts.py"),
    Path("tests/test_ontology_compiler_outputs.py"),
    Path("tests/test_ontology_formal_runtime_assertions.py"),
    Path("tests/test_ontology_repository_contract.py"),
})
_COLLECTION_SUMMARY = re.compile(
    r"(?:no tests collected|\d+ tests? collected|\d+/\d+ tests? collected \(\d+ deselected\))"
    r"(?: in \d+(?:\.\d+)?s)?"
)
Command = Sequence[str]
CommandRunner = Callable[[Command], int]
CollectionRunner = Callable[[Command], subprocess.CompletedProcess[str]]


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
) -> int:
    """Run planner validation, then each discovered test module in isolation."""

    planner_status = _normalize_status(command_runner([sys.executable, "-m", "planner", "check"]))
    if planner_status != 0:
        return planner_status

    modules = discover_test_modules(test_root)
    discovery_status = _validate_discovered_modules(test_root, modules, split_modules)
    if discovery_status != 0:
        return discovery_status

    failed_modules: list[Path] = []
    failed_split_leaves: list[str] = []
    total = len(modules)
    for index, module in enumerate(modules, start=1):
        print(f"[{index}/{total}] {module.as_posix()}", flush=True)
        is_split = module in split_modules
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
    return run_unit_gate()


if __name__ == "__main__":
    raise SystemExit(main())
