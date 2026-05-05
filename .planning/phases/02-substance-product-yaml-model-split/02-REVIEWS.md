---
phase: 2
reviewers: [opencode]
reviewed_at: 2026-05-05T23:42:28+05:00
replanning_commit: dc5f7fdcad23099f8f8f37c781d3ffc3a0d9fe49
plans_reviewed:
  - 02-01-PLAN.md
  - 02-02-PLAN.md
  - 02-03-PLAN.md
  - 02-04-PLAN.md
---

# Cross-AI Plan Review - Phase 2

## OpenCode Review

# Cross-AI Plan Review: Phase 02 - Substance/Product YAML Model Split

**Reviewer:** OpenCode (`build - glm-5.1`)
**Scope:** Plans 02-01 through 02-04, cross-referenced against `planner.py`, YAML data, schemas, tests, and Phase 1 verification.

## Summary

Phase 2 splits the current monolithic product-card model into three distinct entities: `Substance`, `Product`, and `InventoryItem`. It also migrates slot declarations from `time`/`activity` semantics to `near`/`food`. The four plans are structured into sensible waves: schema/data migration, planner validation, scheduler/explainability, and regression verification. Dependencies are correct. Execution risk is moderate because the change touches every data file, all schemas, the planner, and the test suite, but the plans are thorough and the single-user, no-compatibility context limits blast radius.

## Plan 02-01: Data/Schema Migration

### Strengths

- Clean-slate migration is appropriate for this repo: no compatibility adapters or dual readers.
- Multicomponent decomposition is now specified for `nattokinase`, `lions_mane_b6_complex`, `dihydroquercetin_complex`, and `coenzyme_b_complex`.
- The trait-effect migration table gives concrete `time`/`activity` to `near`/`food` replacements.
- `prefer_with` migration is documented from product card to substance card, with acceptance criteria checking `data/substances/creatine.yaml`.

### Concerns

| ID | Severity | Description |
|----|----------|-------------|
| 02-01-M1 | MEDIUM | `lions_mane_b6_complex` `intake:prefers_food` placement is non-deterministic. The plan says to use product/inventory traits if supported, otherwise put it on `lions_mane`. Because 02-01 establishes inventory `traits_override` for `coenzyme_b_complex`, the instruction should choose one deterministic placement. |
| 02-01-M2 | MEDIUM | Single-component product formula creation is implicit. The plan decomposes multicomponent products but does not explicitly say that every remaining inventory key gets a one-component product formula referencing the same substance id. |
| 02-01-L1 | LOW | The acceptance criterion `! grep -R '^traits:' data/products` could technically false-positive if a scalar value contains `traits:` at column 0, though strict schemas make this unlikely. |

### Suggestions

- Resolve `02-01-M1` by matching the `coenzyme_b_complex` pattern: add `traits_override: {add: ["intake:prefers_food"]}` to the `lions_mane_b6_complex` inventory entry.
- Add an explicit sentence or table for single-substance product formula creation.

### Risk Assessment

Medium. The migration is well specified, but incomplete product formula creation or inconsistent trait placement would affect scheduling behavior.

## Plan 02-02: Planner Validation

### Strengths

- Two-pass validation mirrors the domain split: substances first, then product formulas.
- Goal reference validation correctly retargets to substances and uses actionable error text.
- Refresh probe isolation via pytest `tmp_path` avoids polluting repository data.
- Single-file check dispatch is specified for substances, products, inventory, goals, and unknown paths.

### Concerns

| ID | Severity | Description |
|----|----------|-------------|
| 02-02-M1 | MEDIUM | The refresh probe acceptance criterion references plan 02-04 completion. Since the test and `cmd_refresh` update are both in scope of 02-02, clarify whether the test should pass immediately after 02-02 or only when the full 02-04 suite runs. |
| 02-02-L1 | LOW | Single-file check behavior for `data/goals/*.yaml` is described but not directly covered by an acceptance criterion. |

### Suggestions

- Split the refresh-probe criterion into test-exists and test-passes expectations.
- Add `uv run planner.py check data/goals/vascular_health.yaml` to acceptance criteria or verification.

### Risk Assessment

Medium-low. The validation design is strong; remaining issues are mostly about test timing clarity.

## Plan 02-03: Scheduler/Explainability

### Strengths

- `effective_inventory_traits` is a clean design: union component traits, record source mapping, apply overrides, and detect intra-product conflicts separately.
- Intra-product conflict handling is architecturally correct: warn but do not block the physical product from scheduling.
- `prefer_with` resolution through `substance_to_active_items` handles active targets, missing targets, and ambiguous multi-target cases.
- Schedule output preserves Phase 1 fields while adding product/component context.

### Concerns

| ID | Severity | Description |
|----|----------|-------------|
| 02-03-M1 | MEDIUM | Phase 1 tests are expected to break between 02-03 and 02-04 after schedule structure changes. The plan lacks an intermediate automated smoke assertion that can catch 02-03 regressions before the final verification plan lands. |
| 02-03-M2 | MEDIUM | Task 3 says a temporary fixture or pytest case should cover internally conflicting component traits. Because 02-04 creates fixtures, 02-03 should focus on scheduler behavior and avoid ambiguity about where the fixture belongs. |
| 02-03-M3 | MEDIUM | Intra-product conflict derivation should explicitly use the product formula's component list as the product boundary; trait source mapping alone does not encode that boundary. |

### Suggestions

- Add a 02-03 smoke check after `uv run planner.py plan` that verifies `schedule.yaml` has `explanations`, `warnings`, and slot entries that are existing inventory item ids.
- Replace the fixture wording with: "The scheduler emits `intra_product_trait_conflict` warnings; regression fixtures are added in 02-04."
- Add one sentence saying product formula components determine the intra-product boundary.

### Risk Assessment

Medium. The design is sound, but this is the highest-complexity planner change and needs precise verification boundaries.

## Plan 02-04: Regression Verification

### Strengths

- Coverage spans data shape, formulas, B-complex decomposition, refresh isolation, `prefer_with`, intra-product conflicts, and inter-product conflicts.
- Phase 1 test migration is explicit: renamed constants, updated error text, and topology guarantees rather than exact slot placement.
- Final acceptance chain covers `check`, `plan`, `pytest`, and schedule structure assertions.

### Concerns

| ID | Severity | Description |
|----|----------|-------------|
| 02-04-M1 | MEDIUM | The scoring shift from `time` to `near` is not explicitly tested. A bad trait migration could leave an active item with zero useful slot score while topology tests still pass. |
| 02-04-L1 | LOW | The B-complex test could assert the exact eight component substance ids instead of only checking for `coenzyme_b_complex` in the test file. |

### Suggestions

- Add a test that every active inventory item has a non-zero best slot score after the `near`/`food` migration.
- Assert the exact B-vitamin component set for `coenzyme_b_complex`.

### Risk Assessment

Medium-low. The verification plan is comprehensive, but one scoring-regression smoke test would materially improve confidence.

## Cross-Plan Concerns

| ID | Severity | Description |
|----|----------|-------------|
| CROSS-M1 | MEDIUM | Plans 02-01 and 02-03 both affect warning traits. Plan 02-04 should include a test that expected `warning: true` traits produce schedule warnings. |
| CROSS-M2 | MEDIUM | The inactive `lions_mane` inventory entry still needs a one-component product formula. This follows from the general instruction, but it is easy to miss because it is not called out near the multicomponent decomposition list. |
| CROSS-M3 | LOW | Several files overlap across plans. The wave ordering and `read_first` directives handle this, but later waves must treat earlier wave outputs as inputs rather than overwriting wholesale. |

## Consensus Summary

Only OpenCode was invoked because the requested reviewer set was `--opencode`.

### Agreed Strengths

- The phase is coherent and achievable.
- The wave ordering is correct.
- The plans now resolve the previous HIGH-level blockers around `prefer_with`, B-complex decomposition, exact trait-effect migration, wave ordering, risky probe isolation, misleading scheduler grep checks, and Phase 1 goal-ref regression guidance.
- Acceptance criteria are mostly concrete and testable.

### Agreed Concerns

- Remaining concerns are MEDIUM/LOW, mostly about determinism, test timing, and stronger smoke coverage.
- `lions_mane_b6_complex` trait placement should be made deterministic.
- Single-component product formula creation should be explicit for all inventory keys, including inactive `lions_mane`.
- 02-03 would benefit from an intermediate smoke check before the full 02-04 test migration.
- 02-04 should add a non-zero slot-score smoke test after the `near`/`food` migration.

### Divergent Views

- None. This review cycle used one external reviewer.

CYCLE_SUMMARY: current_high=0

## Current HIGH Concerns

None.
