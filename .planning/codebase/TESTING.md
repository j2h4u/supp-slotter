# Testing Patterns

**Analysis Date:** 2026-05-05

## Test Framework

**Runner:**
- pytest, installed through `uv run pytest`; no pytest config file is present.
- Config: Not detected (`pytest.ini`, `pyproject.toml`, `tox.ini`, and `setup.cfg` are absent).

**Assertion Library:**
- Native Python `assert` statements with pytest assertion rewriting: `tests/test_phase_01.py`.
- Standard library helpers are used for assertions and fixtures: `collections.Counter`, `pathlib.Path`, `subprocess.CompletedProcess` in `tests/test_phase_01.py`.

**Run Commands:**
```bash
uv run pytest -q              # Run all tests
uv run pytest -q -k phase_01  # Run the current phase test module by expression
uv run planner.py check       # Run domain validation smoke check
uv run planner.py plan        # Run planner smoke and regenerate schedule.yaml
```

## Test File Organization

**Location:**
- Tests live in a top-level `tests/` directory.
- Current suite is phase-oriented and integration-heavy: `tests/test_phase_01.py`.

**Naming:**
- Test files use `test_<phase_or_area>.py`: `tests/test_phase_01.py`.
- Test functions use descriptive `test_...` names that state the behavior: `test_phase_01_check_passes`, `test_training_slots_and_activity_traits`, `test_plan_generates_stack_partitioned_schedule`.

**Structure:**
```
tests/
└── test_phase_01.py   # CLI smoke tests plus YAML topology and negative validation coverage
```

## Test Structure

**Suite Organization:**
```python
from __future__ import annotations

import subprocess
from collections import Counter
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]


def load_yaml(path: str) -> object:
    return yaml.safe_load((ROOT / path).read_text())


def run_planner(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["uv", "run", "planner.py", *args],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
```

**Patterns:**
- Define shared expected sets as module constants near the top of the test file: `TRAINING_SUBSTANCES`, `DAILY_SUBSTANCES`, `INACTIVE_SUBSTANCES`, `EXPECTED_ACTIVITY_TRAITS` in `tests/test_phase_01.py`.
- Use a small `load_yaml` helper for direct fixture reads from repo root: `tests/test_phase_01.py`.
- Use a small `run_planner` helper for CLI subprocess testing: `tests/test_phase_01.py`.
- Assert subprocess return codes first, with `result.stdout + result.stderr` as the failure message: `tests/test_phase_01.py`.
- Verify both data topology and CLI behavior. Tests inspect `data/slots.yaml`, `data/traits.yaml`, `data/inventory.yaml`, `data/products/*.yaml`, `data/goals/*.yaml`, and `schedule.yaml`.

## Mocking

**Framework:** Not used

**Patterns:**
```python
def test_phase_01_check_passes() -> None:
    result = run_planner("check")

    assert result.returncode == 0, result.stdout + result.stderr
    assert "All checks passed." in result.stdout
    assert "ERROR:" not in result.stderr
```

**What to Mock:**
- Do not mock `planner.py` internals for current coverage. Current tests intentionally exercise the real CLI through `subprocess.run`.
- Mocking is only appropriate for future external services or slow/non-deterministic dependencies; none are present.

**What NOT to Mock:**
- Do not mock YAML fixtures in `data/`, schemas in `schema/`, or CLI subprocess execution when testing planner behavior. The existing suite treats those files as the contract.
- Do not mock generated `schedule.yaml`; preserve and restore it around tests that run `planner.py plan`.

## Fixtures and Factories

**Test Data:**
```python
TRAINING_SUBSTANCES = {
    "l_citrulline_malate",
    "creatine",
    "electrolyte_caps",
    "l_carnitine_l_tartrate",
}

EXPECTED_ACTIVITY_TRAITS = {
    "l_citrulline_malate": "activity:pre_workout",
    "creatine": "activity:any_workout",
    "electrolyte_caps": "activity:any_workout",
    "l_carnitine_l_tartrate": "activity:any_workout",
}
```

**Location:**
- Real fixtures are the committed YAML files under `data/` and JSON Schemas under `schema/`.
- Expected fixture summaries are module constants in `tests/test_phase_01.py`.
- No factory library or `conftest.py` is present.

## Coverage

**Requirements:** None enforced. No coverage configuration or threshold is detected.

**View Coverage:**
```bash
uv run pytest -q
```

## Test Types

**Unit Tests:**
- Limited direct unit coverage. Current tests do not import individual functions from `planner.py`.
- Add direct unit tests for pure helpers such as `slot_matches`, `compute_slot_score`, `must_separate`, and `effective_traits` in `tests/test_*.py` when changing scoring semantics.

**Integration Tests:**
- Primary test style. `tests/test_phase_01.py` runs `uv run planner.py check` and `uv run planner.py plan` against committed repo data.
- Data contract tests assert exact slot keys, trait effects, stack partition counts, goal members, and schedule membership in `tests/test_phase_01.py`.

**E2E Tests:**
- CLI-level smoke tests are the effective E2E layer: `test_phase_01_check_passes` and `test_plan_generates_stack_partitioned_schedule` in `tests/test_phase_01.py`.
- No browser, API server, or external system E2E framework is present.

## Common Patterns

**Async Testing:**
```python
# Not used. All code and tests are synchronous.
```

**Error Testing:**
```python
def test_goal_ref_validator_rejects_missing_product_and_restores_file() -> None:
    goal_path = ROOT / "data/goals/vascular_health.yaml"
    original = goal_path.read_bytes()

    try:
        corrupted = original.replace(
            b"substance: l_citrulline_malate",
            b"substance: bogus_substance_xyz",
            1,
        )
        assert corrupted != original
        goal_path.write_bytes(corrupted)

        result = run_planner("check")

        assert result.returncode != 0
        combined_output = result.stdout + result.stderr
        assert "bogus_substance_xyz" in combined_output
        assert "no matching product card" in combined_output
    finally:
        goal_path.write_bytes(original)
```

**State Restoration:**
- Always restore mutable committed files in `finally` blocks when a test writes to them: `schedule.yaml`, `data/goals/vascular_health.yaml` in `tests/test_phase_01.py`.
- Read original bytes before mutation and write original bytes back after command execution.

**Current Verification:**
- `uv run pytest -q` passes: 7 tests.
- `uv run planner.py check` exits 0 and prints `All checks passed.` after non-fatal `INFO: ... unmatched_concern` lines.

---

*Testing analysis: 2026-05-05*
