---
phase: 260509-vcm
plan: "01"
subsystem: planner
tags: [code-quality, hardening, deduplication, testing, refactor]
dependency_graph:
  requires: []
  provides: [maintenance-write-hardening, scheduling-unit-tests, endpoint-dedup, slot-blocked-helper, test-helper-rename]
  affects: [planner/maintenance.py, planner/cards/relations.py, planner/engine/plan.py, tests/]
tech_stack:
  added: []
  patterns: [OSError-rollback, extracted-helper, module-level-function, inline-fixture-tests]
key_files:
  created:
    - tests/test_scheduling_units.py
  modified:
    - planner/maintenance.py
    - planner/cards/relations.py
    - planner/engine/plan.py
    - tests/test_phase_02.py
    - tests/test_phase_03.py
decisions:
  - "_append_missing_relation_warning uses source_display_side/target_display_side kwargs to reconcile the asymmetric display conventions between balance (active=source) and supports (missing=source)"
  - "test_phase_02.py had 5 call sites for copy_planner_runtime, not 2 as the plan stated; all 5 renamed to copy_planner_runtime_only"
metrics:
  duration: "~18 min"
  completed: "2026-05-09"
  tasks: 3
  files: 6
---

# Phase 260509-vcm Plan 01: Code Quality Structural Improvements (KQ3) Summary

OSError-hardened maintenance write paths, 16 new unit tests for scheduling/warning internals, and extracted `_endpoint_fields`/`_append_missing_relation_warning`/`_slot_is_blocked` helpers eliminating duplicated inline code across relations.py and plan.py.

## Tasks Completed

| Task | Description | Commit |
|------|-------------|--------|
| A | Harden write-failure paths in maintenance.py (SI-01, SI-02, SI-03) | 01c1615 |
| B | Unit tests for scheduling and warning internals (SI-04 through SI-08) | 57f743d |
| C | Deduplication + rename (SI-09 through SI-12) | 5634e24 |

## What Was Built

**Task A — maintenance.py hardening (SI-01/02/03):**
- `acquire_maintenance_lock`: pid write_text wrapped in `try/except OSError`; on failure, `lock_dir.rmdir()` called and `False` returned — no empty lock dir left behind
- `rewrite_substance_refs`: all three write loops (products, dashboards, substances) wrap `path.write_text` in `try/except OSError` with `continue` — function never aborts on per-file write failure
- `normalize_substances`: `old_id_value = substance.get("id")` saved before generating; on write OSError, `substance["id"] = old_id_value` reverted and `None` returned

**Task B — tests/test_scheduling_units.py (SI-04/05/06/07/08):**
16 new tests across 5 function groups. All fixtures built inline — no live DATA_DIR access, no disk YAML reads.

**Task C — deduplication + rename (SI-09/10/11/12):**
- `_endpoint_fields(relation, side)`: extracted from 4 endpoint functions in relations.py; no more duplicated `if side == "source": ... if side == "target":` blocks
- `_append_missing_relation_warning(...)`: extracted shared logic from both `collect_missing_*` functions; each is now ≤10 lines; `source_display_side`/`target_display_side` kwargs handle the asymmetric display conventions
- `_slot_is_blocked(...)`: module-level in plan.py; both `seed_with_greedy_assignment` and `search` use it replacing two paired `any()` guards each
- `copy_planner_runtime_only` in test_phase_02.py (5 sites renamed); `copy_planner_with_data` in test_phase_03.py (all sites renamed); zero stale references

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Display-order inversion in _append_missing_relation_warning**
- **Found during:** Task C SI-10, first test run after refactoring
- **Issue:** The plan's helper spec passed `missing_side` as first display arg (source) and `active_side` as second (target). For balance this produced "Copper -> Zinc" instead of the expected "Zinc -> Copper" (active → source, missing → target). For supports the display convention is the opposite: missing supporter as source, active supported as target.
- **Fix:** Added `source_display_side`/`target_display_side` keyword args to `_append_missing_relation_warning` (default: active→source, missing→target for balance). `collect_missing_support_relations` passes `source_display_side="source", target_display_side="target"` to override to the original per-relation endpoint convention.
- **Files modified:** planner/cards/relations.py
- **Commit:** 5634e24

**2. [Rule 2 - Scope underspecification] test_phase_02.py had 5 copy_planner_runtime call sites, not 2**
- **Found during:** Task C SI-12
- **Issue:** Plan stated 2 call sites (write_split_model_fixture line 176, test_cli_help line 345). Actual count: 5 call sites (lines 168, 331, 352, 371, 387).
- **Fix:** Renamed all 5 via `replace_all=true`. All pass.
- **Files modified:** tests/test_phase_02.py
- **Commit:** 5634e24

## Verification Results

```
grep -c "copy_planner_runtime(" tests/test_phase_02.py tests/test_phase_03.py
# test_phase_02.py: 0
# test_phase_03.py: 0

grep -n "def _endpoint_fields" planner/cards/relations.py          # line 68
grep -n "def _append_missing_relation_warning" planner/cards/relations.py  # line 247
grep -n "def _slot_is_blocked" planner/engine/plan.py              # line 62

uv run pytest tests/ -q
# 64 passed
```

## Known Stubs

None.

## Threat Flags

None — all threat register mitigations (T-kq3-01, T-kq3-02) implemented as specified.

## Self-Check: PASSED

- planner/maintenance.py: modified, committed 01c1615
- tests/test_scheduling_units.py: created, committed 57f743d
- planner/cards/relations.py: modified, committed 5634e24
- planner/engine/plan.py: modified, committed 5634e24
- tests/test_phase_02.py: modified, committed 5634e24
- tests/test_phase_03.py: modified, committed 5634e24
- All commits exist in git log: confirmed
- 64 tests pass: confirmed
