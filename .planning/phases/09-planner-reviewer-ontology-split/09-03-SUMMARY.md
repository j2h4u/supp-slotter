---
phase: 09-planner-reviewer-ontology-split
plan: "03"
subsystem: substance-data-migration
tags: [migration, substance-cards, v2, schema, tests, ontology]
dependency_graph:
  requires:
    - plan 09-02: transitional oneOf schema (v1_flat | v2_nested), dual-format load_substance
  provides:
    - data/substances/*.yaml (198 files): all cards in v2 nested schedule:/knowledge: form
    - scripts/migrate_substance_cards.py: idempotent v1→v2 rewriter (kept one commit per plan)
    - schema/templates/substance.yaml: v2 shape template with SCHEDULING/KNOWLEDGE sections
  affects:
    - plan 09-04: separate_from retirement (data is now all v2; no loader path change needed)
    - plan 09-05: schema tightening to v2-only + v1 loader fallback removal (can now proceed)
tech_stack:
  added: []
  patterns:
    - idempotent batch YAML rewriter with dry-run and mixed-card rejection
    - timing-slug split: TIMING_SLUGS set gates effect→schedule.timing vs knowledge.effect routing
    - Wave-0 transitional tests: accept v1 flat AND v2 nested; reject mixed; pin scheduler exclusion
key_files:
  created:
    - scripts/migrate_substance_cards.py
  modified:
    - data/substances/*.yaml (198 files)
    - schema/templates/substance.yaml
    - tests/test_schemas.py
    - tests/test_scheduling_units.py
decisions:
  - "Migration script raises ValueError on mixed nested+flat cards (partial migrations surfaced, not silently skipped) — per 09-REVIEWS.md MEDIUM-3"
  - "Dashboard YAML from_traits: keys NOT rewritten — substance_carries maps 'is' namespace key to Substance.is_ field via existing rule"
  - "schema remains TRANSITIONAL after plan 03 — v2-only tightening + v1 loader fallback removal happen together in plan 05 per 09-REVIEWS.md SHOULD-fix 2"
  - "Flat-form schema rejection tests deferred to plan 05 alongside schema tightening"
metrics:
  duration_seconds: 2577
  completed_date: "2026-05-13"
  tasks_completed: 3
  files_modified: 202
---

# Phase 9 Plan 03: Substance Card v1→v2 Data Migration Summary

One-liner: Migrated all 198 substance cards from flat v1 namespace form to nested v2 schedule:/knowledge: shape, confirmed planner check and all 13 dashboards pass, updated the substance template, and added Wave-0 tests pinning the transitional schema contract and scheduler Reviewer-isolation rule.

## What Was Built

### Task 1: Migration Script + Data Migration

`scripts/migrate_substance_cards.py` rewrites flat v1 substance cards to v2 nested form in one pass. Key properties:

- **Idempotent**: a second run reports `done: 0/198 cards updated`.
- **Mixed-card rejection** (per 09-REVIEWS.md MEDIUM-3): if a card has both `schedule:` and any flat namespace key (`is`, `intake`, `effect`, `risk`, `activity`, `dashboard`, `prefer_with`), raises `ValueError` naming the card and the offending flat keys. Partial migrations are surfaced, not silently skipped.
- **Timing split**: effect slugs in `TIMING_SLUGS = {"energy_like", "sleep_disruptive", "sleep_support"}` route to `schedule.timing`; all others route to `knowledge.effect`. In practice, all 198 cards used only timing slugs under `effect:` — `knowledge.effect` is empty across the entire corpus.
- **Defensive residual-key check**: after migration, raises `ValueError` if any v1 namespace key or legacy `traits` key remains in the result dict (catches unforeseen card shapes).
- **--dry-run flag**: previews `would migrate:` output without writing.

Migration result: 198/198 cards updated. `uv run python -m planner check` exits 0 against migrated data.

### Task 2: Substance Template + Dashboard Verification

`schema/templates/substance.yaml` rewritten to describe the v2 shape:

- Two new sections replace the flat "SCHEDULING TRAITS" block: `# SCHEDULING — read by Planner` and `# KNOWLEDGE — read by Reviewer`.
- Explanatory note added: "Putting a slug under knowledge:effect or knowledge:risk does NOT affect slot assignment — it only surfaces in `planner review`."
- All references to `traits:` and `separate_from` removed.
- Commented example blocks show all sub-keys with inline constraint notes.

Dashboard YAML `from_traits:` keys were **not rewritten**. The existing `substance_carries` rule maps the `is` namespace key string to `Substance.is_` via `field_name = "is_" if namespace == "is" else namespace` — unchanged. All 13 dashboards verified to resolve to non-empty member sets against the migrated v2 registry.

### Task 3: Wave-0 Tests (TDD)

**`tests/test_schemas.py`** additions/renames:

| Test | Purpose |
|------|---------|
| `test_substance_schema_accepts_nested_form` | v2 card with `schedule:` and `knowledge:` passes schema_errors |
| `test_substance_schema_accepts_flat_form_during_transition` | v1 flat card still passes (transitional schema); deleted in plan 05 |
| `test_substance_schema_rejects_unknown_key_inside_schedule` | `additionalProperties: false` on v2_nested schedule object |
| `test_substance_schema_rejects_unknown_key_inside_knowledge` | `additionalProperties: false` on v2_nested knowledge object |
| `test_substance_schema_rejects_mixed_form` | mixed card matches neither oneOf branch → non-empty errors |
| `test_check_rejects_ambiguous_dual_format` | `load_substance` raises `CardLoadError` on mixed card |

**`tests/test_scheduling_units.py`** additions/changes:

| Item | Purpose |
|------|---------|
| `make_substance` factory expanded | adds `timing`, `activity`, `is_`, `effect`, `risk`, `pathway` kwargs |
| `test_scheduling_traits_exclude_risk_and_knowledge_effect` | asserts `risk:manual_review`, `effect:vasodilator`, `is:mineral` excluded; `intake:food_preferred`, `timing:sleep_support` included |
| `test_make_substance_factory_accepts_timing` | regression guard for factory `timing` kwarg |

`just check` (ruff + pyright + planner check + 93 pytest tests): green.

## Deviations from Plan

None — plan executed exactly as written.

## Intentional Deferrals

- **Schema tightening to v2-only**: deferred to plan 05 so the v1 loader fallback is removed in the same commit (atomic cleanup) — per 09-REVIEWS.md SHOULD-fix 2.
- **Flat-form rejection tests**: deferred to plan 05 alongside schema tightening. The transitional schema in plan 02 still accepts flat form — a rejection test would fail against it.
- **Migration script deletion**: script is kept for one commit per plan spec; deletion happens in plan 05's cleanup task.

## Known Stubs

None.

## Threat Flags

No new security-relevant surface introduced. All changes are local file reads/writes within the existing data directory structure. T-09-03-01 (mixed-card ValueError) and T-09-03-04 (dashboard membership smoke check) both mitigated as planned.

## Self-Check: PASSED

- `scripts/migrate_substance_cards.py` — exists; idempotent; raises ValueError on mixed cards
- `data/substances/*.yaml` (198 files) — all in v2 form; 0 files with flat namespace keys
- `schema/templates/substance.yaml` — has `schedule:` and `knowledge:` sections; no `traits:` or `separate_from`
- All 13 dashboards — resolve to non-empty member sets against migrated v2 registry
- `tests/test_schemas.py` — 14 tests; new tests present; `just check` green
- `tests/test_scheduling_units.py` — 28 tests; `make_substance` has `timing` kwarg; new tests present
- Commits `f09155e` (Task 1), `ff80913` (Task 2), `80dd8ca` (Task 3) — all present in git log
