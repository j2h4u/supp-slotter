---
phase: 260510-l2m
plan: 01
subsystem: cli
tags: [show, pillbox, schedule, cli]
dependency_graph:
  requires: [cmd_plan, load_yaml, SCHEDULE_PATH]
  provides: [cmd_show]
  affects: [planner/__main__.py, planner/engine/__init__.py]
tech_stack:
  added: []
  patterns: [cast/isinstance narrowing for dict[str, Any] in strict pyright]
key_files:
  created:
    - planner/engine/show.py
  modified:
    - planner/engine/__init__.py
    - planner/__main__.py
    - tests/test_phase_03.py
    - tests/test_phase_02.py
decisions:
  - Placed 'show' subparser between 'plan' and 'doctor' in __main__ to reflect workflow order (check → plan → show → doctor)
  - Used _str_field() helper to extract label fields safely under strict pyright without inline ternary on Any
  - Used cast(list[Any], ...) after isinstance(x, list) check to satisfy pyright's reportUnknownArgumentType on len()
metrics:
  duration: ~12min
  completed: 2026-05-10
---

# Phase 260510-l2m Plan 01: Add show command Summary

`show` subcommand added to planner CLI — regenerates schedule via cmd_plan() and prints a pillbox-by-pillbox layout to stdout using slot label fields from the schedule.

## Tasks Completed

| Task | Description | Commit |
|------|-------------|--------|
| 1 | Implement cmd_show in planner/engine/show.py + re-export in __init__.py | 8a7eb30 |
| 2 | Wire show subcommand into __main__.py + subprocess test in test_phase_03.py | a0d92b4 |

## Files Created / Modified

| File | Change |
|------|--------|
| `planner/engine/show.py` | Created — cmd_show() entry point, SEPARATOR constant, _str_field helper |
| `planner/engine/__init__.py` | Added cmd_show import and __all__ entry |
| `planner/__main__.py` | Added show subparser and dispatch branch |
| `tests/test_phase_03.py` | Added test_show_regenerates_and_prints_pillbox_layout |
| `tests/test_phase_02.py` | Fixed test_cli_help_exposes_simple_agent_commands (Rule 1) |

## Test Labels Chosen

The test asserts two stable slot labels:
- `"Morning / empty stomach"` — confirmed non-empty: Best Naturals - Acetyl L-Carnitine (ALCAR), BioGrace - Vitamin B5
- `"Morning / with breakfast"` — confirmed non-empty: Country Life, Futurebiotics, Life Extension, NOW Foods

Both labels are from the daily pillbox which always has products in the current stacks.yaml.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Updated help string assertion in test_phase_02.py**
- **Found during:** Task 2 full pytest run
- **Issue:** `test_cli_help_exposes_simple_agent_commands` asserted `{check,plan,doctor,find,review-substance}` — the exact argparse usage string. Adding `show` changed the string to `{check,plan,show,doctor,find,review-substance}`, breaking the assertion.
- **Fix:** Updated the assertion string to include `show`.
- **Files modified:** `tests/test_phase_02.py`
- **Commit:** a0d92b4

**2. Subparser position:** Placed `show` between `plan` and `doctor` (not after `plan` as literally specified, which would also be between plan and doctor). Position matches "workflow order" intent from the plan.

**3. Pyright strict narrowing:** Used a `_str_field()` helper instead of inline `pillbox.get("label") or key` to satisfy `reportUnknownVariableType` and `reportUnknownArgumentType` in strict mode. Also added `cast(list[Any], raw_products)` before `len()` call.

## Verification Results

- `uv run python -m planner show` exits 0 and prints correct pillbox layout
- All 100 tests pass (`pytest tests/ -x -q`)
- Pyright strict: 0 errors, 0 warnings across all changed files

## Self-Check: PASSED

- planner/engine/show.py: exists
- planner/engine/__init__.py: contains cmd_show
- planner/__main__.py: contains show dispatch
- tests/test_phase_03.py: contains test_show_regenerates_and_prints_pillbox_layout
- Commits 8a7eb30 and a0d92b4: verified in git log
