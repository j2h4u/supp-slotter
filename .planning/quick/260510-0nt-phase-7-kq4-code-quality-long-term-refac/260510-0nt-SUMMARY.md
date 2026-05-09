---
phase: 260510-0nt
plan: "01"
subsystem: planner
tags: [refactor, code-quality, decomposition, docstrings]
dependency_graph:
  requires: []
  provides: [LR-01, LR-02, LR-03, LR-04, LR-05]
  affects:
    - planner/engine/plan.py
    - planner/maintenance.py
    - planner/cards/warnings.py
    - planner/engine/_scheduling.py
    - planner/cards/_common.py
    - planner/cards/schedule.py
    - planner/cards/search.py
    - planner/cards/relations.py
    - planner/contracts.py
tech_stack:
  added: []
  patterns:
    - module-level helper extraction (cmd_plan decomposition)
    - generic normalizer with Callable parameter (_normalize_card_dir)
    - dict-dispatch replacing if/elif chain (warning_action)
    - helper extraction from monolithic function (humanize_warning)
key_files:
  created: []
  modified:
    - planner/engine/plan.py
    - planner/maintenance.py
    - planner/cards/warnings.py
    - planner/engine/_scheduling.py
    - planner/cards/_common.py
    - planner/cards/schedule.py
    - planner/cards/search.py
    - planner/cards/relations.py
    - planner/contracts.py
decisions:
  - _load_plan_inputs returns 8-tuple (includes pillboxes) rather than 7-tuple per spec,
    because _build_schedule_output needs the pillboxes object for build_empty_schedule_pillboxes
  - _normalize_card_dir uses Callable[[Any], str] parameter so lambdas at call sites
    adapt raw dicts to the typed canonical_*_filename functions without modifying callers
metrics:
  duration: ~40min
  completed: "2026-05-09T19:48:03Z"
  tasks: 3
  files_modified: 9
---

# Phase 260510-0nt Plan 01: Phase 7 KQ4 Code Quality Long-term Refactoring Summary

**One-liner:** cmd_plan decomposed into 4 module-level helpers, _normalize_card_dir generic extracted, warning_action converted to dict dispatch, humanize_warning split into two helpers, 8 API-contract docstrings added.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| A | LR-01/LR-02 structural decomposition | ada5aa3 | plan.py, maintenance.py |
| B | LR-03/LR-04 warning dispatch refactor | fd72792 | warnings.py |
| C | LR-05 docstrings | eddd11d | _scheduling.py, _common.py, schedule.py, search.py, relations.py, contracts.py |

## What Was Built

**Task A — cmd_plan decomposition (LR-01):**
- `_load_plan_inputs(data_dir: Path)` — loads pillboxes, traits, stacks, substances, products, relations, dashboard_files; returns 8-tuple including pillboxes
- `_build_active_index(...)` — builds active/item_products/active_components/trait_sources/conflict indexes; validates workout-stack activity trait constraint
- `_resolve_prefer_pairs(...)` — builds substance_to_active_items index, prefer_pairs set, and ambiguous_prefer_with_warnings list
- `_build_schedule_output(...)` — assembles the full schedule dict from a solved B&B assignment
- `cmd_plan` body: ~170 lines (call chain + candidate scoring loop + 5 B&B closures)
- All 5 B&B closures (`seed_with_greedy_assignment`, `search`, `evaluate_complete`, `assignment_tie_key`, `balance_lower_bound`) remain inside `cmd_plan` as they capture many nonlocals

**Task A — _normalize_card_dir extraction (LR-02):**
- `_normalize_card_dir(cards_dir, canonical_fn, id_prefix)` — generic normalizer; handles id generation, file renames, duplicate/collision detection
- `normalize_substances` body reduced to 5 lines (delegate + rewrite refs + return)
- Products block in `run_auto_maintenance_unlocked` replaced with `_normalize_card_dir` call
- Bug fix applied: product write path now has `try/except OSError` matching the substance path (was missing in the original)
- `from collections.abc import Callable` added to maintenance.py imports

**Task B — warning_action lookup tables (LR-03):**
- `_ACTION_BY_TYPE`, `_ACTION_BY_TRAIT`, `_ACTION_BY_RELATION` dicts defined at module level
- `warning_action` body: 4 lines (3 dict lookups + fallback return)

**Task B — humanize_warning decomposition (LR-04):**
- `_format_warning_entities(warning, products, substances)` — resolves all entity IDs to display names; sets risk/concern for risk_cluster_load
- `_derive_concern_text(warning_type, trait, relation, warning)` — derives concern label; returns "" for risk_cluster_load so caller's `if concern:` guard prevents overwriting entity-set concern
- `humanize_warning` delegates to both helpers; `if warning_type == "risk_cluster_load": pass` no-op eliminated

**Task C — 8 docstrings (LR-05):**
- `effective_stack_item_traits`: 3-tuple return documented with field types and semantics
- `connected_components`: singleton-drop behaviour documented
- `build_action_points`: 8-item cap and manual_review skip documented
- `build_placement_notes`: tradeoff-only filter documented
- `search_score`: AND-gate semantics documented
- `combined_search_score`: asymmetric 0.75 penalty documented
- `components_have_global_relation`: always-symmetric both-orderings check documented
- `Slot`: corrected to attribute pillbox/stack join to `load_pillboxes` (not `flatten_pillbox_slots`)

## Verification

- `uv run pytest`: 63 passed, 0 failures (all three tasks)
- `uv run pyright`: 6 pre-existing errors in `tests/test_scheduling_units.py` (unused `reasons`/`score` variables in test unpacks) — present before this task, not introduced

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] _load_plan_inputs returns 8-tuple instead of 7-tuple**
- **Found during:** Task A implementation
- **Issue:** `_build_schedule_output` needs the `pillboxes` object (for `build_empty_schedule_pillboxes`). The plan spec said 7-tuple but didn't account for pillboxes being needed downstream. Returning only the derived `slots` would require a duplicate `load_pillboxes` call in `cmd_plan`.
- **Fix:** Added `pillboxes` as 8th return value; updated `cmd_plan` unpack accordingly. Eliminates the duplicate load that was in the original draft.
- **Files modified:** planner/engine/plan.py

## Known Stubs

None — all code paths are fully wired. No placeholder data.

## Threat Flags

None — no new network endpoints, auth paths, file access patterns, or schema changes introduced. Pure refactor with no behaviour changes.

## Self-Check: PASSED

- All 9 modified files exist on disk
- All 3 task commits confirmed in git log (ada5aa3, fd72792, eddd11d)
- All key functions/dicts confirmed present: _load_plan_inputs, _build_active_index,
  _resolve_prefer_pairs, _build_schedule_output, _normalize_card_dir, _ACTION_BY_TYPE,
  _format_warning_entities, _derive_concern_text
