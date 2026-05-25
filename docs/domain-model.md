# Domain Model

`supp-slotter` is a YAML-first supplement slot planner. It separates shelf state from product labels and substance scheduling rules.

## Core Objects

**Substance** (`data/substances/*.yaml`) is an active ingredient or concrete chemical/form. It owns scheduling traits, substance-level notes, aliases, and unresolved concerns. Use `form` when a named ingredient has distinct practical forms, for example `name: B6` plus `form: pyridoxine HCl`. Substance `id` is a stable opaque key such as `sub_3918fe347e`; it does not change when `name` or `form` changes. Filenames remain readable and include the stable id, for example `magnesium_glycinate__sub_7e02eab0d1.yaml`. Use `aliases` for abbreviations and synonyms such as `NAC`, `EPA`, or `Taxifolin`; aliases do not affect IDs.

**Product** (`data/products/*.yaml`) is a physical label-backed item. It owns `brand`, formula components, component labels/amounts when known, product description URLs, product notes, and label ambiguity. A product may contain one or many substances. Product components are canonical as `sub_*` IDs; during drafting, `uv run python -m planner check` may rewrite exact substance name/form, alias, or filename-stem refs to IDs when the match is unique. Product `id` is a stable opaque key such as `prd_83dffd67bf`; it does not change when `brand` or `name` changes. Product filenames use readable parts plus the id, for example `minami_healthy_foods__nattokinase_13000fu__prd_83dffd67bf.yaml`; if the brand is genuinely unknown, use `unknown`.

Product components may be label-stated or calculated from label-stated chemistry when the calculation is straightforward and high-confidence. Treat calculated components as first-class review facts, but make provenance explicit in the component `notes`. Example: sodium from sodium ascorbate can be listed as a Sodium component when the label gives sodium ascorbate mass and vitamin C equivalent, with the molar-mass calculation recorded in notes.

Non-specific proprietary blends, flavor systems, excipients, and label lines with
no current scheduler, dashboard, relation, or reusable review behavior belong in
product `notes`, not in `data/substances/`. Create a substance card for a blend
only when the blend itself is a reusable review entity or when the planner/review
surface needs to reason about it.

Mineral and trace-element cards use a conservative split. Keep a generic element card for unknown or behavior-neutral sources; create or keep a form/source card when absorption, tolerance, metabolic fate, source variability, safety, scheduling, or reviewer recommendations can differ materially. Preserve the exact label form on product components either way, and do not merge form cards merely because the elemental ion is the same.

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

**Trait** (`data/traits/`) is a scheduling rule or Reviewer classification marker. The registry is split by namespace owner file (`schedule.yaml`, `classes.yaml`, `effects.yaml`, `risks.yaml`, `pathways.yaml`) to keep the checklist readable. `context` membership is resolved through `data/dashboards/`, not the trait registry. Substance cards carry traits in two nested sections that mirror the two actors:

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
  context:
  - cortisol_reduction
```

Traits are declarative: the Planner executes `effects` rules from `intake:`, `timing:`, and `activity:` namespaces only. It reads `knowledge.is:` narrowly for class-level `competes` resolution. All other `knowledge:` fields are Reviewer-only. Broad benefit/risk groupings belong in dashboard clusters — not as flat trait slugs.

Use `knowledge.effect:` for reusable substance-level pharmacologic or functional facts. Avoid new `effect:*_context` slugs by default: use `context:` for curated dashboard membership, `risk:` for safety or interaction flags, `pathway:` for biochemical routes, and more precise effect names such as `*_support`, `*_inhibition`, `*_modulation`, or `*_cofactor` when the fact belongs on the substance. Existing `effect:*_context` slugs may remain when they are real reusable review facts; do not add new ones unless a narrower home would misrepresent the fact.

**Slot** is an intake compartment inside a pillbox. Slots expose simple fields such as `near` and `food`; trait effects match against those fields.

**Dashboard cluster** (`data/dashboards/*.yaml`) is a purpose-driven cluster of substances. A cluster can describe a `benefit`, a `risk`, or both for the same member set. Dashboard clusters do not drive slot assignment; `uv run python -m planner` uses them for goal-membership and risk-load review in generated `schedule.yaml`.

Use `benefit:` for support/membership axes such as `methylation_support` or `skin_support`, and `risk:` for load/overload axes such as `bleeding_load` or `cholinergic_load`. Keep dashboard files in the flat `data/dashboards/` directory; the YAML shape, not the path, is the source of truth. Prefer names ending in `_support`, `_health`, or `_performance` for benefit dashboards and `_load` for risk dashboards. A dashboard may contain both `benefit` and `risk` when the same member set has both review meanings. Goal dashboards are candidate-comparison review surfaces by default; load dashboards are cumulative risk/load surfaces; interaction-review dashboards should say so in the name or description. Prefer semantic projections when the grouping has an existing fact axis: `pathway:` for biochemical pathway views, `risk:` for shared risk flags, and `effect:` for shared review effects. Use explicit `context:` tags only for genuinely operator-curated review contexts that cut across cleaner axes without being reducible to them.

Cluster membership is computed via `from_traits:` rather than an explicit member list. The dashboard yaml declares which (namespace, slug) pairs identify members; the planner scans substance cards and collects every substance whose grouped namespace fields contain a matching slug. To add a substance to a cluster, add the appropriate underlying fact to the substance card, such as `pathway:<slug>`, `risk:<slug>`, `effect:<slug>`, or, when no cleaner axis exists, `context:<slug>`. Do not edit a dashboard yaml member list, because there is no member list. The dashboard yaml is a narrative wrapper (name, description, benefit/risk text) plus the `from_traits:` projection rule.

A substance is a member of dashboard D if there exists at least one (namespace N, slug S) pair where N appears as a key in D.`from_traits`, S appears in D.`from_traits[N]`, and S appears in the substance's per-namespace field for N. Resolution is union (logical OR) across the entire `from_traits` object. There is NO AND semantic across namespace groups — mixing namespaces in one `from_traits` widens membership, never narrows it.

Curated `context:` membership is allowed when the dashboard is an operator review view rather than a universal biological class. It means "show this substance in this review context", not "this slug is an intrinsic property of the substance." This is especially appropriate when a broad semantic projection would over-include, such as treating every `is:electrolyte` form as a workout-performance member. Do not replace this with context-shaped traits under another namespace; add semantic traits only when they name reusable facts about the substance itself.

Dashboard membership is intentionally flat today: it answers whether a substance is relevant to a review cluster, not whether it is a primary driver, cofactor, substrate, contextual support, or risk contributor. Add role metadata only when reviewer output needs to distinguish those roles; until then, keep role nuance in dashboard descriptions, substance notes, or relations.

**Relation** (`data/relations.yaml`) is a centralized substance-to-substance link. Relations are grouped by type and may point either to a base `name` or to one concrete `sub_*` card. Relations may also point to a registered `namespace:slug` trait through `source_trait` or `target_trait` when the relation is category-level review knowledge, for example `effect:incretin_drug_context -> risk:glucose_med_interaction`. Trait endpoints resolve to all substances currently carrying that trait, so use them only when every matching substance should participate in the same relation with the same severity and action. A trait endpoint means automatic inheritance for future cards; preview the current matched substances before adding one. Do not use trait endpoints merely to shorten YAML or to model broad dashboard membership. `planner review` prints concrete active source/target matches for trait-endpoint relations.

[docs/ontology-facts.md](ontology-facts.md) keeps unresolved ontology pressure points that do not yet have a clear home in traits, relations, dashboards, or notes.

## Read Model Boundary

YAML files and the dataclasses in `planner/contracts.py` are the source of truth. Commands build an in-memory SurrealDB read model from those objects for graph-style queries: relation status, stack usage, dashboard member projections, fact indexes, and audit cross-references.

SurrealDB is not persistent storage and does not write source data. The SurrealQL boundary lives under `planner/query_model/`; scheduler, review, and audit code should use the read-model facade instead of importing the SurrealDB SDK or raw query functions.

## Scheduling Semantics

The schedulable unit is the product ID listed in `data/stacks.yaml`. Product components are kept together. The planner aggregates traits from component substances and applies centralized relations from `data/relations.yaml`, assigns active products to compatible slots inside the pillbox mapped to their stack, applies `prefer_with` bonuses, blocks inter-product conflicts, and emits warnings for risks or intra-product conflicts.

`inactive` stack items are validated as known products but are not scheduled.

`uv run python -m planner` writes a full review schedule and prints a compact pillbox view. `summary.take` is grouped by pillbox, so `daily` is the ordinary recurring organizer and `training` is workout-only timing. Each pillbox contains slots with `products` and expanded `substances`. If a substance has `form`, the form is shown in parentheses. The schedule also includes non-warning `placement_notes`, `benefits`, `risks`, `warnings`, `kept_together`, and per-product `explanations`. Do not edit `schedule.yaml` directly; edit source cards and regenerate it.

Active `concerns` of kind `safety` are surfaced as review warnings in `schedule.yaml`. Use `uv run python -m planner review` to see all concerns grouped by kind (safety / data_quality / model_gap), with each entry labeled `[active]`, `[inactive]`, `[knowledge-only]`, or `[tracked-unassigned]`. The same command also shows relations status, risk flags, pathways, and dashboard membership. Use `uv run python -m planner audit` for structural diagnostics. This keeps uncertain or not-yet-modeled facts visible without forcing a new trait or relation type.

Dashboard-cluster output is review-only. Each dashboard cluster must define `benefit`, `risk`, or both. Cluster membership is computed at plan time from `from_traits:`. The planner reports a neutral `members` list and separates independent facts for each member: `relevance.matched_traits`, `product_tracking.state`, and `usage.state`. Catalog presence is implicit because every member comes from a registered substance card. This means a substance can be relevant to a goal without implying that the goal is covered, missing, recommended, or safe. Expert gap/recommendation status belongs in an advisory review artifact, not in deterministic planner output. Dashboard clusters never affect slot assignment.

Broad effect axes such as `bone_mineral_metabolism_support` are review selectors only. They do not imply dose adequacy, recommendation status, coverage, safety, or scheduling behavior. Do not use broad effect axes as relation endpoints; use a narrower `risk:`, `pathway:`, or effect when a warning or relation needs deterministic behavior. Do not create an effect merely to duplicate an existing dashboard/context projection.

Generated dashboard member shape:

```yaml
benefits:
- name: LDL / ApoB Control
  members:
  - substance_id: sub_psyllium01
    substance: Psyllium husk
    relevance:
      matched_traits:
      - namespace: effect
        slug: lipid_metabolism_support
    product_tracking:
      state: no_tracked_product   # or tracked_product
      product_count: 0
    usage:
      state: not_current          # current | on_shelf | unassigned | not_current
      stacks: []
```

Interpretation: `relevance` explains why the member belongs to the dashboard; `product_tracking` says whether any product card contains that substance; `usage` says whether tracked products are currently scheduled, on the shelf, unassigned, or absent. None of these fields is an expert recommendation.

State label glossary:

| Label | Meaning |
|---|---|
| `active` / `current` | A product containing the substance is scheduled through an active stack such as `daily` or `training`. |
| `inactive` / `on_shelf` | A known product is tracked under `inactive`; it is available for review but not scheduled. |
| `tracked-unassigned` / `unassigned` | A product card exists but is not assigned to any stack. |
| `knowledge-only` / `not_current` | A substance card exists without a tracked product currently using it. Keep it when it contains reusable knowledge. |
| `no_tracked_product` | Dashboard output found a relevant substance card but no product card contains it. |
| `reference/review` | Audit grouping for valid knowledge-only cards and non-blocking review hints; not a cleanup command. |

## Review Enrichment Strategy

The current planner should stay conservative: `schedule:` is only for facts that should change slot assignment. Enrichment work should primarily make the repository a better review and recommendation knowledge base for an agent that reads `planner review`, `schedule.yaml`, substance cards, dashboards, and relations.

Use these layers when adding review-oriented knowledge:

1. **Substance facts** — facts that belong to one substance regardless of the current stack. Put pharmacological or functional descriptors in `knowledge.effect`, safety and monitoring flags in `knowledge.risk`, biochemical context in `knowledge.pathway`, and not-yet-modeled high-signal facts in `concerns`. Example: L-carnitine as a TMAO-related cardiovascular review point is review knowledge, not scheduling knowledge.
2. **Relations** — facts where one substance affects another. Use `supports`, `review_with`, `balance`, or `competes` in `data/relations.yaml` instead of duplicating edges in substance cards. Relations should support both classic missing-cofactor review ("target active, supporter absent") and recommendation-oriented insight ("supporter/cofactor active, but the main target or purpose is absent") when the reviewer can use that signal.
3. **Dashboard and goal membership** — facts about areas of usefulness or load. Dashboard clusters should help an agent see relevant members, product availability, current usage, redundancy, and risk pressure across the stack. Gap and adequacy judgments belong to expert review. If future recommendations need to distinguish primary drivers from secondary cofactors or risk contributors inside a cluster, add that role model only after concrete review output needs it.
4. **Evidence and source context** — facts used for recommendations should remain auditable. Prefer concise `concerns` text, relation `reason` / `action`, product `urls`, and source-aware notes over opaque trait labels. Do not turn weak or context-dependent facts into hard scheduler behavior.

The first enrichment target is better review output, not smarter scheduling: active risks, pathway clusters, missing cofactors, orphan cofactors/supporters, redundant clusters, and high-signal review actions. Add new `schedule:` traits only when a fact should deliberately affect pillbox placement.

Start enrichment with a vertical slice through active or near-term-active substances, not with an abstract model pass. Initial candidates: L-carnitine forms, nattokinase, krill oil / EPA / DHA, tadalafil, L-citrulline, magnesium, vitamin D3, B12 / folate / B6, zinc / copper / selenium / iodine / potassium, creatine, astaxanthin, vitamin B5, and sodium ascorbate. This list is a review-enrichment seed, not a special scheduling priority.

Fact routing:

| Fact type | Home |
|---|---|
| Physical label, brand, component label/form, source URL | Product card |
| Reusable substance behavior or pharmacology | Substance card `knowledge.*` |
| Slot timing or food-state behavior | Substance card `schedule.*` |
| Safety or interaction flag on one substance | `knowledge.risk` plus `concerns` when prose is needed |
| Pair or category interaction between substances | `data/relations.yaml` |
| Goal/review cluster membership | Dashboard `from_traits` plus the underlying substance fact |
| Personal health history, actual intake, adherence, reactions | Gitignored `docs/private/` |
| Concrete fact with no clear current home | `docs/ontology-facts.md` |

## Adding Data

Use this document for ownership and ontology semantics. Use the templates and schemas for field-level YAML shape:

- `schema/templates/substance.yaml`
- `schema/templates/product.yaml`
- `schema/*.schema.json`

For stacks, pillboxes, traits, relations, and dashboards, copy the closest existing file under `data/` and keep only fields accepted by the matching schema.

Practical order:

1. Add or enrich concrete substance cards.
2. Add or enrich physical product cards.
3. Put products into `daily`, `training`, or `inactive` in `data/stacks.yaml`.
4. Add relations, traits, or dashboard projections only when they express reusable review/scheduling behavior.
5. Run `uv run python -m planner check`; run `review`, `audit`, or the default planner command when the changed surface needs that output.

## Trait Ontology

Substance cards carry trait information under `schedule:` and `knowledge:`. Each namespace has a defined cardinality and scheduling role.

**`is:` — intrinsic biochemical class.** Polyhierarchical (no cardinality limit). Describes what a substance *is* at the chemistry, pharmacology, market-category, or substance-type level. `is:` is a review-classification axis — it does not influence slot assignment or scoring. Slugs map to the intrinsic-class set registered in `data/traits/classes.yaml`.

`is:` should be a nominal taxonomy: nouns or noun phrases that pass the "is a kind of X" test. It must not encode what the substance does. Action-shaped facts such as support, modulation, inhibition, production, signaling, metabolism, load, risk, or timing belong in `effect:`, `pathway:`, `risk:`, dashboards, or `schedule:`. A noun is not enough by itself: `vasodilator`, `PDE5 inhibitor`, or `fibrinolytic` are noun phrases, but they name action/mechanism facts and therefore belong outside `is:`.

The source of truth for current `is:` slugs and their application rules is
`data/traits/classes.yaml`. Use the registry descriptions when editing cards.
Examples of class slugs include `mineral`, `amino`, `nootropic`, `omega3`,
`fiber`, `pharmaceutical`, and `botanical`.

**`intake:` — food-state scheduling rule.** Mutually exclusive, maxItems: 1 per substance. A functional behavioral assertion that drives slot scoring. Slugs:

- `food_required` — blocks empty-stomach slots and strongly prefers food.
- `food_preferred` — softly prefers food.
- `empty_preferred` — strongly prefers empty-stomach slots and avoids food.
- `fat_meal_required` — approximates a fat-containing meal as `food: true`.
- `food_neutral` — marker that food state should not drive scheduling.

**`timing:` — slot timing effect (Planner).** Mutually exclusive, maxItems: 1. Scheduling-relevant effects only: `energy_like` (prefers wake slots, avoids sleep slots), `sleep_disruptive` (hard-blocks sleep slots), `sleep_support` (prefers sleep slots). These three are the only registered timing slugs.

**`effect:` — pharmacological effects (Reviewer).** Polyhierarchical. For reusable functional or pharmacologic facts not relevant to slot assignment: vasodilator, cholinergic support, fibrinolytic activity, PDE5 inhibition, etc. Slugs are registered in `data/traits/effects.yaml`, surfaced by `planner review`, and never read by the Planner.

**`risk:` — safety/interaction flags (Reviewer).** Polyhierarchical. Surfaced by `planner review` in the Risk flags section; the Planner does not read `risk:`. Stack-level loads such as bleeding, blood pressure, or cholinergic pressure belong in dashboard clusters with a nested `risk` block.

**`activity:` — workout timing marker.** Mutually exclusive, maxItems: 1 per substance. Products containing those substances should usually be placed in the `training` stack. The `training` pillbox gives them `pre_workout` and `post_workout` slots through `near`.

**`context:` — curated review-context membership.** Polyhierarchical. Each slug names a dashboard/review context that the substance belongs to. `context:` is not an intrinsic trait about the substance; it is editorial membership in a reviewer view. Prefer dashboard `from_traits:` projections from reusable semantic facts (`is:`, `effect:`, `risk:`, `pathway:`) whenever they preserve the intended membership. Use `context:` when membership is genuinely hand-curated and a cleaner projection would over-include or under-explain the review context. Membership is extensional (closed-world): only substances explicitly tagged with a slug are cluster members. Contrast with semantic projections such as `is:`, where any future substance that acquires the projected slug automatically joins the dashboard without requiring an editor to update dashboard membership.

**`pathway:` — metabolic pathway membership (Reviewer).** Polyhierarchical. Names the biochemical pathway a substance participates in: `methylation_cycle`, `tmao_precursor`, etc. Surfaced by `planner review`; never read by the Planner.

**Scheduling namespaces** (`intake`, `timing`, `activity`) live under `schedule:` in the card and drive slot assignment. **Reviewer namespaces** (`is`, `effect`, `risk`, `context`, `pathway`) live under `knowledge:` and are surfaced by `planner review` only. The Planner reads `knowledge.is:` narrowly for class-level `competes` resolution — that is the only documented exception.

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
  severity: high
  reason: Mg-dependent hydroxylase required for 25(OH)D → 1,25(OH)2D conversion; without Mg, D3 activation is blocked.

review_with:
- source_substance: sub_a873e428ee
  target_name: Levodopa
  severity: high
  reason: Pyridoxine HCl can reduce levodopa effect in a specific medication context.
```

Endpoint fields define how broadly the relation applies:

- `source_name` / `target_name` apply to every current and future substance card with that exact `name`, regardless of `form`. Use them only when the relation deliberately applies across the whole named substance family. If beta-carotene should not inherit a preformed-retinol relation, or one vitamin/mineral form behaves differently enough to matter, use `source_substance`, `target_substance`, or a narrower trait endpoint.
- `source_substance` / `target_substance` apply only to one concrete substance card.

Mixed endpoints are valid when only one side is form-specific, for example `source_substance` for pyridoxine HCl and `target_name` for all `Levodopa` cards.

Trait endpoints are valid when the relation applies to a registered category of substances:

```yaml
review_with:
  - source_trait: effect:incretin_drug_context
    target_trait: risk:glucose_med_interaction
    reason: "Incretin drugs and glucose-lowering supplement contexts should be reviewed together."
```

Do not add relation mirrors. `balance` and `competes` are symmetric by planner semantics. `supports` and `review_with` are directional.

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

  # class-level
  - source_class: mineral
    target_class: fat_soluble
    reason: "Minerals and fat-soluble vitamins have conflicting timing requirements."
```

Class membership is resolved from `knowledge.is:` at plan time. This is the Planner's only documented read of the `knowledge:` section.
Class endpoints are supported only for `competes`; they exist to express broad class-level slot-blocking rules. Use `source_trait` / `target_trait` for category-level review facts that do not affect slot blocking.

`review_with` is an asymmetric review relation: when both endpoints are simultaneously active in the stack, the pairing should be surfaced for human or agent review. Use it for drug-supplement interactions, additive pharmacology, nutrient-status effects, or dose-dependent functional opposition that should not affect slot placement. The planner emits a `review_with_substance_present` warning; it does not calculate dose and does not separate products by slot.

`planner review` renders relation state semantically, not as raw source/target absence. `actionable_now` means the relation currently fires (`balance` one-side missing, `supports` target active without supporter, `review_with` both active, or `competes` both active). `active_pair_present` means both endpoints are active but no absence warning is implied. `latent_one_side_present` means one endpoint is active but the relation does not fire. `inactive` means neither endpoint is active.

All relation types accept an optional `severity` field (`critical`, `high`, `medium`, `low`). Treat it as operator-visible review priority, not a medical risk calculation. Leave it unset for routine relations. The planner includes severity in generated warnings when present. Use `critical` only when the operator should stop and resolve the issue before relying on the stack; use `high` for major review items, `medium` for ordinary review priority, and `low` for weak or contextual signals.

Relations may define optional `action` text for generated review output. Relations do not calculate dose, ratio, or medical inference.

## Ownership Rules

- Put product label facts in products.
- Fill product cards as richly as the label/source allows: components, component labels/forms, amounts, `urls`, and non-active label facts in `notes` or component `notes`. Do not invent missing label facts, and do not add fields outside the schema.
- If a product label gives a mineral salt/form, preserve it at least in the component `label` / `notes`. Model it as a separate substance only when that form/source is review- or scheduling-significant; otherwise point the component to the generic element card.
- Put universal scheduling behavior in substances and traits.
- Put all substance-to-substance links in `data/relations.yaml`, not in substance cards.
- Put only stack membership in `data/stacks.yaml`.
- Keep actual intake history, per-day doses, adherence, reactions, or operator notes out of tracked domain data. If user-specific context is needed for guided product work, store it under gitignored `docs/private/`; a real journal model is still a separate future decision.
- Do not add taxonomy unless the planner, validator, warnings, or downstream consumers use it. `is:*` slugs are an approved exception for intrinsic pharmacological categories; use the defined set in the Trait Ontology section rather than inventing new slugs.
- To add a substance to a dashboard cluster, update the membership source named by that dashboard's `from_traits:`. Prefer semantic axes (`is:`, `effect:`, `risk:`, `pathway:`) and add/refine the underlying reusable fact on the substance card. Use `context:` only for explicit operator-curated review contexts with no cleaner axis. Do not edit the dashboard yaml as an explicit member list, because membership is computed dynamically from `from_traits:` at plan time.

Use `uv run python -m planner audit` to list deterministic diagnostics: valid
knowledge-only substance cards, products outside stacks, unused review traits, potential
duplicate cards, empty stacks, and stack/pillbox mismatches. Use
`uv run python -m planner audit --full` only when source completion matters for the
current task, especially active product source and identity gaps. Component `amount`
values are optional label/context metadata for human review, not a dose-computation
contract and not a quality gate by themselves. Audit findings are review hints;
unknown amounts, knowledge-only cards, potential duplicates, or intentionally unused
scheduler capabilities do not automatically mean wrong.

Slot IDs must be unique across all pillboxes. The planner keeps slot IDs flat in explanations and tests, so `check` rejects duplicate slot IDs instead of silently namespacing them.

After changing product `brand`/`name` or substance `name`/`form`, keep the stable `id`. `uv run python -m planner check` and `uv run python -m planner` automatically generate missing card ids and rename product/substance files to the readable `...__id.yaml` form when that fix is deterministic.

## Non-Goals

This is not a medical ontology, dose engine, regimen tracker, evidence grader, or journal. Keep the model small unless a concrete planner behavior or data-maintenance problem requires more structure.
