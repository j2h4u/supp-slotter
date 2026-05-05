---
phase: 02-substance-product-yaml-model-split
plan: 02
subsystem: validation
tags: [yaml, json-schema, substances, products, inventory, goals, pytest]

requires:
  - phase: 02-substance-product-yaml-model-split
    provides: direct Substance/Product/InventoryItem YAML shape from plan 02-01
provides:
  - split substance and product formula registries in planner.py
  - product component, inventory product, and goal substance referential checks
  - product-backed refresh entries with isolated tmp_path regression coverage
affects: [scheduler, validation, refresh, tests]

tech-stack:
  added: []
  patterns:
    - substances are the universal trait source
    - products are concrete formulas whose components aggregate into one inventory item
    - refresh tests copy repository data into tmp_path before mutation

key-files:
  created:
    - tests/test_phase_02.py
  modified:
    - planner.py
    - tests/test_phase_01.py

key-decisions:
  - "Kept no legacy product-as-substance reader; all universal traits now come from data/substances."
  - "Inventory product refs are fatal when missing; product formulas without inventory refs remain non-fatal refresh candidates."
  - "Plan scheduling now aggregates component substance traits onto the inventory item instead of splitting component assignments."

patterns-established:
  - "cmd_check target mode validates substances, products, inventory, goals, slots, and traits through explicit path branches."
  - "cmd_refresh accepts an optional data root for isolated tests while the CLI keeps repo-root behavior."

requirements-completed: []

duration: 7min
completed: 2026-05-05
---

# Phase 02 Plan 02: Planner Validation Split Model Summary

**Split-model planner validation with substance registries, product formula component checks, inventory product refs, goal substance refs, and isolated refresh regression coverage.**

## Performance

- **Duration:** 7 min
- **Started:** 2026-05-05T18:58:23Z
- **Completed:** 2026-05-05T19:05:07Z
- **Tasks:** 4
- **Files modified:** 3

## Accomplishments

- Added `SUBSTANCES_DIR`, `load_substance`, `check_substances`, `check_product_formulas`, and the `mechanism` trait namespace.
- Reworked `cmd_check` to validate substances, product formulas, inventory product refs, inventory trait overrides, and goal member substance refs in full-scan and target-path modes.
- Updated `cmd_plan` to schedule inventory items as inseparable product-backed units with traits aggregated from component substance cards.
- Updated `cmd_refresh` to append missing product formulas as `{product: <id>, stack: inactive}` and covered it with a `tmp_path` fixture that cannot mutate repository data.

## Task Commits

The implementation was committed as one cohesive commit because the loader, validator, scheduler, refresh, and test updates depend on the same split-model registry behavior.

1. **Tasks 1-4: Split-model loaders, validators, refresh, and tests** - `2d691b0` (feat)

## Files Created/Modified

- `planner.py` - split registry loaders, validation flow, target checks, component-aware scheduling, and refresh shape.
- `tests/test_phase_01.py` - aligned legacy Phase 1 assertions with the split model.
- `tests/test_phase_02.py` - isolated refresh regression using copied data under `tmp_path`.

## Decisions Made

- Product formulas are not compatibility-read as substance cards.
- Missing inventory `product` refs are errors; product formulas without inventory refs are non-fatal refresh candidates.
- Component substance conflicts aggregate onto one inventory item; no split assignments are introduced in this plan.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Updated stale Phase 1 regression assertions**
- **Found during:** Task 4 verification
- **Issue:** The existing Phase 1 tests still asserted old slot `activity` fields, product-level `traits`, and goal errors mentioning product cards.
- **Fix:** Updated the tests to assert `near` slot fields, substance-level activity traits, and goal errors against substance cards.
- **Files modified:** `tests/test_phase_01.py`
- **Verification:** `uv run pytest` passes.
- **Committed in:** `2d691b0`

---

**Total deviations:** 1 auto-fixed (Rule 1 bug).
**Impact on plan:** No scope expansion in product behavior; the fix keeps the existing regression suite meaningful after the split model.

## Issues Encountered

- `uv run pytest` does not inherit `planner.py` PEP 723 script dependencies when importing `planner` as a module, so the refresh test uses a temp copy of `planner.py` and runs it through `uv run planner.py refresh`.
- A `uv run planner.py plan` smoke generated `schedule.yaml` during verification; it was restored and not committed because the plan did not require schedule regeneration.

## Verification

- PASS `uv run planner.py check`
- PASS negative product component ref check: temporary `bogus_substance_xyz` caused failure mentioning `unknown substance` and `data/substances/bogus_substance_xyz.yaml`.
- PASS negative goal member ref check: temporary `bogus_substance_xyz` caused failure mentioning `has no matching substance card`.
- PASS single-file checks:
  - `uv run planner.py check data/substances/nattokinase.yaml`
  - `uv run planner.py check data/products/nattokinase.yaml`
  - `uv run planner.py check data/inventory.yaml`
  - `uv run planner.py check data/goals/vascular_health.yaml`
- PASS refresh help mentions appending missing product formulas as `{product: <id>, stack: inactive}`.
- PASS `uv run pytest tests/test_phase_02.py -k refresh`
- PASS `uv run pytest`

## Known Stubs

None.

## Threat Flags

None - this plan extends local YAML validation only and implements the planned trust-boundary mitigations for product, inventory, and goal refs.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

Plan 02-03 can build on product-backed scheduling and explanation output. The validator now rejects missing product component substances, missing inventory product refs, and missing goal substance refs before scheduling.

## Self-Check: PASSED

- Found files: `planner.py`, `tests/test_phase_01.py`, `tests/test_phase_02.py`.
- Found implementation commit: `2d691b0`.
- Stub scan found no placeholder/TODO patterns in modified files.
- Summary file created at `.planning/phases/02-substance-product-yaml-model-split/02-02-SUMMARY.md`.

---
*Phase: 02-substance-product-yaml-model-split*
*Completed: 2026-05-05*
