# Domain Model

`supp-slotter` is a YAML-first supplement slot planner. It separates shelf state from product labels and substance scheduling rules.

## Core Objects

**Substance** (`data/substances/*.yaml`) is an active ingredient or concrete chemical/form. It owns scheduling traits, substance-level notes, aliases, and unresolved concerns. Use `form` when a named ingredient has distinct practical forms, for example `name: B6` plus `form: pyridoxine HCl`. Substance `id` is a stable opaque key such as `sub_3918fe347e`; it does not change when `name` or `form` changes. Filenames remain readable and include the stable id, for example `magnesium_glycinate__sub_7e02eab0d1.yaml`. Use `aliases` for abbreviations and synonyms such as `NAC`, `EPA`, or `Taxifolin`; aliases do not affect IDs.

**Product** (`data/products/*.yaml`) is a physical label-backed item. It owns `brand`, formula components, component labels/amounts when known, product description URLs, product notes, and label ambiguity. A product may contain one or many substances. Product `id` is a stable opaque key such as `prd_83dffd67bf`; it does not change when `brand` or `name` changes. Product filenames use readable parts plus the id, for example `minami_healthy_foods__nattokinase_13000fu__prd_83dffd67bf.yaml`; if the brand is genuinely unknown, use `unknown`.

**Inventory** (`data/inventory.yaml`) is only the operator's current shelf grouped by stack:

```yaml
stacks:
  daily:
  - prd_bb212cffc2
  training:
  - prd_20bf2df267
  inactive:
  - prd_a6342d7725
```

Inventory does not own brands, doses, notes, or trait overrides.

**Trait** (`data/traits.yaml`) is a planner-facing rule or marker. Traits are declarative: the planner does not infer medical meaning, it only executes `effects`, `separate_from`, and `warning`.

**Slot** (`data/slots.yaml`) is a place/time where products can be assigned. Slots expose simple fields such as `stack`, `near`, and `food`; trait effects match against those fields.

**Goal** (`data/goals/*.yaml`) is a purpose-driven cluster of substances. Goals are descriptive and do not drive scheduling yet.

## Scheduling Semantics

The schedulable unit is the inventory product ID. Product components are kept together. The planner aggregates traits from all component substances, assigns active products to compatible slots, applies `prefer_with` bonuses, blocks inter-product conflicts, and emits warnings for risks or intra-product conflicts.

`inactive` inventory items are validated as known products but are not scheduled.

`uv run planner.py plan` writes a full review schedule. Each slot has a `products` list with scheduled product IDs and a `substances` list with expanded substance names. If a substance has `form`, the form is shown in parentheses.

## Trait Ontology

`intake:*` is the explicit food-axis:

- `intake:food_required` blocks empty-stomach slots and strongly prefers food.
- `intake:food_preferred` softly prefers food.
- `intake:empty_preferred` strongly prefers empty-stomach slots and avoids food.
- `intake:fat_meal_required` approximates a fat-containing meal as `food: true`.
- `intake:food_neutral` is a marker that food state should not drive scheduling.

`competition:*_absorption` declares explicit absorption conflicts. It is not a biological family taxonomy. Current conflict groups are magnesium, calcium, zinc, and copper absorption; only declared `separate_from` edges affect scheduling.

`class:*` is marker-only. It describes categories such as fat-soluble, mineral, and electrolyte, but does not score slots.

`risk:*` emits schedule warnings when assigned. Unused risk traits are not kept as reserved taxonomy.

`activity:*` handles workout timing. `activity:post_workout` currently remains unused and is reported by `planner.py doctor`.

`effect:*` still mixes effect labels and timing behavior. It is intentionally left unchanged for now; `effect:sleep_disruptive` is unused and reported by `planner.py doctor`.

`mechanism:*` is marker-only. It documents mechanisms such as vasodilator, nitric-oxide precursor, and fibrinolytic.

## Ownership Rules

- Put product label facts in products.
- Put universal scheduling behavior in substances and traits.
- Put only stack membership in inventory.
- Put actual intake history, per-day doses, adherence, reactions, or operator notes nowhere for now; that would be a separate journal model if it becomes needed.
- Do not add taxonomy unless the planner, validator, or warnings use it.

Use `uv run planner.py doctor` to list cleanup candidates: unused substances, products outside inventory, unused traits, empty stacks, and stack/slot mismatches.

After changing product `brand`/`name` or substance `name`/`form`, keep the stable `id`. `uv run planner.py check`, `plan`, and `doctor` automatically generate missing card ids and rename product/substance files to the readable `...__id.yaml` form when that fix is deterministic.

## Non-Goals

This is not a medical ontology, dose engine, regimen tracker, evidence grader, or journal. Keep the model small unless a concrete planner behavior or data-maintenance problem requires more structure.
