---
phase: 4-code-quality-quick-wins
plan: uo9
subsystem: planner/tests
tags: [refactor, cleanup, test-quality]
dependency_graph:
  requires: []
  provides: [QW-01, QW-02, QW-03, QW-04, QW-05, QW-06, QW-07]
  affects: [planner/cards/stacks.py, planner/engine/check.py, planner/cards/substance.py, planner/cards/product.py, planner/cards/relations.py, tests/test_phase_02.py, tests/test_phase_03.py]
tech_stack:
  added: []
  patterns: []
key_files:
  created: []
  modified:
    - tests/test_phase_02.py
    - tests/test_phase_03.py
    - planner/cards/stacks.py
    - planner/engine/check.py
    - planner/cards/substance.py
    - planner/cards/product.py
    - planner/cards/relations.py
decisions: []
metrics:
  duration: ~10min
  completed: "2026-05-09"
---

# Phase 4 Plan uo9: Code Quality Quick Wins Summary

Pure deletions and one-liner substitutions applying 7 cross-AI code review findings: 11 dead fixture_id() calls removed, 1 liar test deleted, 1 silently-skippable assertion made unconditional, unused `trait_ids` param dropped from validate_stacks, two stderr prefixes corrected from "plan:" to "warning:", WARN: stripped from informational advisory, and 3 verbatim noise docstrings deleted.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Remove dead test code (QW-01, QW-02, QW-03) | 6716a83 | tests/test_phase_02.py, tests/test_phase_03.py |
| 2 | Fix source code issues (QW-04, QW-05, QW-06, QW-07) | 6fa0ccf | planner/cards/stacks.py, planner/engine/check.py, planner/cards/substance.py, planner/cards/product.py, planner/cards/relations.py |

## What Changed

### QW-01 — Dead fixture_id() calls (test_phase_02.py)
Removed 11 bare `fixture_id()` calls across 4 test functions whose return values were discarded. These were left-over stubs that silently did nothing.

### QW-02 — Liar test deleted (test_phase_03.py)
`test_no_regimen_file_exists` asserted `regimen.yaml` doesn't exist — a property that has always been true by design (the model deliberately uses no regimen file). Test was vacuously passing, not testing correctness.

### QW-03 — Unconditional Glycine ordering assertion (test_phase_03.py)
Removed `if "Glycine" in result.stdout:` guard from the ordering assertion in `test_find_searches_multiple_fuzzy_words`. Glycine exists as a live substance card and is always present in search output; the guard made the assertion silently skippable.

### QW-04 — Remove unused trait_ids param from validate_stacks
Dropped `trait_ids: set[str]` (with its `# noqa: ARG001` suppression) from `validate_stacks` in `planner/cards/stacks.py`. Updated the single call site in `planner/engine/check.py` from `validate_stacks(STACKS_PATH, product_ids, trait_ids)` to `validate_stacks(STACKS_PATH, product_ids)`.

### QW-05 — Correct stderr prefix in loaders
Changed `"plan: skipping substance card: ..."` and `"plan: skipping product card: ..."` to `"warning: ..."` — the `plan:` prefix was a copy-paste artifact that misidentified the message source.

### QW-06 — Remove WARN: from informational advisory
`check_stack_alignment` printed `WARN: {STACKS_PATH}: product ...` for products not yet in any stack. This is informational (not an error or warning), so the `WARN:` prefix was misleading.

### QW-07 — Delete verbatim noise docstrings
Removed three docstrings that exactly restated the function name in prose:
- `load_substance_registry`: `"""Load all substance cards into an id-keyed registry."""`
- `load_product_registry`: `"""Load all product cards into an id-keyed registry."""`
- `load_global_relations`: `"""Load all substance-to-substance relations into typed Relation objects."""`

## Verification

All verification checks from the plan passed:
- `uv run pytest` — 48 passed, 0 failures
- No bare `fixture_id(` lines remain in test_phase_02.py
- `test_no_regimen_file_exists` absent from test_phase_03.py
- No `if "Glycine" in` guard in test_phase_03.py
- No `trait_ids` references in planner/cards/stacks.py
- No `"plan:` prefix in substance.py or product.py
- No `"WARN:` in stacks.py
- No noise docstrings in substance.py, product.py, or relations.py

## Deviations from Plan

None — plan executed exactly as written.

## Known Stubs

None.

## Threat Flags

None — all changes are pure deletions or string substitutions with no new network, auth, or schema surface.

## Self-Check: PASSED

- Task 1 commit `6716a83` exists: confirmed
- Task 2 commit `6fa0ccf` exists: confirmed
- All 7 modified files exist on disk: confirmed
- Test suite exits 0: confirmed (48 passed)
