---
phase: quick-260510-iwv
plan: 01
subsystem: planner/engine, planner/cards, planner/maintenance, tests
tags: [rename, docstring, comment, cleanup]
dependency_graph:
  requires: []
  provides: [accurate-bnb-locals, intent-driven-maintenance-names, corrected-check-message, sentinel-contract-docs]
  affects: [planner/engine/plan.py, planner/engine/_scheduling.py, planner/maintenance.py, planner/cards/_common.py, planner/cards/relations.py, planner/cards/warnings.py, planner/engine/check.py, tests/test_phase_02.py]
tech_stack:
  added: []
  patterns: [file-local rename, docstring rewrite]
key_files:
  modified:
    - planner/engine/plan.py
    - planner/engine/_scheduling.py
    - planner/maintenance.py
    - planner/cards/_common.py
    - planner/cards/relations.py
    - planner/cards/warnings.py
    - planner/engine/check.py
    - tests/test_phase_02.py
decisions:
  - connected_components not renamed (imported by substance.py); docstring-only change
  - Task 2 split into two commits as specified (one per rename)
metrics:
  duration: ~12min
  completed: "2026-05-10"
  tasks: 4
  commits: 5
---

# Phase quick-260510-iwv Plan 01: Naming, Docstring, and Message-Fidelity Cleanup Summary

**One-liner:** Renamed 5 misleading BnB/maintenance/test locals, corrected the liar `cmd_check` failure message, and removed 4 zero-rent docstrings/comments across 8 files.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Rename BnB locals in plan.py | cb73609 | planner/engine/plan.py |
| 2A | Rename generated_id → needs_new_id | d7f6049 | planner/maintenance.py |
| 2B | Rename normalize_stack_items → group_items_by_stack | a941d31 | tests/test_phase_02.py |
| 3 | Fix cmd_check message + docstrings | 9cd9d21 | check.py, _common.py, warnings.py |
| 4 | Remove redundant docstrings/comment | 17eacb8 | _scheduling.py, relations.py, warnings.py |

## Renames Performed

### planner/engine/plan.py (all file-local)
- `remaining_max_scores` → `remaining_score_upper_bound` — it is a prefix-sum array used as an upper bound on remaining score in BnB pruning
- `scored_slots_by_item` → `feasible_slots_by_item` — holds slots already filtered for feasibility, not just scored
- `item_ids_in_order` → `item_id_sequence` — "in_order" implies sorted; this is dict-insertion order used as a stable tiebreak

### planner/maintenance.py
- `generated_id` → `needs_new_id` — boolean flag indicating the card still needs an ID assigned; old name was past-tense for a future event

### tests/test_phase_02.py
- `normalize_stack_items` → `group_items_by_stack` — function pivots item_id→stack mapping into stack→[item_ids]; "normalize" implies same-shape in/out

## Docstrings / Comments Removed

| Location | What was removed | Why |
|----------|-----------------|-----|
| `_scheduling.py` `slot_matches` | `"Slot satisfies match if all listed fields equal."` | Restates the 3-line body |
| `_scheduling.py` `compute_slot_score` | `"Returns (score, blocked, reasons)."` | Restates the return type annotation |
| `relations.py` `collect_missing_balance_relations` | `# Balance display: active endpoint → source, missing endpoint → target` | Documents the default kwarg convention already expressed by parameter defaults in `_append_missing_relation_warning` |
| `warnings.py` `_format_warning_entities` | `"Resolve product/substance/source/target IDs to display names."` | Restates the function name |

## Docstrings Improved

| Location | Change |
|----------|--------|
| `_common.py` `connected_components` | Singleton-drop behavior moved to the lead sentence; was buried in second sentence |
| `warnings.py` `_derive_concern_text` | Rewritten to explicitly name the empty-string sentinel contract and `_format_warning_entities` as the populating function |

## cmd_check Message Fix

Old: `"check: skipped (maintenance lock held)"` — false on card-load-error path where `auto_maintenance_needed` returns `None`

New: `"check: skipped (auto-maintenance failed; see errors above)"` — accurate in both failure modes (lock held and card-load-error)

## Deviations from Plan

None — plan executed exactly as written.

## Verification

```
grep -rn "remaining_max_scores|scored_slots_by_item|item_ids_in_order|generated_id|normalize_stack_items" --include="*.py"
# → no matches in working repo

grep -n "maintenance lock held" planner/engine/check.py
# → no matches

grep -n "Balance display:" planner/cards/relations.py
# → no matches

pyright planner/ → 0 errors/warnings
pytest tests/ -x -q → 78 passed
```

## Self-Check: PASSED

- cb73609 exists: confirmed
- d7f6049 exists: confirmed
- a941d31 exists: confirmed
- 9cd9d21 exists: confirmed
- 17eacb8 exists: confirmed
- All 8 target files modified
- 78 tests pass, pyright 0 errors
