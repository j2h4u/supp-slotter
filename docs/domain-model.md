# Domain Model

`supp-slotter` is a YAML-first supplement slot planner. It separates shelf state from product labels and substance scheduling rules.

## Core Objects

**Substance** (`data/substances/*.yaml`) is an active ingredient or concrete chemical/form. It owns scheduling traits, substance-level notes, aliases, unresolved concerns, and simple relations to other substances. Use `form` when a named ingredient has distinct practical forms, for example `name: B6` plus `form: pyridoxine HCl`. Substance `id` is a stable opaque key such as `sub_3918fe347e`; it does not change when `name` or `form` changes. Filenames remain readable and include the stable id, for example `magnesium_glycinate__sub_7e02eab0d1.yaml`. Use `aliases` for abbreviations and synonyms such as `NAC`, `EPA`, or `Taxifolin`; aliases do not affect IDs.

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

**Goal** (`data/goals/*.yaml`) is a purpose-driven cluster of substances. Goals do not drive slot assignment; `planner.py plan` uses them for coverage review in generated `schedule.yaml`.

[docs/ontology-facts.md](ontology-facts.md) stress-tests how supplement facts fit the ontology before they are encoded as traits, relations, or notes.

## Scheduling Semantics

The schedulable unit is the inventory product ID. Product components are kept together. The planner aggregates traits and scheduling relations from all component substances, assigns active products to compatible slots, applies `prefer_with` bonuses, blocks inter-product conflicts, and emits warnings for risks or intra-product conflicts.

`inactive` inventory items are validated as known products but are not scheduled.

`uv run planner.py plan` writes a full review schedule. Each slot has a `products` list with scheduled product names and a `substances` list with expanded substance names. If a substance has `form`, the form is shown in parentheses. The schedule also includes top-level `summary`, `action_points`, `goals`, `warnings`, `kept_together`, and per-product `explanations`. Do not edit `schedule.yaml` directly; edit source cards and regenerate it.

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
# data/goals/example_goal.yaml
name: Example Goal
description: Why this cluster exists.
status: active
members:
- substance: <existing sub_* id>
  status: taking
  role: Why it belongs to the goal.
```

Practical order: create or update concrete substance cards first, then product cards, then inventory membership, then run `uv run planner.py plan`. Use `uv run planner.py doctor` to review cleanup candidates, not as an automatic todo list.

## Trait Ontology

`intake:*` is the explicit food-axis:

- `intake:food_required` blocks empty-stomach slots and strongly prefers food.
- `intake:food_preferred` softly prefers food.
- `intake:empty_preferred` strongly prefers empty-stomach slots and avoids food.
- `intake:fat_meal_required` approximates a fat-containing meal as `food: true`.
- `intake:food_neutral` is a marker that food state should not drive scheduling.

`class:*` is marker-only. It describes categories such as fat-soluble, mineral, and electrolyte, but does not score slots.

`risk:*` emits schedule warnings when assigned. Unused risk traits are not kept as reserved taxonomy.

`activity:*` handles workout timing. `activity:post_workout` currently remains unused and is reported by `planner.py doctor`.

`effect:*` still mixes effect labels and timing behavior. It is intentionally left unchanged for now; `effect:sleep_disruptive` is unused and reported by `planner.py doctor`.

`mechanism:*` is marker-only. It documents mechanisms such as vasodilator, nitric-oxide precursor, and fibrinolytic.

## Substance Relations

`relations` declares explicit substance-to-substance links. Most relation types are stack-review warnings; `competes` also affects slot placement.

Supported relation types:

```yaml
relations:
- type: balance
  substances:
  - sub_844a0cc551
  reason: Long-term high-dose zinc supplementation can depress copper status.
- type: supports
  substances:
  - sub_d997f98e03
  reason: Selenium supports glutathione-related antioxidant defense with NAC.
- type: supported_by
  substances:
  - sub_59bza5s7h0
  reason: NAC is paired with selenium in this stack.
- type: competes
  substances:
  - sub_844a0cc551
  reason: Zinc and copper can compete for absorption when co-administered.
- type: antagonizes
  substances:
  - sub_shib6nr9jc
  reason: High-dose vitamin E can antagonize vitamin K-dependent clotting factors.
- type: antagonized_by
  substances:
  - sub_844a87d72b
  reason: High-dose vitamin E can antagonize vitamin K-dependent clotting factors.
```

Relations are deliberately written on both substance cards for human and agent authoring convenience. `planner.py check` enforces mirrors:

- `A balance B` must be mirrored as `B balance A`.
- `A supports B` must be mirrored as `B supported_by A`.
- `B supported_by A` must be mirrored as `A supports B`.
- `A competes B` must be mirrored as `B competes A`.
- `A antagonizes B` must be mirrored as `B antagonized_by A`.
- `B antagonized_by A` must be mirrored as `A antagonizes B`.

Use `supported_by` when editing the main or target substance card and asking "what supports this substance?". Use `supports` when editing the cofactor, enhancer, or supporter card and asking "what does this substance support?". Use `balance` on both cards when the stack should review the pair together.

`balance` is source-active: when a substance with a balance relation is active but a related substance is absent from active products, `planner.py doctor` and `planner.py plan` emit a warning.

`supports` is supporter-to-many: the card that provides support lists the substances it can support. This handles substances such as selenium or piperine that may support many targets. Review warnings can be derived from this mirrored support pair when the target is active and the supporter is absent; mirror checks keep the target-side `supported_by` relation aligned for human editing.

`competes` is a concrete scheduling relation between two substances. The planner avoids assigning products with competing substances to the same slot. If both substances are components of the same physical product, the product is kept together and the schedule gets an `intra_product_relation_conflict` warning.

`antagonizes` is an asymmetric review relation: the source can oppose or reduce the target's function in a practical stack-review context. It does not affect slot placement and does not calculate dose.

Relations do not calculate dose, ratio, or medical inference.

## Ownership Rules

- Put product label facts in products.
- Fill product cards as richly as the label/source allows: components, component labels/forms, amounts, `urls`, and non-active label facts in `notes` or component `notes`. Do not invent missing label facts, and do not add fields outside the schema.
- Put universal scheduling behavior in substances and traits.
- Put only stack membership in inventory.
- Put actual intake history, per-day doses, adherence, reactions, or operator notes nowhere for now; that would be a separate journal model if it becomes needed.
- Do not add taxonomy unless the planner, validator, or warnings use it.

Use `uv run planner.py doctor` to list cleanup candidates: unused substances, products outside inventory, unused traits, clustered similar substance names, empty stacks, and stack/slot mismatches. Doctor findings are review hints; unused or similar does not always mean wrong.

After changing product `brand`/`name` or substance `name`/`form`, keep the stable `id`. `uv run planner.py check`, `plan`, and `doctor` automatically generate missing card ids and rename product/substance files to the readable `...__id.yaml` form when that fix is deterministic.

## Non-Goals

This is not a medical ontology, dose engine, regimen tracker, evidence grader, or journal. Keep the model small unless a concrete planner behavior or data-maintenance problem requires more structure.
