---
phase: 260510-is4
plan: 01
subsystem: tests
tags: [unit-tests, coverage, scheduling, relations]
dependency_graph:
  requires: []
  provides: [food-axis-coverage, support-warning-coverage]
  affects: [tests/test_scheduling_units.py]
tech_stack:
  added: []
  patterns: [inline-fixture, field-by-field-assertion]
key_files:
  created: []
  modified:
    - tests/test_scheduling_units.py
decisions:
  - "Tightened existing block test to also assert score == 0, exposing that blocked slots accumulate no score"
  - "New food-axis tests use explicit near=None to make food-only matching intent clear at the call site"
  - "Warning-direction test asserts each dict field individually, not the whole object, to stay robust to future field additions"
metrics:
  duration: "~5min"
  completed: "2026-05-10T08:34:51Z"
---

# Phase 260510-is4 Plan 01: Close C4 and C5 — Food-Axis and Support-Warning Coverage Summary

Food-axis branch of `compute_slot_score` and warning-emitting direction of `collect_missing_support_relations` are now exercised by dedicated unit tests.

## What Was Built

**C4 — food-axis coverage (Task 1):** Three new SI-04 tests covering `compute_slot_score` food discriminant:
- `test_compute_slot_score_food_axis_match` — `TraitEffectMatch(near=None, food=False)` fires on a `food=False` slot, accumulating `LEVEL_SCORES["prefer_strong"]`
- `test_compute_slot_score_food_axis_mismatch` — same match does not fire on a `food=True` slot; score stays 0
- `test_compute_slot_score_food_axis_block` — block=True on food-axis match sets `blocked=True`

Existing `test_compute_slot_score_block_on_matching_slot` tightened: unpack changed to `score, blocked, _` and `assert score == 0` added.

**C5 — warning-direction coverage (Task 2):** One new SI-08 test:
- `test_collect_missing_support_relations_target_active_source_absent_emits_warning` — target active, source absent → exactly one `missing_support_substance` warning with correct `source_substance`, `source_name`, `target_substance`, `target_name`, and `reason` fields.

## Commits

| Task | Commit | Message |
|------|--------|---------|
| C4 (Task 1) | 3d79d3b | test(260510-is4): C4 — food-axis coverage for compute_slot_score |
| C5 (Task 2) | 0c819a3 | test(260510-is4): C5 — warning-direction coverage for collect_missing_support_relations |

## Deviations from Plan

None — plan executed exactly as written.

## Verification

- `python3 -m pytest tests/test_scheduling_units.py -x -q` → 20 passed
- `pyright planner/ tests/` → 0 errors, 0 warnings

## Self-Check: PASSED

- tests/test_scheduling_units.py exists and contains all new tests
- Commits 3d79d3b and 0c819a3 exist in git log
- No production code modified
