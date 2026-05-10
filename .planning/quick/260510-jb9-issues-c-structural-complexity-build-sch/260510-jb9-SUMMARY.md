---
phase: 260510-jb9
plan: "01"
subsystem: planner
tags: [refactor, complexity, namedtuple, data-table]
dependency_graph:
  requires: []
  provides: [PlanInputs, ActiveIndex, _CONTEXT_KEY_RULES, _rewrite_dict_refs_in_files, _rewrite_prefer_with_in_substances]
  affects: [planner/engine/plan.py, planner/maintenance.py, planner/cards/warnings.py]
tech_stack:
  added: []
  patterns: [NamedTuple, data-driven dispatch, load-mutate-write helper extraction]
key_files:
  created: []
  modified:
    - planner/cards/warnings.py
    - planner/maintenance.py
    - planner/engine/plan.py
decisions:
  - "Used two helpers (_rewrite_dict_refs_in_files + _rewrite_prefer_with_in_substances) rather than one over-parameterised helper, because the products/dashboards path mutates dict fields while the substances path mutates a list-of-strings — different shapes, different helpers"
  - "Added cards_dir.exists() guard to _rewrite_dict_refs_in_files for both products and dashboards calls; products dir always exists in normal layout so behaviour is identical, and dashboards previously had the same guard"
  - "In cmd_plan, kept local aliases only for slots/substances/products/trait_defs (used 3+ times each); read other inputs inline via inputs.<field>"
metrics:
  duration: ~8 minutes
  completed: "2026-05-10T09:25:03Z"
  tasks_completed: 3
  tasks_total: 3
  files_changed: 3
---

# Phase 260510-jb9 Plan 01: Structural Complexity Refactors Summary

Three behaviour-preserving structural refactors across warnings.py, maintenance.py, and plan.py — reducing parameter-count noise, eliminating triplicated load-mutate-write loops, and replacing a 9-branch keyword chain with a data table.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 (CX3) | Table-drive review_context_key | c342b46 | planner/cards/warnings.py |
| 2 (CX2) | Extract load-mutate-write helpers | a704b5c | planner/maintenance.py |
| 3 (CX1) | Introduce PlanInputs + ActiveIndex NamedTuples | 5932a76 | planner/engine/plan.py |

## What Was Built

**CX3 — warnings.py:** `review_context_key` replaced with a data-table scan over `_CONTEXT_KEY_RULES` (module-level tuple of 9 `(bucket_key, keywords)` pairs). First-hit ordering preserved verbatim. Function body reduced from 9 if-branches to a single for-loop + return-None.

**CX2 — maintenance.py:** `rewrite_substance_refs` (97 lines) collapsed to a 9-line body delegating to two private helpers: `_rewrite_dict_refs_in_files` (handles products and dashboards — dict members with `.substance` field) and `_rewrite_prefer_with_in_substances` (handles the list-of-strings `prefer_with` field). Yaml dump options (sort_keys=False, default_flow_style=False, allow_unicode=True) preserved identically.

**CX1 — plan.py:** Introduced `PlanInputs` and `ActiveIndex` NamedTuples (engine-private, defined in plan.py). `_load_plan_inputs` now returns `PlanInputs | None`. `_build_active_index` now returns `ActiveIndex | None`. `_build_schedule_output` parameter count reduced from 20 to 15 (six per-item index dicts + item_traits replaced by a single `active: ActiveIndex`). `_run_plan_search` signature unchanged. All field accesses inside `_build_schedule_output` read directly from `active.<field>`.

## Verification

- `pytest tests/ -q -k "not phase_02 and not phase_03 and not schemas"`: 49 passed (pre-existing failures in phase_02/03/schemas tests are unrelated — all fail with `ModuleNotFoundError: yaml` in isolated uv environments and were failing before this plan)
- `pyright planner/ --outputjson`: 0 errors, 0 warnings
- `_build_schedule_output` param count: 15 (target ≤ 15 met)
- `rewrite_substance_refs` body: 9 lines (target ≤ 10 met)
- `review_context_key` body: single loop + return-None (target met)

## Deviations from Plan

None — plan executed exactly as written.

## Known Stubs

None.

## Threat Flags

None — pure internal refactors, no new I/O or trust boundaries introduced.

## Self-Check: PASSED

- `planner/cards/warnings.py` — modified, `_CONTEXT_KEY_RULES` present, loop body confirmed
- `planner/maintenance.py` — modified, two helpers present, body ≤ 10 lines confirmed
- `planner/engine/plan.py` — modified, `class PlanInputs` and `class ActiveIndex` present
- Commits c342b46, a704b5c, 5932a76 — all verified in git log
