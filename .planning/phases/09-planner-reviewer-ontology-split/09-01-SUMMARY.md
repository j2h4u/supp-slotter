---
phase: 09-planner-reviewer-ontology-split
plan: "01"
subsystem: traits-ontology
tags: [traits, namespace, ontology, v2, timing, pathway]
dependency_graph:
  requires: []
  provides:
    - data/traits.yaml with timing: and pathway: namespaces
    - schema/traits.schema.json with separate_from removed
    - planner/io.py REGISTERED_NAMESPACES v2
    - planner/cards/traits.py NAMESPACE_ORDER v2 + readable_traits updated
  affects:
    - plan 09-02: substance schema/loader migration (reads updated REGISTERED_NAMESPACES)
    - plan 09-04: TraitDef.separate_from retirement (must_separate call sites)
tech_stack:
  added: []
  patterns:
    - timing: namespace for scheduling-relevant slugs (energy_like, sleep_disruptive, sleep_support)
    - pathway: namespace for Reviewer-only metabolic membership
key_files:
  created: []
  modified:
    - data/traits.yaml
    - schema/traits.schema.json
    - planner/io.py
    - planner/cards/traits.py
decisions:
  - "effect: namespace removed from REGISTERED_NAMESPACES; the three scheduling slugs now live under timing:"
  - "pathway: namespace registered but Reviewer-only; excluded from readable_traits alongside timing:"
  - "TraitDef.separate_from field retained in load_traits for plan 04 compatibility; check_traits no longer validates it"
  - "dashboard: stays in REGISTERED_NAMESPACES (substance cards carry dashboard: lists referenced by dashboard YAMLs)"
metrics:
  duration_seconds: 204
  completed_date: "2026-05-13"
  tasks_completed: 3
  files_modified: 4
---

# Phase 9 Plan 01: Namespace Foundation (timing: + pathway:) Summary

One-liner: Renamed `effect:` → `timing:` in traits.yaml and the planner namespace registry, added `pathway:` bootstrap with methylation_cycle seed, removed `separate_from` from schema and check_traits validation.

## What Was Built

Foundation step for the Phase 9 Planner/Reviewer ontology split. Establishes the v2 namespace topology without touching any substance cards.

### Final REGISTERED_NAMESPACES

```python
{"intake", "timing", "is", "risk", "activity", "dashboard", "pathway"}
```

`effect` removed; `timing` and `pathway` added.

### Final NAMESPACE_ORDER

```python
("is", "intake", "timing", "risk", "activity", "dashboard", "pathway")
```

### 3 Timing Slugs Relocated

From `effect:` → `timing:` (verbatim, no rule changes):
- `timing:energy_like` — prefer_strong wake, prefer day_meal, avoid_strong sleep
- `timing:sleep_disruptive` — block: true on sleep
- `timing:sleep_support` — prefer_strong sleep

### 1 Bootstrap Pathway Slug Added

- `pathway:methylation_cycle` — label/description/applies_when only; no effects block

### separate_from Status

`TraitDef.separate_from` field is still populated by `load_traits` (line 67 of traits.py) but is no longer validated by `check_traits`. The `must_separate` call sites in `_scheduling.py` still reference it; they will be retired in plan 04. No `separate_from:` keys exist in `data/traits.yaml` (confirmed by grep).

## Task Commits

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Restructure data/traits.yaml | 32bbd8c | data/traits.yaml |
| 2 | Update schema/traits.schema.json | 0e1d608 | schema/traits.schema.json |
| 3 | Update planner/io.py + planner/cards/traits.py | cfc3180 | planner/io.py, planner/cards/traits.py |

## Verification Results

All targeted unit checks pass:
- `data/traits.yaml`: top-level keys `intake, timing, is, risk, activity, pathway`; timing has exactly 3 slugs; pathway has methylation_cycle; no `separate_from` fields
- `schema/traits.schema.json`: `separate_from` property removed; `jsonschema.Draft202012Validator` accepts post-Task-1 traits.yaml
- `planner.io.REGISTERED_NAMESPACES` matches v2 set
- `planner.cards.traits.NAMESPACE_ORDER` matches v2 tuple
- `readable_traits` excludes `timing:*` and `pathway:*`, keeps `intake:*`
- `ruff check` and `pyright` both exit 0 on touched files

`uv run python -m planner check` reports 16 errors for substance cards carrying `effect:<timing-slug>` references — **expected and intended** as the trigger for plan 02.

## Deviations from Plan

None — plan executed exactly as written.

## Known Stubs

None. The `pathway:methylation_cycle` bootstrap entry is intentional and documented in the plan; it is not a stub — it is the seed entry required for schema `minProperties: 1` compliance.

## Threat Flags

No new security-relevant surface introduced. All changes are local file reads/writes; no new network endpoints, auth paths, or trust boundaries.

## Self-Check: PASSED

- `data/traits.yaml` — exists, parses, structure correct
- `schema/traits.schema.json` — exists, no separate_from, validates traits.yaml
- `planner/io.py` — REGISTERED_NAMESPACES updated
- `planner/cards/traits.py` — NAMESPACE_ORDER updated, check_traits loop removed, readable_traits exclusions added
- Commits `32bbd8c`, `0e1d608`, `cfc3180` — all present in git log
