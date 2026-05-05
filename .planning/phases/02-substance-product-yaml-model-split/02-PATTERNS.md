# Phase 02 Pattern Map

## PATTERN MAPPING COMPLETE

## Files and Existing Analogs

| Target | Role | Closest Existing Analog | Pattern to Reuse |
|--------|------|-------------------------|------------------|
| `schema/substance.schema.json` | Schema for universal substance cards | `schema/product.schema.json` | Draft 2020-12 JSON Schema, `additionalProperties: false`, strict id pattern |
| `schema/product.schema.json` | Schema for concrete formula cards | current `schema/product.schema.json` | Keep id/name/notes pattern, replace universal `traits` with `components[]` references |
| `schema/inventory.schema.json` | Inventory item schema | current `schema/inventory.schema.json` | Root `version` plus mapping under `supplements`; strict override fields |
| `schema/slots.schema.json` | Slot declarations | current `schema/slots.schema.json` | `slots` mapping with strict slot fields and enums |
| `data/substances/*.yaml` | Universal substance facts | current `data/products/*.yaml` | Same id/name/traits/notes authoring style |
| `data/products/*.yaml` | Concrete product formulas | current multicomponent cards such as `lions_mane_b6_complex.yaml` | Formula card with named components that reference substances |
| `data/inventory.yaml` | User shelf/protocol | current `data/inventory.yaml` | Preserve stack partition and operator override concept |
| `planner.py` | Loader, validator, scheduler | current `planner.py` | Reuse helper functions, check phases, scoring, explanations, warnings |
| `tests/test_phase_02.py` | Regression tests | `tests/test_phase_01.py` | `uv run planner.py check`/`plan` subprocess pattern with restore of generated schedule |

## Code Patterns

Current `cmd_check` flow:

1. Load slots and traits.
2. Validate schemas.
3. Derive slot fields from actual slots.
4. Validate trait namespaces and effect match keys.
5. Load all card files.
6. Validate inventory alignment and overrides.
7. Validate goal references.

Phase 2 should keep that shape but replace the single card registry with:

- `substance_ids: dict[str, Path]`
- `product_ids: dict[str, Path]`
- `inventory_ids: set[str]`

Current `cmd_plan` flow:

1. Run `cmd_check`.
2. Load slots, traits, inventory.
3. Build active candidates from inventory.
4. Compute effective traits.
5. Score candidate slots and skip blocked ones.
6. Assign and improve by local search.
7. Write `schedule.yaml` with explanations and warnings.

Phase 2 should keep that algorithm and change the candidate object from substance id to inventory item id with:

- `product_id`
- `component_substances`
- `effective_traits`
- `component_trait_sources`
- `stack`

## Landmines

- Do not keep `data/products/*.yaml` as substance cards under a compatibility reader.
- Do not let product components become schedulable units.
- Do not let goal references validate against products after the split.
- Do not add MCP, import workflow state, database, drafts, approvals, or web parsing.
- Do not leave slot trait effects matching removed fields like `time` or `activity`.

