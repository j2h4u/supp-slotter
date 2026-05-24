# Ontology Audit Notes - 2026-05-24

Status: working audit brief. This document records the audit frame before changing
the ontology. It is not an implementation plan yet.

Source read through Exa MCP:
[Palantir - Ontology design: Best practices and anti-patterns](https://www.palantir.com/docs/foundry/ontology/ontology-best-practices-and-anti-patterns).

## Why This Audit Exists

The ontology has grown from a small supplement planner into a richer knowledge
base: products, substances, traits, dashboards, relations, SurrealDB read-model
queries, and agent review surfaces. The current model is valid enough to run,
but growth creates semantic drift risk: broad traits, catch-all risk labels,
wide dashboard selectors, and relation endpoints that may apply to more forms
than intended.

The audit goal is to keep the model deterministic, readable, and useful for an
external expert agent without turning it into an over-engineered medical
knowledge graph.

## Palantir Frame Translated To Supp Slotter

| Palantir principle / anti-pattern | Local translation |
|---|---|
| Model reality, not systems | `Product` should mean a physical bottle or label-backed item. `Substance` should mean a reusable ingredient/form fact. `Dashboard` should mean a review view, not a storage convenience. |
| Curate intentionally | Every trait, relation, and dashboard selector should answer a current review, scheduling, or validation question. |
| Keep object types focused | Avoid substance cards that are really product-label artifacts, blend placeholders, historical notes, or dashboards in disguise. |
| Use the right tool | Scheduling facts belong in `schedule.*`; review facts in `knowledge.*`; pair/category interactions in `relations.yaml`; goal views in dashboards. |
| Avoid the Kitchen Sink | Watch broad `effect:*_context`, `risk:manual_review`, and dashboards that collect too many unrelated facts. |
| Avoid the God Object | Do not let `Substance`, `effect`, or `context` become "anything an agent might want to know." |
| Avoid Misnomers | Names should tell an agent what the field does without requiring project history. |
| Avoid Time Machine | Historical audit notes do not belong in the active ontology; git is the history. |

## Initial Repo Snapshot

Commands run before this document:

- `uv run python -m planner audit --full`
- `uv run python -m planner review`
- Ad-hoc YAML scans over `data/substances`, `data/products`,
  `data/dashboards`, and `data/relations.yaml`

Observed counts:

| Surface | Count / signal |
|---|---:|
| Substance cards | 255 |
| Product cards | 58 |
| Dashboard files | 19 |
| `planner audit --full` actionable diagnostics | 0 |
| Knowledge-only substance cards | 49 |
| Active concerns in `planner review` | 21 |
| Relation review, actionable now | 4 |
| Risk memberships active in current stack | 32 |
| Dashboard views with current members | 16 |
| Dashboard views with zero current members | 3 |
| Effect registry slugs | 126 |
| Effect slugs ending in `_context` | 80 |
| Substances carrying `risk:manual_review` | 113 |

Important interpretation: `0 actionable` means the current YAML is structurally
healthy. It does not mean the ontology is semantically optimal.

## Existing Strengths

- The core entity split is coherent:
  - `Product` is label-backed and stack-scoped.
  - `Substance` is reusable ingredient/form knowledge.
  - `Stack` tracks current use state.
  - `Pillbox` tracks scheduling slots.
  - `Dashboard` is a review projection.
  - `Relation` is a centralized substance-to-substance or category-to-category
    link.
- Source YAML remains the source of truth; SurrealDB is a read model, not
  storage.
- `schedule:` and `knowledge:` are separated. The planner only executes a narrow
  scheduling subset.
- Reference-only substance cards are explicitly valid knowledge-base entries,
  not cleanup candidates.
- Dashboard output now distinguishes relevance, product tracking, and usage
  state instead of pretending that "not current" means "missing" or
  "recommended."

## Initial Risk Areas

### 1. `effect:` May Be Becoming A Kitchen Sink

The registry currently has 126 `effect` slugs; 80 end in `_context`. That naming
pattern is not automatically wrong, but it is a strong smell: "context" can mean
mechanism, goal membership, review reason, weak association, safety prompt, or
dashboard selector.

Audit question: for every broad `effect:*_context`, is it a reusable substance
fact, or is it really dashboard membership, risk, pathway, relation rationale,
or prose in `concerns`?

Likely examples to inspect first:

- `glucose_metabolism_context`
- `antioxidant_context`
- `bone_mineral_metabolism_support`
- `energy_production_support`
- `neuromuscular_function_support`
- `lipid_metabolism_support`
- `cognitive_performance_context`
- `blood_pressure_context`

### 2. `risk:manual_review` May Be Too Broad

`risk:manual_review` appears on 113 substances. It is useful as a safety valve,
especially for pharmaceuticals, research chemicals, botanicals, and uncertain
products. At this volume, it may also become low-information noise.

Audit question: should `manual_review` stay as a generic marker, or should common
reasons split into a small number of concrete review risks such as regulatory
status, product-quality uncertainty, medication-interaction review, hormone
activity, CNS-depressant review, or experimental-human-use review?

Constraint: do not add new risk slugs just to make the registry look tidy. Split
only where reviewer output becomes more actionable.

### 3. Dashboard Selectors Can Over-Include

Dashboard membership is OR-based across `from_traits`. This is deliberately
simple, but it means every additional selector widens membership.

Broad current dashboard sizes:

| Dashboard | Relevant substances |
|---|---:|
| Antioxidant Protection | 49 |
| Neurocognitive Support | 39 |
| Vascular Health | 31 |
| Skin Support | 28 |
| Digestive / Gut Support | 26 |
| GLP / Incretin Interaction Review | 23 |
| Mitochondrial Health | 22 |
| Workout Performance | 21 |

Audit question: for each dashboard, what question is it supposed to answer?
If the answer is "show every possibly adjacent substance," the dashboard is too
broad for expert review. If the answer is "show all candidates, including
inactive and knowledge-only cards, so an expert can compare options," then the
wide surface may be correct, but the dashboard description must say that.

### 4. Relation Endpoints May Inherit Too Widely

`relations.yaml` supports name, substance ID, trait, and class endpoints. This is
powerful and dangerous. Name endpoints currently apply across all forms with the
same `name`.

Examples of wide name groups:

| Name | Form count |
|---|---:|
| Magnesium | 9 |
| Calcium | 6 |
| Selenium | 5 |
| Zinc | 4 |
| Copper | 3 |
| Vitamin B12 | 3 |
| Vitamin E | 3 |
| Iodine | 3 |

Audit question: for every relation using `source_name` or `target_name` against
a multi-form name, should the relation apply to every current and future form?
If not, use `source_substance` / `target_substance` or a narrower trait endpoint.

Trait endpoints need the same review: they automatically include future cards.
Use them only when the relation is truly category-level knowledge.

### 5. Blend-Like Substance Cards Need Boundary Review

Some cards represent blend-level concepts or product-label placeholders, for
example probiotic blends, proprietary fiber blends, or brand-specific botanical
standardizations. Some are legitimate because a blend is the actual label-backed
unit; others may be product artifacts that should not become reusable substance
entities.

Audit question: is the card a reusable real-world entity, or only a temporary
label parsing convenience? If it is only label parsing, keep the fact on the
product card unless reviewer logic needs a reusable node.

### 6. Generic Form Cards Are Mostly Under Control

`planner audit --full` reports no generic no-form cards that are both unreferenced
and duplicated by form-specific cards. It does report active products using a few
generic no-form cards while form-specific cards exist:

- `L-Arginine` while AAKG exists.
- `L-Lysine` while HCl exists.
- `Vitamin B12` while methylcobalamin and cyanocobalamin exist.
- `Zeaxanthin` while RR-zeaxanthin and meso-zeaxanthin exist.

This may be correct when the product label is generic. Do not "fix" these unless
the product label or source URL identifies the form.

## Audit Order

### Pass 1 - Trait Registry

Focus:

- `data/traits/effects.yaml`
- `data/traits/risks.yaml`
- `data/traits/classes.yaml`
- `data/traits/pathways.yaml`

Questions:

- Is each slug a reusable fact?
- Does the namespace match the function?
- Can the slug be understood without historical context?
- Is `_context` hiding a more precise category?
- Would the planner, reviewer, or dashboard output become worse if the slug were
  removed or renamed?

### Pass 2 - Dashboard Semantics

Focus:

- `data/dashboards/*.yaml`
- generated dashboard sections in `schedule.yaml`
- `planner review` dashboard summary

Questions:

- What review question does this dashboard answer?
- Is the selector set intentionally broad or accidentally broad?
- Are `context:` selectors being used because a semantic fact is missing?
- Does the dashboard imply coverage, adequacy, recommendation, or safety when it
  only knows relevance and usage state?

### Pass 3 - Relation Endpoint Scope

Focus:

- `data/relations.yaml`
- relation output in `planner review`

Questions:

- Are name endpoints intentionally all-form?
- Are trait endpoints intentionally future-inheriting?
- Are class endpoints limited to scheduler-relevant cases?
- Should an endpoint be narrowed to a specific `sub_*`?
- Does the relation type match behavior: `balance`, `competes`, `supports`, or
  `review_with`?

### Pass 4 - Object Boundary And Naming

Focus:

- representative product cards
- representative substance cards
- blend-like cards
- `docs/domain-model.md`

Questions:

- Is each object one real-world entity?
- Are product-label facts leaking into reusable substance cards?
- Are personal/operator facts absent from tracked ontology files?
- Are names self-explanatory for a fresh agent?

## Guardrails

- Do not preserve old concepts for compatibility unless a current runtime need
  is demonstrated.
- Do not delete reference-only substances merely because they are not in the
  current stack.
- Do not add ontology primitives for one-off facts; use `notes`, `concerns`,
  relation `reason`, or dashboard prose first.
- Do not create a dose model during this audit. Dose thresholds may remain in
  prose until scheduler decisions require reliable quantities.
- Prefer fewer, sharper categories over more clever taxonomy.
- If a change needs a judgment call, capture the decision before editing data.

## Immediate Next Step

Start with Pass 1: audit `data/traits/effects.yaml` and identify broad
`*_context` slugs that are:

1. clearly valid reusable substance facts;
2. actually dashboard membership;
3. better modeled as `risk:`, `pathway:`, or `relation`;
4. too vague and worth renaming or removing.

The output of Pass 1 should be a short table of proposed changes, not immediate
mass edits.

## Pass 1A - Effect Registry Usage Map

Status: evidence collected, no ontology edits yet.

Commands / scans:

- Parsed `data/traits/effects.yaml`.
- Counted effect usage in `data/substances/*.yaml`.
- Counted effect selectors in `data/dashboards/*.yaml`.
- Counted effect trait endpoints in `data/relations.yaml`.

Summary:

| Signal | Count |
|---|---:|
| Registered `effect` slugs | 126 |
| Slugs ending in `_context` | 80 |
| Slugs ending in `_support` | 37 |
| Effect slugs used by dashboards | 51 |
| Effect slugs used as relation endpoints | 4 |

Main finding: `effect` currently performs three different jobs:

1. reusable substance fact, for example `pde5_inhibition` or
   `phosphocreatine_support`;
2. dashboard selector, for example `antioxidant_context` in
   `antioxidant_protection`;
3. category-level relation endpoint, for example `effect:incretin_drug_context` in
   GLP / glucose / protein / creatine review relations.

This is not automatically wrong. It is the main semantic pressure point because
each role has different blast radius. A broad review fact can be harmless on a
substance card, but risky when used as a dashboard selector or future-inheriting
relation endpoint.

### High-Use Effects With No Dashboard Or Relation Consumer

These slugs are widely applied but currently do not drive dashboard membership or
relations. They may still be useful in `planner review` / fact indexes, but they
deserve a purpose check: either they should feed a review view, be renamed to a
clearer fact, or be demoted to notes/concerns when too vague.

| Effect slug | Substance count | Initial read |
|---|---:|---|
| `glucose_metabolism_context` | 25 | Very broad. Mixes minerals, biotin, lipoic acid, botanicals, and incretin drugs. May need a cardiometabolic dashboard or narrower split. |
| `bone_mineral_metabolism_support` | 22 | Looks like a legitimate review axis, but it is currently hidden from dashboards. Consider a bone/mineral dashboard or keep only if review output surfaces it clearly. |
| `energy_production_support` | 18 | Broad ATP/metabolism fact. Could be legitimate, but overlaps mitochondrial and B-vitamin/pathway facts. |
| `neuromuscular_function_support` | 16 | Mostly minerals/electrolytes. Could be useful, but may overlap electrolyte balance and workout/performance views. |
| `blood_pressure_context` | 13 | Broad and not currently the hypotensive-load selector. Needs distinction from `risk:hypotension_med_interaction`, `vasodilator`, and `vascular_tone_context`. |
| `cognitive_performance_context` | 13 | Applied to nootropics/stimulants but not used by neurocognitive dashboard. This may be an unharvested dashboard selector or too broad. |
| `vascular_polyphenol_context` | 12 | Looks semantically useful, but it is not directly used by vascular dashboard despite the name. |
| `protein_synthesis_support` | 10 | Broad tissue-building fact. Needs distinction from `muscle_protein_synthesis_context`. |

### Broad Dashboard Selectors To Review First

These slugs affect dashboard membership directly, so false positives matter more.

| Effect slug | Substance count | Dashboard usage | Initial read |
|---|---:|---|---|
| `antioxidant_context` | 25 | `antioxidant_protection` | Candidate Kitchen Sink. It overlaps `is:antioxidant` and more precise redox/lipid/glutathione effects. |
| `lipid_metabolism_support` | 14 | `vascular_health`, `ldl_apob_control` | May be too broad for LDL/ApoB if it includes generic lipid metabolism rather than LDL-relevant effects. |
| `cholinergic_support` | 11 | `cholinergic_load` | Likely valid: effect is concrete enough and dashboard is load-focused. |
| `sleep_context` | 10 | `sleep_recovery` | Broad. Could stay as a review selector, but it should not imply efficacy or scheduling. |
| `calming_context` | 9 | `sleep_recovery` | Broad but useful if sleep dashboard intentionally includes calming supports. |
| `skin_barrier_context` | 8 | `skin_support` | Probably valid, but should be distinguished from skin matrix and wound-healing facts. |
| `digestive_comfort_context` | 7 | `digestive_gut_support` | Broad symptom-oriented selector; valid only if dashboard is explicitly a broad review surface. |
| `gut_microbiome_context` | 7 | `digestive_gut_support` | Likely valid and more concrete than generic digestive support. |
| `redox_metabolism_support` | 6 | `mitochondrial_health` | Likely valid, but overlaps antioxidant dashboard semantics. |
| `wound_healing_support` | 6 | `skin_support` | Concrete enough to keep if dashboard wants tissue repair. |
| `nitric_oxide_support` | 5 | `workout_performance`, `vascular_health`, `hypotensive_load` | High blast radius because it is also a relation endpoint. Likely valid but must stay tightly defined. |

### Effect Relation Endpoints

Only four effect slugs are relation endpoints today:

| Effect endpoint | Substance count | Relation usage | Initial read |
|---|---:|---|---|
| `incretin_drug_context` | 6 | GLP / protein / creatine / glucose / metformin / fiber review | Semantically useful and now drug-class-specific enough for relation endpoint use. |
| `nitric_oxide_support` | 5 | NO support + PDE5 inhibition review | Valid category-level endpoint if membership remains limited to direct NO substrates/donors. |
| `gastric_acid_suppressing_drug_context` | 4 | Acid suppression + B12 review | Semantically useful and now drug-class-specific enough for relation endpoint use. |
| `pde5_inhibition` | 1 | NO support + PDE5 inhibition review | Good precise effect. Keep. |

Relation endpoint rule emerging from this pass: an `effect` slug used in
relations must be narrower and more stable than an ordinary dashboard selector,
because future cards inherit that relation automatically.

### Low-Use Context Slugs

Single-use or two-use slugs are not inherently bad. They are fine when they name
a precise reusable fact that will be useful for future cards. They are suspicious
when they only preserve a one-off explanation that could live in `notes` or
`concerns`.

Low-use examples to inspect later:

- `cell_signaling_context`
- `longevity_context`
- `mucolytic_context`
- `osmolyte_context`
- `paresthesia_tolerance_context`
- `purine_metabolism_context`
- `stress_performance_context`
- `sulfur_connective_tissue_context`
- `urinary_adhesion_context`
- `urinary_tract_context`
- `anti_catabolic_context`
- `hpa_axis_context`
- `leucine_metabolite_context`

Initial rule: keep a low-use effect only when it is expected to be reused or
materially improves review output today. Otherwise prefer prose in the substance
card.

## Pass 1A Proposed Decisions

No data changes yet. Proposed decision buckets:

| Bucket | Slugs / examples | Proposed treatment |
|---|---|---|
| Keep as precise effects | `pde5_inhibition`, `fibrinolytic`, `platelet_aggregation_modulation`, `phosphocreatine_support`, `glutathione_precursor_support`, `cholinergic_support` | These have clear functional meaning and useful review behavior. |
| Keep but enforce narrow membership | `nitric_oxide_support`, `incretin_drug_context`, `gastric_acid_suppressing_drug_context` | Valid if used carefully; relation endpoint use means each future matching card must truly inherit the relation. |
| Rename candidates | maybe `sleep_context` | Relation endpoint rename candidates were handled in Phase 2; remaining rename candidates should be lower blast-radius review selectors. |
| Dashboard-selector audit | `antioxidant_context`, `lipid_metabolism_support`, `sleep_context`, `digestive_comfort_context`, `exercise_performance_context` | Check dashboard false positives before editing. |
| Hidden broad axes | `glucose_metabolism_context`, `bone_mineral_metabolism_support`, `energy_production_support`, `blood_pressure_context`, `cognitive_performance_context`, `vascular_polyphenol_context` | Decide whether they deserve dashboards, narrower effects, or demotion. |
| One-off context audit | Low-use `*_context` slugs listed above | Keep only if they are reusable facts, not one-card notes encoded as ontology. |

## Next Pass 1B

Audit the high-use broad effects first, because they produce the largest semantic
surface:

1. `antioxidant_context`
2. `glucose_metabolism_context`
3. `bone_mineral_metabolism_support`
4. `energy_production_support`
5. `neuromuscular_function_support`
6. `lipid_metabolism_support`
7. `blood_pressure_context`
8. `cognitive_performance_context`
9. `vascular_polyphenol_context`

For each one, inspect actual member substances and answer:

- Is the slug a real reusable effect?
- Is it only dashboard membership?
- Does it overlap a cleaner `is`, `risk`, or `pathway` fact?
- Would removing it make reviewer output worse?
- If kept, does the name need to become more specific?

## Pass 1B - High-Use Broad Effect Verdicts

Status: first verdict pass complete, still no ontology edits.

The nine high-use broad effect slugs were inspected against actual member
substances plus their `is`, `risk`, `pathway`, `context`, dashboard, and relation
usage.

### Verdict Table

| Effect slug | Count | Current consumers | Verdict | Why |
|---|---:|---|---|---|
| `antioxidant_context` | 25 | `antioxidant_protection` dashboard | Candidate cleanup / split | It mostly restates `is:antioxidant`, `is:flavonoid`, `is:carotenoid`, and narrower redox/lipid/glutathione facts. It also has several members where the better fix may be class/context correction rather than keeping a broad effect. |
| `glucose_metabolism_context` | 25 | none | High-priority split / purpose check | It mixes incretin drugs, magnesium forms, biotin, lipoic acid, botanicals, chromium/vanadium, and glucose-medication risks. This is too broad to become a dashboard or relation selector as-is. |
| `bone_mineral_metabolism_support` | 22 | none | Keep as coherent axis, decide surface | Membership is coherent: calcium, magnesium, phosphorus, vitamin D/K, boron, strontium, manganese. It overlaps `pathway:vitamin_d_calcium_axis` but covers a wider mineral review view. |
| `energy_production_support` | 18 | none | Candidate consolidation | It overlaps many cleaner pathway facts: `thiamine_energy_metabolism`, `flavin_redox`, `nad_metabolism`, `coa_metabolism`, `electron_transport_chain`, and `vitamin_d_calcium_axis`. The broad slug may be useful for review, but it should not drive relations. |
| `neuromuscular_function_support` | 16 | none | Keep only if review output uses it | Membership is mostly calcium/magnesium plus sodium. It overlaps `is:electrolyte`, `electrolyte_balance`, and `vitamin_d_calcium_axis`. It may be redundant unless a neuromuscular/cramp review view appears. |
| `lipid_metabolism_support` | 14 | `ldl_apob_control`, `vascular_health` dashboards | Keep, but document scope | Membership is mostly plausible LDL/lipid candidates: psyllium, glucomannan, oat beta-glucan, plant sterols, red yeast rice, berberine, niacin, soy protein, garlic, citrus bergamot. The slug is broad but currently useful. |
| `blood_pressure_context` | 13 | none | Do not use as load selector; maybe rename later | Membership mixes magnesium forms, sodium, beetroot, garlic, pomegranate, pycnogenol. This is a review context, not a risk/load signal. Keep away from `hypotensive_load` unless narrowed. |
| `cognitive_performance_context` | 13 | none | Candidate dashboard selector after scope decision | Membership is mostly nootropics plus Panax/Rhodiola and L-tyrosine. It overlaps `is:nootropic`, but captures adaptogen/cognitive-performance items the current neurocognitive dashboard misses. |
| `vascular_polyphenol_context` | 12 | none | Candidate vascular dashboard selector after scope decision | Membership is coherent: flavonoid/polyphenol vascular candidates. It is not currently used by `vascular_health`, which instead relies on explicit `context:vascular_health` for only some members. |

### Concrete Observations

#### `antioxidant_context`

Current members are mostly antioxidants, flavonoids, carotenoids, and botanicals.
The broad effect is carrying dashboard membership for `antioxidant_protection`.

Problem: the slug duplicates several cleaner axes:

- `is:antioxidant`
- `is:flavonoid`
- `is:carotenoid`
- `effect:lipid_antioxidant_support`
- `effect:redox_metabolism_support`
- `effect:glutathione_precursor_support`
- `pathway:glutathione_metabolism`

Likely treatment:

1. keep `antioxidant_protection` broad as a dashboard;
2. reduce dependence on `effect:antioxidant_context`;
3. fix missing `is:antioxidant` or more precise effects on individual cards
   where the broad effect is only compensating for incomplete classification.

Do not mass-delete yet: some cards may currently enter the dashboard only through
this slug.

#### `glucose_metabolism_context`

Current members fall into several different concepts:

- incretin drugs: dulaglutide, exenatide, liraglutide, semaglutide,
  tirzepatide, retatrutide;
- mineral/electrolyte cofactors: many magnesium forms, manganese, chromium,
  vanadium;
- nutrient cofactors: biotin;
- redox/metabolic compounds: alpha lipoic acid and R-lipoic acid;
- botanicals/compounds with glucose-medication review: berberine, cinnamon,
  gymnema, Panax ginseng.

Problem: those are not one effect. They are at least four review concepts:

- incretin-drug pharmacology;
- glucose-medication interaction risk;
- insulin/glucose signaling support;
- broad metabolic cofactor context.

Likely treatment:

- do not use `glucose_metabolism_context` as a dashboard selector yet;
- keep `risk:glucose_med_interaction` for safety;
- keep `effect:incretin_drug_context` or rename it to a drug-class-specific slug;
- consider narrowing the remaining supplement/metabolic use to more concrete
  facts only after dashboard needs are clear.

#### `bone_mineral_metabolism_support`

Current members are coherent and unsurprising. This is probably a valid review
axis, not a Kitchen Sink.

Open decision: should this become a dashboard, or remain a fact surfaced only in
substance review / fact indexes?

Likely treatment:

- keep for now;
- do not create new structure until a bone/mineral review workflow needs it;
- if a dashboard is added later, make it explicit that this is mineral-balance
  review, not dose adequacy.

#### `energy_production_support`

Current members overlap heavily with pathway facts. Many members already have a
cleaner biochemical pathway:

- B1 -> `thiamine_energy_metabolism`
- B2 -> `flavin_redox`
- B3 / NR -> `nad_metabolism`
- B5 -> `coa_metabolism`
- CoQ10 -> `electron_transport_chain`
- magnesium forms -> `vitamin_d_calcium_axis` plus mineral/electrolyte classes

Likely treatment:

- keep away from relations;
- prefer pathway facts in dashboards where possible;
- audit whether the broad slug adds useful review value beyond the pathway list.

#### `neuromuscular_function_support`

Current members are mostly calcium and magnesium forms plus sodium. This is a
real physiological review concept, but it overlaps the electrolyte model.

Likely treatment:

- keep if future review wants cramps/neuromuscular function;
- otherwise do not use it as a dashboard selector yet;
- do not conflate it with workout-performance coverage.

#### `lipid_metabolism_support`

Current membership is fairly coherent for LDL/ApoB review:

- fibers: psyllium, glucomannan, oat beta-glucan, inulin, ground flaxseed;
- phytosterols;
- red yeast rice;
- berberine;
- citrus bergamot;
- niacin;
- soy protein;
- garlic, green tea, artichoke leaf.

Likely treatment:

- keep as the LDL/ApoB dashboard selector;
- keep dashboard wording explicit: this is a candidate review surface, not
  coverage, adequacy, prescription, or safety;
- possibly rename later only if a clearer LDL-specific slug is worth the churn.

#### `blood_pressure_context`

Current membership mixes several meanings:

- mineral/electrolyte blood-pressure context;
- sodium/fluid context;
- botanical/polyphenol vascular context;
- nitrate/NO vasodilation context.

Likely treatment:

- do not use as a relation endpoint;
- do not use as a hypotensive-load selector;
- keep `hypotensive_load` based on narrower risk/effect axes;
- revisit name if a blood-pressure dashboard is added.

#### `cognitive_performance_context`

Current members are mostly nootropics and stimulants, plus a few adaptogens and
amino/vitamin-adjacent items.

Problem: `neurocognitive_support` currently uses `is:nootropic` plus curated
`context:neurocognitive_support`, so this effect is mostly hidden from that
dashboard even though it appears semantically relevant.

Likely treatment:

- decide whether `neurocognitive_support` should be a broad candidate review
  surface;
- if yes, consider adding `effect:cognitive_performance_context` as a dashboard
  selector;
- if no, keep the slug as a narrower product-positioning fact and do not widen
  the dashboard.

#### `vascular_polyphenol_context`

Current members are coherent flavonoid/polyphenol vascular candidates. The slug
is not used by `vascular_health`, while the dashboard currently includes only
some polyphenols through explicit `context:vascular_health`.

Likely treatment:

- decide whether `vascular_health` should include all vascular-polyphenol
  candidates or only operator-curated active vascular priorities;
- if the dashboard is meant for expert comparison, add the effect selector;
- if the dashboard is meant to stay narrower, keep explicit `context` membership
  and document that choice.

## Pass 1B Decision Points

These are the first real decisions before editing YAML:

1. Should broad dashboards show all plausible candidates, or only curated
   high-signal candidates? This affects `antioxidant_context`,
   `vascular_polyphenol_context`, and `cognitive_performance_context`.
2. Do we want a cardiometabolic/glucose dashboard? If yes,
   `glucose_metabolism_context` must be split before use.
3. Do we want a bone/mineral dashboard? If yes,
   `bone_mineral_metabolism_support` is a good seed.
4. Should broad "energy" facts remain as effect slugs, or should mitochondrial
   review rely mostly on pathways?
5. Should `*_context` names be tolerated for review-only selectors, or should
   relation endpoints and dashboard selectors get sharper names first?

No automatic migration should happen until these decisions are made. The lowest
risk immediate cleanup is naming and scope documentation for relation endpoints,
because they have the highest future-inheritance risk.

## Pass 1C - Effect Relation Endpoint Audit

Status: relation endpoint membership checked; high-blast-radius names hardened in
Phase 2.

Effect slugs currently used as relation endpoints:

| Effect endpoint | Current members | Relations using it | Verdict |
|---|---:|---|---|
| `effect:incretin_drug_context` | 6 | 5 | Membership is clean; name is acceptable after Phase 2 hardening. |
| `effect:nitric_oxide_support` | 5 | 1 | Membership and name are acceptable if kept narrow. |
| `effect:gastric_acid_suppressing_drug_context` | 4 | 1 | Membership is clean; name is acceptable after Phase 2 hardening. |
| `effect:pde5_inhibition` | 1 | 1 | Good precise relation endpoint. |

### `effect:incretin_drug_context`

Current members:

- Dulaglutide
- Exenatide
- Liraglutide
- Retatrutide
- Semaglutide
- Tirzepatide

All current members are `is:pharmaceutical` and carry
`risk:incretin_drug_medical_review`. That is good: the endpoint is not currently
pulling ordinary glucose-support supplements into GLP relations.

Relations using this endpoint:

- protein / whey support relation for lean-mass preservation context;
- creatine support relation for lean-mass and training context;
- glucose-medication interaction review;
- metformin review;
- fiber / delayed gastric emptying and GI tolerance review.

Verdict: keep. The slug is now specific enough to signal prescription or
investigational incretin-mimetic drug context rather than ordinary glucose,
appetite, or metabolic supplement context.

### `effect:nitric_oxide_support`

Current members:

- Beetroot extract
- Betaine nitrate / NO3-T
- L-Arginine
- L-Arginine alpha-ketoglutarate
- L-Citrulline malate

All current members also carry `pathway:nitric_oxide_cgmp`. Most carry
`risk:hypotension_med_interaction`. This is a clean category-level endpoint for
NO donor / precursor review.

Relation using this endpoint:

- `review_with` against `effect:pde5_inhibition` for additive vasodilatory /
  hypotension review.

Verdict: keep. The important guardrail is membership discipline: do not add this
effect to generic endothelial, antioxidant, or vascular-health substances unless
they are direct NO substrates, nitrate donors, or equivalent direct NO-support
agents.

### `effect:gastric_acid_suppressing_drug_context`

Current members:

- Cimetidine
- Lansoprazole
- Omeprazole
- Ranitidine

All current members are pharmaceuticals. The relation is a B12 review relation:
acid suppression may reduce absorption of food-bound B12.

Verdict: keep. The slug is now specific enough to mark proton-pump inhibitor and
H2-blocker cards, not ordinary digestive-support supplements. Do not add betaine
HCl, enzymes, probiotics, or other gut-support substances to this endpoint.

### `effect:pde5_inhibition`

Current member:

- Tadalafil

Verdict: keep. This is the cleanest relation endpoint in the group: precise,
mechanistic, and safely future-inheriting if sildenafil/vardenafil/etc. are
added later.

## Pass 1D - Dashboard Selector Impact Checks

Status: simulated selector changes, no dashboard edits yet.

### Antioxidant Protection Without `effect:antioxidant_context`

Simulation: remove only `effect:antioxidant_context` from
`antioxidant_protection`.

Result:

- current members: 49;
- members after removal: 48;
- only lost member: Elderberry extract.

Interpretation: `effect:antioxidant_context` looks broad, but it is not carrying
most antioxidant dashboard membership today. Most members are already captured
through `is:antioxidant`, `context:antioxidant_protection`, narrower effects, or
pathways.

Likely low-risk cleanup path:

1. decide whether Elderberry really belongs in `antioxidant_protection`;
2. if yes, give it a cleaner membership reason (`is:antioxidant` or
   `context:antioxidant_protection`);
3. then remove `effect:antioxidant_context` from the dashboard selector;
4. later decide whether the effect slug itself is still useful as a broad review
   fact.

Do not delete the slug immediately; first inspect cards that still carry it.

### Vascular Health With `effect:vascular_polyphenol_context`

Simulation: add `effect:vascular_polyphenol_context` to `vascular_health`.

Result:

- current members: 31;
- members after addition: 38;
- seven newly included substances:
  - Bilberry
  - Citrus Bioflavonoid Complex
  - Dihydroquercetin
  - Grape extract
  - Hesperidin
  - Quercetin dihydrate
  - Rutin

Interpretation: this is not a simple cleanup. It changes dashboard scope from
"current/operator-curated vascular priorities plus major mechanisms" toward
"all plausible vascular polyphenol candidates." Both can be valid, but they are
different product experiences for an expert agent.

Decision needed: should `vascular_health` be a broad candidate-comparison view
or a narrower high-signal/operator-priority view?

### Neurocognitive Support With `effect:cognitive_performance_context`

Simulation: add `effect:cognitive_performance_context` to
`neurocognitive_support`.

Result:

- current members: 39;
- members after addition: 41;
- two newly included substances:
  - Panax ginseng
  - Rhodiola rosea

Interpretation: most cognitive-performance members already enter through
`is:nootropic`. Adding the effect selector mostly pulls in adaptogens with
cognitive-performance positioning.

Decision needed: should adaptogens with cognitive-performance claims appear in
the neurocognitive dashboard by default? If yes, this is a small, reasonable
selector addition. If no, keep curated `context:neurocognitive_support`.

### LDL / ApoB Control Current Selector

`ldl_apob_control` currently uses only `effect:lipid_metabolism_support`.

Current members:

- Artichoke leaf extract
- Berberine
- Citrus bergamot extract
- Garlic
- Glucomannan
- Green tea extract
- Ground flaxseed
- Inulin
- Oat beta-glucan
- Plant sterols / stanols
- Psyllium husk
- Red yeast rice
- Soy protein
- Vitamin B3 / niacin

Interpretation: this selector is broad but coherent for LDL/ApoB candidate
review. Some members have stronger evidence/centrality than others, but the
dashboard already frames this as a review cluster, not a recommendation.

No immediate ontology cleanup needed here.

### Hypothetical Glucose Dashboard From `glucose_metabolism_context`

Simulation: use `effect:glucose_metabolism_context` as a dashboard selector.

Result: 25 members spanning GLP/GIP drugs, magnesium forms, chromium, vanadium,
biotin, lipoic acid, berberine, cinnamon, gymnema, Panax ginseng, manganese.

Interpretation: this is too mixed for a single clean dashboard without more
structure. A glucose/cardiometabolic review surface probably needs separate
selectors or sections:

- incretin drugs;
- glucose-medication interaction risk;
- glucose/insulin signaling support;
- fiber/appetite/weight-management context;
- mineral/cofactor background.

Do not create a dashboard directly from `glucose_metabolism_context`.

## Pass 1C/1D Immediate Recommendations

Low-risk documentation/modeling recommendations:

1. Treat relation-endpoint effects as stricter than ordinary effect facts.
   Document that they must be narrow and future-inheritance-safe.
2. Relation endpoint names were hardened in Phase 2:
   - `incretin_drug_context`;
   - `gastric_acid_suppressing_drug_context`.
3. Consider removing `effect:antioxidant_context` from the antioxidant dashboard
   after handling Elderberry membership explicitly.
4. Do not add `vascular_polyphenol_context` to `vascular_health` until deciding
   whether that dashboard is broad candidate-comparison or curated high-signal.
5. Consider adding `cognitive_performance_context` to `neurocognitive_support`
   only if adaptogen cognitive positioning should be in-scope.
6. Do not build a glucose dashboard from `glucose_metabolism_context` as-is.

The relation-endpoint naming recommendations were applied in Phase 2. The
dashboard-scope recommendations remain audit conclusions until those dashboard
scope decisions are made.

## Pass 1E - `risk:manual_review` Audit

Status: usage checked, no risk-trait edits yet.

`risk:manual_review` is the largest risk trait by far.

| Signal | Count |
|---|---:|
| Substances with `risk:manual_review` | 113 |
| Active substances with `risk:manual_review` | 13 |
| Non-active/reference substances with `risk:manual_review` | 100 |
| `manual_review` cards with no other risk trait | 58 |
| `manual_review` cards with no `concerns` | 39 |
| `manual_review` cards with no other risk and no `concerns` | 20 |

Top classes carrying `manual_review`:

| `is:` class | Count among manual-review cards |
|---|---:|
| `botanical` | 27 |
| `nootropic` | 20 |
| `pharmaceutical` | 18 |
| `antioxidant` | 10 |
| `fat_soluble` | 10 |
| `mineral` | 9 |
| `adaptogen` | 7 |
| `ergogenic` | 7 |
| `vitamin` | 7 |

Most common co-risks:

| Co-risk | Count |
|---|---:|
| `bleeding_med_interaction` | 16 |
| `serotonergic_med_interaction` | 7 |
| `cyp450_med_interaction` | 6 |
| `incretin_drug_medical_review` | 6 |
| `liver_injury_review` | 4 |
| `hypotension_med_interaction` | 4 |
| `glucose_med_interaction` | 4 |
| `narrow_therapeutic_window` | 4 |

Interpretation: `manual_review` is not a single risk. It currently mixes at
least five meanings:

1. **workflow marker**: "an expert should look at this card before use";
2. **drug marker**: ordinary supplements should not be treated like
   pharmaceuticals or investigational drugs;
3. **product-quality marker**: form, dose, extract standardization, adulteration,
   route, or label completeness materially changes interpretation;
4. **generic medication-context marker**: there may be interactions, but no
   specific risk slug exists yet;
5. **temporary modeling gap marker**: the card has a fact that does not yet have
   a precise ontology home.

That makes `manual_review` a Palantir-style Misnomer and Kitchen Sink candidate:
the name is true but not specific enough to guide an agent.

### Cards Where `manual_review` Explains Least

Cards with `risk:manual_review` as the only risk and no `concerns`:

- Alpha-GPC
- Cimetidine
- Efavirenz
- HICA
- Huperzia serrata
- Lansoprazole
- Levodopa
- Metformin
- Methotrexate
- Midazolam
- N-Acetyl Cysteine
- Omeprazole
- Papain
- Ranitidine
- Rhodiola rosea
- Stinging nettle
- Sulfasalazine
- Vitamin E d-alpha tocopheryl succinate
- Vitamin E tocopherol
- Vitamin E tocotrienols

These are the cleanest audit targets because the flag currently has no local
explanation beyond the generic registry text.

### Active Stack Impact

Active substances currently carrying `manual_review`:

- Copper bisglycinate
- DHA
- EPA
- Ginkgo biloba
- Krill Oil
- L-Carnitine acetyl
- L-Carnitine L-tartrate
- L-Citrulline malate
- Nattokinase
- Potassium citrate
- Red yeast rice
- Vitamin B3 / niacin
- Vitamin E tocopherol

Most active cases already have a more specific co-risk or a safety concern. This
suggests `manual_review` may be redundant noise for active review output when a
specific risk already exists.

### Manual Review Buckets

A heuristic scan of notes/concerns suggests these recurring reasons:

| Bucket | Approx count | Examples |
|---|---:|---|
| medication interaction context | 56 | botanicals, anticoagulant/antiplatelet contexts, CYP/P-gp contexts |
| product quality / standardization / dose uncertainty | 54 | extracts, proprietary blends, research compounds, route-dependent products |
| GI tolerance / GI disease context | 40 | fibers, digestive agents, GLP/incretin drugs, acid/gallbladder contexts |
| hormone/endocrine/pregnancy context | 31 | DHEA, chasteberry, black cohosh, thyroid/iodine contexts |
| pharmaceutical / drug-like card | 19 | metformin, PPIs/H2 blockers, methotrexate, GLP/GIP drugs, tadalafil-like drugs |
| liver context | 14 | black cohosh, green tea extract, cinnamon, ashwagandha, red yeast rice |
| nootropic / research / regulatory context | 13 | racetams, Noopept, Dihexa, Phenibut, Modafinil, Picamilon |

These buckets are not yet proposed schema. They show that one generic risk is
covering several reusable reasons.

### Verdict

`manual_review` should not be treated as an ordinary biological risk. It is a
review workflow marker currently encoded in the risk namespace.

Low-risk path:

1. Keep `risk:manual_review` for now so current warnings and review surfaces do
   not lose information.
2. Do not add new `manual_review` to cards when a specific risk already exists
   and a `concerns` entry can explain the uncertainty.
3. Audit the 20 cards where `manual_review` has no co-risk and no concerns.
   Either add a concrete concern explaining the review need, replace it with a
   specific risk, or remove the generic marker.
4. Consider adding a small number of concrete risk traits only when repeated
   cards need the same reviewer action. Candidate families:
   - `drug_medical_review` for pharmaceuticals that are not ordinary
     supplements;
   - `product_quality_review` for extract/standardization/route uncertainty;
   - `experimental_nootropic_review` for racetams/research nootropics;
   - `hormone_endocrine_review` only if hormone-active cards keep recurring.
5. Longer term, consider whether `manual_review` belongs outside `risk:` as
   review-state metadata. Do not do that during this audit unless the current
   warning output becomes actively harmful.

The Kaizen version: first fix unexplained `manual_review`; only then decide
whether a new mini-taxonomy is justified.

## Execution Roadmap

This roadmap is ordered from lowest product-decision load to highest. The goal is
to improve semantic clarity without turning the ontology into a larger taxonomy
before the existing model is disciplined.

### Phase 1 - Explain Or Remove Unclear `manual_review`

Scope:

- The 20 cards where `risk:manual_review` is the only risk and there are no
  `concerns`.

Goal:

- No substance should carry `manual_review` without a local explanation.

Allowed actions:

- add a concrete `concerns` entry when manual review is genuinely needed;
- replace `manual_review` with a specific existing risk when one fits;
- remove `manual_review` when the card is already adequately represented by
  class/effect/pathway facts and no warning should be emitted.

Do not add a new risk taxonomy in this phase.

### Phase 2 - Harden Relation-Endpoint Effects

Scope:

- `effect:incretin_drug_context`;
- `effect:gastric_acid_suppressing_drug_context`;
- `effect:nitric_oxide_support`;
- `effect:pde5_inhibition`;
- relation endpoint guidance in docs.

Goal:

- Every `effect` used as a relation endpoint must be narrow,
  future-inheritance-safe, and self-explanatory.

Completed changes:

- use `incretin_drug_context` as the drug-class-specific GLP/GIP/incretin
  relation anchor;
- use `gastric_acid_suppressing_drug_context` as the drug-class-specific
  PPI/H2-blocker relation anchor;
- keep `nitric_oxide_support` and `pde5_inhibition` with explicit membership
  guardrails.

### Phase 3 - Low-Impact Dashboard Selector Cleanup

Scope:

- `antioxidant_protection`;
- `effect:antioxidant_context`;
- Elderberry membership.

Goal:

- Remove broad selector dependency where it is not doing useful work.

Expected path:

- decide whether Elderberry belongs in the antioxidant dashboard;
- give Elderberry a cleaner membership reason or let it fall out;
- remove `effect:antioxidant_context` from `antioxidant_protection` selectors;
- keep or remove the underlying effect slug only after checking remaining card
  use.

### Phase 4 - Relation Name/Form Endpoint Scope Audit

Scope:

- `data/relations.yaml`;
- all `source_name` / `target_name` endpoints where the name has multiple forms:
  Magnesium, Calcium, Selenium, Zinc, Copper, Vitamin B12, Vitamin E, Iodine,
  and similar groups.

Goal:

- Confirm whether each name endpoint should intentionally apply to every current
  and future form.

Allowed actions:

- keep name endpoints when the relation is truly all-form;
- narrow to `source_substance` / `target_substance` when form matters;
- add explanatory `reason` text when a broad endpoint is intentional.

### Phase 5 - Dashboard Scope Decisions

Scope:

- `vascular_health`;
- `neurocognitive_support`;
- `glp_incretin_interaction_review`;
- possible glucose/cardiometabolic dashboard;
- possible bone/mineral dashboard.

Goal:

- Decide what kind of product experience each dashboard should provide:
  broad candidate comparison, curated high-signal review, risk-load review, or
  operator-specific context.

Do not change dashboard selectors before the scope decision is explicit.

### Phase 6 - Remaining Trait Registry Audit

Scope:

- low-use `effect:*_context` slugs;
- `is:` taxonomy;
- `pathway:` taxonomy;
- remaining `risk:` slugs.

Goal:

- Remove or rename one-off, vague, or misplaced traits only after the high-blast
  radius issues are handled.

### Phase 7 - Object Boundary / Blend-Like Cards

Scope:

- blend-like substance cards;
- product-label artifacts;
- branded extracts;
- proprietary complexes.

Goal:

- Confirm each substance card represents a reusable real-world entity, not just
  a temporary product-label parsing artifact.

### Phase 8 - Docs And Agent Guidance Sync

Scope:

- `docs/domain-model.md`;
- `docs/ontology-facts.md`;
- `SKILL.md`;
- README/docs index if public guidance changes.

Goal:

- Update docs only after model decisions land, so documentation describes the
  current ontology rather than the audit process.

### Validation Gates

For each implementation phase:

- run `uv run python -m planner check`;
- run targeted audit/review command when the changed surface affects output;
- run `git diff --check`;
- avoid changing `schedule.yaml` unless the phase intentionally changes
  generated output.

## Phase 1 Result - Unclear `manual_review`

Status: completed.

Result:

- unexplained cards with only `risk:manual_review` and no `concerns`: 20 -> 0;
- no new risk taxonomy added;
- `uv run python -m planner check` passes.

Changes made:

- Added concrete concerns to cards where `manual_review` is still needed:
  Alpha-GPC, Cimetidine, Efavirenz, Huperzia serrata, Lansoprazole, Levodopa,
  Metformin, Methotrexate, Midazolam, NAC, Omeprazole, Ranitidine, Rhodiola,
  Stinging nettle, Sulfasalazine, and the three Vitamin E form cards.
- Removed `manual_review` from HICA, where existing ergogenic/effect facts are
  sufficient and no warning-worthy concern was encoded.
- Replaced Papain's generic `manual_review` with the existing
  `risk:bleeding_med_interaction`, matching its notes and the current risk
  registry.

This does not mean `manual_review` is fully solved. It means the most ambiguous
usage class is gone: every remaining standalone `manual_review` now has a local
concern explaining why the card needs operator review.

## Phase 2 Result - Relation-Endpoint Effect Names

Status: completed.

Result:

- old broad relation-anchor names removed from data and docs;
- `uv run python -m planner check` passes;
- `planner review` renders the updated relation labels.

Changes made:

- `incretin_drug_context` is now the GLP/GIP/incretin drug-class relation anchor.
- `gastric_acid_suppressing_drug_context` is now the PPI/H2-blocker relation
  anchor.
- Updated substance cards, `data/relations.yaml`, the GLP dashboard selector,
  `data/traits/effects.yaml`, and domain/audit docs.

Guardrail:

- Do not add ordinary glucose-support, appetite-support, digestive-support, or
  gut-support supplements to either endpoint. These slugs are for drug-class
  relation inheritance, not broad physiology review.

## Phase 3 Result - Antioxidant Dashboard Selector

Status: completed.

Result:

- `antioxidant_protection` no longer depends on the broad
  `effect:antioxidant_context` selector;
- dashboard membership remains at 49 substances;
- `uv run python -m planner check` passes.

Changes made:

- Elderberry extract remains in the antioxidant dashboard through explicit
  `context:antioxidant_protection`.
- `effect:antioxidant_context` was removed from the dashboard selector list.

Reasoning:

- The selector impact check showed that removing `effect:antioxidant_context`
  would drop only Elderberry.
- Elderberry is a reasonable antioxidant-dashboard candidate, but dashboard
  membership is clearer as an explicit curated context than as dependence on a
  broad effect slug.

Guardrail:

- Do not delete `effect:antioxidant_context` yet. It still exists on substance
  cards as a broad review fact. Its future should be decided during the
  remaining trait-registry audit, not as part of this dashboard cleanup.

## Phase 4 Result - Relation Name/Form Scope

Status: completed for current obvious scope errors.

Result:

- multi-form `source_name` / `target_name` endpoints were audited;
- one over-broad endpoint was narrowed;
- `uv run python -m planner check` passes;
- `planner review` now renders the narrowed endpoint as
  `Vitamin A (retinol) -> Vitamin K...`.

Change made:

- The Vitamin A / Vitamin K review relation now uses
  `source_substance: sub_31a1408cad` for Vitamin A retinol instead of
  `source_name: Vitamin A`.

Reasoning:

- `source_name: Vitamin A` matched both retinol and beta-carotene.
- The beta-carotene card explicitly models it as provitamin A and says it should
  not be treated as preformed retinol exposure.
- The relation reason is about preformed vitamin A / retinol, so the endpoint
  should not future-inherit to all cards named Vitamin A.

Reviewed and kept as broad name endpoints:

- mineral-family balance and competition relations: Zinc/Copper, Calcium/Iron,
  Calcium/Zinc;
- B12/B9 balance and medication review relations;
- Selenium/NAC and Selenium/Iodine support relations;
- Magnesium/Calcium and Magnesium/Vitamin D3 support relations;
- Vitamin C/Iron support relation;
- Vitamin E/Vitamin A, Vitamin E/omega-3, and Vitamin E/Vitamin K review
  relations;
- L-Lysine/L-Arginine competition relation, including generic and form-specific
  cards.

Guardrail:

- A name endpoint is acceptable only when the relation is deliberately about the
  nutrient/substance family across forms. If a future card changes the biological
  exposure class, use `source_substance`, `target_substance`, or a narrow trait
  endpoint instead.

## Phase 5 Result - Dashboard Scope Decisions

Status: completed for the current high-signal dashboards.

Result:

- goal dashboards are now treated as candidate-comparison review surfaces unless
  their name explicitly says `Load` or `Interaction Review`;
- operator-specific wording was removed from dashboard descriptions touched in
  this phase;
- `uv run python -m planner check` passes;
- `planner review` shows the expected widened review surfaces.

Changes made:

- Added `data/dashboards/bone_mineral_support.yaml`.
- Added `effect:vascular_polyphenol_context` to `vascular_health`, making the
  dashboard include vascular polyphenol candidates instead of only curated
  vascular priorities and major mechanisms.
- Added `effect:cognitive_performance_context` to `neurocognitive_support`,
  making cognitive-performance adaptogens visible to expert review.
- Removed operator-specific language from `vascular_health`,
  `serotonergic_load`, and `cortisol_reduction` descriptions.

Observed review output after the change:

| Dashboard | Relevant substances | Current stack | On shelf | Knowledge only |
|---|---:|---:|---:|---:|
| Bone / Mineral Support | 23 | 7 | 15 | 1 |
| Neurocognitive Support | 41 | 8 | 14 | 19 |
| Vascular Health | 38 | 9 | 15 | 14 |

Explicit non-change:

- No glucose/cardiometabolic dashboard was added from
  `effect:glucose_metabolism_context`. That slug currently mixes incretin drugs,
  glucose-medication review, minerals, botanicals, lipoic acid, and B vitamins.
  It is too heterogeneous for a clean one-selector dashboard.

Guardrail:

- Use broad semantic selectors for dashboards that are meant to help expert
  agents compare candidates. Use `*_load` dashboards for cumulative risk/load
  review. Use `context:` only when the cluster is intentionally curated and no
  cleaner reusable axis exists.

## Phase 6/7 Result - Remaining Traits And Object Boundaries

Status: completed for obvious low-value cases.

Result:

- one one-off formula-context effect was removed;
- two product-label artifact substance cards were removed;
- substance cards: 255 initial audit snapshot -> 253 after cleanup;
- `uv run python -m planner check` passes.

Changes made:

- Removed `effect:b_complex_matrix_context` from Inositol and deleted the effect
  registry entry. The B-complex label context remains in Inositol notes, but it
  is not modeled as a reusable biological effect.
- Removed `Orchard Fruits & Garden Veggies Blend` as a substance card. The
  100 mg proprietary blend label fact now lives in the Nature's Way Alive Calcium
  product note.
- Removed `AstraGin` as a substance card. The 25 mg branded blend label fact now
  lives in the Genius Pre product note.

Reasoning:

- Both removed blend cards were label-backed product details with no current
  scheduler, dashboard, relation, or reusable review trait.
- Keeping them as substance cards made the ontology look more precise than it
  was. The product notes preserve the label information without creating reusable
  entities for non-actionable proprietary blends.
- Other low-use `*_context` effects were kept when they named precise reusable
  facts, for example urinary adhesion, fluid balance, mild stimulant context,
  carnosine buffering, and catecholamine precursor context.

Guardrail:

- Blend-like cards are valid when the blend is itself a reusable review entity
  or has scheduler/dashboard/relation behavior. If a blend is only a proprietary
  label line with no actionable traits, keep it in the product note instead of
  creating a substance card.

## Phase 8 Result - Documentation And Validation

Status: completed.

Docs updated:

- `docs/domain-model.md` now states the proprietary-blend boundary, dashboard
  scope categories, and the all-forms semantics of `source_name` /
  `target_name` relation endpoints.
- `docs/ontology-facts.md` now records the current boundaries for
  candidate-comparison dashboards and label-only blends.
- `SKILL.md` now tells agents to keep non-actionable proprietary blends in
  product notes, to treat `source_name` / `target_name` as all-current-and-future
  forms, and to name dashboard scope explicitly.

Validation:

- `uv run python -m planner` regenerated `schedule.yaml`;
- `uv run python -m planner review` passes and reports 20 dashboard views;
- `uv run python -m planner audit` reports 0 actionable diagnostics, 0 unused
  review traits, 0 empty dashboards, and 0 potential duplicate substance cards;
- `git diff --check` passes;
- `just check` passes: ruff, pyright, `planner check`, and 139 pytest tests.

Remaining explicit decision:

- Do not build a glucose/cardiometabolic dashboard from
  `effect:glucose_metabolism_context` as-is. That requires a separate modeling
  decision because the current slug mixes incretin drugs, glucose-interaction
  risks, minerals, botanicals, lipoic acid, and B-vitamin cofactors.
