---
phase: 03
reviewers: [claude, opencode]
reviewed_at: 2026-05-06T12:45:22+05:00
plans_reviewed:
  - 03-01-PLAN.md
  - 03-02-PLAN.md
  - 03-03-PLAN.md
  - 03-04-PLAN.md
---

# Cross-AI Plan Review - Phase 03

## Claude Review

Overall risk: MEDIUM.

Claude found the phase decomposition logically sound: preserve product facts, migrate inventory shape, split B6 forms, then run regression verification. It also confirmed that the plans respect the user's KISS/YAGNI constraints and avoid inventing a separate `regimen.yaml` or unused B-vitamin taxonomy.

### HIGH

1. Operator usage doses can be silently dropped between 03-01 and 03-02.
   - Current inventory `dose` values mix label facts and operator usage regimen.
   - `vitamin_d3: 10000 IU` and `electrolyte_caps: 1 g/cap` look like per-cap label facts.
   - `magnesium_glycinate: 200 mg x 2/day (= 400 mg elemental Mg)` is operator usage.
   - 03-01 should explicitly route every existing `dose` string to product component amount, product notes, product `unmatched_concerns`, inventory notes, or intentional discard before 03-02 strips the field.

2. 03-02 Task 2 has a fragile verification gate.
   - If schema and data are migrated before planner loader changes, `planner.py check data/inventory.yaml` can pass vacuously because the legacy loader sees no `supplements`.
   - The plan should either merge schema+data+loader into one atomic task/commit, make the intermediate state fail loudly, or teach the loader the new shape before migrating the data.

3. 03-03 collides with existing Phase 2 B-vitamin test assertions.
   - `tests/test_phase_02.py` still expects `vitamin_b6` inside `B_COMPLEX_SUBSTANCES`.
   - It also asserts `class:b_vitamin`, which Phase 3 explicitly rejects as unused taxonomy.
   - 03-03 must explicitly update Phase 2 tests: replace generic B6 with `b6_pyridoxal_5_phosphate` where appropriate and remove or narrow the taxonomy assertion.

### MEDIUM

1. Existing inventory `notes` need provenance classification.
   - Some notes are product facts, such as label/form/capsule statements.
   - Some notes are shelf/operator state.
   - The plan should route product-fact notes to product cards instead of leaving them in inventory.

2. `traits_override` preservation should be verified explicitly.
   - Current overrides exist for `vitamin_d3`, `coenzyme_b_complex`, `electrolyte_caps`, and `trace_minerals`.
   - The `coenzyme_b_complex` override is load-bearing because meal tolerance is product-level/operator placement, not a substance trait.

3. Generic `vitamin_b6.yaml` disposition is ambiguous.
   - Since `nattokinase` may still reference generic B6 due to unknown form, the plan should state whether the old card remains and how its notes/traits are trimmed.

4. New B6 cards should preserve useful notes.
   - The current generic B6 notes contain context about Coenzyme B-Complex and Lion's Mane.
   - Relevant context should migrate to `b6_pyridoxal_5_phosphate` and `b6_pyridoxine_hcl`.

5. 03-04 should expect the schedule explanations to change.
   - B6 component IDs will change in `schedule.yaml`.
   - The plan should verify slot assignments, score, and quality remain stable unless a deliberate delta is documented.

### LOW

1. 03-01 tests that iterate inventory brands may become vacuous after 03-02 strips brand from inventory.
2. Phase 1 hard-coded stack-count tests need a helper that flattens the new top-level stack shape.
3. Schema should clarify whether empty stack groups are valid.
4. CLI help and refresh printed messages should be tested after shape migration.
5. Phase 3 should include a concrete assertion that no `class:b_vitamin` or `family:vitamin_b6` taxonomy is introduced.

## OpenCode Review

Overall risk: MEDIUM.

OpenCode agreed that the phase is well-scoped and that the main risk is concentrated in the inventory migration. It highlighted the same need for atomicity in 03-02 and the same ambiguity around generic B6 cleanup.

### HIGH

1. 03-02 packs schema, data, loader, and tests into one plan with only three tasks.
   - Schema/data migration and planner loader update are tightly coupled.
   - If they land separately, there is an unavoidable broken or misleading intermediate state.
   - OpenCode recommends merging Tasks 2 and 3 into a single atomic commit.

2. 03-02 Task 1 says tests fail before inventory migration and pass after Tasks 2 and 3, but Tasks 2 and 3 touch different files.
   - The plan should acknowledge the intermediate break and handle it intentionally.

### MEDIUM

1. 03-01 lacks a completeness test for brand migration.
   - A partial copy could pass if tests only spot-check known items.
   - Add a set-completeness assertion against all current non-unknown inventory brands before brand is removed from inventory.

2. `traits_override` preservation needs a test.
   - If any inventory item uses overrides, the migration should prove they survive.

3. 03-03 does not specify exactly what happens to `data/substances/vitamin_b6.yaml`.
   - Delete it only if no references remain.
   - Otherwise keep it intentionally and verify no product references generic B6 except explicitly unresolved cases.

### LOW

1. Add a summary or manual check showing copied brands, amounts, and concerns.
2. Test the shape of `unmatched_concerns`.
3. Ensure `cmd_refresh` handles missing `stacks.inactive`.
4. Make the "no weakened tests" check in 03-04 more mechanical.
5. Consider a determinism check for `planner.py plan`.

## Consensus Summary

Both reviewers agree Phase 03 is directionally correct and should achieve the user-level goal: product facts move to product cards, inventory becomes a shelf/stack map, B6 forms become concrete substances, and no unused taxonomy or separate regimen file is introduced.

Before execution, the plans should be tightened in these areas:

1. Add an explicit migration routing table for every existing inventory `brand`, `dose`, and `notes` value.
2. Make 03-02 schema+data+loader migration atomic or otherwise prevent vacuous validation.
3. Add preservation tests for `traits_override`.
4. Enumerate Phase 2 test updates required by the B6 split and removal of `class:b_vitamin`.
5. State the exact disposition of `data/substances/vitamin_b6.yaml`.
6. Make 03-04 verify stable schedule score/quality/slot membership, with only expected explanation/component-id changes.

Recommended next step: run `$gsd-plan-phase 3 --reviews` and incorporate these review findings before `$gsd-execute-phase 3`.
