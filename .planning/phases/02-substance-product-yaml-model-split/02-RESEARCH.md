# Phase 02 Research: Substance/Product YAML model split

## RESEARCH COMPLETE

## Planning-Relevant Findings

Phase 2 is a direct YAML data-model migration. There is no external compatibility contract, so plans should move the repo directly to the target shape instead of introducing dual readers or compatibility adapters.

The current `data/products/*.yaml` directory mostly contains substance-like cards. The new shape should make the domain split explicit:

- `data/substances/*.yaml`: universal facts about active ingredients, nutrients, mechanisms, scheduling traits, risks, and notes.
- `data/products/*.yaml`: concrete formulas/bottles, with `components[]` that reference substances.
- `data/inventory.yaml`: user shelf/protocol items, each referencing one product and carrying stack, dose, brand, active/inactive state through `stack`, and operator overrides.

The current planner already has useful foundations:

- `load_yaml`, `load_schema`, `schema_errors`, and `report` are reusable.
- Trait effects are generic AND matches against slot fields, so `near` and `food` fit the current scoring design.
- `cmd_check` is the natural place for reference validation: product component -> substance, inventory item -> product, goal member -> substance.
- `cmd_plan` already builds active candidates, scores slots, enforces `separate_from`, writes explanations, and emits warning traits.

## Target Slot Model

Keep physical slot declarations small:

- `near: wake`, `food: false` for the first daily empty slot.
- `near: breakfast`, `food: true` for the first food slot.
- `near: day_meal`, `food: true` for the second food slot.
- `near: sleep`, `food: false` for the last daily empty slot.
- `near: workout_before`, `food: false` and `near: workout_after`, `food: false` for training slots.

The existing `stack` field should remain because Phase 1 verified daily/training partitioning. Replace slot timing fields such as `time` and `activity` with `near`, rather than adding `proximity`, `anchor`, `phase`, or `meal_anchor`.

## Ontology Scope

The ontology should improve only where it changes scheduling, warnings, or explanations. Practical first-pass additions:

- `mechanism:vasodilator`
- `mechanism:no_precursor`
- `mechanism:fibrinolytic`
- `risk:hypotension_stack`
- `risk:fibrinolytic_bleeding`
- `risk:antiplatelet_bleeding`
- `risk:hyperkalemia_med_interaction`
- `risk:dose_monitoring`
- `risk:narrow_therapeutic_window`
- `family:copper_like`
- `intake:requires_fat_containing_meal`
- `intake:with_water_or_food`
- `intake:food_neutral`

Risk traits should use `warning: true` when they should appear in `schedule.yaml` warnings. Mechanism traits can be pure markers unless they directly affect scheduling.

## Product Formula Rules

Products are physically inseparable. The planner should aggregate component substance traits and inventory overrides into one schedulable unit. If components compete, the planner must not split them into separate slots; it should schedule the product/inventory item and emit a product/inventory warning that names the competing traits.

The concrete Phase 2 example is the current nattokinase shelf item. Its product formula should include nattokinase plus vitamin B6 and vitamin B12 components. Nattokinase carries the empty-stomach/fibrinolytic facts as a substance; B6/B12 have separate substance cards; the product binds them into one physical item.

## Execution Risks

- Goal cards currently refer to product-card ids even though their field is named `substance`. After the split, goal members should continue to refer to substances and validation should use `data/substances`.
- Schedule output currently lists substance ids. After the split it should list inventory item ids or product ids consistently, and explanations should show aggregated component substance reasons.
- `cmd_refresh` currently discovers product cards and adds inventory rows. With inventory rows now referencing products, refresh should discover products without inventory rows and create inactive inventory entries with `product: <product_id>`.
- Tests from Phase 1 should be rewritten around product/inventory ids while preserving the verified topology guarantees.

