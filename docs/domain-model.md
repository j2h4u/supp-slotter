# Domain Model

`supp-slotter` is a YAML-first supplement slot planner. It separates shelf state from product labels and substance scheduling rules.

## Core Objects

**Substance** (`data/substances/*.yaml`) is an active ingredient or concrete chemical/form. It owns scheduling traits, substance-level notes, and unresolved concerns. Use concrete forms when they matter, for example `b6_pyridoxal_5_phosphate` vs `b6_pyridoxine_hcl`.

**Product** (`data/products/*.yaml`) is a physical label-backed item. It owns `brand`, formula components, component labels/amounts when known, product notes, and label ambiguity. A product may contain one or many substances.

**Inventory** (`data/inventory.yaml`) is only the operator's current shelf grouped by stack:

```yaml
stacks:
  daily:
  - coenzyme_b_complex
  training:
  - electrolyte_caps
  inactive:
  - lions_mane
```

Inventory does not own brands, doses, notes, or trait overrides.

**Trait** (`data/traits.yaml`) is a planner-facing rule or marker. Current axes are `intake:*` for the food/empty/fat-meal axis, `competition:*_absorption` for explicit absorption conflicts, `risk:*` for warnings, `activity:*` for workout timing, `effect:*` for current effect/timing rules, `mechanism:*` for marker-only mechanisms, and `class:*` for marker-only categories.

**Slot** (`data/slots.yaml`) is a place/time where products can be assigned. Slots expose simple fields such as `stack`, `near`, and `food`; trait effects match against those fields.

**Goal** (`data/goals/*.yaml`) is a purpose-driven cluster of substances. Goals are descriptive and do not drive scheduling yet.

## Scheduling Semantics

The schedulable unit is the inventory product ID. Product components are kept together. The planner aggregates traits from all component substances, assigns active products to compatible slots, applies `prefer_with` bonuses, blocks inter-product conflicts, and emits warnings for risks or intra-product conflicts.

`inactive` inventory items are validated as known products but are not scheduled.

## Ownership Rules

- Put product label facts in products.
- Put universal scheduling behavior in substances and traits.
- Put only stack membership in inventory.
- Put actual intake history, per-day doses, adherence, reactions, or operator notes nowhere for now; that would be a separate journal model if it becomes needed.
- Do not add taxonomy unless the planner, validator, or warnings use it.

Use `uv run planner.py orphans` to list cleanup candidates: unused substances, products outside inventory, unused traits, empty stacks, and stack/slot mismatches.

## Non-Goals

This is not a medical ontology, dose engine, regimen tracker, evidence grader, or journal. Keep the model small unless a concrete planner behavior or data-maintenance problem requires more structure.
