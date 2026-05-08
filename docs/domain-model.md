# Domain Model

`supp-slotter` is a YAML-first supplement slot planner. It separates shelf state from product labels and substance scheduling rules.

## Core Objects

**Substance** (`data/substances/*.yaml`) is an active ingredient or concrete chemical/form. It owns scheduling traits, substance-level notes, aliases, and unresolved concerns. Use `form` when a named ingredient has distinct practical forms, for example `name: B6` plus `form: pyridoxine HCl`. Substance `id` is a stable opaque key such as `sub_3918fe347e`; it does not change when `name` or `form` changes. Filenames remain readable and include the stable id, for example `magnesium_glycinate__sub_7e02eab0d1.yaml`. Use `aliases` for abbreviations and synonyms such as `NAC`, `EPA`, or `Taxifolin`; aliases do not affect IDs.

**Product** (`data/products/*.yaml`) is a physical label-backed item. It owns `brand`, formula components, component labels/amounts when known, product description URLs, product notes, and label ambiguity. A product may contain one or many substances. Product `id` is a stable opaque key such as `prd_83dffd67bf`; it does not change when `brand` or `name` changes. Product filenames use readable parts plus the id, for example `minami_healthy_foods__nattokinase_13000fu__prd_83dffd67bf.yaml`; if the brand is genuinely unknown, use `unknown`.

**Inventory** (`data/inventory.yaml`) is only the operator's current products grouped by stack:

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

**Pillbox** (`data/pillboxes.yaml`) maps one inventory stack to one physical or logical organizer. A pillbox owns its slots. In this repository `daily_pillbox` serves the ordinary daily stack and `training_pillbox` serves workout-adjacent products.

**Trait** (`data/traits.yaml`) is a planner-facing scheduling rule or warning marker. Traits are declarative: the planner does not infer medical meaning, it only executes `effects`, `separate_from`, and `warning`. Broad benefit/risk groupings belong in goal clusters, not in traits.

**Slot** is an intake compartment inside a pillbox. Slots expose simple fields such as `near` and `food`; trait effects match against those fields.

**Goal cluster** (`data/goals/*.yaml`) is a purpose-driven cluster of substances. A cluster can describe a `benefit`, a `risk`, or both for the same member set. Goal clusters do not drive slot assignment; `planner.py plan` uses them for benefit coverage and risk-load review in generated `schedule.yaml`.

**Relation** (`data/relations.yaml`) is a centralized substance-to-substance link. Relations are grouped by type and may point either to a base `name` or to one concrete `sub_*` card.

[docs/ontology-facts.md](ontology-facts.md) stress-tests how supplement facts fit the ontology before they are encoded as traits, relations, or notes.

## Scheduling Semantics

The schedulable unit is the inventory product ID. Product components are kept together. The planner aggregates traits from component substances and applies centralized relations from `data/relations.yaml`, assigns active products to compatible slots inside the pillbox mapped to their inventory stack, applies `prefer_with` bonuses, blocks inter-product conflicts, and emits warnings for risks or intra-product conflicts.

`inactive` inventory items are validated as known products but are not scheduled.

`uv run planner.py plan` writes a full review schedule. `summary.take` is grouped by pillbox, so `daily_pillbox` is the ordinary recurring organizer and `training_pillbox` is workout-only timing. Each pillbox contains slots with `products` and expanded `substances`. If a substance has `form`, the form is shown in parentheses. The schedule also includes top-level `action_points`, grouped `review_contexts`, non-warning `placement_notes`, `benefits`, `risks`, `warnings`, `kept_together`, and per-product `explanations`. Do not edit `schedule.yaml` directly; edit source cards and regenerate it.

Active `unmatched_concerns` are surfaced as review warnings in `schedule.yaml`. This keeps uncertain or not-yet-modeled facts visible without forcing a new trait or relation type.

Goal-cluster output is review-only. Each goal cluster must define `benefit`, `risk`, or both. `taking` is the tracked member list used for benefit coverage and risk-load calculations. `candidates` lists substances worth considering later, and `declined` lists explicitly rejected substances. `benefits[].coverage_percent` counts `taking` substances currently active in scheduled inventory. `risks[].active_count` counts active risk-cluster members and emits a warning only when `risk.warning_threshold` is reached. Cluster entries separate active substances from `inactive` substances that exist on the shelf but are not scheduled and `missing` substances that are not in inventory. Goal clusters never affect slot assignment.

## Adding Data

Use the schemas as the final contract, but these are the smallest useful shapes:

```yaml
# data/substances/example.yaml
# id may be omitted for new cards; check/plan/doctor can generate it.
name: Example Substance
form: optional concrete form
aliases:
- EX
traits: []
notes: Short universal substance note.
```

```yaml
# data/products/example_product.yaml
# id may be omitted for new cards; check/plan/doctor can generate it.
brand: Example Brand
name: Example Product
urls:
- https://example.com/product
components:
- substance: <existing sub_* id>
  label: Label ingredient name
  amount: 100 mg
notes: Product label context or non-active facts.
```

```yaml
# data/inventory.yaml
stacks:
  daily:
  - <existing prd_* id>
  training: []
  inactive: []
```

```yaml
# data/pillboxes.yaml
pillboxes:
  daily_pillbox:
    label: Daily pillbox
    inventory_stack: daily
    slots:
      morning_food:
        label: Morning / with breakfast
        order: 1
        near: breakfast
        food: true
```

```yaml
# data/goals/example_goal.yaml
name: Example Goal
description: Why this cluster exists.
benefit:
  description: What useful coverage this cluster represents.
risk:
  description: What load or caution this same member set can create.
  warning_threshold: 2
  action: What to review when the threshold is reached.
taking:
- substance: <existing sub_* id>
  role: Why it belongs to the goal.
candidates:
- name: Candidate substance
  role: Why it may belong later.
declined:
- name: Rejected substance
  reason: Why it was rejected.
```

Practical order: create or update concrete substance cards first, then product cards, then inventory membership, then run `uv run planner.py plan`. Use `uv run planner.py doctor` to review cleanup candidates, not as an automatic todo list.

## Trait Ontology

`intake:*` is the explicit food-axis:

- `intake:food_required` blocks empty-stomach slots and strongly prefers food.
- `intake:food_preferred` softly prefers food.
- `intake:empty_preferred` strongly prefers empty-stomach slots and avoids food.
- `intake:fat_meal_required` approximates a fat-containing meal as `food: true`.
- `intake:food_neutral` is a marker that food state should not drive scheduling.

`class:*` is marker-only. It describes categories such as fat-soluble, mineral, and electrolyte, but does not score slots and is hidden from generated `review_tags`.

`risk:*` emits single-substance schedule warnings when assigned. Stack-level loads such as bleeding, blood pressure, cholinergic pressure, or other repeated mechanisms belong in goal clusters with a nested `risk` block.

`activity:*` handles workout timing. Products containing those substances should usually be placed in the `training` inventory stack, which maps to `training_pillbox`. The trait then prefers `pre_workout`, `post_workout`, or either workout slot through `near`.

`effect:*` is only for timing-relevant effects. For example, sleep-disruptive and energy-like effects can affect slots. Review-only effects such as nootropic or calming support belong in goal clusters.

Mechanism-only labels are not traits. If a mechanism matters for review, encode it as a benefit/risk cluster or a centralized relation.

## Substance Relations

`data/relations.yaml` declares explicit substance-to-substance links in one central place. Most relation types are stack-review warnings; `competes` also affects slot placement.

Supported relation types:

```yaml
balance:
- source_name: Zinc
  target_name: Copper
  reason: Long-term high-dose zinc supplementation can depress copper status.
  action: Review zinc/copper balance in long-term active stacks.

competes:
- source_name: Zinc
  target_name: Copper
  reason: Zinc and copper can compete for absorption when co-administered.

supports:
- source_name: Selenium
  target_name: N-Acetyl Cysteine
  reason: Selenium supports glutathione-related antioxidant defense with NAC.

antagonizes:
- source_substance: sub_a873e428ee
  target_name: Levodopa
  reason: Pyridoxine HCl can reduce levodopa effect in a specific medication context.
```

Endpoint fields define how broadly the relation applies:

- `source_name` / `target_name` apply to every active substance card with that exact `name`, regardless of `form`.
- `source_substance` / `target_substance` apply only to one concrete substance card.

Mixed endpoints are valid when only one side is form-specific, for example `source_substance` for pyridoxine HCl and `target_name` for all `Levodopa` cards.

Do not add relation mirrors. `balance` and `competes` are symmetric by planner semantics. `supports` and `antagonizes` are directional.

`balance` warns when one side is active and the paired side is absent from active products.

`supports` is supporter-to-target. This handles substances such as selenium or piperine that may support many targets. Review warnings are emitted when the target is active and the supporter is absent.

`competes` is a concrete scheduling relation between two substances. The planner avoids assigning products with competing substances to the same slot. If both substances are components of the same physical product, the product is kept together and the schedule gets an `intra_product_relation_conflict` warning.

`antagonizes` is an asymmetric review relation: the source can oppose or reduce the target's function in a practical stack-review context. It does not affect slot placement and does not calculate dose.

Relations may define optional `action` text for generated review output. Relations do not calculate dose, ratio, or medical inference.

## Ownership Rules

- Put product label facts in products.
- Fill product cards as richly as the label/source allows: components, component labels/forms, amounts, `urls`, and non-active label facts in `notes` or component `notes`. Do not invent missing label facts, and do not add fields outside the schema.
- If a product label gives a mineral salt/form, model that concrete form, for example `Magnesium (citrate)` or `Calcium (lactate)`. No-`form` mineral cards are only unknown-form fallbacks when the source does not disclose the form.
- Put universal scheduling behavior in substances and traits.
- Put all substance-to-substance links in `data/relations.yaml`, not in substance cards.
- Put only stack membership in inventory.
- Put actual intake history, per-day doses, adherence, reactions, or operator notes nowhere for now; that would be a separate journal model if it becomes needed.
- Do not add taxonomy unless the planner, validator, or warnings use it.

Use `uv run planner.py doctor` to list cleanup candidates: unused substances, products outside inventory, unused traits, clustered similar substance names, empty stacks, and stack/pillbox mismatches. Doctor findings are review hints; unused or similar does not always mean wrong.

Slot IDs must be unique across all pillboxes. The planner keeps slot IDs flat in explanations and tests, so `check` rejects duplicate slot IDs instead of silently namespacing them.

After changing product `brand`/`name` or substance `name`/`form`, keep the stable `id`. `uv run planner.py check`, `plan`, and `doctor` automatically generate missing card ids and rename product/substance files to the readable `...__id.yaml` form when that fix is deterministic.

## Non-Goals

This is not a medical ontology, dose engine, regimen tracker, evidence grader, or journal. Keep the model small unless a concrete planner behavior or data-maintenance problem requires more structure.
