# Testing Patterns

**Analysis Date:** 2026-05-22

## Test Framework

**Runner:**
- pytest 9+ from the `dev` dependency group in `pyproject.toml`.
- Config: `pyproject.toml` declares dependencies and type/lint settings; no dedicated `pytest.ini`, `tox.ini`, or `[tool.pytest]` configuration is present.
- CI runs on GitHub Actions in `.github/workflows/test.yml`.

**Assertion Library:**
- Plain Python `assert` statements.
- `pytest.raises`, `pytest.MonkeyPatch`, `pytest.CaptureFixture`, and `tmp_path` fixtures are used where needed in files such as `tests/test_maintenance.py`, `tests/test_schemas.py`, and `tests/test_phase_03.py`.

**Run Commands:**
```bash
uv run pytest tests/              # Run all pytest tests
uv run pytest tests/test_schemas.py # Run one test module
uv run pytest -q tests/           # Run all tests with quieter output
```

Quality commands:
```bash
uv run python -m planner check    # Validate live YAML and cross-references
uv run ruff check .               # Lint
uv run pyright                    # Strict type check
just check                        # Lint, typecheck, planner check, pytest
```

## Test File Organization

**Location:**
- Tests live in `tests/` and are separate from implementation modules under `planner/`.
- Shared pytest import setup lives in `tests/conftest.py`.
- Shared in-process CLI helpers live in `tests/helpers.py`.

**Naming:**
- Use `test_*.py` files, such as `tests/test_phase_03.py`, `tests/test_scheduling_units.py`, `tests/test_primary_component_scoring.py`, `tests/test_schemas.py`, `tests/test_maintenance.py`, and `tests/test_review_command.py`.
- Use `test_<behavior>_<expected_result>()` function names, such as `test_compute_slot_score_prefer_strong_match`, `test_substance_schema_rejects_flat_form`, and `test_cmd_review_output_has_section_headers`.
- Use `_helper_name` for test-local fixture builders, such as `_make_substance_card` in `tests/test_schemas.py` and `_write_minimal_data_root` in `tests/test_review_command.py`.

**Structure:**
```
tests/
├── conftest.py                  # Adds repo root to sys.path
├── helpers.py                   # In-process CLI runner
├── test_scheduling_units.py     # Pure scheduling and warning internals
├── test_primary_component_scoring.py
├── test_schemas.py              # JSON schema and reference-integrity behavior
├── test_phase_03.py             # CLI/review/search/maintenance regressions
├── test_maintenance.py          # IO, maintenance, and lock/error regressions
└── test_review_command.py       # Review/audit command output contracts
```

## Test Structure

**Suite Organization:**
```python
from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from planner.engine import cmd_check, cmd_plan


def test_behavior_name(tmp_path: Path) -> None:
    # arrange: write YAML or construct dataclasses
    # act: call command/helper directly
    # assert: inspect structured result and important output text
    result = cmd_check(data_root=tmp_path)
    assert result.exit_code == 0, "\n".join(result.errors)
```

**Patterns:**
- Prefer direct function calls for unit-level behavior, such as `compute_slot_score` and `effective_stack_item_traits` in `tests/test_scheduling_units.py`.
- Use inline dataclass constructors for pure scheduling tests in `tests/test_scheduling_units.py` and `tests/test_primary_component_scoring.py`.
- Use temp YAML trees for planner/check integration scenarios in `tests/test_phase_03.py`, `tests/test_maintenance.py`, and review/audit/relation tests.
- Assert on structured result fields when available, such as `CheckResult.errors`, `PlanResult.errors`, `ReviewResult.output`, and `RunResult.returncode`.
- Assert on key output substrings only for CLI presentation contracts, as in `tests/test_review_command.py` and `tests/test_phase_03.py`.

## Mocking

**Framework:** pytest monkeypatch and local temp filesystem fixtures.

**Patterns:**
```python
def test_check_reports_missing_product_reference(tmp_path: Path) -> None:
    temp_data = copy_data_tree(tmp_path)
    stacks = yaml.safe_load((temp_data / "stacks.yaml").read_text())
    stacks["daily"].append("prd_missing")
    (temp_data / "stacks.yaml").write_text(yaml.safe_dump(stacks, sort_keys=False))

    result = cmd_check(data_root=tmp_path)

    assert result.exit_code != 0
    assert any("prd_missing" in error for error in result.errors)
```

```python
def run_planner(*args: str, root: Path = ROOT) -> RunResult:
    old_argv = sys.argv[:]
    sys.argv = ["planner", *args]
    try:
        with redirect_stdout(stdout_buf), redirect_stderr(stderr_buf):
            main(data_root=root)
    finally:
        sys.argv = old_argv
```

**What to Mock:**
- Prefer command `data_root` parameters and `tests.helpers.run_planner(root=...)` for isolated data roots.
- Patch module constants with `monkeypatch.setattr` only when a test needs one specific non-root dependency redirected.
- Use `tmp_path` or `tempfile.TemporaryDirectory` for filesystem effects instead of touching live `data/` in behavior tests.

**What NOT to Mock:**
- Do not mock core planner algorithms in `planner/engine/_scheduling.py` or `planner/engine/plan.py`; construct dataclasses or YAML fixtures and run the real implementation.
- Do not mock schema validation for schema tests; call `planner.schema_validation.schema_errors` or loader functions against real schemas in `schema/`.
- Do not mock command output when testing CLI presentation; capture stdout/stderr with `capsys`, `contextlib.redirect_stdout`, or `tests.helpers.run_planner`.

## Fixtures and Factories

**Test Data:**
```python
def make_slot(near: str = "breakfast", food: bool = True) -> Slot:
    return Slot(
        slot_id="test_slot",
        label="Test Slot",
        order=1,
        near=near,  # type: ignore[arg-type]
        food=food,
        pillbox="daily",
        pillbox_label="Daily",
        stack="daily",
    )
```

```python
def write_yaml(path: Path, data: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(data, sort_keys=False))
```

**Location:**
- Keep module-specific builders next to the tests that use them, as in `tests/test_scheduling_units.py`, `tests/test_primary_component_scoring.py`, and `tests/test_schemas.py`.
- Put shared CLI/data-root helpers in `tests/helpers.py`.
- Use real live `data/` only for whole-repo validation or smoke contracts, such as `_load_trait_ids` in `tests/test_schemas.py` and `test_cmd_review_exits_zero` in `tests/test_review_command.py`.

## Coverage

**Requirements:** No coverage threshold is configured in `pyproject.toml`, `.github/workflows/test.yml`, or a dedicated pytest coverage config.

**View Coverage:**
```bash
uv add --dev pytest-cov          # Not currently declared; add only if coverage reporting becomes required
uv run pytest --cov=planner tests/
```

## Test Types

**Unit Tests:**
- Pure scheduling and warning logic tests belong in `tests/test_scheduling_units.py` and `tests/test_primary_component_scoring.py`.
- Use dataclass constructors from `planner/contracts.py` and direct imports from `planner/engine/_scheduling.py` for low-level algorithm checks.

**Integration Tests:**
- Planner/check command tests with temp YAML roots belong in `tests/test_phase_03.py`, `tests/test_maintenance.py`, and targeted command/relation/audit test modules.
- Schema and reference-integrity tests belong in `tests/test_schemas.py` and should exercise real JSON schemas under `schema/`.
- CLI smoke tests should use `tests.helpers.run_planner` or command functions from `planner.engine` rather than spawning a subprocess unless process-level behavior is the subject.

**E2E Tests:**
- No browser or external E2E framework is used.
- The closest end-to-end path is `uv run python -m planner check` plus `uv run pytest tests/`, as wired in `justfile` and `.github/workflows/test.yml`.

## Common Patterns

**Async Testing:**
```python
# Not applicable: planner code is synchronous Python CLI code.
```

**Error Testing:**
```python
def test_load_yaml_malformed_yaml_raises_card_load_error(tmp_path: Path) -> None:
    bad = tmp_path / "bad.yaml"
    bad.write_text(":\n  - bad: [")
    with pytest.raises(CardLoadError) as exc_info:
        load_yaml(bad)
    assert "invalid YAML" in exc_info.value.message
```

```python
def test_cmd_review_surfaces_risk_manual_review() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        _write_minimal_data_root(tmp)
        result = cmd_review(data_root=tmp)
        assert result.exit_code == 0, f"cmd_review failed: {result.stderr}"
        assert "manual_review" in result.output
```

---

*Testing analysis: 2026-05-22*
