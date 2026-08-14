---
phase: "08"
plan: "08-01"
subsystem: ontology
tags: [schema-migration, traits, dashboards, data-migration]
dependency_graph:
  requires: []
  provides: [grouped-trait-schema, from_traits-dashboard-schema, migrated-substance-data, migrated-dashboard-data]
  affects: [planner/contracts.py, planner/cards/substance.py, planner/cards/dashboards.py, planner/engine/_scheduling.py, planner/engine/doctor.py, planner/engine/review.py, planner/engine/check.py, planner/maintenance.py]
tech_stack:
  added: []
  patterns: [grouped-namespace-fields, from_traits-resolution, union-or-semantics]
key_files:
  created: []
  modified:
    - schema/substance.schema.json
    - schema/dashboard.schema.json
    - data/traits.yaml
    - planner/io.py
    - planner/contracts.py
    - planner/cards/substance.py
    - planner/cards/dashboards.py
    - planner/engine/_scheduling.py
    - planner/engine/doctor.py
    - planner/engine/review.py
    - planner/engine/check.py
    - planner/maintenance.py
    - data/substances/*.yaml (200 files)
    - data/dashboards/*.yaml (12 modified, 1 deleted)
    - tests/test_phase_01.py
    - tests/test_phase_02.py
    - tests/test_phase_03.py
    - tests/test_maintenance.py
    - tests/test_primary_component_scoring.py
    - tests/test_scheduling_units.py
    - tests/test_schemas.py
    - schedule.yaml
decisions:
  - "from_traits resolution is union (logical OR): substance member if ANY (ns, slug) pair matches"
  - "dashboard: namespace excluded from scheduling traits (curation marker only)"
  - "6 substances had dual intake traits (fat_meal_required + food_required) — kept fat_meal_required only (more specific)"
  - "maintenance.py _substance_from_mapping also needed traits= removal (auto-fixed Rule 1)"
  - "ruamel.yaml added then removed — used only for migration scripts, not committed to production deps"
metrics:
  duration: "~2 hours"
  completed: "2026-05-11"
  tasks_completed: 15
  files_changed: 235
---

# Plan 08-01 Summary

**Status:** complete
**Commit:** 5eb7f4b

## What was built

Replaced the flat `traits: [ns:slug, ...]` substance schema with 6 per-namespace fields (`is:`, `intake:`, `effect:`, `risk:`, `activity:`, `dashboard:`), and replaced dashboard `taking: []` substance-ID lists with `from_traits: {ns: [slugs]}` tag-based membership. All 200 substance YAML files were migrated in a single combined pass from a pre-migration snapshot; all 12 surviving dashboard YAMLs were converted to `from_traits: {dashboard: [slug]}`; `vasodilation_no_pathway.yaml` was deleted (strict 5/5 subset of `vascular_health`). The `from_traits` resolution semantics are union/OR: a substance is a member of a dashboard if ANY (namespace, slug) pair in `from_traits` matches ANY of its per-namespace fields.

## Verification

- uv run python -m planner check: exit 0
- uv run pytest: exit 0 (112/112 tests passed)
- uv run python -m planner (plan): exit 0
- uv run python -m planner review-substance: exit 0 (no AttributeError)
- uv run python -m planner doctor: exit 0

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] maintenance.py _substance_from_mapping used traits=() keyword**
- **Found during:** Task 08-01-11 (planner check run)
- **Issue:** `_substance_from_mapping` in `planner/maintenance.py` constructed `Substance(..., traits=tuple(...))` which broke after Substance lost the `traits` field
- **Fix:** Removed `traits=tuple(data.get("traits") or ())` — no traits field needed, Substance now derives all from per-namespace fields
- **Files modified:** planner/maintenance.py
- **Commit:** 5eb7f4b (included in atomic commit)

**2. [Rule 1 - Bug] 6 substance files had dual intake slugs violating maxItems:1**
- **Found during:** Task 08-01-11 (planner check run after migration)
- **Issue:** Astaxanthin, krill oil, and 4 vitamin K/D files had `traits: [intake:fat_meal_required, intake:food_required]` — both migrated to `intake:`, violating the new `maxItems: 1` constraint
- **Fix:** Kept `fat_meal_required` only (more specific — fat-containing meal implied, food_required is redundant)
- **Files modified:** 6 substance YAML files
- **Commit:** 5eb7f4b (included in atomic commit)

**3. [Rule 1 - Bug] traits.yaml dashboard entries missing required applies_when field**
- **Found during:** Task 08-01-11 (planner check run)
- **Issue:** All 13 new `dashboard:` namespace entries lacked `applies_when` which is required by the traits schema
- **Fix:** Added `applies_when` to all 13 dashboard trait entries
- **Files modified:** data/traits.yaml
- **Commit:** 5eb7f4b (included in atomic commit)

**4. [Rule 1 - Bug] test_phase_02.py, test_phase_03.py, test_maintenance.py, test_primary_component_scoring.py referenced old traits API**
- **Found during:** Task 08-01-12 (pytest run)
- **Issue:** Multiple test files used `Substance(..., traits=())`, `substance["traits"]`, fixture substances with `traits: []`, and `bleeding_load["taking"]`
- **Fix:** Updated all call sites to grouped namespace API; fixture substance creation now produces grouped fields via `group_trait_ids()` helper
- **Files modified:** tests/test_phase_02.py, tests/test_phase_03.py, tests/test_maintenance.py, tests/test_primary_component_scoring.py
- **Commit:** 5eb7f4b (included in atomic commit)

**5. [Observation] schedule.yaml benefits count is 10, not 13**
- bleeding_load, cholinergic_load, and serotonergic_load are risk-only dashboards (no benefit field). They appear in schedule.yaml risks (3 entries). Total benefits + risks = 13, matching the plan's semantic intent.

## Known Stubs

None — all dashboard memberships are fully wired via `dashboard:` tags on substance cards and `from_traits: {dashboard: [slug]}` on dashboard cards.

## Threat Flags

None — no new network endpoints, auth paths, or file access patterns introduced. Schema changes are internal data model only.

## Self-Check: PASSED

- schema/substance.schema.json: FOUND
- schema/dashboard.schema.json: FOUND
- data/traits.yaml: FOUND (13 dashboard: entries, 8 is: entries)
- planner/contracts.py: FOUND (Substance with is_, Dashboard with from_traits)
- Commit 5eb7f4b: FOUND
- All 5 verification commands: exit 0
- 112/112 tests passing
- 13 total dashboard entries in schedule.yaml (10 benefits + 3 risks)
- vasodilation_no_pathway.yaml: deleted
