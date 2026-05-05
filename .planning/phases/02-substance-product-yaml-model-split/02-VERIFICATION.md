---
phase: 02-substance-product-yaml-model-split
verified: 2026-05-05T20:45:00Z
status: passed
score: 10/10 must-haves verified
overrides_applied: 0
gaps: []
---

# Phase 2: Substance/Product YAML Model Split Verification Report

**Phase Goal:** Split the YAML model into Substance, Product, and InventoryItem entities; migrate slots to declarative `near + food`; keep products physically inseparable during scheduling; and add only practical ontology improvements for scheduling, warnings, and explanations.
**Verified:** 2026-05-05T20:45:00Z
**Status:** passed
**Re-verification:** Yes - after `02-05` gap closure

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
| 7 | Planner validation supports split registries, target-path checks, and deterministic schema errors | VERIFIED | `uv run planner.py check` passes; `uv run planner.py check data/substances/creatine.yaml` passes; malformed inventory scalar entries now fail with schema text naming `supplements.vitamin_d3` and no traceback. |
| 8 | Scheduler treats product components as inseparable inventory items | VERIFIED | `planner.py` aggregates component substance traits in `effective_inventory_traits`; `cmd_plan` schedules inventory item ids, tracks `item_products`, `active_components`, `item_stacks`, and emits intra-product conflict warnings without splitting products. |
| 9 | Regression tests cover split shape, formula refs, scheduling, conflicts, refresh isolation, Phase 1 topology, and gap closure | VERIFIED | `uv run pytest` passed with 17 tests. Tests cover product/inventory refs, B-complex split, nattokinase inseparability, intra/inter-product conflicts, prefer_with, refresh isolation, goal refs, target-mode `creatine.yaml`, and malformed inventory entries. |
| 10 | Generated schedule reflects split-model behavior | VERIFIED | `uv run planner.py plan` passed, wrote `schedule.yaml`, reported `quality: 4/5`, and kept product/component explanations, warnings, prefer_with pairs, and inventory item assignments. |

**Score:** 10/10 truths verified

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
| `planner.py` | Split-model validation and scheduler | VERIFIED | Full check, target substance check, malformed inventory regression, and scheduler smoke all pass. |
| `tests/test_phase_01.py` | Phase 1 topology regression after split | VERIFIED | Updated to inventory-item scheduling and substance-card goal refs. |
| `tests/test_phase_02.py` | Phase 2 regression suite | VERIFIED | Covers split shape, formula refs, refresh isolation, nattokinase scheduling, conflicts, prefer_with, and validation gaps. |
| `schedule.yaml` | Generated split-model schedule | VERIFIED | Contains product/component explanations, warnings, prefer_with pairs, and inventory item assignments. |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `planner.py` | `data/substances/*.yaml` | `SUBSTANCES_DIR`, `load_substance`, `check_substances`, `load_substance_registry` | WIRED | Full and target-mode checks load the registry needed for `prefer_with` refs. |
| `planner.py` | `data/products/*.yaml` | `PRODUCTS_DIR`, `load_product`, `check_product_formulas`, `load_product_registry` | WIRED | Product formulas validate component refs and scheduler loads products by inventory `product`. |
| `planner.py` | `data/inventory.yaml` | `validate_inventory`, `check_inventory_alignment`, `check_inventory_overrides` | WIRED | Normal inventory data works and malformed non-mapping entries report schema errors without crashes. |
| `planner.py` | `data/slots.yaml` / `data/traits.yaml` | `derive_slot_fields`, `check_traits`, `compute_slot_score` | WIRED | Effects match actual slot `near`/`food` fields. |
| `tests/test_phase_02.py` | `planner.py` behavior | subprocess fixtures using `uv run planner.py` | WIRED | Tests exercise check/plan behavior in repo and temp fixtures. |
| `schedule.yaml` | product/component model | `cmd_plan` output explanations and warnings | WIRED | Schedule entries are inventory item ids with `product` and `components` explanation context. |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Full split-model validation passes | `uv run planner.py check` | Exit 0, `All checks passed.` | PASS |
| Target substance check handles valid prefer_with | `uv run planner.py check data/substances/creatine.yaml` | Exit 0, `All checks passed.` | PASS |
| Malformed inventory reports schema errors without crashing | `uv run pytest tests/test_phase_02.py -k malformed_inventory -q` | Exit 0, regression asserts schema text and no traceback | PASS |
| Schedule generation succeeds | `uv run planner.py plan` | Exit 0, schedule written, quality 4/5, warnings 17 | PASS |
| Regression suite passes | `uv run pytest` | Exit 0, `17 passed` | PASS |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|-------------|-------------|--------|----------|
| Phase 2 roadmap goal | ROADMAP | Split YAML into Substance/Product/InventoryItem, migrate slots to near+food, keep products inseparable, add practical ontology | VERIFIED | Core model, scheduler, validator, tests, and generated schedule verified. |
| PHASE-02-GAP-VALIDATION | 02-05-PLAN.md | Close target-mode prefer_with and malformed inventory validation gaps | VERIFIED | `02-05-SUMMARY.md`, `planner.py`, and `tests/test_phase_02.py` contain the fixes and regressions. |

### Human Verification Required

None. This phase is CLI/YAML/test behavior and was verified programmatically.

### Gaps Summary

None. The previous validation gaps were closed by `02-05-PLAN.md`.

---
_Verified: 2026-05-05T20:45:00Z_
_Verifier: Codex inline GSD verification_
