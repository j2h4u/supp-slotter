# Domain Model

`supp-slotter` is a YAML-first supplement slot planner. It separates shelf state from product labels and substance scheduling rules.

## Core Objects

**Substance** (`data/substances/*.yaml`) is an active ingredient or concrete chemical/form. It owns scheduling traits, substance-level notes, aliases, and unresolved concerns. Use `form` when a named ingredient has distinct practical forms, for example `name: B6` plus `form: pyridoxine HCl`. Substance `id` is a stable opaque key such as `sub_3918fe347e`; it does not change when `name` or `form` changes. Filenames remain readable and include the stable id, for example `magnesium_glycinate__sub_7e02eab0d1.yaml`. Use `aliases` for abbreviations and synonyms such as `NAC`, `EPA`, or `Taxifolin`; aliases do not affect IDs.

**Product** (`data/products/*.yaml`) is a physical label-backed item. It owns `brand`, formula components, component labels/amounts when known, product description URLs, product notes, and label ambiguity. A product may contain one or many substances. Product `id` is a stable opaque key such as `prd_83dffd67bf`; it does not change when `brand` or `name` changes. Product filenames use readable parts plus the id, for example `minami_healthy_foods__nattokinase_13000fu__prd_83dffd67bf.yaml`; if the brand is genuinely unknown, use `unknown`.

Product components may be label-stated or calculated from label-stated chemistry when the calculation is straightforward and high-confidence. Treat calculated components as first-class review facts, but make provenance explicit in the component `notes`. Example: sodium from sodium ascorbate can be listed as a Sodium component when the label gives sodium ascorbate mass and vitamin C equivalent, with the molar-mass calculation recorded in notes.

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

**Trait** (`data/traits.yaml`) is a scheduling rule or Reviewer classification marker. The file is grouped by namespace (`is`, `intake`, `timing`, `risk`, `activity`, `dashboard`, `pathway`) to keep the checklist readable. Substance cards carry traits in two nested sections that mirror the two actors:

```yaml
# Planner section — drives slot assignment
schedule:
  intake:
  - empty_preferred     # food-state rule; max 1
  timing:
  - sleep_support       # slot timing effect; max 1
  activity:             # workout marker; max 1

# Reviewer section — surfaced by `planner review`
knowledge:
  is:
  - adaptogen
  dashboard:
  - cortisol_reduction
```

Traits are declarative: the Planner executes `effects` rules from `intake:`, `timing:`, and `activity:` namespaces only. It reads `knowledge.is:` narrowly for class-level `competes` resolution. All other `knowledge:` fields are Reviewer-only. Broad benefit/risk groupings belong in dashboard clusters — not as flat trait slugs.

**Slot** is an intake compartment inside a pillbox. Slots expose simple fields such as `near` and `food`; trait effects match against those fields.

**Dashboard cluster** (`data/dashboards/*.yaml`) is a purpose-driven cluster of substances. A cluster can describe a `benefit`, a `risk`, or both for the same member set. Dashboard clusters do not drive slot assignment; `python -m planner plan` uses them for benefit coverage and risk-load review in generated `schedule.yaml`.

Cluster membership is computed via `from_traits:` rather than an explicit member list. The dashboard yaml declares which (namespace, slug) pairs identify members; the planner scans substance cards and collects every substance whose grouped namespace fields contain a matching slug. To add a substance to a cluster, add the appropriate `dashboard:<slug>` tag to the substance card — do not edit the dashboard yaml's member list, because there is no member list. The dashboard yaml is a narrative wrapper (name, description, benefit/risk text) plus the `from_traits:` projection rule.

A substance is a member of dashboard D if there exists at least one (namespace N, slug S) pair where N appears as a key in D.`from_traits`, S appears in D.`from_traits[N]`, and S appears in the substance's per-namespace field for N. Resolution is union (logical OR) across the entire `from_traits` object. There is NO AND semantic across namespace groups — mixing namespaces in one `from_traits` widens membership, never narrows it.

**Relation** (`data/relations.yaml`) is a centralized substance-to-substance link. Relations are grouped by type and may point either to a base `name` or to one concrete `sub_*` card.

[docs/ontology-facts.md](ontology-facts.md) stress-tests how supplement facts fit the ontology before they are encoded as traits, relations, or notes.

## Scheduling Semantics

The schedulable unit is the product ID listed in `data/stacks.yaml`. Product components are kept together. The planner aggregates traits from component substances and applies centralized relations from `data/relations.yaml`, assigns active products to compatible slots inside the pillbox mapped to their stack, applies `prefer_with` bonuses, blocks inter-product conflicts, and emits warnings for risks or intra-product conflicts.

`inactive` stack items are validated as known products but are not scheduled.

`uv run python -m planner` writes a full review schedule and prints a compact pillbox view. `summary.take` is grouped by pillbox, so `daily` is the ordinary recurring organizer and `training` is workout-only timing. Each pillbox contains slots with `products` and expanded `substances`. If a substance has `form`, the form is shown in parentheses. The schedule also includes non-warning `placement_notes`, `benefits`, `risks`, `warnings`, `kept_together`, and per-product `explanations`. Do not edit `schedule.yaml` directly; edit source cards and regenerate it.

Active `concerns` of kind `safety` are surfaced as review warnings in `schedule.yaml`. Use `python -m planner review` to see concerns grouped by kind (safety / data_quality / model_gap), plus relations status, risk flags, pathways, and dashboard membership. Use `python -m planner audit` for structural cleanup candidates. This keeps uncertain or not-yet-modeled facts visible without forcing a new trait or relation type.

Dashboard-cluster output is review-only. Each dashboard cluster must define `benefit`, `risk`, or both. Cluster membership is computed at plan time from `from_traits:` — the planner resolves members dynamically and separates them into `covered` (active), `inactive` (on shelf but not scheduled), and `missing` (not in stacks). Dashboard clusters never affect slot assignment.

## Review Enrichment Strategy

The current planner should stay conservative: `schedule:` is only for facts that should change slot assignment. Enrichment work should primarily make the repository a better review and recommendation knowledge base for an agent that reads `planner review`, `schedule.yaml`, substance cards, dashboards, and relations.

Use these layers when adding review-oriented knowledge:

1. **Substance facts** — facts that belong to one substance regardless of the current stack. Put pharmacological or functional descriptors in `knowledge.effect`, safety and monitoring flags in `knowledge.risk`, biochemical context in `knowledge.pathway`, and not-yet-modeled high-signal facts in `concerns`. Example: L-carnitine as a TMAO-related cardiovascular review point is review knowledge, not scheduling knowledge.
2. **Relations** — facts where one substance affects another. Use `supports`, `antagonizes`, `balance`, or `competes` in `data/relations.yaml` instead of duplicating edges in substance cards. Relations should support both classic missing-cofactor review ("target active, supporter absent") and recommendation-oriented insight ("supporter/cofactor active, but the main target or purpose is absent") when the reviewer can use that signal.
3. **Dashboard and goal coverage** — facts about areas of usefulness or load. Dashboard clusters should help an agent see coverage, gaps, redundancy, and risk pressure across the stack. If future recommendations need to distinguish primary drivers from secondary cofactors or risk contributors inside a cluster, add that role model only after concrete review output needs it.
4. **Evidence and source context** — facts used for recommendations should remain auditable. Prefer concise `concerns` text, relation `reason` / `action`, product `urls`, and source-aware notes over opaque trait labels. Do not turn weak or context-dependent facts into hard scheduler behavior.

The first enrichment target is better review output, not smarter scheduling: active risks, pathway clusters, missing cofactors, orphan cofactors/supporters, redundant clusters, and high-signal review actions. Add new `schedule:` traits only when a fact should deliberately affect pillbox placement.

Start enrichment with a vertical slice through active or near-term-active substances, not with an abstract model pass. Initial candidates: L-carnitine forms, nattokinase, krill oil / EPA / DHA, tadalafil, L-citrulline, magnesium, vitamin D3, B12 / folate / B6, zinc / copper / selenium / iodine / potassium, creatine, astaxanthin, vitamin B5, and sodium ascorbate. This list is a review-enrichment seed, not a special scheduling priority.

## Adding Data

Use the schemas as the final contract, but these are the smallest useful shapes:

```yaml
# data/substances/example.yaml
# id may be omitted for new cards; check assigns it on first run.
name: Example Substance
form: optional concrete form
aliases:
- EX
notes: Short universal substance note.
# schedule: — Planner reads this section only (plus knowledge.is: for class-level competes)
schedule:
  intake:
  - empty_preferred    # food-state rule (maxItems: 1)
  timing: []           # energy_like | sleep_disruptive | sleep_support (maxItems: 1)
  activity: []         # pre_workout | post_workout | any_workout (maxItems: 1)
  prefer_with: []      # sub_* IDs — co-placement scheduling bonus
# knowledge: — Reviewer reads this section; Planner never reads it (except is: for competes)
knowledge:
  is:
  - adaptogen          # intrinsic biochemical class (polyhierarchical)
  effect: []           # pharmacological effects not relevant to timing
  risk: []             # safety/interaction flags
  dashboard:
  - cortisol_reduction # operator-curated cluster membership (polyhierarchical)
  pathway: []          # metabolic pathway membership
```

```yaml
# data/products/example_product.yaml
# id may be omitted for new cards; check/default schedule generation can assign it.
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

Practical order: create or update concrete substance cards first, then product cards, then stack membership, then run `uv run python -m planner`. Use `uv run python -m planner audit` to review cleanup candidates, not as an automatic todo list.

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

**`timing:` — slot timing effect (Planner).** Mutually exclusive, maxItems: 1. Scheduling-relevant effects only: `energy_like` (prefers wake slots, avoids sleep slots), `sleep_disruptive` (hard-blocks sleep slots), `sleep_support` (prefers sleep slots). These three are the only registered timing slugs.

**`effect:` — pharmacological effects (Reviewer).** Polyhierarchical. For effects not relevant to slot assignment: vasodilator, nootropic, ergogenic, adaptogen, etc. Surfaced by `planner review`; never read by the Planner.

**`risk:` — safety/interaction flags (Reviewer).** Polyhierarchical. Surfaced by `planner review` in the Risk flags section; the Planner does not read `risk:`. Stack-level loads such as bleeding, blood pressure, or cholinergic pressure belong in dashboard clusters with a nested `risk` block.

**`activity:` — workout timing marker.** Mutually exclusive, maxItems: 1 per substance. Products containing those substances should usually be placed in the `training` stack. The `training` pillbox gives them `pre_workout` and `post_workout` slots through `near`.

**`dashboard:` — operator-curated cluster membership.** Polyhierarchical. Each slug names a dashboard cluster that the substance belongs to. `dashboard:` is a review-classification axis — it does not influence slot assignment or scoring. Membership is extensional (closed-world): only substances explicitly tagged with a slug are cluster members. Contrast with `is:`, which dashboards can project intensionally (open-world): any future substance that acquires an `is:` slug automatically joins dashboards projecting that slug, without requiring an editor to update those dashboards.

**`pathway:` — metabolic pathway membership (Reviewer).** Polyhierarchical. Names the biochemical pathway a substance participates in: `methylation_cycle`, `tmao_precursor`, etc. Surfaced by `planner review`; never read by the Planner.

**Scheduling namespaces** (`intake`, `timing`, `activity`) live under `schedule:` in the card and drive slot assignment. **Reviewer namespaces** (`is`, `effect`, `risk`, `dashboard`, `pathway`) live under `knowledge:` and are surfaced by `planner review` only. The Planner reads `knowledge.is:` narrowly for class-level `competes` resolution — that is the only documented exception.

Mechanism-only labels are not traits. If a mechanism matters for review, encode it as a benefit/risk cluster or a centralized relation.

## Substance Relations

`data/relations.yaml` declares explicit substance-to-substance links in one central place. Most relation types are stack-review warnings; `competes` also affects slot placement.

Supported relation types:

```yaml
balance:
- source_name: Zinc
  target_name: Copper
  severity: medium
  reason: Long-term high-dose zinc supplementation can depress copper status.
  action: Review zinc/copper balance in long-term active stacks.

competes:
- source_name: Zinc
  target_name: Copper
  reason: Zinc and copper can compete for absorption when co-administered.

supports:
- source_name: Magnesium
  target_name: Vitamin D3
  severity: critical
  reason: Mg-dependent hydroxylase required for 25(OH)D → 1,25(OH)2D conversion; without Mg, D3 activation is blocked.

antagonizes:
- source_substance: sub_a873e428ee
  target_name: Levodopa
  severity: high
  reason: Pyridoxine HCl can reduce levodopa effect in a specific medication context.
```

Endpoint fields define how broadly the relation applies:

- `source_name` / `target_name` apply to every active substance card with that exact `name`, regardless of `form`.
- `source_substance` / `target_substance` apply only to one concrete substance card.

Mixed endpoints are valid when only one side is form-specific, for example `source_substance` for pyridoxine HCl and `target_name` for all `Levodopa` cards.

Do not add relation mirrors. `balance` and `competes` are symmetric by planner semantics. `supports` and `antagonizes` are directional.

`balance` warns when one side is active and the paired side is absent from active products.

`supports` is supporter-to-target. This handles substances such as selenium or piperine that may support many targets. Review warnings are emitted when the target is active and the supporter is absent.

`competes` is a scheduling relation. The planner avoids assigning products with competing substances to the same slot. If both substances are in the same physical product, the product is kept together and the schedule gets an intra-product conflict warning.

`competes` also supports **class-level entries** that block entire substance classes from sharing a slot:

```yaml
competes:
  # substance-level (existing)
  - source_name: Zinc
    target_name: Copper
    reason: "..."

  # class-level (new in v2)
  - source_class: mineral
    target_class: fat_soluble
    reason: "Minerals and fat-soluble vitamins have conflicting timing requirements."
```

Class membership is resolved from `knowledge.is:` at plan time. This is the Planner's only documented read of the `knowledge:` section.

`antagonizes` is an asymmetric review relation: the source can oppose or reduce the target's function. When both endpoints are simultaneously active in the stack, the planner emits an `antagonizes_substance_present` warning. It does not affect slot placement and does not calculate dose.

All relation types accept an optional `severity` field (`critical`, `high`, `medium`, `low`). Set it only for clinically significant entries — leave it unset for routine relations. The planner includes severity in generated warnings when present.

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

Use `uv run python -m planner audit` to list cleanup candidates: unused substances, products outside stacks, unused traits, clustered similar substance names, empty stacks, and stack/pillbox mismatches. Audit findings are review hints; unused or similar does not always mean wrong.

Slot IDs must be unique across all pillboxes. The planner keeps slot IDs flat in explanations and tests, so `check` rejects duplicate slot IDs instead of silently namespacing them.

After changing product `brand`/`name` or substance `name`/`form`, keep the stable `id`. `uv run python -m planner check` and `uv run python -m planner` automatically generate missing card ids and rename product/substance files to the readable `...__id.yaml` form when that fix is deterministic.

## Non-Goals

This is not a medical ontology, dose engine, regimen tracker, evidence grader, or journal. Keep the model small unless a concrete planner behavior or data-maintenance problem requires more structure.
