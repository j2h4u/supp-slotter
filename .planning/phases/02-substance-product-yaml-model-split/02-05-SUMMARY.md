---
phase: 02-substance-product-yaml-model-split
plan: 05
subsystem: validation
tags: [yaml, jsonschema, planner, regression-tests]
requires:
  - phase: 02-substance-product-yaml-model-split
    provides: Split Substance/Product/InventoryItem validation and regression coverage
provides:
  - Target substance checks resolve prefer_with refs against the full substance registry
  - Malformed inventory supplement entries report deterministic schema errors
  - Regression coverage for Phase 2 verification gaps
affects: [planner.py, tests, phase-02-verification]
tech-stack:
  added: []
  patterns:
    - schema-first validation before guarded deep cross-reference checks
    - target-mode validators may use full registries for reference resolution
key-files:
  created:
    - .planning/phases/02-substance-product-yaml-model-split/02-05-SUMMARY.md
  modified:
    - planner.py
    - tests/test_phase_02.py
key-decisions:
  - "Target-mode substance validation checks the target card locally but resolves prefer_with refs against the full data/substances registry."
  - "Inventory alignment and override checks skip non-mapping supplement entries so schema validation owns malformed-entry errors."
patterns-established:
  - "Reference registries can be passed into target validators without weakening duplicate-id checks for the target set."
  - "Deep inventory validators must guard entry shape before calling mapping methods."
requirements-completed: ["PHASE-02-GAP-VALIDATION"]
duration: 15 min
completed: 2026-05-05
---

# Phase 02 Plan 05: Validation Gap Closure Summary

**Split-model validator gap closure for target substance prefer_with refs and malformed inventory entries**

## Performance

- **Duration:** 15 min
- **Started:** 2026-05-05T20:22:00Z
- **Completed:** 2026-05-05T20:37:18Z
- **Tasks:** 3
- **Files modified:** 2

## Accomplishments

- Added focused regressions for `creatine.yaml` target checks and malformed inventory supplement entries.
- Updated `check_substances` so target-mode checks can validate `prefer_with` against the full substance registry.
- Guarded inventory alignment and override checks against non-mapping supplement entries.
- Verified the full planner check and complete pytest suite pass.

## Task Commits

Each task was committed atomically where practical:

1. **Task 1: Add validation-gap regressions** - `2517c23` (test)
2. **Task 2: Validate target substance prefer_with against the full registry** - `e8fdcb3` (fix)
3. **Task 3: Guard inventory deep checks after schema errors** - `e8fdcb3` (fix)

**Plan metadata:** pending this docs commit

## Files Created/Modified

- `planner.py` - Adds optional `prefer_with_registry` support and non-mapping inventory guards.
- `tests/test_phase_02.py` - Adds regressions for target substance validation and malformed inventory entries.

## Decisions Made

- Target substance checks still validate only the requested card's local schema and duplicate scope, while resolving outbound `prefer_with` references through the full substance-id registry loaded by `cmd_check`.
- Malformed inventory supplement entries are not caught with broad exception handling; deeper checks skip non-mappings and let `schema_errors` produce the deterministic validation message.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

- The initial regression run reproduced both planned failures: target-mode `creatine.yaml` check rejected a valid `prefer_with` target, and malformed inventory crashed with `AttributeError`.
- Task 2 and Task 3 code changes were committed together in `e8fdcb3` because both fixes were adjacent validator changes in `planner.py`.

## Verification

- `uv run pytest tests/test_phase_02.py -k 'creatine or malformed_inventory' -q` - passed, 2 tests.
- `uv run planner.py check data/substances/creatine.yaml` - passed with `All checks passed.`
- `uv run pytest tests/test_phase_02.py -k creatine -q` - passed, 1 test.
- `uv run pytest tests/test_phase_02.py -k malformed_inventory -q` - passed, 1 test.
- `uv run planner.py check` - passed with `All checks passed.`
- `uv run pytest` - passed, 17 tests.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

Phase 2 verification gaps are closed. The split Substance/Product/InventoryItem validator now passes target-mode and malformed-input checks and is ready for re-verification.

## Self-Check: PASSED

All must-haves from `02-05-PLAN.md` are satisfied: code paths exist, regressions cover both gaps, and full verification passes.

---
*Phase: 02-substance-product-yaml-model-split*
*Completed: 2026-05-05*
