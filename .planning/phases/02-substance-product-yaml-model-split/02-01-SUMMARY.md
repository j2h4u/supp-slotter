---
phase: 02-substance-product-yaml-model-split
plan: 01
subsystem: data-model
tags: [yaml, json-schema, supplements, ontology, inventory]

requires:
  - phase: 01-training-stacks-goals-ontology
    provides: stack-aware inventory, goal refs, activity slots
provides:
  - strict substance/product/inventory/slot schemas
  - direct YAML migration to substances, product formulas, and inventory product refs
  - declarative slots using stack, near, and food fields
  - practical mechanism, warning, intake, and family traits
affects: [planner, validation, schedule-generation, goals]

tech-stack:
  added: []
  patterns:
    - universal facts live in data/substances
    - product cards are concrete formulas with component substance refs
    - inventory rows reference product formulas and carry operator overrides
    - trait effects match slot near/food fields

key-files:
  created:
    - schema/substance.schema.json
    - data/substances/*.yaml
  modified:
    - schema/product.schema.json
    - schema/inventory.schema.json
    - schema/slots.schema.json
    - schema/traits.schema.json
    - data/products/*.yaml
    - data/inventory.yaml
    - data/slots.yaml
    - data/traits.yaml

key-decisions:
  - "Migrated directly to the Phase 2 target YAML shape with no compatibility adapter or dual-read path."
  - "Kept prefer_with only on substances and moved creatine -> l_citrulline_malate there."
  - "Represented product-level practical scheduling as inventory overrides when the fact is not universal to each component substance."

patterns-established:
  - "Substance cards carry traits, notes, unmatched_concerns, and substance-only prefer_with."
  - "Product formula cards carry id, name, and non-empty components with substance refs."
  - "Slots expose only label, order, stack, near, and food."

requirements-completed: []

duration: 7min
completed: 2026-05-05
---

# Phase 02 Plan 01: Substance/Product YAML Model Split Summary

**Direct YAML migration from substance-like product cards to universal substances, concrete product formulas, inventory product refs, near/food slots, and practical warning traits.**

## Performance

- **Duration:** 7 min
- **Started:** 2026-05-05T18:47:29Z
- **Completed:** 2026-05-05T18:54:43Z
- **Tasks:** 4
- **Files modified:** 88

## Accomplishments

- Added `schema/substance.schema.json` and rewrote product, inventory, slot, and trait schemas for the Phase 2 target model.
- Created `data/substances/` and converted `data/products/*.yaml` into concrete formula cards without top-level universal `traits` or `prefer_with`.
- Decomposed combination formulas including nattokinase+B6+B12, Lion's Mane+B6, dihydroquercetin+A/C/E, B-complex, electrolyte caps, and trace minerals.
- Rewrote slots to six declarative `near + food` slots.
- Added practical mechanism/risk/intake traits and applied them to substances or inventory overrides.

## Task Commits

1. **Task 1: Create strict Substance/Product/Inventory schemas** - `03f7d6a` (feat)
2. **Task 2: Move universal cards into data/substances and rewrite products as formulas** - `452266a` (feat)
3. **Task 3: Rewrite inventory and slots to the target YAML shape** - `5fff2ad` (feat)
4. **Task 4: Update practical ontology traits to match near + food** - `cc2ebb3` (feat)

## Files Created/Modified

- `schema/substance.schema.json` - new universal substance card schema.
- `schema/product.schema.json` - product formulas with component substance refs.
- `schema/inventory.schema.json` - inventory rows require `product` and `stack`.
- `schema/slots.schema.json` - slot schema uses `near` enum and `food`.
- `schema/traits.schema.json` - trait matches are constrained to `near` and `food`.
- `data/substances/*.yaml` - universal substance cards and decomposed component substances.
- `data/products/*.yaml` - concrete product formula cards.
- `data/inventory.yaml` - inventory product refs and operator overrides.
- `data/slots.yaml` - six physical slots using `near` and `food`.
- `data/traits.yaml` - near/food scheduling effects and practical ontology additions.

## Decisions Made

- Inventory-facing product ids were preserved, including `nattokinase`, `coenzyme_b_complex`, `lions_mane_b6_complex`, and `dihydroquercetin_complex`.
- B-complex meal tolerance is an inventory override, not a universal trait copied to every B-vitamin component.
- Electrolyte caps and trace minerals were explicitly decomposed because they are existing multicomponent formulas.
- Product formula notes were kept formula-specific so universal substance facts live under `data/substances`.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

`uv run planner.py check` fails after this plan because `planner.py` still has the old namespace registry and does not include `mechanism`. This is expected by the plan-level verification; later Phase 2 plans update planner behavior.

## Verification

- PASS Task 1 acceptance criteria: schema file-shape checks for `substance`, `components`, `product`, `near`, `workout_before`, removed `time`/`activity`, and substance-only `prefer_with`.
- PASS Task 2 acceptance criteria: `data/substances` exists, nattokinase/B6/B12 substances exist, combination formulas contain required component refs, product cards have no top-level `traits` or `prefer_with`, and inventory has the B-complex override.
- PASS Task 3 acceptance criteria: inventory has `product`, no `active`, slots include all six `near` values, and slots have no `time` or `activity`.
- PASS Task 4 acceptance criteria: new mechanism/risk/intake traits exist, effects use `near`, and no trait effect matches `time` or `activity`.
- PASS JSON schema and YAML parse smoke test.
- PASS product component refs resolve to substance cards and inventory product refs resolve to product cards.
- EXPECTED FAIL `uv run planner.py check`: `mechanism:*` namespace is not registered in `planner.py` yet.

## Known Stubs

None.

## Threat Flags

None - this plan changes local YAML/schema files only and introduces no new network endpoint, auth path, file access pattern, or schema trust boundary beyond the planned local YAML model.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

The YAML target shape is in place for the next Phase 2 plans to update planner loading, validation, scoring, and generated schedule output.

## Self-Check: PASSED

- Found summary file path after creation.
- Found commits: `03f7d6a`, `452266a`, `5fff2ad`, `cc2ebb3`.
- Verified created `schema/substance.schema.json` and `data/substances/`.
- Verified acceptance criteria and local data reference sanity checks.

---
*Phase: 02-substance-product-yaml-model-split*
*Completed: 2026-05-05*
