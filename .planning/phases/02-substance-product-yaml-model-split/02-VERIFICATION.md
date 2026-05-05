---
phase: 02-substance-product-yaml-model-split
verified: 2026-05-05T19:30:08Z
status: gaps_found
score: 9/10 must-haves verified
overrides_applied: 0
gaps:
  - truth: "Planner validation supports the split model, including target-path checks and deterministic schema error reporting"
    status: failed
    reason: "The full repository check passes, but two planned validation surfaces are not actually correct: single-file substance target checks falsely reject valid cross-file prefer_with refs, and malformed inventory entries crash before schema errors can be reported."
    artifacts:
      - path: "planner.py"
        issue: "cmd_check target mode re-runs check_substances([target], trait_ids), so prefer_with is validated against only the target file instead of the full substance registry."
      - path: "planner.py"
        issue: "validate_inventory continues into check_inventory_alignment/check_inventory_overrides after schema errors, and those helpers assume every supplement entry is a mapping."
    missing:
      - "Validate target substance prefer_with refs against the full substance_ids registry already loaded by cmd_check."
      - "Skip alignment/override checks for non-mapping inventory entries or return schema errors before deeper inventory checks."
      - "Add regressions for uv run planner.py check data/substances/creatine.yaml and malformed inventory entry handling."
---

# Phase 2: Substance/Product YAML Model Split Verification Report

**Phase Goal:** Split the YAML model into Substance, Product, and InventoryItem entities; migrate slots to declarative `near + food`; keep products physically inseparable during scheduling; and add only practical ontology improvements for scheduling, warnings, and explanations.
**Verified:** 2026-05-05T19:30:08Z
**Status:** gaps_found
**Re-verification:** No - initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | Data migrated directly to the target YAML shape with no legacy compatibility path | VERIFIED | `data/substances/` and formula-style `data/products/` exist; `planner.py` loads `SUBSTANCES_DIR` and `PRODUCTS_DIR` separately; no compatibility reader for old product-as-substance cards was found. |
| 2 | YAML remains the local deterministic model with no MCP/server/database/import workflow scope | VERIFIED | The changed surface is local YAML, JSON schemas, `planner.py`, tests, and `schedule.yaml`; no network/server/database/import workflow code was found. |
| 3 | Substance, Product, and InventoryItem are represented separately | VERIFIED | 43 substance cards, 23 product formulas, and 23 inventory entries were parsed; every product component resolves to a substance and every inventory `product` resolves to a product formula. |
| 4 | Slots use declarative stack + near + food fields only | VERIFIED | `data/slots.yaml` has six slots with near values `wake`, `breakfast`, `day_meal`, `sleep`, `workout_before`, `workout_after`; each slot has only `label`, `order`, `stack`, `near`, and `food`. |
| 5 | Ontology updates are practical and use near/food for scheduling effects | VERIFIED | `data/traits.yaml` includes practical mechanism/risk/intake/family additions; trait effect matches use only `near` and `food`, not removed `time` or `activity` match fields. |
| 6 | Nattokinase shelf product is modeled as one multi-component product | VERIFIED | `data/products/nattokinase.yaml` components are `nattokinase`, `vitamin_b6`, and `vitamin_b12`; empty-stomach/fibrinolytic traits live on `data/substances/nattokinase.yaml`. |
| 7 | Planner validation supports split registries, target-path checks, and deterministic schema errors | FAILED | `uv run planner.py check` passes, but `uv run planner.py check data/substances/creatine.yaml` fails on a valid `prefer_with` edge, and a malformed inventory entry crashes with `AttributeError` instead of reporting schema errors. |
| 8 | Scheduler treats product components as inseparable inventory items | VERIFIED | `planner.py` aggregates component substance traits in `effective_inventory_traits`; `cmd_plan` schedules inventory item ids, tracks `item_products`, `active_components`, `item_stacks`, and emits intra-product conflict warnings without splitting products. |
| 9 | Regression tests cover split shape, formula refs, scheduling, conflicts, refresh isolation, and Phase 1 topology | VERIFIED | `tests/test_phase_01.py` and `tests/test_phase_02.py` exist and `uv run pytest` passed with 15 tests. Tests cover product/inventory refs, B-complex split, nattokinase inseparability, intra/inter-product conflicts, prefer_with, refresh isolation, and goal refs. |
| 10 | Generated schedule reflects split-model behavior | VERIFIED | `uv run planner.py plan` regenerated `schedule.yaml` with inventory item ids, product/component explanations, warning context, `quality: ****- (4/5)` equivalent output, and `nattokinase` scheduled once without standalone `vitamin_b6`/`vitamin_b12` component assignments. |

**Score:** 9/10 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `schema/substance.schema.json` | Universal substance card schema | VERIFIED | Requires `id`, `name`, `traits`; allows substance-only `prefer_with`. |
| `schema/product.schema.json` | Concrete product formula schema | VERIFIED | Requires non-empty `components[].substance`; no top-level `traits` or `prefer_with`. |
| `schema/inventory.schema.json` | Inventory item schema with `product` and `stack` | VERIFIED | Requires `product` and `stack`; keeps `dose`, `brand`, `notes`, and `traits_override`. |
| `schema/slots.schema.json` | Slot schema with `near` and `food` | VERIFIED | Allows only `label`, `order`, `stack`, `near`, and `food`; near enum has the six planned values. |
| `schema/traits.schema.json` | Trait effects matching near/food | VERIFIED | Effect matches are constrained to `near` and `food`. |
| `data/substances/*.yaml` | Substance cards | VERIFIED | 43 substance cards parsed; ids match filenames in executable `planner.py check`. |
| `data/products/*.yaml` | Product formula cards | VERIFIED | 23 formulas parsed; no product top-level `traits` or `prefer_with`; component refs resolve. |
| `data/inventory.yaml` | Inventory items referencing products | VERIFIED | 23 entries with `product` and `stack`; no `active` field. |
| `data/slots.yaml` | Six physical slots | VERIFIED | All six required slots and near values present. |
| `data/traits.yaml` | Practical ontology updates | VERIFIED | Mechanism, risk, intake, family, class, activity traits validate through `planner.py check`. |
| `planner.py` | Split-model validation and scheduler | PARTIAL | Happy-path validation and scheduling work; target-mode substance validation and malformed inventory handling have gaps. |
| `tests/test_phase_01.py` | Phase 1 topology regression after split | VERIFIED | Updated to inventory-item scheduling and substance-card goal refs. |
| `tests/test_phase_02.py` | Phase 2 regression suite | VERIFIED | Covers split shape, formula refs, refresh isolation, nattokinase scheduling, conflicts, and prefer_with. |
| `schedule.yaml` | Generated split-model schedule | VERIFIED | Contains product/component explanations, warnings, prefer_with pairs, and inventory item assignments. |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `planner.py` | `data/substances/*.yaml` | `SUBSTANCES_DIR`, `load_substance`, `check_substances`, `load_substance_registry` | WIRED | Full check loads substance registry and scheduler uses substance component traits. Target-mode prefer_with validation is flawed. |
| `planner.py` | `data/products/*.yaml` | `PRODUCTS_DIR`, `load_product`, `check_product_formulas`, `load_product_registry` | WIRED | Product formulas validate component refs and scheduler loads products by inventory `product`. |
| `planner.py` | `data/inventory.yaml` | `validate_inventory`, `entry.get("product")`, active inventory loop | PARTIAL | Normal inventory data works; malformed non-mapping entries crash during deeper checks. |
| `planner.py` | `data/slots.yaml` / `data/traits.yaml` | `derive_slot_fields`, `check_traits`, `compute_slot_score` | WIRED | Effects match actual slot `near`/`food` fields. |
| `tests/test_phase_02.py` | `planner.py` behavior | subprocess fixtures using `uv run planner.py` | WIRED | Tests exercise check/plan behavior in repo and temp fixtures. |
| `schedule.yaml` | product/component model | `cmd_plan` output explanations and warnings | WIRED | Schedule entries are inventory item ids with `product` and `components` explanation context. |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|---------------|--------|--------------------|--------|
| `planner.py` | `substances` | `load_substance_registry()` from `data/substances/*.yaml` | Yes | FLOWING |
| `planner.py` | `products` | `load_product_registry()` from `data/products/*.yaml` | Yes | FLOWING |
| `planner.py` | `active`, `item_products`, `active_components`, `item_stacks` | `data/inventory.yaml` plus product formulas | Yes | FLOWING |
| `planner.py` | `assignment` / `schedule` | Greedy plus first-improvement scheduler over active inventory items | Yes | FLOWING |
| `schedule.yaml` | `explanations.nattokinase.components` | Product formula components from `data/products/nattokinase.yaml` | Yes | FLOWING |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Full split-model validation passes | `uv run planner.py check` | Exit 0, `All checks passed.` | PASS |
| Schedule generation succeeds | `uv run planner.py plan` | Exit 0, `quality: ****- (4/5)`, `warnings: 17` | PASS |
| Regression suite passes | `uv run pytest` | Exit 0, `15 passed` | PASS |
| Target substance check handles valid prefer_with | `uv run planner.py check data/substances/creatine.yaml` | Exit 1, false error: `prefer_with target 'l_citrulline_malate' has no matching substance card` | FAIL |
| Malformed inventory reports schema errors without crashing | temp copy with `supplements.vitamin_d3` as scalar, then `uv run planner.py check data/inventory.yaml` | Crashes with `AttributeError: 'str' object has no attribute 'get'` | FAIL |
| Split-model invariants hold | Python YAML invariant script | `invariant_errors: []`; counts `43 substances 23 products 23 inventory` | PASS |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|-------------|-------------|--------|----------|
| Phase 2 roadmap goal | ROADMAP | Split YAML into Substance/Product/InventoryItem, migrate slots to near+food, keep products inseparable, add practical ontology | PARTIAL | Core model/scheduler/tests/schedule verified, but validation target-mode and malformed-input behavior have gaps. |
| Plan frontmatter requirements | PLAN files | `requirements: []` | N/A | No requirement IDs declared for Phase 2; `.planning/REQUIREMENTS.md` has no Phase 2 requirement IDs. |

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `planner.py` | 255 | `entry.get("product")` assumes inventory entry shape after schema errors | Blocker | Malformed inventory entries crash validation instead of producing deterministic schema errors. |
| `planner.py` | 417 | Target substance check validates `prefer_with` against one-file registry | Blocker | Valid `data/substances/creatine.yaml` fails target-path validation. |

No TODO/FIXME/placeholder/console-only stub patterns were found in `planner.py`, tests, data, schemas, or `schedule.yaml`.

### Human Verification Required

None. This phase is CLI/YAML/test behavior and was verified programmatically.

### Gaps Summary

The data split, product formulas, near/food slot model, practical ontology, product-level scheduling, component-aware warnings/explanations, generated schedule, and regression tests are implemented and working on the main path.

The phase cannot be marked passed because planner validation is part of the stated goal and plan contract. Two validation surfaces fail: valid single-file substance checks can be falsely rejected when `prefer_with` points to another substance, and malformed inventory entries crash instead of returning schema validation errors. These should be closed in `planner.py` with targeted regressions.

---

_Verified: 2026-05-05T19:30:08Z_
_Verifier: the agent (gsd-verifier)_
