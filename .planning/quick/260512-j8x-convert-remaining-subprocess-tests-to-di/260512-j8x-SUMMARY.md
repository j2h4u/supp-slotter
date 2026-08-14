---
phase: quick-260512-j8x
plan: 01
subsystem: test-infrastructure
tags: [test-refactor, subprocess-elimination, di, structured-results]
dependency_graph:
  requires: [260512-ib5]
  provides: [full-subprocess-elimination-in-phase02-03-tests]
  affects: [tests/test_phase_02.py, tests/test_phase_03.py, planner/engine/results.py, planner/engine/plan.py, planner/cards/stacks.py, planner/engine/check.py, planner/maintenance.py]
tech_stack:
  added: []
  patterns: [DI via data_root param, structured result dataclasses, collect_errors threading]
key_files:
  created: []
  modified:
    - planner/engine/results.py
    - planner/engine/plan.py
    - tests/test_phase_02.py
    - tests/test_phase_03.py
    - planner/cards/stacks.py
    - planner/engine/check.py
    - planner/maintenance.py
decisions:
  - "PlanResult.errors uses field(default_factory=list[str]) — required by pyright strict on frozen dataclasses"
  - "check_stack_alignment returns (errors, info) tuple; info carries the non-fatal no-stack-entry advisory"
  - "acquire_maintenance_lock/run_auto_maintenance accept optional collect_errors list — additive, no call-site churn"
  - "_cmd_check_inner initialises errors before maintenance call so lock-blocked message flows into CheckResult.errors"
metrics:
  duration: "~20 min"
  completed: "2026-05-12"
  tasks: 2
  files: 7
---

# Phase quick-260512-j8x Plan 01: Convert Remaining Subprocess Tests to DI — Summary

**One-liner:** Eliminated all non-CLI-contract subprocess calls from test_phase_02.py and test_phase_03.py by calling `cmd_check`/`cmd_plan` directly and asserting against typed `CheckResult`/`PlanResult` fields.

## What Was Built

### Task 1 — PlanResult.errors + test_phase_02.py

- Added `errors: list[str]` field to `PlanResult` with `field(default_factory=list[str])` (required to satisfy pyright strict on frozen dataclasses; bare `list` produces `list[Unknown]`).
- All print-then-return-None paths in `_build_active_index` and `_cmd_plan_inner` now append the formatted message to a local `errors` list that flows into the returned `PlanResult.errors`.
- `plan_in_temp_dir` helper: `run_planner(root=tmp_path)` → `cmd_plan(data_root=tmp_path)`; assertion uses `result.exit_code` + `"\n".join(result.errors)`.
- `check_in_temp_dir` helper: return type changed from `RunResult` to `CheckResult`; body calls `cmd_check(data_root=tmp_path)`.
- Three `check_in_temp_dir` consumers retargeted: `result.returncode` → `result.exit_code`, `result.stdout + result.stderr` → `"\n".join(result.errors + result.info)`.
- `test_cli_help_exposes_simple_agent_commands` left untouched on `run_planner`.

### Task 2 — test_phase_03.py (7 tests)

Converted the seven enumerated tests to `cmd_check`/`cmd_plan` direct calls:

| Test | Command | Assertion target |
|------|---------|-----------------|
| test_check_auto_renames_files_when_names_change | cmd_check | exit_code == 0 |
| test_check_warns_about_products_without_stack_entry | cmd_check | result.info |
| test_duplicate_stack_item_across_stacks_is_rejected | cmd_check | result.errors |
| test_auto_maintenance_lock_only_blocks_mutations | cmd_check x2 | result.errors |
| test_workout_activity_product_is_not_scheduled_as_daily | cmd_plan | result.errors |
| test_duplicate_slot_ids_across_pillboxes_are_rejected | cmd_check | result.errors |
| test_relation_validation_rejects_unknown_substance_name | cmd_check | result.errors |

4 review-substance CLI-contract tests remain on `run_planner` unchanged.

## Subprocess-call Delta

| File | Before | After | Kept |
|------|--------|-------|------|
| tests/test_phase_02.py | 5 | 1 | `--help` only |
| tests/test_phase_03.py | 11 | 4 | 4 review-substance CLI tests |
| **Total** | **16** | **5** | |

Final `rg 'run_planner\('` gate output (exactly 5 lines as required):
```
tests/test_phase_02.py:213:    result = run_planner("--help")
tests/test_phase_03.py:144:    result = run_planner("review-substance", ...)
tests/test_phase_03.py:154:    result = run_planner("review-substance", ...)
tests/test_phase_03.py:165:    result = run_planner("review-substance", ...)
tests/test_phase_03.py:176:    result = run_planner("review-substance", ...)
```

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing structured capture] check_stack_alignment: no-stack-entry advisory was a bare print()**

- **Found during:** Task 2 — `test_check_warns_about_products_without_stack_entry` failed; `result.info` was empty despite the message appearing in captured stdout.
- **Issue:** `check_stack_alignment` used a bare `print()` to stdout for the "has no stack entry" advisory — the message never entered `CheckResult.info`.
- **Fix:** Changed `check_stack_alignment` return type from `list[str]` to `tuple[list[str], list[str]]` (errors, info); the advisory goes into `info` (still printed to stdout for CLI users). `validate_stacks` propagated the tuple. `check.py` unpacks it.
- **Files modified:** `planner/cards/stacks.py`, `planner/engine/check.py`
- **Commit:** c317a76

**2. [Rule 2 - Missing structured capture] Maintenance lock-blocked message escaped CheckResult.errors**

- **Found during:** Task 2 — `test_auto_maintenance_lock_only_blocks_mutations` failed; `blocked_result.errors` was empty despite the message in captured stderr.
- **Issue:** `acquire_maintenance_lock` used a bare `print(..., file=sys.stderr)` for the "another planner process is running" message. `_cmd_check_inner` returned `CheckResult(errors=[])` on maintenance failure.
- **Fix:** Added `collect_errors: list[str] | None = None` optional parameter to `acquire_maintenance_lock` and `run_auto_maintenance` (additive; all existing callers unchanged). `_cmd_check_inner` initialises `errors: list[str] = []` before the maintenance call and passes it as `collect_errors=errors`; the early-return path uses `errors=errors`.
- **Files modified:** `planner/maintenance.py`, `planner/engine/check.py`
- **Commit:** c317a76

## Known Stubs

None.

## Threat Flags

None — no new network endpoints, auth paths, or schema changes at trust boundaries.

## Self-Check: PASSED

- `planner/engine/results.py` — exists, `PlanResult.errors` field present
- `planner/engine/plan.py` — exists, all PlanResult returns include `errors=errors`
- `tests/test_phase_02.py` — exists, helpers rewritten
- `tests/test_phase_03.py` — exists, 7 tests converted
- `planner/cards/stacks.py` — exists, tuple return
- `planner/engine/check.py` — exists, unpacks tuple
- `planner/maintenance.py` — exists, collect_errors parameter
- Commits: 58991f4 (Task 1), c317a76 (Task 2) — both present in git log
- `just lint && just typecheck && just test` — all passed (86/86, 0/0/0, ruff clean)
