---
phase: 260510-lwy
plan: "01"
subsystem: planner/engine
tags: [scheduler, scoring, primary-component, nattokinase]
dependency_graph:
  requires: []
  provides: [primary-component-scoring]
  affects: [planner/engine/plan.py, planner/engine/_scheduling.py, planner/io.py, planner/contracts.py, schedule.yaml]
tech_stack:
  added: []
  patterns: [primary-secondary trait split, weighted secondary scoring, 5-tuple return contract]
key_files:
  created:
    - tests/test_primary_component_scoring.py
  modified:
    - planner/contracts.py
    - schema/product.schema.json
    - planner/cards/product.py
    - planner/io.py
    - data/products/minami_healthy_foods__nattokinase_13000fu__prd_83dffd67bf.yaml
    - planner/engine/_scheduling.py
    - planner/engine/plan.py
    - tests/test_phase_03.py
    - schedule.yaml
decisions:
  - "SECONDARY_TRAIT_WEIGHT = 0.25 derived from LEVEL_SCORES algebraically (not hardcoded)"
  - "primary_traits discarded (_primary_traits) in _build_active_index; secondary_only_traits stored in ActiveIndex for scoring loop"
  - "explain_slot_choice and review_tags continue to use full effective union (display accuracy)"
  - "must_separate and _slot_is_blocked use full effective union (physical inseparability)"
metrics:
  duration: "~10 minutes"
  completed: "2026-05-10"
  tasks_completed: 2
  files_changed: 9
---

# Phase 260510-lwy Plan 01: Primary Component Scoring Summary

Primary-component flag added to `ProductComponent`; scheduler now splits trait scoring between primary and secondary components, fixing Nattokinase 13000FU landing in a fat-meal slot due to EPA's `intake:fat_meal_required` outranking nattokinase's `intake:empty_preferred`.

## What Was Built

### Task 1: Contracts, schema, loader, constant, YAML

- `planner/contracts.py`: `ProductComponent` gains `primary: bool = True` as the last field (backwards-compatible; all existing call sites unaffected).
- `schema/product.schema.json`: `primary: boolean` added as optional property under `components.items.properties` (`additionalProperties: false` was already in place).
- `planner/cards/product.py`: loader passes `primary=bool(c.get("primary", True))` explicitly to `ProductComponent`.
- `planner/io.py`: `SECONDARY_TRAIT_WEIGHT = 0.25` added immediately after `LEVEL_SCORES` with the full algebraic derivation block comment as specified.
- `data/products/minami_healthy_foods__nattokinase_13000fu__prd_83dffd67bf.yaml`: nattokinase (`sub_877c24aad4`) marked `primary: true`; all 8 other components marked `primary: false`.

### Task 2: Scheduler wiring

- `planner/engine/_scheduling.py`: `effective_stack_item_traits` extended from 3-tuple to 5-tuple `(effective, primary_traits, secondary_only_traits, trait_sources, internal_conflicts)`. Iterates `product.components` directly (not just substance IDs) to access `component.primary`. Removed now-unused `product_component_substances` import.
- `planner/engine/plan.py`:
  - `ActiveIndex` gains `secondary_traits_by_item: dict[str, set[str]]` adjacent to `item_traits`.
  - `_build_active_index` unpacks the 5-tuple; stores `secondary_only_traits` in `secondary_traits_by_item`. `primary_traits` is discarded (`_primary_traits`) since it is recomputed as `item_traits[sid] - secondary_traits` in the scoring loop.
  - Feasibility scoring loop: primary traits score at full weight (with blocking); secondary-only traits scored with a second `compute_slot_score` call, result scaled by `SECONDARY_TRAIT_WEIGHT`, added to base score (`int(round(...))`). Blocking from the secondary pass is ignored.
  - Zero-primary fallback: if `primary_traits` is empty, `score_traits = traits` (full effective set), preserving unchanged behaviour.
- `tests/test_primary_component_scoring.py`: 8 new tests covering 5-tuple split, shared-trait-is-primary invariant, all-secondary fallback, SECONDARY_TRAIT_WEIGHT value/formula, primary-wins integration scenario, flat-union regression guard, and all-secondary scheduling path.
- `tests/test_phase_03.py`: schedule snapshot updated to reflect Nattokinase's correct new placement.

## Nattokinase 13000FU Placement

**Slot:** `morning_empty` (Daily pillbox / Morning / empty stomach)

**why_here (from schedule.yaml):**
- Prefers empty stomach: fits this slot.
- Requires fat-containing meal: blocked incompatible slots. *(tradeoff note)*
- Requires food: blocked incompatible slots. *(tradeoff note)*

**review_tags:** `['Prefers empty stomach', 'Requires fat-containing meal', 'Requires food']`

The tradeoff notes appear because `explain_slot_choice` uses the full effective trait union for display (correct — it shows the complete picture). The primary trait `intake:empty_preferred` is the first and dominant driver confirming nattokinase is the scheduling anchor.

## SECONDARY_TRAIT_WEIGHT Derivation

```
SECONDARY_TRAIT_WEIGHT = (prefer - avoid) / (4 * prefer_strong)
                       = (2 - (-2)) / (4 * 4)
                       = 4 / 16
                       = 0.25
```

Confirmed post-import: `from planner.io import SECONDARY_TRAIT_WEIGHT; SECONDARY_TRAIT_WEIGHT == 0.25` → True.

## Schedule Placement Shifts

Products that changed slot as a result of the primary-scoring change:

| Product | Old Slot | New Slot | Reason |
|---------|----------|----------|--------|
| Minami Healthy Foods - Nattokinase 13000FU | `day_food` | `morning_empty` | Primary intent: nattokinase (empty_preferred) now dominates over EPA (fat_meal_required) |
| BioGrace - Vitamin B5 (pantothenic acid) | `morning_empty` | `morning_food` | Displaced by Nattokinase; balance reflow |
| NOW Foods - Potassium Citrate 99 mg | `morning_food` | `day_food` | Balance reflow after B5 moved in |

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Removed unused import `product_component_substances` from `_scheduling.py`**
- Found during: Task 2 (pyright reported `reportUnusedImport`)
- Issue: After refactoring `effective_stack_item_traits` to iterate `product.components` directly, the `product_component_substances` import became unreferenced.
- Fix: Removed the import line.
- Files modified: `planner/engine/_scheduling.py`
- Commit: `98d2acc`

**2. [Rule 1 - Bug] Replaced `primary_traits` with `_primary_traits` in `_build_active_index` unpack**
- Found during: Task 2 (pyright reported `reportUnusedVariable`)
- Issue: The 5-tuple unpack bound `primary_traits` but it was never consumed at that site (recomputed in the scoring loop as `traits - secondary_traits`).
- Fix: Renamed to `_primary_traits` to explicitly discard.
- Files modified: `planner/engine/plan.py`
- Commit: `98d2acc`

**3. [Rule 1 - Bug] Updated test_phase_03.py schedule snapshot**
- Found during: Task 2 (pytest regression test failure)
- Issue: `test_schedule_baseline_remains_stable` snapshot captured old `day_food` placement for Nattokinase; new correct placement is `morning_empty`.
- Fix: Updated `EXPECTED_SCHEDULE_SLOTS` and the `day_food` substances assertion.
- Files modified: `tests/test_phase_03.py`
- Commit: `98d2acc`

## Deferred Items

- Products with zero primary components (`primary: false` on all components) are silently accepted. A future `planner check` lint could flag these as a smell. Documented in the `effective_stack_item_traits` docstring.

## Self-Check: PASSED

All key files confirmed present; both task commits verified in git log.
