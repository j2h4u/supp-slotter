---
phase: quick-260510-k5m
plan: 01
subsystem: planner
tags: [rename, type-safety, dead-code, observability, docstrings]
dependency_graph:
  requires: []
  provides:
    - RelationSide Literal alias in planner/cards/relations.py
    - strip_root_prefix replacing display_message in planner/io.py
    - make_* test factory names in tests/test_scheduling_units.py
  affects:
    - planner/io.py
    - planner/maintenance.py
    - planner/engine/review.py
    - planner/engine/_scheduling.py
    - planner/cards/relations.py
    - planner/cards/substance.py
    - planner/cards/product.py
    - planner/cards/search.py
    - planner/contracts.py
    - tests/test_scheduling_units.py
tech_stack:
  added: []
  patterns:
    - Literal alias for constrained string parameters
    - Registry loader skip-count observability pattern
key_files:
  created: []
  modified:
    - planner/io.py
    - planner/maintenance.py
    - planner/engine/review.py
    - planner/engine/_scheduling.py
    - planner/cards/relations.py
    - planner/cards/substance.py
    - planner/cards/product.py
    - planner/cards/search.py
    - planner/contracts.py
    - tests/test_scheduling_units.py
decisions:
  - "_endpoint_fields unreachable branch removed: with RelationSide Literal, the else/return None branch became unreachable; removed rather than left as dead defensive code"
  - "_append_missing_relation_warning internal signature also narrowed to RelationSide; loop variable typed via explicit list annotation to satisfy pyright"
metrics:
  duration: ~10min
  completed: 2026-05-10
  tasks_completed: 4
  tasks_total: 4
---

# Phase quick-260510-k5m Plan 01: Recommendations Pass — Naming Micro-Rename Summary

**One-liner:** Four naming renames, RelationSide Literal alias on six functions, dead helper deleted, registry-load skip summaries, eight docstrings, three noise lines removed.

## Tasks Completed

| # | Name | Commit | Files |
|---|------|--------|-------|
| 1 | Naming micro-renames | 0bbd130 | io.py, maintenance.py, engine/review.py, _scheduling.py, test_scheduling_units.py |
| 2 | RelationSide alias + dead code | 79c4a96 | cards/relations.py, cards/substance.py |
| 3 | Registry-load observability | 8f3905e | cards/substance.py, cards/product.py |
| 4 | Docstrings + noise cleanup | e019786 | io.py, cards/search.py, cards/substance.py, contracts.py, maintenance.py, test_scheduling_units.py |

## What Was Done

**Task 1 — Three renames:**
- `display_message` → `strip_root_prefix` (planner/io.py def + 3 internal call sites; import updated in maintenance.py and engine/review.py with 8+2 call sites)
- `notes` → `reasons` local variable in `explain_slot_choice` (_scheduling.py)
- `_slot`/`_trait_def`/`_substance`/`_product` → `make_slot`/`make_trait_def`/`make_substance`/`make_product` in test_scheduling_units.py (4 defs + all call sites); `_NO_SOURCES` sentinel left unchanged

**Task 2 — Type safety + dead code:**
- Added `from typing import Literal` and `RelationSide = Literal["source", "target"]` in relations.py
- Narrowed `side: str` → `side: RelationSide` on all six endpoint functions and `_append_missing_relation_warning`
- Removed the now-unreachable `return None, None` branch from `_endpoint_fields` (exhaustive if/elif over Literal)
- Deleted `substance_is_covered_by_active_name` (zero callers confirmed)

**Task 3 — Observability:**
- Both `load_substance_registry` and `load_product_registry` now track `skipped` count and print `warning: loaded N/total cards; M skipped` to stderr iff `skipped > 0`; happy-path output unchanged

**Task 4 — Docstrings + noise:**
- Added docstrings to: `schema_errors` (io.py), `collect_search_strings`, `search_words` (search.py), `Pillbox.slots` field comment (contracts.py), extended `check_substances` docstring (substance.py), `read_lock_pid`, `clear_stale_lock` (maintenance.py) — 8 surfaces total
- Removed 3 noise lines: inline comment on `test_compute_slot_score_no_matching_effects`, second sentence of `test_collect_missing_support_relations_source_active_target_absent_returns_empty` docstring, trailing comment on `data["id"] = old_id` in maintenance.py

## Deviations from Plan

**1. [Rule 2 - Missing critical functionality] `_append_missing_relation_warning` signature also narrowed**
- Found during: Task 2
- Issue: Pyright reported 4 errors — internal helper `_append_missing_relation_warning` also accepted `side: str`, and the for-loop tuple in `collect_missing_balance_relations` inferred as `str` rather than `RelationSide`
- Fix: Narrowed helper signature to `RelationSide` parameters; typed loop variable via explicit `list[tuple[RelationSide, RelationSide]]` annotation
- Files modified: planner/cards/relations.py
- Commit: 79c4a96

## Known Stubs

None — all changes are renames, removals, and documentation additions. No data flow stubs.

## Threat Flags

None — no new network endpoints, auth paths, file access patterns, or schema changes introduced.

## Self-Check: PASSED

- planner/io.py: def strip_root_prefix present, display_message absent
- planner/cards/relations.py: RelationSide alias present
- planner/cards/substance.py: substance_is_covered_by_active_name absent
- tests/test_scheduling_units.py: make_slot/make_trait_def/make_substance/make_product defs present
- Commits 0bbd130, 79c4a96, 8f3905e, e019786 all in git log
- 99 tests pass; 0 new pyright errors (2 pre-existing in test_maintenance.py, confirmed pre-plan)
