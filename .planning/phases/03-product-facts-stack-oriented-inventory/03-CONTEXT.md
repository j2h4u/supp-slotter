# Phase 03: Product Facts + Stack-Oriented Inventory - Context

**Gathered:** 2026-05-05
**Status:** Ready for planning
**Source:** Chat decisions after Phase 2 verification/security closure

<domain>
## Phase Boundary

Phase 3 corrects data ownership and YAML ergonomics after the Phase 2
Substance/Product/Inventory split.

This phase does not redesign the scheduler. It keeps the existing three-entity
model:

- `data/substances/*.yaml` - universal substance/form cards and scheduling traits.
- `data/products/*.yaml` - concrete product label/formula facts.
- `data/inventory.yaml` - the operator's shelf and use-state grouping.

</domain>

<decisions>
## Locked Decisions

### Inventory Shape

- `data/inventory.yaml` must become stack-oriented at the top level:
  `stacks.daily`, `stacks.training`, and `stacks.inactive`.
- Each stack contains item ids as keys, with item data under each key.
- `stack` must no longer be repeated inside every inventory item.
- The planner may normalize this shape internally to keep scheduling code simple.

### Product Fact Ownership

- `brand` is a product fact and belongs in `data/products/*.yaml`, not in
  `data/inventory.yaml`.
- Label facts such as component form and amount belong in product cards, usually
  on `components[].label`, `components[].amount`, and `components[].notes`.
- Inventory should keep only shelf/use-state data:
  product reference, stack grouping, operator notes, and inventory-specific trait
  overrides when needed.
- Do not add `regimen.yaml`; it is currently YAGNI.
- Do not introduce broad product sourcing metadata unless needed by current
  validation or label-fact ownership. If a source field is needed, keep it
  minimal and optional.

### Vitamin B6 Forms

- The existing `vitamin_b6` substance is too generic for current products.
- Split concrete B6 forms into file names that sort/read clearly:
  - `b6_pyridoxal_5_phosphate`
  - `b6_pyridoxine_hcl`
- `coenzyme_b_complex` must reference `b6_pyridoxal_5_phosphate`.
- `lions_mane_b6_complex` must reference `b6_pyridoxine_hcl`.
- Do not add `class:b_vitamin` or `family:vitamin_b6` unless a planner,
  validator, or warning rule actually uses it. Right now it is taxonomy noise.
- Traits are added only when they drive scheduling, validation, warnings, or
  explanations.

### YAGNI / KISS Constraints

- No separate regimen model in this phase.
- No dose equivalence modeling.
- No medical upper-limit math.
- No broad nutrient ontology cleanup beyond concrete B6 forms needed by current
  products.
- Do not infer label amounts. Move/record only facts supported by current files
  or explicit labels; otherwise record an unresolved concern.

</decisions>

<canonical_refs>
## Canonical References

Downstream agents must read these before planning or implementing.

### Current Model

- `.planning/PROJECT.md` - current project state and non-goals.
- `.planning/ROADMAP.md` - phase ordering and Phase 3 goal.
- `.planning/STATE.md` - Phase 2 decisions and accumulated context.
- `.planning/phases/02-substance-product-yaml-model-split/02-VERIFICATION.md` - current verified Phase 2 behavior.
- `.planning/phases/02-substance-product-yaml-model-split/02-SECURITY.md` - closed threat register.

### Data and Schemas

- `schema/inventory.schema.json` - current inventory item schema with per-item stack/brand/dose fields.
- `schema/product.schema.json` - current product formula schema with optional brand and component labels/amounts.
- `schema/substance.schema.json` - substance-card schema.
- `data/inventory.yaml` - current shelf data that must become stack-oriented.
- `data/products/*.yaml` - concrete product formula cards to receive product facts.
- `data/substances/vitamin_b6.yaml` - generic B6 card to replace with concrete forms.

### Runtime and Tests

- `planner.py` - validation, refresh, and scheduling loaders.
- `tests/test_phase_01.py` - stack topology regression.
- `tests/test_phase_02.py` - split-model/product-inseparability regressions.

</canonical_refs>

<specifics>
## Specific Ideas

- Desired inventory shape:

```yaml
version: 1
stacks:
  daily:
    vitamin_d3:
      product: vitamin_d3
  training:
    creatine:
      product: creatine
  inactive:
    lions_mane:
      product: lions_mane
```

- `trace_minerals` is already a multi-component product and should stay a
  product. It currently has ten components: zinc, copper, manganese, selenium,
  chromium, molybdenum, iodine, boron, vanadium, and silica.
- Product-card completeness is currently thin: inventory has brand/dose fields
  that belong to product cards when they are label facts.

</specifics>

<deferred>
## Deferred Ideas

- Separate `regimen.yaml`.
- Dose normalization or nutrient equivalence math.
- General vitamin-family taxonomy.
- Broad label-source/vendor/marketplace modeling unless it is needed to keep
  current product facts honest.

</deferred>

---

*Phase: 03-product-facts-stack-oriented-inventory*
*Context gathered: 2026-05-05 via chat decisions*
