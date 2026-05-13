---
phase: 09-planner-reviewer-ontology-split
plan: "02"
subsystem: substance-schema-loader
tags: [schema, ontology, v2, transitional, dual-format, planner-reviewer-split]
dependency_graph:
  requires:
    - plan 09-01: data/traits.yaml with timing: and pathway: namespaces
  provides:
    - schema/substance.schema.json: transitional oneOf schema (v1_flat | v2_nested)
    - planner/contracts.py: Substance dataclass v2 with timing and pathway fields
    - planner/cards/substance.py: dual-format load_substance + check_substances v2
    - planner/engine/_scheduling.py: scheduling traits from schedule.* only
    - planner/engine/audit.py: _collect_cleanup_sections iterates 8 v2 fields
    - planner/cards/dashboards.py: substance_carries with defensive hasattr guard
    - planner/engine/review.py: ns_to_substance_slugs covers all 8 v2 namespaces
  affects:
    - plan 09-03: data migration of v1 substance cards to v2 shape
    - plan 09-04: retire TraitDef.separate_from and must_separate call sites
    - plan 09-05: tighten schema to v2-only, remove v1 loader fallback
tech_stack:
  added: []
  patterns:
    - transitional oneOf JSON Schema with v1_flat and v2_nested $defs branches
    - dual-format loader discriminated by presence of 'schedule' key
    - schedule.* (Planner) / knowledge.* (Reviewer) actor split in Substance dataclass
key_files:
  created: []
  modified:
    - schema/substance.schema.json
    - planner/contracts.py
    - planner/cards/substance.py
    - planner/engine/_scheduling.py
    - planner/engine/audit.py
    - planner/cards/dashboards.py
    - planner/engine/review.py
    - tests/test_schemas.py
    - tests/test_phase_02.py
decisions:
  - "v2_nested branch requires 'schedule' as mandatory field to resolve oneOf ambiguity on bare cards ({id, name} only)"
  - "effect: and risk: and pathway: slugs under knowledge: are Reviewer-only — check_substances skips trait_ids lookup for these namespaces"
  - "separate_from / must_separate left intact for plan 04 retirement — scheduler loop is a quiet no-op post-plan-01 (no separate_from entries in traits.yaml)"
  - "risk: warning emission intentionally suspended until plan 05 routes it to cmd_review — T-09-02-02 accepted at MEDIUM severity"
metrics:
  duration_seconds: 2400
  completed_date: "2026-05-13"
  tasks_completed: 4
  files_modified: 9
---

# Phase 9 Plan 02: Transitional Substance Schema + Planner/Reviewer Code Split Summary

One-liner: Rewrote substance schema as transitional oneOf (v1_flat | v2_nested), split Substance dataclass into schedule:/knowledge: field groups, made load_substance a dual-format reader, and narrowed scheduler trait aggregation to schedule.* fields only.

## What Was Built

Completes the Planner/Reviewer separation at the code boundary. The scheduling actor (`effective_stack_item_traits`) now reads only `intake:`, `timing:`, `activity:` from the Substance. The review actor (`cmd_review_substance`, `_collect_cleanup_sections`) iterates all 8 v2 namespace fields. v1 flat cards continue to load via the transitional schema's v1_flat oneOf branch until plan 03 migrates them.

### Transitional Schema Strategy

The schema uses a top-level `oneOf` against two `$defs` branches:

- `v1_flat`: flat namespace keys (is/intake/effect/risk/activity/dashboard/prefer_with) at top level; `additionalProperties: false`; NO schedule/knowledge keys.
- `v2_nested`: requires `schedule` key (mandatory discriminator); nested `schedule:` (intake/timing/activity/prefer_with) and `knowledge:` (is/effect/risk/dashboard/pathway) objects; `additionalProperties: false`; NO flat namespace keys at top level.

The mandatory `schedule` on `v2_nested` resolves the ambiguity: bare cards (`{id, name}` only) match `v1_flat` exclusively. Cards with `schedule:` key match `v2_nested` exclusively. Cards with both `schedule:` and flat namespace keys match neither branch — rejected.

This is the per-09-REVIEWS.md HIGH finding 1 fix: the v1 loader fallback is reachable because `schema_errors` now accepts v1 cards via `v1_flat`, not just v2 cards.

### Substance Dataclass v2 Field Order

```python
@dataclass(frozen=True, slots=True)
class Substance:
    id: str
    name: str
    # --- schedule: section (Planner reads these) ---
    intake: tuple[str, ...] = ()
    timing: tuple[str, ...] = ()   # NEW
    activity: tuple[str, ...] = ()
    prefer_with: tuple[str, ...] = ()
    # --- knowledge: section (Reviewer reads these) ---
    is_: tuple[str, ...] = ()
    effect: tuple[str, ...] = ()
    risk: tuple[str, ...] = ()
    dashboard: tuple[str, ...] = ()
    pathway: tuple[str, ...] = ()  # NEW
    # --- common ---
    form: str | None = None
    aliases: tuple[str, ...] = ()
    notes: str | None = None
    concerns: tuple[Concern, ...] = ()
```

### Dual-Format Loader Behavior

`load_substance` discriminates on `"schedule" in data`:
- **v2 path**: reads `sched = data["schedule"]` and `know = data["knowledge"]`; constructs all 9 Substance namespace fields from the two nested objects.
- **v1 path**: reads flat top-level keys; sets `timing=()` and `pathway=()` explicitly (v1 cards never carried these).
- **Ambiguous-card guard**: if both `schedule:` and any flat namespace key are present, raises `CardLoadError` with "ambiguous format" message (belt-and-suspenders; schema oneOf already rejects this case first).

`check_substances` mirrors the same dual-branch logic:
- v2 branch: validates `intake/timing/activity` from `schedule:` against `trait_ids`; validates `is/dashboard` from `knowledge:` against trait_ids/file-existence; skips `effect/risk/pathway` (Reviewer-only, operator-curated).
- v1 branch: unchanged (flat namespace iteration preserved for unmigrated cards; removed in plan 05).

### Scheduler Trait Aggregation (Task 3a)

`effective_stack_item_traits` scheduling_traits set:
```python
scheduling_traits = (
    {f"intake:{s}" for s in substance.intake}
    | {f"timing:{s}" for s in substance.timing}
    | {f"activity:{s}" for s in substance.activity}
)
```
`is:`, `risk:`, `effect:`, `dashboard:`, `pathway:` slugs are NOT in this set.

### Audit Cleanup Iterator (Task 3a)

`_collect_cleanup_sections` iterates exactly 8 (field_name, ns) pairs in this order:
`intake/intake`, `timing/timing`, `activity/activity`, `is_/is`, `effect/effect`, `risk/risk`, `dashboard/dashboard`, `pathway/pathway`.

### Dashboards Resolver and Review Display (Task 3b)

`substance_carries`: added `if not hasattr(substance, field_name): return False` guard before `getattr` — unknown namespace keys return False instead of AttributeError. Docstring updated to list all supported namespace keys.

`_review_substance_inner` ns_to_substance_slugs builder now lists all 8 (field, ns) pairs in v2 field order. The downstream `for namespace in all_namespaces:` loop picks up `timing:` and `pathway:` automatically via NAMESPACE_ORDER.

## Task Commits

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Transitional substance schema + Substance dataclass v2 | ce6c29a | schema/substance.schema.json, planner/contracts.py |
| 2 | Dual-format load_substance + check_substances v2 | f9b2345 | planner/cards/substance.py |
| 3a | Scheduler trait aggregator + audit cleanup iterator | fedf50d | planner/engine/_scheduling.py, planner/engine/audit.py |
| 3b | Dashboards resolver + review-substance display | 03475d0 | planner/cards/dashboards.py, planner/engine/review.py |
| fix | Schema v2_nested requires schedule; stale test fixes | b513058 | schema/substance.schema.json, tests/test_schemas.py, tests/test_phase_02.py |

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] v2_nested schema branch matched bare cards — oneOf ambiguity**
- **Found during:** Task 2 verification (test suite run after Task 3b)
- **Issue:** A substance card with only `id` and `name` (no optional namespace fields) trivially satisfied both `v1_flat` and `v2_nested` since neither required anything beyond `id` and `name`. This caused jsonschema's `oneOf` to reject the card with "valid under each of" (matched both).
- **Fix:** Added `"required": ["schedule"]` to the `v2_nested` branch. Cards without `schedule:` key are now exclusively `v1_flat`; cards with `schedule:` key are exclusively `v2_nested`.
- **Files modified:** `schema/substance.schema.json`
- **Commit:** b513058

**2. [Rule 1 - Bug] Stale test: test_dashboard_excluded_from_scheduling_traits asserted is: in scheduling set**
- **Found during:** Task 3b test run
- **Issue:** The test was written before plan 09-02 to show `is:` WAS in the scheduling set (as the positive comparator to `dashboard:` being excluded). Plan 09-02 explicitly moves `is:` to the knowledge/Reviewer group — it must NOT be in the scheduling set.
- **Fix:** Renamed test to `test_knowledge_and_dashboard_excluded_from_scheduling_traits`; updated assertions to verify both `is:` and `dashboard:` are excluded; added `intake:` and `timing:` as the positive scheduling-included cases.
- **Files modified:** `tests/test_schemas.py`
- **Commit:** b513058

**3. [Rule 1 - Bug] test_phase_02.py intra/inter-product separate_from tests used effect: namespace**
- **Found during:** Task 3b test run
- **Issue:** Two separate_from conflict tests used `effect:alpha`/`effect:beta` traits. After plan 09-01, `effect:` was removed from REGISTERED_NAMESPACES; after plan 09-02, `effect:*` no longer enters the scheduling trait set. The fixture traits were writing flat `effect: [alpha]` substance YAML — which is valid v1 schema — but the scheduler never saw them.
- **Fix:** Updated fixture substance traits and trait defs from `effect:alpha`/`effect:beta` to `intake:alpha`/`intake:beta`. `intake:` is the correct v1-schema-compatible scheduling namespace for `separate_from` fixture tests.
- **Files modified:** `tests/test_phase_02.py`
- **Commit:** b513058

## Intentional Deferrals

- **`separate_from` / `must_separate`**: Left intact as plan 04 retirement scope. Post-plan-01, no `separate_from:` entries exist in `data/traits.yaml`, so the `internal_conflicts` loop in `effective_stack_item_traits` is a quiet no-op.
- **`risk:` warning emission**: Suspended between plan 02 and plan 05 (T-09-02-02, accepted MEDIUM severity). The risk-warning path via `trait_def.warning` is silently dropped until plan 05 routes it to `cmd_review`.
- **Schema tightening to v2-only**: Deferred to plan 05 so the v1 loader fallback can be removed in the same commit (atomic cleanup).

## Verification Results

- `schema_errors` accepts v1 flat cards, v2 nested cards; rejects mixed cards (oneOf) and bare-minimum cards route exclusively to v1_flat.
- `load_substance` v2/v1/ambiguous: all three cases verified.
- `effective_stack_item_traits`: `timing:sleep_support` and `intake:food_preferred` in effective set; `risk:manual_review`, `effect:vasodilator`, `is:mineral` excluded.
- `_collect_cleanup_sections` field order: confirmed via source inspection.
- `substance_carries`: handles `pathway:`, `is:`, and unknown namespace (no AttributeError).
- `_review_substance_inner` ns_to_substance_slugs: all 8 namespaces covered.
- `uv run python -m planner check`: exits 0 against live v1 substance cards.
- `just check` (ruff + pyright + planner check + pytest): 86/86 tests pass.

## Known Stubs

None.

## Threat Flags

No new security-relevant surface introduced. All changes are local file reads/writes within the existing data directory structure.

## Self-Check: PASSED

- `schema/substance.schema.json` — exists; oneOf with v1_flat + v2_nested; v2_nested requires schedule
- `planner/contracts.py` — Substance has timing and pathway fields
- `planner/cards/substance.py` — dual-format loader with ambiguous guard
- `planner/engine/_scheduling.py` — scheduling_traits uses intake/timing/activity only
- `planner/engine/audit.py` — 8-pair field iteration in v2 order
- `planner/cards/dashboards.py` — hasattr guard present
- `planner/engine/review.py` — 8 namespaces in ns_to_substance_slugs
- Commits `ce6c29a`, `f9b2345`, `fedf50d`, `03475d0`, `b513058` — all present in git log
