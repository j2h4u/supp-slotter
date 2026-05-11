# Domain Model

`supp-slotter` is a YAML-first supplement slot planner. It separates shelf state from product labels and substance scheduling rules.

## Core Objects

**Substance** (`data/substances/*.yaml`) is an active ingredient or concrete chemical/form. It owns scheduling traits, substance-level notes, aliases, and unresolved concerns. Use `form` when a named ingredient has distinct practical forms, for example `name: B6` plus `form: pyridoxine HCl`. Substance `id` is a stable opaque key such as `sub_3918fe347e`; it does not change when `name` or `form` changes. Filenames remain readable and include the stable id, for example `magnesium_glycinate__sub_7e02eab0d1.yaml`. Use `aliases` for abbreviations and synonyms such as `NAC`, `EPA`, or `Taxifolin`; aliases do not affect IDs.

**Product** (`data/products/*.yaml`) is a physical label-backed item. It owns `brand`, formula components, component labels/amounts when known, product description URLs, product notes, and label ambiguity. A product may contain one or many substances. Product `id` is a stable opaque key such as `prd_83dffd67bf`; it does not change when `brand` or `name` changes. Product filenames use readable parts plus the id, for example `minami_healthy_foods__nattokinase_13000fu__prd_83dffd67bf.yaml`; if the brand is genuinely unknown, use `unknown`.

**Stacks** (`data/stacks.yaml`) are only the operator's current products grouped by stack:

```yaml
daily:
- prd_bb212cffc2
training:
- prd_20bf2df267
inactive:
- prd_a6342d7725
```

Stacks do not own brands, doses, notes, or trait overrides.

**Pillbox** (`data/pillboxes.yaml`) maps one stack to one physical or logical organizer. A pillbox owns its slots. In this repository `daily` serves the ordinary daily stack and `training` serves workout-adjacent products.

**Trait** (`data/traits.yaml`) is a planner-facing scheduling rule or warning marker. The file is grouped by namespace (`is`, `intake`, `effect`, `risk`, `activity`, `dashboard`) to keep the checklist readable. Substance cards carry trait information as top-level namespace keys holding arrays of bare slugs. For example, a substance with one food rule, one intrinsic class, and one dashboard membership looks like:

```yaml
is:
- adaptogen
intake:
- empty_preferred
dashboard:
- cortisol_reduction
```

Traits are declarative: the planner does not infer medical meaning, it only executes `effects`, `separate_from`, and `warning`. Broad benefit/risk groupings belong in dashboard clusters, expressed via `dashboard:` tags on substance cards — not as flat prefixed strings.

**Slot** is an intake compartment inside a pillbox. Slots expose simple fields such as `near` and `food`; trait effects match against those fields.

**Dashboard cluster** (`data/dashboards/*.yaml`) is a purpose-driven cluster of substances. A cluster can describe a `benefit`, a `risk`, or both for the same member set. Dashboard clusters do not drive slot assignment; `python -m planner plan` uses them for benefit coverage and risk-load review in generated `schedule.yaml`.

Cluster membership is computed via `from_traits:` rather than an explicit member list. The dashboard yaml declares which (namespace, slug) pairs identify members; the planner scans substance cards and collects every substance whose grouped namespace fields contain a matching slug. To add a substance to a cluster, add the appropriate `dashboard:<slug>` tag to the substance card — do not edit the dashboard yaml's member list, because there is no member list. The dashboard yaml is a narrative wrapper (name, description, benefit/risk text) plus the `from_traits:` projection rule.

A substance is a member of dashboard D if there exists at least one (namespace N, slug S) pair where N appears as a key in D.`from_traits`, S appears in D.`from_traits[N]`, and S appears in the substance's per-namespace field for N. Resolution is union (logical OR) across the entire `from_traits` object. There is NO AND semantic across namespace groups — mixing namespaces in one `from_traits` widens membership, never narrows it.

**Relation** (`data/relations.yaml`) is a centralized substance-to-substance link. Relations are grouped by type and may point either to a base `name` or to one concrete `sub_*` card.

[docs/ontology-facts.md](ontology-facts.md) stress-tests how supplement facts fit the ontology before they are encoded as traits, relations, or notes.

## Scheduling Semantics

The schedulable unit is the product ID listed in `data/stacks.yaml`. Product components are kept together. The planner aggregates traits from component substances and applies centralized relations from `data/relations.yaml`, assigns active products to compatible slots inside the pillbox mapped to their stack, applies `prefer_with` bonuses, blocks inter-product conflicts, and emits warnings for risks or intra-product conflicts.

`inactive` stack items are validated as known products but are not scheduled.

`uv run python -m planner plan` writes a full review schedule. `summary.take` is grouped by pillbox, so `daily` is the ordinary recurring organizer and `training` is workout-only timing. Each pillbox contains slots with `products` and expanded `substances`. If a substance has `form`, the form is shown in parentheses. The schedule also includes non-warning `placement_notes`, `benefits`, `risks`, `warnings`, `kept_together`, and per-product `explanations`. Do not edit `schedule.yaml` directly; edit source cards and regenerate it.

Active `concerns` of kind `safety` are surfaced as review warnings in `schedule.yaml`. Use `python -m planner audit` to see all concerns grouped by kind (safety / data_quality / model_gap). This keeps uncertain or not-yet-modeled facts visible without forcing a new trait or relation type.

Dashboard-cluster output is review-only. Each dashboard cluster must define `benefit`, `risk`, or both. Cluster membership is computed at plan time from `from_traits:` — the planner resolves members dynamically and separates them into `covered` (active), `inactive` (on shelf but not scheduled), and `missing` (not in stacks). Dashboard clusters never affect slot assignment.

## Adding Data

Use the schemas as the final contract, but these are the smallest useful shapes:

```yaml
# data/substances/example.yaml
# id may be omitted for new cards; check/plan/doctor can generate it.
name: Example Substance
form: optional concrete form
aliases:
- EX
# Namespace keys hold arrays of bare slugs. Omit any namespace that does not apply.
# intake: is mutually exclusive (maxItems: 1). is:, effect:, risk:, dashboard: are polyhierarchical.
is:
- adaptogen          # intrinsic biochemical class (polyhierarchical — multiple allowed)
intake:
- empty_preferred    # food-state rule (mutually exclusive — at most one per substance)
dashboard:
- cortisol_reduction # operator-curated cluster membership (polyhierarchical)
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
# data/stacks.yaml
daily:
- <existing prd_* id>
training: []
inactive: []
```

```yaml
# data/pillboxes.yaml
daily:
  label: Daily
  slots:
    morning_food:
      label: Morning / with breakfast
      order: 1
      near: breakfast
      food: true
```

```yaml
# data/traits.yaml
intake:
  food_preferred:
    label: Prefers food
    description: Food improves tolerance or practical use.
    applies_when: Use when food mainly reduces nausea or irritation.
    effects:
    - match: {food: true}
      level: prefer
```

```yaml
# data/dashboards/example_dashboard.yaml
name: Example Dashboard
description: Why this cluster exists.
benefit:
  description: What useful coverage this cluster represents.
risk:
  description: What load or caution this same member set can create.
# from_traits: declares membership — the planner resolves members dynamically from substance cards.
# Resolution is union (logical OR): a substance joins if it matches ANY listed (namespace, slug) pair.
from_traits:
  dashboard:
  - example_cluster   # matches substances with dashboard: [example_cluster] on their card
```

Practical order: create or update concrete substance cards first, then product cards, then stack membership, then run `uv run python -m planner plan`. Use `uv run python -m planner doctor` to review cleanup candidates, not as an automatic todo list.

## Trait Ontology

Substance cards carry trait information as top-level namespace keys. Each namespace has a defined cardinality and scheduling role.

**`is:` — intrinsic biochemical class.** Polyhierarchical (no cardinality limit). Describes what a substance *is* at the chemistry or pharmacology level. `is:` is a review-classification axis — it does not influence slot assignment or scoring. Slugs map to the intrinsic-class set registered in `data/traits.yaml`. Current slugs:

- `fat_soluble` — vitamins A, D, E, K and fat-soluble carotenoids or oils.
- `mineral` — Mg, Ca, Fe, Zn, K, Cu, Se, I, and related minerals.
- `electrolyte` — Na, K, Cl, and similar electrolyte ions.
- `adaptogen` — stress-modulating botanicals such as Ashwagandha, Rhodiola, Holy Basil, Bacopa, and Panax ginseng.
- `antioxidant` — direct free-radical scavengers and antioxidant-pathway substances such as NAC, quercetin, resveratrol, lipoic acid, and L-ergothioneine. Fat-soluble antioxidants such as CoQ10 or astaxanthin may carry both `fat_soluble` and `antioxidant`.
- `ergogenic` — workout-performance substances such as creatine, L-carnitine, L-citrulline, HICA, and beta-alanine.
- `nootropic` — cognitive-support substances such as Alpha-GPC, Lion's Mane, Ginkgo, and Huperzia serrata. Adaptogens with strong cognitive evidence may carry both `adaptogen` and `nootropic`.
- `omega3` — EPA, DHA, and direct EPA/DHA sources such as krill oil. Not for ALA-only sources.

**`intake:` — food-state scheduling rule.** Mutually exclusive, maxItems: 1 per substance. A functional behavioral assertion that drives slot scoring. Slugs:

- `food_required` — blocks empty-stomach slots and strongly prefers food.
- `food_preferred` — softly prefers food.
- `empty_preferred` — strongly prefers empty-stomach slots and avoids food.
- `fat_meal_required` — approximates a fat-containing meal as `food: true`.
- `food_neutral` — marker that food state should not drive scheduling.

**`effect:` — slot timing effect.** Polyhierarchical. Only for timing-relevant effects such as sleep-disruptive or energy-like effects that affect slot assignment. Review-only effects such as nootropic support or calming belong in dashboard clusters, not here.

**`risk:` — warning markers.** Polyhierarchical. Emits single-substance schedule warnings when assigned. Stack-level loads such as bleeding, blood pressure, or cholinergic pressure belong in dashboard clusters with a nested `risk` block.

**`activity:` — workout timing marker.** Mutually exclusive, maxItems: 1 per substance. Products containing those substances should usually be placed in the `training` stack. The `training` pillbox gives them `pre_workout` and `post_workout` slots through `near`.

**`dashboard:` — operator-curated cluster membership.** Polyhierarchical. Each slug names a dashboard cluster that the substance belongs to. `dashboard:` is a review-classification axis — it does not influence slot assignment or scoring. Membership is extensional (closed-world): only substances explicitly tagged with a slug are cluster members. Contrast with `is:`, which dashboards can project intensionally (open-world): any future substance that acquires an `is:` slug automatically joins dashboards projecting that slug, without requiring an editor to update those dashboards.

**`is:` and `dashboard:` are review-classification axes** — they describe what a substance is for review and audit purposes but do not influence slot assignment or scoring. The other four namespaces (`intake`, `effect`, `risk`, `activity`) drive scheduling behavior.

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
- Put only stack membership in `data/stacks.yaml`.
- Put actual intake history, per-day doses, adherence, reactions, or operator notes nowhere for now; that would be a separate journal model if it becomes needed.
- Do not add taxonomy unless the planner, validator, warnings, or downstream consumers use it. `is:*` slugs are an approved exception for intrinsic pharmacological categories; use the defined set in the Trait Ontology section rather than inventing new slugs.
- To add a substance to a dashboard cluster, add the appropriate `dashboard:<slug>` tag in the substance's `dashboard:` grouped key — do not edit the dashboard yaml directly, because membership is computed dynamically from `from_traits:` at plan time. The dashboard yaml is a narrative wrapper (name, description, benefit/risk text) plus the `from_traits:` projection rule.

Use `uv run python -m planner doctor` to list cleanup candidates: unused substances, products outside stacks, unused traits, clustered similar substance names, empty stacks, and stack/pillbox mismatches. Doctor findings are review hints; unused or similar does not always mean wrong.

Slot IDs must be unique across all pillboxes. The planner keeps slot IDs flat in explanations and tests, so `check` rejects duplicate slot IDs instead of silently namespacing them.

After changing product `brand`/`name` or substance `name`/`form`, keep the stable `id`. `uv run python -m planner check`, `plan`, and `doctor` automatically generate missing card ids and rename product/substance files to the readable `...__id.yaml` form when that fix is deterministic.

## Non-Goals

This is not a medical ontology, dose engine, regimen tracker, evidence grader, or journal. Keep the model small unless a concrete planner behavior or data-maintenance problem requires more structure.
