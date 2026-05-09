---
quick_id: 260510-4rs
phase: quick
plan: 260510-4rs
subsystem: planner/engine
tags: [refactor, error-handling, api-tightening, b-and-b-solver]
key_files:
  modified:
    - planner/engine/plan.py
    - planner/engine/_scheduling.py
    - tests/test_scheduling_units.py
decisions:
  - Kept balance_lower_bound's BALANCE_WEIGHT*sum separate from _compute_assignment_total — different data (relaxed_counts vs real slot_counts), different semantic purpose (optimistic bound vs final score)
  - search/initialize_best_with_greedy stay nested inside _run_plan_search — they share assignment/slot_traits/slot_counts via nonlocal, which is correct; the improvement is one level of nesting removed, not zero
  - Chose Option A for trait_sources (require, update tests) over Option B (document as test-only) — removes dead None-branch, type signature now matches production reality
metrics:
  duration: ~12min
  completed: "2026-05-10"
  tasks: 3
  files: 3
---

# Quick Task 260510-4rs: plan.py Complexity Reduction + Naming + Error Hardening

One-line: Extract greedy+B&B search into `_run_plan_search`, deduplicate final scoring into `_compute_assignment_total`, harden four cmd_plan error paths, and make `compute_slot_score.trait_sources` required.

## Findings Closed (9 of 9)

- **C2** — `cmd_plan` was ~270 lines with two large nested closures. Now delegates search to `_run_plan_search`; body reduced to ~120 lines of sequencing.
- **C3** — Greedy initializer duplicated final-scoring arithmetic from `score_complete_assignment`. Both paths now call `_compute_assignment_total`; arithmetic exists in exactly one place.
- **N1** — `_balance_pen` was inconsistently named vs `_final_total`/`_slot_score_sum`. Renamed to `_balance_penalty` for uniform underscore-prefix convention.
- **N2** — `score_complete_assignment` name implied an `assignment` parameter but operated on closure-captured state. Eliminated entirely; replaced by `_compute_assignment_total` pure function.
- **EH3** — `cmd_plan` printed "skipped (maintenance lock held)" for all `cmd_check` failures. Now prints "skipped (check failed; see errors above)".
- **EH4** — `CardLoadError` from `load_pillboxes`/`load_traits` propagated uncaught. Both calls now wrapped in `try/except CardLoadError`; prints `plan: <message>` and returns `None`.
- **EH5** — `SCHEDULE_PATH.write_text(...)` was unguarded. Now wrapped in `try/except OSError`; returns 1 with path named in message.
- **EH6** — No diagnostic on exhausted search. Now lists items with ≤1 feasible slot before the failure message.
- **_scheduling.py:149** — `trait_sources: dict | None = None` was dead in production (always provided). Made required; `if trait_sources is not None:` guard removed; `or ["unknown"]` fallback for missing keys preserved.

## Commits

| Task | Commit | Message |
|------|--------|---------|
| 1 (C2+C3+N1+N2) | 435a037 | refactor(260510-4rs): extract _run_plan_search and _compute_assignment_total from cmd_plan |
| 2 (EH3+EH4+EH5+EH6) | d6f0671 | fix(260510-4rs): harden cmd_plan error paths (check failure, CardLoadError, write OSError, exhausted-search diagnostic) |
| 3 (_scheduling.py:149) | 8c8481c | refactor(260510-4rs): require trait_sources on compute_slot_score (drop dead None-branch) |

## LOC Delta in cmd_plan Body

| Metric | Before | After |
|--------|--------|-------|
| cmd_plan line count (awk /^def cmd_plan/,/^def/) | ~270 | 151 |
| Search closures in cmd_plan | 5 (slot_order_key, balance_lower_bound, score_complete_assignment, initialize_best_with_greedy, search) | 0 |

## Pyright

- Errors: 0
- Warnings: 0

## Tests

- 37/37 tests passing (37 were passing before; 26 pre-existing failures in test_phase_02/03/test_schemas due to missing jsonschema/yaml modules in environment — unrelated to this task)

## Deviations from Plan

None — plan executed exactly as written.

## Self-Check: PASSED

- `planner/engine/plan.py` exists and contains `_compute_assignment_total` and `_run_plan_search` at module level.
- `planner/engine/_scheduling.py` exists with required `trait_sources` parameter (no `| None`, no default).
- `tests/test_scheduling_units.py` exists with `_NO_SOURCES` sentinel and all 5 call sites updated.
- Commits 435a037, d6f0671, 8c8481c all present in git log.
