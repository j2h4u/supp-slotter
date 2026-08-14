---
phase: 09-planner-reviewer-ontology-split
plan: "04"
subsystem: scheduler
tags: [relations, competes, class-level, separate_from-retirement, planner-reviewer-split]
dependency_graph:
  requires: [09-03]
  provides: [class-level-competes, mineral-fat_soluble-rule, must_separate-retired]
  affects: [planner/engine/plan.py, planner/engine/_scheduling.py, planner/contracts.py, data/relations.yaml]
tech_stack:
  added: []
  patterns: [class-level-competes-via-is_-slugs, symmetric-competes-check, frozen-dataclass-extension]
key_files:
  created: []
  modified:
    - schema/relations.schema.json
    - planner/contracts.py
    - planner/cards/relations.py
    - planner/cards/traits.py
    - planner/engine/_scheduling.py
    - planner/engine/plan.py
    - planner/engine/audit.py
    - data/relations.yaml
    - tests/test_scheduling_units.py
    - tests/test_primary_component_scoring.py
decisions:
  - "TraitDef.separate_from is fully removed; must_separate and _declares_against are deleted — class-level competes is the sole block-pair mechanism going forward."
  - "internal_conflicts in effective_stack_item_traits stays as [] (return-shape compat with build_explanation) rather than changing the 5-tuple return type and all callers."
  - "trait_defs kept in _slot_is_blocked signature (not used by new path) to avoid touching two call sites; pyright is silent on the unused parameter."
metrics:
  duration: "~25min"
  completed: "2026-05-13"
  tasks: 3
  files_modified: 10
---

# Phase 09 Plan 04: Class-Level Competes + separate_from Retirement Summary

Class-level competes is operational end-to-end: schema, loader, scheduler, live rule, and behavior-pinned tests. The `separate_from` / `must_separate` mechanism is fully retired from the codebase.

## What Was Built

### Relation dataclass new fields

Two fields added to `planner/contracts.py Relation`, positioned between `target_name` and `action`:

```python
source_class: str | None = None
target_class: str | None = None
```

`load_global_relations` in `planner/cards/relations.py` now reads these from YAML and populates the fields. The existing substance-level fields (`source_substance`, `target_substance`, `source_name`, `target_name`) are unchanged.

### _slot_is_blocked's new class-level branch

`_slot_is_blocked` in `planner/engine/plan.py` now has two block paths:

1. **Class-level competes (new, first):** Pre-filters `global_relations` to entries where `r.type == "competes" AND r.source_class AND r.target_class`. For each existing item in the slot, builds `item_classes` and `existing_classes` from `substance.is_` slugs (the single documented Planner ↛ knowledge isolation exception, commented inline). Checks symmetric match: returns `True` if any `(source_class, target_class)` pair overlaps both class sets in either direction.

2. **Substance-level competes (unchanged, second):** `component_sets_have_relation(..., "competes", ...)` — identical to before.

### The seeded mineral ↔ fat_soluble rule

`data/relations.yaml` competes block now contains:

```yaml
- source_class: mineral
  target_class: fat_soluble
  reason: "Minerals and fat-soluble vitamins have competing intake requirements (general food vs fat-containing meal). Co-placement is suboptimal even when no specific substance pair clashes."
```

No `severity`, `action`, or substance/name fields — class-level entries carry only the class pair and reason.

### separate_from fully retired

The following dead code was removed:

- `TraitDef.separate_from: tuple[str, ...]` field — deleted from `planner/contracts.py`
- `must_separate` function — deleted from `planner/engine/_scheduling.py`
- `_declares_against` helper — deleted from `planner/engine/_scheduling.py`
- `separate_from=tuple(trait.get("separate_from") or ())` kwarg — removed from `load_traits` in `planner/cards/traits.py`
- `separate_from` loop in `audit.py` — removed (dead code after TraitDef field removal)
- `must_separate` import — removed from `planner/engine/plan.py`
- `internal_conflicts` loop — replaced with `internal_conflicts: list[dict[str, Any]] = []` + comment in `effective_stack_item_traits`

Three `must_separate` tests in `test_scheduling_units.py` were retired (replaced by a section comment). The `make_trait_def` factory in both test files had `separate_from` param removed.

### Behavior-pinned tests (3 new)

- `test_class_level_competes_blocks_slot` — mineral + fat_soluble → blocked
- `test_class_level_competes_does_not_block_unrelated_classes` — mineral + amino → not blocked
- `test_class_level_competes_symmetric` — fat_soluble-as-item and mineral-as-item both blocked

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] audit.py and test files referenced retired TraitDef.separate_from**

- **Found during:** Task 2 — `just check` pyright output
- **Issue:** `planner/engine/audit.py` iterated `trait.separate_from`; both test `make_trait_def` factories passed `separate_from=` kwarg; `test_scheduling_units.py` imported `must_separate` from the deleted function
- **Fix:** Removed the audit loop (replaced with comment), dropped `separate_from` param from both `make_trait_def` factories, removed `must_separate` import, retired the three `must_separate` tests with a comment block
- **Files modified:** `planner/engine/audit.py`, `tests/test_scheduling_units.py`, `tests/test_primary_component_scoring.py`
- **Commit:** 71c5e27

## Known Stubs

None.

## Threat Flags

None beyond what the plan's threat model covers (T-09-04-01: schema slug pattern enforcement; T-09-04-02: accepted Planner ↛ knowledge isolation exception documented inline).

## Self-Check: PASSED

- `schema/relations.schema.json` — modified, source_class/target_class branch present
- `planner/contracts.py` — Relation.source_class/target_class added, TraitDef.separate_from removed
- `planner/cards/relations.py` — source_class/target_class populated from YAML
- `planner/engine/_scheduling.py` — must_separate/\_declares_against deleted, internal_conflicts = []
- `planner/engine/plan.py` — class-level competes block present, must_separate import removed
- `data/relations.yaml` — mineral↔fat_soluble entry confirmed present
- `tests/test_scheduling_units.py` — 3 new tests added and passing
- `just check` — 93/93 tests pass, ruff clean, pyright 0 errors
- `uv run python -m planner check` — All checks passed
- Commits: 5c68c7c (Task 1), 71c5e27 (Task 2), 75a36ff (Task 3)
