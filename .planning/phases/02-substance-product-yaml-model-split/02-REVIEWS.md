---
phase: 2
reviewers: [opencode]
reviewed_at: 2026-05-05T23:18:31+05:00
replanning_commit: 61503cda0a492f8a2985f693c930902db1dcb906
plans_reviewed:
  - 02-01-PLAN.md
  - 02-02-PLAN.md
  - 02-03-PLAN.md
  - 02-04-PLAN.md
---

# Cross-AI Plan Review - Phase 2

## OpenCode Review

# Phase 2 Plan Review: Substance/Product YAML Model Split

## Plan 02-01: Data/Schema Migration

### Summary

This plan migrates the YAML data from the flat product-card model to a three-entity Substance/Product/InventoryItem split with declarative `near`+`food` slots and practical ontology additions. The task decomposition is logical and the acceptance criteria are concrete and testable. However, there are several ambiguities around multi-component product decomposition that could cause execution issues.

### Strengths

- **Clean wave-1 isolation**: Pure data migration with no planner changes needed, correctly deferred to plan 02-02.
- **Concrete acceptance criteria**: Every task has grep-based checks that are unambiguous and machine-verifiable.
- **Explicit multi-component decomposition**: Task 2 names every combination product (`nattokinase`, `lions_mane_b6_complex`, `dihydroquercetin_complex`, `coenzyme_b_complex`) and specifies what to do with each.
- **`near`/`food` migration table**: Task 4's `time` to `near` and `activity` to `near` mapping is explicit and covers all known slot fields.

### Concerns

- **HIGH - `coenzyme_b_complex` decomposition is underspecified for B-vitamin substance cards**: Task 2 says "create component substances for the meaningful B-vitamin components represented in the card notes, at minimum `vitamin_b1`...`vitamin_b12`." Eight new substance cards is a significant scope item inside one task. The plan doesn't specify what traits each B-vitamin gets. Will every one get `class:b_vitamin`? Will they get `intake:prefers_food` individually or will that be a product-level override? The current card only has `class:b_vitamin` and `intake:prefers_food`. If every component gets both, the planner sees redundant traits; if only some do, the decision is unspecified. This is a judgment call that the executing agent will have to make ad-hoc, increasing risk of inconsistency.

- **HIGH - `prefer_with` migration is not addressed in any task**: The current planner supports `prefer_with` on product cards (`schedule.yaml:66-70` shows `creatine` and `l_citrulline_malate` as a prefer_with pair). The schema spec says `prefer_with` "lives on substances and references substance ids only" but Task 4 (traits update) doesn't mention migrating prefer_with refs from product cards to substance cards, and no task addresses what happens to the `prefer_with` field during the product to substance card migration. Task 1 says `prefer_with` "if retained in Phase 2" - but the planner already uses it.

- **MEDIUM - Trait-effect migration from `time: morning` to `near` is ambiguous for `effect:energy_like` and `effect:nootropic`**: Currently `effect:energy_like` has `{time: morning}` to `prefer_strong` and `{time: day}` to `prefer`. But after migration, `near: wake` does not equal `near: breakfast` (both are "morning" slots). Should energy_like prefer `near: wake` strongly and `near: breakfast` weakly? Or only `near: wake`? The mapping table says `time: morning` to `near: wake` for "empty morning" or `near: breakfast` for "food-associated morning" - but trait effects aren't slot-specific, they're slot-field-specific. A trait matching `{near: wake}` won't fire on the `morning_food` slot at all. This changes scheduling behavior and may cause regressions.

- **MEDIUM - Task 2 acceptance criterion `! grep -R '^traits:' data/products` is fragile**: YAML indentation and flow style can make this grep miss top-level traits. A product file with `traits:` at top level under a different indent or style would pass. A more robust check would be schema validation (Task 1 already adds `traits` forbidden on products), but the plan treats these as independent acceptance criteria.

- **MEDIUM - `dihydroquercetin_complex` trait placement is under-specified**: Task 2 says "Move `class:fat_soluble`, `intake:requires_food`, and `risk:manual_review` to the fat-soluble bottleneck substances `vitamin_a` and/or `vitamin_e`" but `vitamin_c` and `dihydroquercetin` are water-soluble. If `intake:requires_food` only goes on `vitamin_a`/`vitamin_e`, the product still gets scheduled to a food slot correctly (via component aggregation), but `dihydroquercetin` itself has no traits at all - just unmatched concerns. This is fine for scheduling but may be confusing for explainability.

### Suggestions

- Add an explicit sub-step or note in Task 2 for migrating `prefer_with` from current product cards to substance cards.
- In Task 4, add explicit trait-effect YAML for `effect:energy_like`, `effect:nootropic`, `effect:sleep_support`, `effect:calming`, `effect:sleep_disruptive`, and `family:magnesium_like` showing the exact new match patterns with `near`. These are the traits currently matching `{time: ...}` and their conversion is the highest-risk part of the migration.
- Consider splitting Task 2 into two tasks: (a) single-substance card migration and (b) multi-component product decomposition - the latter is the bulk of the complexity.

### Risk Assessment: **MEDIUM**

The data shapes are well-understood, but the trait-effect migration (`time` to `near`, `activity` to `near`) and multi-component decomposition carry enough ambiguity that an executing agent may make inconsistent or incorrect decisions, especially for B-complex.

---

## Plan 02-02: Planner Validation

### Summary

This plan updates `planner.py` validation and loading to work with the split model. The task breakdown follows the natural check-flow: loaders -> substance validation -> product formula validation -> inventory/goal ref validation -> refresh. The plan is well-structured and directly grounded in the existing code patterns.

### Strengths

- **Excellent grounding in existing code**: Tasks reference specific existing functions (`load_product`, `check_products`, `check_inventory_alignment`, `check_goals`) and describe exact replacement behavior.
- **Behavior-contract acceptance criteria**: Task 4 explicitly says "do not rely on exact local variable names" and focuses on CLI output behavior, which is the right approach.
- **Proper severity distinction**: Task 3 distinguishes between fatal errors (inventory references missing product) and non-fatal warnings (product with no inventory entry).
- **Single-file check mode is addressed**: Task 3 specifies behavior for `cmd_check(target)` with individual file paths.

### Concerns

- **HIGH - Task 4 acceptance criteria requires creating and cleaning up a temporary file during autonomous execution**: The probe test (`__refresh_probe__`) is a good idea in principle but risky for autonomous execution. If the agent crashes mid-task, the probe file and inventory entry remain, breaking `check`. Consider using an in-memory test or a pytest fixture instead of filesystem manipulation inside the plan task.

- **MEDIUM - `check_goals` currently references `card_ids` (product ids), not substance ids**: Looking at `planner.py:219-247`, the current `check_goals` receives `card_ids` which is the product-card id map. After the split, goals reference substances, but the current error message says "has no matching product card". Task 3 correctly specifies changing to "has no matching substance card" but doesn't mention that the current Phase 1 test (`test_goal_ref_validator_rejects_missing_product_and_restores_file`) asserts "no matching product card" in output. That test must be updated in plan 02-04, but there's no explicit cross-reference.

- **MEDIUM - `check_inventory_alignment` refactoring scope is underspecified**: Currently this function checks bidirectional alignment (product to inventory and inventory to product). After the split, it must also handle the `product` field in inventory entries. Task 3 says "Update `check_inventory_alignment`" but doesn't specify whether the function signature changes, whether it now receives both `product_ids` and `substance_ids`, or how the old `card_ids` parameter maps to the new world.

- **LOW - `mechanism` namespace addition has no schema enforcement**: Task 1 adds `mechanism` to `REGISTERED_NAMESPACES`, but the trait pattern in `schema/traits.schema.json` may need updating too (currently `"pattern": "^[a-z]+:[a-z][a-z0-9_]*$"` which already matches). This is fine but could be noted explicitly.

### Suggestions

- Replace the `__refresh_probe__` filesystem test with a pytest-based test in plan 02-04, or use a git-restore safety net.
- Add an explicit note in Task 3 about the Phase 1 test that will break (the goal ref test asserting "no matching product card").
- Specify the new function signature for `check_inventory_alignment` to avoid ambiguity.

### Risk Assessment: **MEDIUM**

The plan is well-grounded but the refresh-probe acceptance criterion and the implicit cross-reference to Phase 1 test updates add risk.

---

## Plan 02-03: Scheduler/Explainability

### Summary

This plan updates the scheduling engine to treat inventory items as inseparable units with aggregated component traits, and adds component-aware explanations and intra-product conflict warnings. This is the highest-complexity plan and the one most likely to encounter subtle bugs.

### Strengths

- **Correct architectural decision**: Aggregating component substance traits at the product level, rather than scheduling components individually, is the right approach and matches D-11/D-12.
- **Intra-product self-conflict handling is well-designed**: Task 3 explicitly addresses the self-conflict edge case with `intra_product_trait_conflict` warnings that don't block scheduling. This is the critical subtlety of the whole phase.
- **`effective_inventory_traits` returns trait source mapping**: Recording `trait_id -> [substance_id, ...]` enables component-aware explanations without a second pass.
- **Verification section includes specific negative checks**: The inter-product conflict fixture and intra-product conflict fixture are concrete test cases.

### Concerns

- **HIGH - `prefer_with` migration is still not addressed**: After the split, `prefer_with` lives on substances. But scheduling operates on inventory items/products. When product A's aggregated traits include substance X with `prefer_with: Y`, and substance Y is a component of product B, the current code looks up `prefer_with` targets in the `active` dict (which contains inventory item ids). The substance id `Y` won't be in `active` - product B's inventory id will be. Task 4 says "remove the bonus for Phase 2" if ambiguous, but this is a scheduling regression: the current `creatine` to `l_citrulline_malate` prefer_with pair is both cross-product and cross-slot. The plan needs to decide and document: does prefer_with survive the split or not?

- **HIGH - Task 1 acceptance criteria includes `! grep -q 'effective_traits(card' planner.py`**: This checks that the old function signature is removed. But the existing `effective_traits` is called at `planner.py:478` and its signature is `(card: dict, inventory_entry: dict)`. If the new function is named differently but old references remain (e.g., in comments or dead code paths), the grep could be misleading. More importantly, this acceptance criterion doesn't verify that the new function actually works - only that the old one is gone.

- **MEDIUM - Schedule output format change is under-specified for consumers**: The current `schedule.yaml` uses substance ids in `slots.*` arrays and `explanations` keys. After the split, these become inventory item ids. The plan says "inventory item ids" but doesn't address that inventory item ids currently equal product-card ids (e.g., `nattokinase` is both). If inventory items keep the same keys, the schedule output looks identical for single-component products - but this implicit equivalence should be documented.

- **MEDIUM - Task 3 acceptance criteria says `! grep -q 'substance:' schedule.yaml || grep -q 'item:' schedule.yaml`**: This is confusing. The `||` means it passes if either `substance:` is absent OR `item:` is present. But warnings already contain `substance:` as a field name (Task 3 itself specifies `substance: <substance_id>` in warning format). This acceptance criterion will always pass because warnings contain `substance:`.

- **MEDIUM - Trait aggregation wideness for separate_from is acknowledged but risky**: The plan says "aggregated trait sets intentionally widen inter-product conflict matching. That is desired." But consider: if `dihydroquercetin_complex` (inactive) has `family:magnesium_like` on a component, and `magnesium_glycinate` has `family:magnesium_like`, and `family:magnesium_like` has `separate_from: family:calcium_like` - now `dihydroquercetin_complex` picks up `separate_from: family:calcium_like` for its `vitamin_c` component if vitamin C has no calcium conflict. This is the correct behavior (the physical unit carries the constraint), but the plan should note that adding traits to component substances has scheduling side effects on the parent product.

### Suggestions

- Make an explicit decision on `prefer_with` in this plan (not just "if ambiguous, remove"). The current `creatine` to `l_citrulline_malate` pair needs a concrete migration path.
- Fix the acceptance criterion in Task 3 to not have the tautological `||` with warnings containing `substance:`.
- Add an explicit example of the new `schedule.yaml` format showing how explanations look for the multi-component `nattokinase` product.

### Risk Assessment: **HIGH**

This plan has the most subtle behavior changes (aggregation, self-conflicts, prefer_with migration, schedule format) and the highest risk of subtle regressions. The prefer_with question in particular is a known-unknown that must be resolved before execution.

---

## Plan 02-04: Regression Verification

### Summary

This plan adds Phase 2 regression tests and updates Phase 1 tests for the split model. The topology-preservation approach (verify daily/training partition, not exact slot placements) is the right call given the `time` to `near` migration will shift some assignments.

### Strengths

- **Topology-over-placement testing**: Task 3 explicitly says "do not assert exact daily item slot placement" - this is correct and shows awareness that `near`+`food` may cause legitimate reassignments.
- **Comprehensive data-shape coverage**: Task 1 covers all the new structural invariants (substance/product/inventory/slot/traits).
- **Nattokinase inseparability is a dedicated test**: Task 2 verifies the multi-component product doesn't get split, which is the core behavioral guarantee.
- **Final smoke test sequence is practical**: Task 4 runs the exact commands an operator would run.

### Concerns

- **HIGH - Phase 1 test update is under-specified for the goal-ref test**: The current `test_goal_ref_validator_rejects_missing_product_and_restores_file` (`test_phase_01.py:187-210`) asserts `"no matching product card"` in output. After plan 02-02 Task 3, the error message changes to `"has no matching substance card"`. Task 3 of this plan says the test should expect `"has no matching substance card"` but doesn't mention that the test's mechanism (replacing `l_citrulline_malate` with `bogus_substance_xyz`) may need to change - because `l_citrulline_malate` is now in `data/substances/` not `data/products/`. The test is actually still correct in mechanism (it corrupts a goal file, not a product/substance file), but the assertion text must change. This is a minor detail but worth being explicit about.

- **MEDIUM - Task 1 acceptance criterion `grep -q 'test_substance_product_inventory_split'` is fragile**: This requires an exact test function name in the file. If the implementation uses multiple test functions instead of one monolithic test, this criterion fails even though the behavior is correct.

- **MEDIUM - No test for `intra_product_trait_conflict` warning**: Plan 02-03 Task 3 specifies this warning type, but plan 02-04 doesn't include a dedicated test for it. The nattokinase product doesn't have conflicting internal traits, so the inseparability test won't exercise this path. A synthetic test fixture is needed.

- **MEDIUM - `TRAINING_SUBSTANCES` and `DAILY_SUBSTANCES` constant renaming is unclear**: Task 3 says "Rename constants from `*_SUBSTANCES` to `*_ITEMS`" but the test at line 178 asserts `scheduled_training == TRAINING_SUBSTANCES` and `scheduled_daily == DAILY_SUBSTANCES`. If these are renamed to `TRAINING_ITEMS`/`DAILY_ITEMS`, the assertion semantics stay the same (inventory item ids match the set). But if the actual inventory item ids diverge from substance ids (e.g., if inventory keys change), the sets would need updating. The plan doesn't clarify whether inventory item ids stay the same as current keys.

- **LOW - The `schedule.yaml` regeneration in Task 4 could be affected by `prefer_with` decisions**: If `prefer_with` is removed (as suggested in plan 02-03 Task 4), the total score and slot assignments will change, which is expected. But the test should be resilient to this.

### Suggestions

- Add a dedicated test for `intra_product_trait_conflict` using a synthetic product with two internally-conflicting component substances.
- Make the Phase 1 goal-ref test update explicit about the exact assertion change.
- Consider testing that `schedule.yaml` warnings now include `product:` context for multi-component items.

### Risk Assessment: **MEDIUM**

The testing approach is sound, but the missing intra-product conflict test and the implicit Phase 1 test coupling mean some edge cases may not be covered.

---

## Cross-Plan Concerns

| Concern | Severity | Plans Affected |
|---------|----------|---------------|
| **`prefer_with` has no owner**: No plan explicitly takes responsibility for migrating or removing `prefer_with`. Plan 02-01 Task 1 mentions it conditionally; Plan 02-03 Task 4 says "if ambiguous, remove." This needs a single decision point. | **HIGH** | 01, 03, 04 |
| **Trait-effect migration (`time`/`activity` -> `near`) is split across two plans**: Plan 01-04 (Task 4) specifies the mapping table, but the actual trait YAML changes must happen in plan 01-01 (data migration). Meanwhile, the planner in plan 02-02 needs the new match fields to validate correctly. The ordering is correct (01 -> 02), but the concrete YAML for `effect:energy_like` matching `{near: wake}` vs `{near: breakfast}` is never shown. | **HIGH** | 01, 02 |
| **Wave-2 plans 02-02 and 02-03 run in parallel**: Both modify `planner.py`. Plan 02-02 adds new functions and validation; plan 02-03 replaces the scheduling core. If both are auto-executed in parallel, merge conflicts in `planner.py` are guaranteed. | **HIGH** | 02, 03 |
| **Schedule format change**: Plan 02-03 changes `schedule.yaml` format (adds `product:`, `components:`), but no plan documents the expected format diff or migration for the existing schedule. The regenerated schedule in plan 02-04 Task 4 is the only reconciliation point. | **MEDIUM** | 03, 04 |

## Overall Risk Assessment: **HIGH**

The phase goal is achievable and the plans are mostly well-structured, but three issues push the risk to HIGH:

1. **`prefer_with` has no clear owner** - it's a working feature with no explicit migration or removal plan.
2. **Trait-effect conversion from `time`/`activity` to `near`** - the exact match patterns for time-of-day traits (`energy_like`, `nootropic`, `sleep_support`, `calming`, `sleep_disruptive`, `magnesium_like`) are never specified in YAML, leaving the most behavior-critical migration to agent judgment.
3. **Plans 02-02 and 02-03 both modify `planner.py` in wave 2** - if autonomous execution runs them in parallel, merge conflicts are certain. They should be sequential (02-02 -> 02-03) or carefully coordinated.

---

## Consensus Summary

Only OpenCode was invoked because the requested reviewer set was `--opencode`.

### Agreed Strengths

- The phase remains achievable and the overall split-model direction is coherent.
- The plan set preserves the right high-level order: data/schema migration, validation/scheduler updates, then regression verification.
- The current replan addresses important prior gaps: all known multicomponent products are now named, single-file check mode is covered, and intra-product self-conflict handling is explicitly represented.
- Regression planning correctly favors topology guarantees over exact slot placement.

### Agreed Concerns

- **HIGH: `prefer_with` has no clear owner or migration/removal decision.** It appears in schema/data planning and scheduler planning, but no task explicitly owns its current behavior after scheduling moves from substances/products to inventory items.
- **HIGH: B-complex substance decomposition remains underspecified.** Creating at least eight B-vitamin substance cards without trait placement guidance leaves too much to executor judgment.
- **HIGH: `time`/`activity` to `near` migration needs exact trait-effect YAML.** The current mapping table does not fully determine behavior for traits that used broad `time` matches such as morning/day/evening.
- **HIGH: Wave-2 execution order is unsafe if plans 02-02 and 02-03 run in parallel.** Both modify `planner.py`; the plan should serialize or explicitly coordinate them.
- **HIGH: Some acceptance criteria still inspect source text or require risky workspace mutation.** The `effective_traits(card` grep and `__refresh_probe__` filesystem probe can fail correct implementations or leave dirty state if interrupted.
- **HIGH: Phase 1 goal-ref regression update needs explicit assertion and fixture guidance.** The plan mentions the new message text, but should explicitly handle the existing test name/mechanism/assertion coupling.

### Divergent Views

- None. This review cycle used one external reviewer.

### Current HIGH Concerns

- `coenzyme_b_complex` decomposition is underspecified for B-vitamin substance cards and trait placement.
- `prefer_with` lacks a clear migration/removal owner across data, scheduler, and regression plans.
- The refresh probe acceptance criterion risks leaving temporary files or inventory entries if autonomous execution is interrupted.
- The `effective_traits(card` grep criterion does not verify scheduler behavior and can be misleading.
- The Phase 1 goal-ref regression update needs explicit assertion and fixture guidance.
- Exact trait-effect YAML for `time`/`activity` to `near` migration is not specified for behavior-critical traits.
- Wave-2 plans 02-02 and 02-03 both modify `planner.py`; parallel execution would create merge conflicts.

