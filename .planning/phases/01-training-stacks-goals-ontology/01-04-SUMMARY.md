---
phase: 01-training-stacks-goals-ontology
plan: 04
subsystem: testing
tags: [smoke-test, schedule, stack-partition, goal-validation]

requires:
  - phase: 01-training-stacks-goals-ontology
    provides: Data migration, goal cards, and planner support from plans 01-03
provides:
  - End-to-end smoke evidence for all Phase 1 success criteria
  - Generated stack-partitioned schedule.yaml
  - Negative-test evidence for bogus goal member refs
affects: [verification, roadmap]

tech-stack:
  added: []
  patterns:
    - Inline smoke assertions against generated YAML
    - Transient corruption negative test with byte restore

key-files:
  created: []
  modified:
    - schedule.yaml

key-decisions:
  - "Kept the negative-test mutation transient and restored vascular_health.yaml byte-for-byte."

patterns-established:
  - "Phase smoke tests assert topology rather than exact greedy assignment where exact placement is not semantically required."
  - "Goal referential integrity is proven by a failing check with a bogus substance ref, then a clean post-revert check."

requirements-completed: [TRAIN-01, TRAIN-02, TRAIN-03, GOAL-01, GOAL-02, GOAL-03]

duration: 2 min
completed: 2026-05-05
---

# Phase 01 Plan 04: Smoke Test Summary

**End-to-end Phase 1 smoke test proving stack-partitioned scheduling and goal-card validation**

## Performance

- **Duration:** 2 min
- **Started:** 2026-05-05T16:41:44Z
- **Completed:** 2026-05-05T16:42:52Z
- **Tasks:** 2
- **Files modified:** 1

## Accomplishments

- Ran `uv run planner.py check`: passed with existing unmatched-concern INFO lines and final `All checks passed.`
- Ran `uv run planner.py plan`: produced `schedule.yaml`.
- Verified training, daily, and inactive topology assertions.
- Verified both goal cards' member shapes.
- Verified a bogus `members[0].substance` ref fails check with the expected referential-integrity error.
- Restored `vascular_health.yaml` and verified post-revert `check` exits 0.

## Task Commits

1. **Task 1: End-to-end smoke test** - `1b1f354` (test)
2. **Task 2: Negative referential validator test** - no committed files; transient mutation restored

## Files Created/Modified

- `schedule.yaml` - Regenerated schedule from the migrated stack-aware planner.

## Smoke Log

- PASS inventory stack histogram: `daily=11`, `training=4`, `inactive=8`.
- PASS training topology: `creatine`, `electrolyte_caps`, `l_carnitine_l_tartrate`, `l_citrulline_malate`.
- PASS daily topology: `acetyl_l_carnitine`, `astaxanthin`, `coenzyme_b_complex`, `lions_mane_b6_complex`, `magnesium_glycinate`, `nattokinase`, `potassium_citrate`, `tadalafil`, `trace_minerals`, `vitamin_b5`, `vitamin_d3`.
- PASS inactive substances absent.
- PASS goal card member assertions.
- PASS final line: `SMOKE TEST: all assertions passed`.

## Negative Test

- Corrupted first vascular-health member to `bogus_substance_xyz`.
- `uv run planner.py check` exited non-zero with:
  `members[0].substance 'bogus_substance_xyz' has no matching product card`.
- Restored original `vascular_health.yaml` bytes.
- Post-revert `uv run planner.py check` exited 0.

## Schedule Evidence

- `total_score`: 48.5
- `slot_score_total`: 66
- `prefer_with_bonus`: 3
- `balance_penalty`: 20.5
- Slot loads:
  - `morning_empty`: 2
  - `morning_food`: 4
  - `day_food`: 3
  - `evening_empty`: 2
  - `pre_workout`: 2
  - `post_workout`: 2

## Success Criteria Mapping

- SC1: `uv run planner.py check` passed.
- SC2: training substances appear only in `pre_workout`/`post_workout`.
- SC3: daily substances appear only in the four daily slots.
- SC4: inactive substances are absent from `schedule.yaml`.
- SC5: inventory has no `active` field and valid stack values.
- SC6: `vascular_health.yaml` has four taking members with expected refs.
- SC7: `mitochondrial_health.yaml` has ALCAR taking plus two name-only candidates.
- SC8: bogus goal-card ref triggers the referential validator.
- SC9: goal schema is registered and used by `planner.py check`.
- SC10: `l_carnitine_l_tartrate` is in the training stack.

## Decisions Made

None - followed plan as specified.

## Deviations from Plan

None - plan executed exactly as written.

**Total deviations:** 0 auto-fixed.
**Impact on plan:** No impact.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

All Phase 1 plans have summaries and the smoke test proves the 10 roadmap success criteria. Ready for phase verification / security gate routing.

---
*Phase: 01-training-stacks-goals-ontology*
*Completed: 2026-05-05*
