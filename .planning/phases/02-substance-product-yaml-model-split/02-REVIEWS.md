---
phase: 2
reviewers: [opencode]
reviewed_at: 2026-05-05T23:06:55+05:00
plans_reviewed:
  - 02-01-PLAN.md
  - 02-02-PLAN.md
  - 02-03-PLAN.md
  - 02-04-PLAN.md
---

# Cross-AI Plan Review - Phase 2

## OpenCode Review

# Cross-AI Plan Review: Phase 2 - Substance/Product YAML Model Split

## Plan 02-01: Data/schema migration

### Summary

A well-scoped data-only migration plan that creates schemas and YAML files for the split model. The task breakdown is logical and acceptance criteria are precise grep-based checks. The main risk is that the plan touches 23 existing substance cards, several of which are genuine multicomponent products that need careful decomposition, and there are edge cases in that decomposition that the plan does not fully address.

### Strengths

- Acceptance criteria are concrete and machine-verifiable.
- The `near + food` slot model is minimal and directly maps to the current `time + food + activity` fields.
- Schemas are authored first, before data, which lets schema validation catch data errors.
- The nattokinase product is correctly identified as the canonical multicomponent example and given explicit target YAML.
- Clean separation of concerns: this plan produces data only, and expects `planner.py` to break until later plans fix it.

### Concerns

- **MEDIUM: The plan misses the existing multicomponent products.** The codebase already has `lions_mane_b6_complex`, `dihydroquercetin_complex`, and `coenzyme_b_complex`. Task 2 focuses on nattokinase but does not give explicit migration instructions for these three. Each has top-level `traits` that need to migrate to component substances, and autonomous execution may make inconsistent decisions about which traits belong on which component.
- **MEDIUM: Inventory key to product ID identity problem.** Current inventory keys match product card filenames. After the split, inventory must reference `product: <product_id>`, but some inventory keys may conceptually reference substances that do not have matching product cards. The plan implies every current inventory key gets a product formula card, but should state that explicitly.
- **LOW: `activity:*` trait migration needs explicit mapping.** Current activity traits match on `activity`; after slot fields move to `near`, `activity:pre_workout`, `activity:post_workout`, and `activity:any_workout` need explicit new effects.
- **LOW: `prefer_with` location after the split is ambiguous.** Task 1 allows `prefer_with` on substances, but does not define whether refs are substance, product, or inventory refs.

### Suggestions

- Add explicit guidance for migrating `lions_mane_b6_complex`, `dihydroquercetin_complex`, and `coenzyme_b_complex`, including where each existing trait should land.
- Clarify that every current inventory key must have a corresponding product formula card; single-substance items get one-component product formulas.
- Show explicit `activity:*` to `near` migration, for example `activity:pre_workout` to `near: workout_before` and `activity:any_workout` to both workout slots.
- Specify where `prefer_with` lives in the new model and what entity type it references.

## Plan 02-02: Planner validation

### Summary

A solid plan to update `planner.py` validation for the split model. The task breakdown follows the natural flow of loading, schema checking, and reference validation. The main concern is that some acceptance criteria are fragile source-text checks rather than behavior.

### Strengths

- The two-pass validation, substances first and product formulas against substance ids second, mirrors the dependency graph correctly.
- Error message formats are specified explicitly, which aids testability.
- The refresh update is well scoped.
- Negative verification steps for bogus product component refs and bogus goal refs are good regression checks.

### Concerns

- **HIGH: Task 4 acceptance criteria are fragile and may be unreachable in isolation.** `grep -q '"product": new_id' planner.py` and `grep -q 'product: <id>' planner.py` require exact implementation text. Equivalent correct code using another variable name or doc wording could fail the plan despite matching the behavior.
- **MEDIUM: No explicit handling for `cmd_check` single-file mode.** Current `cmd_check` accepts an optional target path. After the split, single-file checking needs to distinguish substance files from product files, or the mode should be explicitly removed/deferred.
- **MEDIUM: Missing inventory entries semantics are unclear.** Current alignment treats missing inventory entries as errors with a refresh instruction. The plan says to report product formulas with no inventory entry as refresh candidates, but does not say whether that should be error or warning.
- **LOW: The plan does not mention updating `REGISTERED_NAMESPACES`.** The `mechanism` namespace is introduced in Phase 2 but `planner.py` currently hardcodes valid namespaces.

### Suggestions

- Replace fragile grep criteria with behavioral checks, or broaden the source checks to accept equivalent implementations.
- Address `cmd_check(target)` directly.
- Clarify whether product formulas without inventory entries make `check` exit non-zero.
- Explicitly add `mechanism` to `REGISTERED_NAMESPACES`.

## Plan 02-03: Scheduler/explainability

### Summary

This plan updates scheduling to use inventory items as atomic units while aggregating component substance traits. The trait aggregation logic is the core change and is described well. The main risk is around `separate_from` behavior after aggregation.

### Strengths

- `effective_inventory_traits` with trait-to-substance source mapping is clean and enables component-aware explanations.
- `intra_product_trait_conflict` is a pragmatic way to warn about conflicting components without splitting a physical product.
- Task 4 explicitly handles `prefer_with` ambiguity and allows removing the bonus if it becomes unclear.
- The plan preserves the greedy plus first-improvement search algorithm and only changes the scheduling unit.

### Concerns

- **HIGH: `separate_from` semantics can break with trait aggregation.** A multicomponent product has the union of all component traits. If two component traits inside the same product conflict, normal `must_separate` logic can treat the item as conflicting with itself or can produce incorrect blocking when slot occupants are re-evaluated. The plan requires an intra-product warning but does not spell out how to keep that self-conflict out of the normal slot-conflict loop.
- **MEDIUM: Aggregated trait sets widen conflict matching.** `slot_traits[slot_name]` currently contains one set per scheduled substance. After aggregation, each set may include several substances, increasing the chance of `separate_from` matches. This may be correct for inter-product conflicts but should be intentionally handled.
- **MEDIUM: Time/activity to near migration remains underspecified.** Scheduler code can keep generic matching, but data must define exact mappings such as `time: morning` to `near: wake` and/or `near: breakfast`.
- **LOW: `! grep -q 'effective_traits(card' planner.py` could fail on comments or aliases even if behavior is correct.

### Suggestions

- Add explicit scheduler handling for intra-product `separate_from`: detect internal conflicts for the candidate item, emit `intra_product_trait_conflict`, and do not feed that self-conflict into normal co-location blocking.
- Document expected `time` to `near` mapping: `morning` to `wake` and `breakfast`, `day` to `day_meal`, `evening` to `sleep`.
- Decide whether the `activity` namespace remains as marker traits with `near`-based effects or is retired.

## Plan 02-04: Regression verification

### Summary

A well-structured test plan that creates Phase 2 tests and updates Phase 1 tests to the new model. The approach of preserving topology guarantees while updating assertions is sound. The main risk is test fragility around exact slot placement.

### Strengths

- The split between data-shape tests, formula-specific tests, Phase 1 topology preservation, and final smoke tests follows the dependency order.
- The nattokinase inseparability test directly validates the core physical-product requirement.
- Preserving Phase 1 tests instead of deleting them ensures behavioral continuity.
- The negative goal-ref test for `has no matching substance card` is precise.

### Concerns

- **MEDIUM: Phase 1 topology may not be exactly preserved.** Stack partition guarantees should still hold, but exact slot assignments may shift after `time` to `near` migration depending on trait effect mapping. Tests should focus on the verified topology guarantees rather than exact placement.
- **MEDIUM: The goal-ref test function name should be updated.** The current name refers to missing product cards, but after the split the assertion is about missing substance cards.
- **LOW: Nattokinase component tests should also verify B6/B12 are not standalone inventory entries unless intentionally modeled as standalone products.

### Suggestions

- Keep Phase 1 regression tests focused on daily/training/inactive topology rather than exact slot assignment.
- Rename the goal-ref negative test to use substance-card terminology.
- Add a test that `vitamin_b6` and `vitamin_b12` are components only, not standalone inventory entries, unless standalone products are explicitly added.

## Overall Risk Assessment: MEDIUM

The plans are well structured and the phase goals are achievable. The most important gaps are: explicit migration guidance for existing multicomponent products, exact `time`/`activity` to `near` trait-effect mapping, and explicit `separate_from` handling after component trait aggregation.

---

## Consensus Summary

Only OpenCode was invoked because the requested reviewer set was `--opencode`.

### Agreed Strengths

- Phase 2 is scoped correctly as a direct YAML model migration with no compatibility or server work.
- The wave ordering is sound: data/schema migration first, validation and scheduling second, regression tests last.
- Product inseparability and component-aware explanations are represented in the plans.
- Negative validation tests are called out in the right places.

### Agreed Concerns

- **HIGH: `02-02` contains fragile acceptance criteria that can fail correct implementations based on source text rather than behavior.**
- **HIGH: `02-03` needs explicit `separate_from` handling after product component traits are aggregated, especially intra-product conflicts.**
- **MEDIUM: `02-01` needs explicit treatment for existing multicomponent products beyond nattokinase.**
- **MEDIUM: Trait-effect migration from `time`/`activity` to `near` needs a concrete mapping.**
- **MEDIUM: Validation semantics for single-file check mode and missing inventory entries need to be specified.**

### Divergent Views

- None. This review cycle used one external reviewer.
