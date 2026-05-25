# Ontology Audit 2 - 2026-05-24

Status: second audit findings. This document is intentionally separate from
`260524-ontology.md`, which records the first Palantir-framed ontology audit and
the cleanup phases that followed it.

Source frame:
[Palantir - Ontology design: Best practices and anti-patterns](https://www.palantir.com/docs/foundry/ontology/ontology-best-practices-and-anti-patterns).

## Audit Goal

The first audit removed several obvious broad buckets and product-label
artifacts. This second audit checks what remains after that cleanup.

The focus is not structural validity. The current repository already validates.
The focus is Palantir-style semantic drift:

- stale review tags that no longer drive a dashboard;
- broad `effect:*_context` slugs that survive without a clear consumer;
- generic review markers that explain little by themselves;
- relation endpoints whose matching scope could surprise future cards;
- product-label concepts that may still be pretending to be reusable
  substances.

## Initial Second-Audit Snapshot

Commands and scans run during this audit:

- `git status --short --branch`
- YAML scan over `data/substances`, `data/products`, `data/dashboards`,
  `data/relations.yaml`, and `data/traits/*.yaml`
- `uv run python -m planner audit --full`
- `uv run python -m planner review`

Observed state before implementing the second-audit cleanup phases:

| Surface | Current signal |
|---|---:|
| Substance cards | 253 |
| Product cards | 58 |
| Dashboard files | 21 |
| Relation entries | 36 |
| Registered `effect` slugs | 122 |
| Used `effect:*_context` slugs | 78 |
| `effect:*_context` assignments | 345 |
| Substances carrying `risk:manual_review` | 110 |
| Active substances carrying `risk:manual_review` | 13 |
| `manual_review` as only risk | 55 |
| `manual_review` with no local concern | 19 |
| `manual_review` as only risk and no local concern | 0 |
| `planner audit --full` actionable diagnostics | 0 |
| `planner review` active concerns | 22 |
| `planner review` actionable relations | 4 |
| `planner review` active risk memberships | 32 |
| `planner review` dashboard views | 21 |

Interpretation: the first audit succeeded structurally. The remaining issues are
mostly semantic clarity and future-maintenance risks.

## Findings

### Finding 1 - Stale `context:` Tags Survived The Dashboard Refactor

Severity: medium. Anti-patterns: Misnomer, Kitchen Sink residue.

`knowledge.context` is documented as curated dashboard membership. Most current
context slugs line up with dashboard `from_traits.context` selectors, but two no
longer do:

| Context slug | Substance assignments | Dashboard selector? | Current dashboard reality |
|---|---:|---|---|
| `electrolyte_balance` | 10 | no | `Electrolyte Balance` now selects `is:electrolyte` |
| `hypotensive_load` | 1 | no | `Hypotensive Load` now selects `risk:` and `effect:` axes |

This is stale ontology residue. These tags do not add dashboard membership, do
not drive scheduling, and are not registered as reusable facts. They make the
card look more intentionally curated than it is.

Recommendation:

- remove `context:electrolyte_balance` from the 10 mineral/electrolyte cards;
- remove `context:hypotensive_load` from Betaine nitrate / NO3-T;
- consider adding an audit diagnostic for `context:` slugs that are not used by
  any dashboard selector, unless a future explicit exception exists.

### Finding 2 - `effect:antioxidant_context` Is Now Redundant

Severity: medium. Anti-pattern: Kitchen Sink.

The first audit removed `effect:antioxidant_context` from the
`antioxidant_protection` dashboard selector. After that, the effect remains on
25 substances but has no dashboard or relation consumer.

All 25 current members still have another dashboard membership path:

- many have `is:antioxidant`;
- many have `context:antioxidant_protection`;
- vascular polyphenols have `effect:vascular_polyphenol_context`;
- lipid/redox/glutathione cards have narrower effect or pathway facts.

This means `effect:antioxidant_context` now mostly repeats other facts. It is a
good second-audit cleanup target.

Recommendation:

- remove `effect:antioxidant_context` from substance cards;
- delete the registry entry after all card assignments are gone;
- keep specific antioxidant facts such as `lipid_antioxidant_support`,
  `redox_metabolism_support`, `glutathione_precursor_support`, and
  `antioxidant_enzyme_cofactor`.

Do not replace it with another broad umbrella.

### Finding 3 - Several No-Consumer `*_context` Effects Are Hidden Backlog

Severity: medium. Anti-patterns: Kitchen Sink, The Misnomer.

High-use context effects with no dashboard or relation consumer remain:

| Effect slug | Assignments | Active assignments | Initial read |
|---|---:|---:|---|
| `blood_pressure_context` | 13 | 3 | Mixed electrolyte, sodium, nitrate/polyphenol, and vascular context. Keep away from `hypotensive_load` unless narrowed. |
| `appetite_context` | 11 | 0 | Mixes incretin drugs, fibers, gymnema, African mango. Could be dashboard backlog or prose. |
| `weight_metabolic_context` | 9 | 0 | Overlaps incretin and appetite/weight positioning. Needs purpose check before any dashboard use. |
| `joint_comfort_context` | 9 | 0 | Looks like a missing joint-review dashboard candidate, not a scheduling fact. |
| `blood_clotting_context` | 9 | 2 | Concrete biology but not currently a load/relation selector. Keep separate from bleeding load. |
| `neurocognitive_context` | 9 | 1 | Overlaps `neurocognitive_support` and `cognitive_performance_context`; name is vague. |
| `essential_amino_acid_context` | 7 | 0 | Possibly class-like rather than effect-like. |
| `learning_context` | 6 | 0 | Likely too vague unless a learning/memory dashboard exists. |
| `capillary_support_context` | 6 | 0 | More concrete; may be a vascular/skin selector candidate. |
| `polyphenol_context` | 5 | 0 | Looks class-like or dashboard-adjacent rather than effect-like. |
| `stress_resilience_context` | 5 | 0 | Overlaps adaptogen/cortisol/cognitive positioning. |
| `memory_recall_context` | 5 | 0 | Could be a neurocognitive sub-axis, but not currently consumed. |
| `ocular_retina_context` | 5 | 0 | Clear candidate for a future eye/retina review dashboard. |

These are not all bad. The problem is that they are mixed:

- some are real reusable review facts;
- some are dashboard backlog;
- some are class-like labels living under `effect:`;
- some may be one-off prose encoded as ontology.

Recommendation:

- do not mass-delete this class;
- process one cluster at a time;
- for each slug, choose exactly one fate: keep as reusable effect, connect to a
  dashboard, move to `is:` / `pathway:` / `risk:`, or demote to notes/concerns.

### Finding 4 - `manual_review` Is Explained But Still Overloaded

Severity: low-medium. Anti-pattern: Misnomer.

The first audit fixed the worst `manual_review` problem:

- there are now zero cards where `manual_review` is the only risk and there is
  no local concern.

The remaining shape is still broad:

- 110 substances carry `risk:manual_review`;
- 55 use it as the only risk;
- 19 have no local concern, but they do have other risk traits;
- 13 active substances carry it.

This is acceptable as a workflow marker, but weak as a biological risk. The
important distinction is already emerging:

- specific risks such as `bleeding_med_interaction`,
  `glucose_med_interaction`, `hypotension_med_interaction`, and
  `tmao_cardiometabolic_review` are useful;
- `manual_review` is a "human must inspect this" marker.

Recommendation:

- keep `manual_review` for now;
- do not add it to new cards when a specific risk plus a local concern would be
  clearer;
- only split it into new traits when repeated cards need the same reviewer
  action in output.

Possible future splits, only if output needs them:

- `drug_medical_review`;
- `product_quality_review`;
- `experimental_nootropic_review`;
- `hormone_endocrine_review`.

### Finding 5 - Relation Trait Endpoints Are Currently Disciplined

Severity: low.

Trait endpoints are the highest future-inheritance risk because new cards
inherit relations automatically. Current relation trait endpoints are still
small and understandable:

| Trait endpoint | Current members | Relation references | Verdict |
|---|---:|---:|---|
| `effect:incretin_drug_context` | 6 | 5 | Keep; drug-class-specific and clean. |
| `effect:gastric_acid_suppressing_drug_context` | 4 | 1 | Keep; PPI/H2-blocker-specific and clean. |
| `effect:nitric_oxide_support` | 5 | 1 | Keep narrow; direct NO donors/precursors only. |
| `effect:pde5_inhibition` | 1 | 1 | Keep; precise mechanism. |
| `is:fiber` | 7 | 1 | Acceptable for GLP/fiber GI review, but future fiber cards inherit the relation. |
| `pathway:omega3_eicosanoid` | 3 | 1 | Acceptable if all omega-3 pathway members need vitamin E/peroxidation review. |
| `risk:glucose_med_interaction` | 6 | 1 | Acceptable as safety-review endpoint. |

Recommendation:

- keep current trait endpoints;
- continue to reject broad dashboard selectors as relation endpoints;
- preview current and likely future members before adding any new relation trait
  endpoint.

### Finding 6 - All-Form Name Endpoints Need Ongoing Reason Text Discipline

Severity: low.

The obvious over-broad `Vitamin A` endpoint was already narrowed in the first
audit. Remaining multi-form name endpoints mostly look intentional: minerals,
vitamins, B12/B9, zinc/copper, calcium/iron, magnesium/vitamin D, and amino-acid
competition.

The main maintenance risk is not a known current bug; it is unclear future
reader intent. A `source_name` or `target_name` endpoint means every current and
future form with that `name` inherits the relation.

Recommendation:

- keep all current broad name endpoints unless a form-specific counterexample
  appears;
- when editing a broad endpoint reason, state all-form intent explicitly when
  the name has many forms;
- prefer `source_substance` / `target_substance` when a future card could change
  biological exposure class.

### Finding 7 - Remaining Blend-Like Substance Cards Are Defensible

Severity: low.

After the first audit removed obvious product-label artifacts, the remaining
blend/complex candidates have product references and explicit review behavior:

| Substance | Current read |
|---|---|
| `Citrus Bioflavonoid Complex` | Label-backed but useful as undisclosed flavonoid/polyphenol review component. |
| `Fiber seed blend` | Product-level fiber/seed matrix with gut-regularity and microbiome review behavior. |
| `Probiotic blend` | Product-level probiotic marker until strain-level behavior is needed. |
| Mineral `amino acid chelate complex` cards | Form/source review is material enough to keep separate. |
| `Sea-Iodine Complex` | Mixed iodine source with dose/source variability, worth separate review. |

Recommendation:

- do not delete these just because the names contain `blend` or `complex`;
- keep requiring local notes that explain why a blend is reusable enough to be a
  substance card;
- continue putting non-actionable proprietary label lines in product notes.

## Recommended Next Work

Order matters. Start with the lowest-ambiguity cleanup and leave taxonomy
expansion until a real review surface needs it.

### Phase A - Remove Stale Dashboard Context Tags

Scope:

- `context:electrolyte_balance`;
- `context:hypotensive_load`.

Goal:

- no `context:` slug should remain unless it is actually used by a dashboard
  selector or explicitly documented as a rare exception.

Validation:

- `uv run python -m planner check`;
- `uv run python -m planner review`;
- confirm dashboard counts are unchanged except for any context-list display.

Result:

- completed;
- removed `context:electrolyte_balance` from the 10 mineral/electrolyte cards;
- removed `context:hypotensive_load` from Betaine nitrate / NO3-T while keeping
  its `vascular_health` and `workout_performance` contexts;
- no unused `knowledge.context` slugs remain;
- `planner review` still reports `Electrolyte Balance` at 17 relevant
  substances and `Hypotensive Load` at 7 relevant substances.

### Phase B - Remove Redundant `effect:antioxidant_context`

Scope:

- 25 substance cards currently carrying `effect:antioxidant_context`;
- registry entry in `data/traits/effects.yaml`.

Goal:

- remove a broad no-consumer effect without changing antioxidant dashboard
  membership.

Validation:

- `uv run python -m planner check`;
- `uv run python -m planner review`;
- confirm `Antioxidant Protection` remains at 49 members.

Result:

- completed;
- removed `effect:antioxidant_context` from 25 substance cards;
- deleted the `antioxidant_context` registry entry from
  `data/traits/effects.yaml`;
- no `antioxidant_context` references remain under `data/`;
- `planner review` still reports `Antioxidant Protection` at 49 relevant
  substances.

### Phase C - Classify Remaining No-Consumer Context Effects

Scope:

- `blood_pressure_context`;
- `appetite_context`;
- `weight_metabolic_context`;
- `joint_comfort_context`;
- `neurocognitive_context`;
- `essential_amino_acid_context`;
- `ocular_retina_context`;
- other low-use `*_context` effects.

Goal:

- for each slug, decide whether it is a real reusable effect, a dashboard
  selector candidate, a misplaced class/pathway/risk, or prose.

Validation:

- document decisions before broad edits;
- avoid adding new dashboards unless the review question is clear.

#### Phase C1 Result - `blood_pressure_context`

Status: completed.

Result:

- removed `effect:blood_pressure_context` from 13 substance cards;
- deleted the `blood_pressure_context` registry entry from
  `data/traits/effects.yaml`;
- updated `vascular_polyphenol_context` guidance so it points to narrower
  vascular-tone, capillary, or safety-risk facts instead of the deleted broad
  effect;
- no `blood_pressure_context` references remain under `data/`.

Reasoning:

- the slug had no dashboard or relation consumer;
- nitrate/NO members already carry `nitrate_context`, `nitric_oxide_support`,
  `pathway:nitric_oxide_cgmp`, and/or `risk:hypotension_med_interaction`;
- vascular botanicals/polyphenols already carry `vascular_tone_context`,
  `vascular_polyphenol_context`, `endothelial_context`, or `vascular_health`;
- magnesium and sodium are already represented through `is:electrolyte`,
  `fluid_balance_context`, `bone_mineral_metabolism_support`, and notes;
- a future blood-pressure review surface should be built from narrower axes, not
  by recreating this umbrella effect.

Validation:

- `uv run python -m planner check` passes;
- `planner review` still reports `Electrolyte Balance` at 17 relevant
  substances, `Hypotensive Load` at 7 relevant substances, and `Vascular Health`
  at 38 relevant substances.

#### Phase C2 Result - `appetite_context` And `weight_metabolic_context`

Status: completed.

Result:

- removed `effect:appetite_context` from 11 substance cards;
- removed `effect:weight_metabolic_context` from 9 substance cards;
- deleted both registry entries from `data/traits/effects.yaml`;
- no `appetite_context` or `weight_metabolic_context` references remain under
  `data/`.

Reasoning:

- neither slug had a dashboard or relation consumer;
- incretin-drug cards already carry `effect:incretin_drug_context` and
  `risk:incretin_drug_medical_review`;
- fiber cards already carry `is:fiber`, digestive/gut effects, and/or
  `effect:lipid_metabolism_support`;
- Gymnema already carries `effect:insulin_signaling_context` and
  `risk:glucose_med_interaction`;
- African Mango and MCT weight/appetite positioning remains in notes rather than
  as reusable ontology facts until a concrete review surface needs it;
- no weight/appetite dashboard was added because the current grouping would mix
  drug pharmacology, fiber satiety, glucose-interaction review, and marketing
  positioning.

Validation:

- `uv run python -m planner check` passes;
- `planner review` still reports `GLP / Incretin Interaction Review` at 23,
  `Glucose / Glycemic Review` at 13, `Digestive / Gut Support` at 26, and
  `LDL / ApoB Control` at 14 relevant substances.

#### Phase C3 Result - `joint_comfort_context`

Status: completed.

Result:

- kept `effect:joint_comfort_context` as a real reusable review fact;
- added `data/dashboards/joint_comfort_review.yaml`;
- the new dashboard projects from `effect:joint_comfort_context`,
  `effect:cartilage_matrix_context`, `effect:glycosaminoglycan_context`,
  `effect:joint_lubrication_context`, and
  `effect:sulfur_connective_tissue_context`;
- no substance cards were changed for this phase.

Reasoning:

- unlike the deleted umbrella effects, `joint_comfort_context` is not redundant
  for all members;
- Boswellia, Ginger, and Turmeric would lose their only structured joint signal
  if the effect were deleted;
- adding `joint_comfort_context` to `Connective Tissue Support` would blur a
  collagen/matrix dashboard with symptom-oriented joint-comfort review;
- a separate dashboard keeps cartilage substrates, lubrication-positioned
  ingredients, collagen/connective-tissue supports, and anti-inflammatory
  joint-positioned botanicals visible without changing scheduling behavior.

Validation:

- `uv run python -m planner check` passes;
- final `planner review` reports 27 dashboard views after later Phase C routing;
- `Joint Comfort Review` reports 11 relevant substances: 0 current, 10 on shelf,
  and 1 knowledge-only;
- `uv run python -m planner audit --full` still reports 0 actionable diagnostics.

#### Phase C4 Result - `neurocognitive_context`

Status: completed.

Result:

- removed `effect:neurocognitive_context` from 9 substance cards;
- deleted the `neurocognitive_context` registry entry from
  `data/traits/effects.yaml`;
- updated `nervous_system_support` guidance so it no longer points to the
  deleted broad neurocognitive effect;
- no `neurocognitive_context` references remain under `data/`.

Reasoning:

- the slug had no dashboard or relation consumer;
- almost all members already enter `Neurocognitive Support` through
  `is:nootropic`, `context:neurocognitive_support`, or
  `effect:cognitive_performance_context`;
- narrower member facts remain, such as `catecholamine_precursor_context`,
  `phospholipid_membrane_context`, `circulation_support`,
  `vascular_tone_context`, `stress_reactivity_context`, and
  `nervous_system_support`;
- S-Adenosylmethionine stays represented through methylation and serotonergic
  review rather than a broad brain-function tag.

Validation:

- `uv run python -m planner check` passes;
- `planner review` still reports `Neurocognitive Support` at 41 relevant
  substances, `Methylation Support` at 13, and `Serotonergic Load` at 7.

#### Phase C5 Result - Route The Remaining Useful Context Effects

Status: completed.

Result:

- added five review dashboards:
  - `data/dashboards/eye_retina_support.yaml`;
  - `data/dashboards/stress_adaptogen_review.yaml`;
  - `data/dashboards/immune_barrier_review.yaml`;
  - `data/dashboards/urinary_tract_review.yaml`;
  - `data/dashboards/cyp_medication_metabolism_review.yaml`;
- expanded existing dashboards with narrow selectors:
  - `Neurocognitive Support`: alertness, learning, memory, stimulant,
    focus-relaxation, catecholamine precursor, phospholipid membrane, and
    stress-performance context;
  - `Vascular Health`: capillary and endothelial context;
  - `Bone / Mineral Support`: vascular calcification context;
  - `Joint Comfort Review`: glycosaminoglycan and sulfur connective-tissue
    context;
  - `Workout Performance`: anti-catabolic and leucine-metabolite context;
  - `Electrolyte Balance`: fluid-balance context;
- narrowed `phospholipid_membrane_context` to neurocognitive membrane-precursor
  use and removed it from generic Phosphorus and Krill Oil cards so it does not
  pull non-nootropic structural-lipid facts into `Neurocognitive Support`.

Reasoning:

- these slugs had coherent review questions and were not merely class labels;
- adding selectors to already coherent dashboards changed intent more than
  membership in most cases;
- new dashboards were added only where the user-facing review question is clear:
  eye/retina, stress/adaptogen, immune/barrier, urinary tract, and CYP/medication
  metabolism.

Validation:

- no assigned `effect:*_context` slug remains without a dashboard or relation
  consumer;
- `uv run python -m planner check` passes;
- `planner review` reports 27 dashboards, 20 with current members and 7 with
  zero current members;
- new dashboard counts:
  - `CYP / Medication Metabolism Review`: 9 relevant substances;
  - `Eye / Retina Support`: 7;
  - `Immune / Barrier Review`: 13;
  - `Stress / Adaptogen Review`: 10;
  - `Urinary Tract Review`: 3.

#### Phase C6 Result - Delete Remaining Broad Or Prose-Like Context Effects

Status: completed.

Result:

- deleted broad/class-like no-consumer effects from cards and registry:
  `blood_clotting_context`, `essential_amino_acid_context`,
  `polyphenol_context`, `energy_context`, and `lipid_membrane_context`;
- deleted one-off mechanism/tolerance effects from cards and registry:
  `cell_signaling_context`, `nitrogen_metabolism_context`, `longevity_context`,
  `paresthesia_tolerance_context`, `purine_metabolism_context`, and
  `osmolyte_context`;
- updated `amino_acid_metabolism_support` guidance so it no longer references
  the deleted `essential_amino_acid_context`.

Reasoning:

- `blood_clotting_context` mixed calcium biology with vitamin-K safety review;
  vitamin K cards still carry `risk:vitamin_k_anticoagulant_review` and
  `effect:vascular_calcification_context`, while calcium forms remain covered by
  bone/mineral and electrolyte facts;
- `essential_amino_acid_context` and `polyphenol_context` were class-like labels
  living under `effect:`;
- `energy_context` mostly repeated product positioning and is better represented
  by narrower fatigue, endurance, cognitive, mitochondrial, or fatty-acid facts;
- the one-off slugs were better kept in notes or narrower effects until repeated
  cards need a reusable dashboard/relation behavior.

Validation:

- exact data scan reports zero assigned no-consumer `effect:*_context` slugs;
- `uv run python -m planner check` passes;
- `uv run python -m planner audit --full` reports `0 actionable, 49
  reference/review`;
- `git diff --check` passes.

### Phase D - Consider A Small `manual_review` Split Only If Output Needs It

Scope:

- cards where `manual_review` is the only risk;
- active cards where `manual_review` adds little beyond a specific co-risk.

Goal:

- improve reviewer actionability without creating a large safety taxonomy.

Validation:

- `planner review` should become clearer, not merely more categorized.

Result:

- no split implemented in this audit;
- `risk:manual_review` remains an operator-review marker rather than a
  biological risk axis;
- active review output is already carried by concrete concerns and specific
  risk surfaces such as bleeding, glucose, hypotension, CYP/medication
  metabolism, serotonergic, incretin, vitamin K/anticoagulant, and
  statin-like/monacolin review.

Reasoning:

- splitting `manual_review` now would mostly duplicate existing specific risks
  or local concern text;
- there are still zero cards where `manual_review` is the only risk and there
  is no local concern;
- a future split should be driven by repeated reviewer actions in output, not by
  taxonomy neatness.

Validation:

- `planner review` still reports 13 active `manual_review` memberships, but the
  active safety section is explained by concrete concern text and co-risks;
- `uv run python -m planner audit --full` remains at `0 actionable, 49
  reference/review`.

### Phase E - Add Audit Diagnostics For Stale Semantic Tags

Potential checks:

- `knowledge.context` slug not referenced by any dashboard selector;
- high-use `effect:*_context` slug with no dashboard or relation consumer;
- relation trait endpoint whose member count exceeds a configurable threshold.

Result:

- added `planner audit` cleanup diagnostics for:
  - `context.without_dashboard_selector`;
  - `effects.context_without_consumer`;
- added tests proving that stale context tags and high-use unconsumed
  `effect:*_context` slugs are reported with a concrete resolution hint;
- deferred the relation-endpoint-size diagnostic because the current broad
  relation endpoints (`is:mineral` and `is:fat_soluble`) are intentional
  scheduler rules; a raw threshold would be noisy without an allowlist or
  relation-specific policy.

Reasoning:

- the first two diagnostics directly target drift fixed in Phase A, Phase B, and
  Phase C;
- both diagnostics are quiet on the current ontology after this cleanup;
- the relation-endpoint diagnostic needs more policy before implementation.

Validation:

- `uv run ruff check planner/query_model/audit.py planner/engine/audit.py
  tests/test_audit_command.py` passes;
- `uv run pytest tests/test_audit_command.py` passes: 13 tests;
- `uv run python -m planner audit --full` remains at `0 actionable, 49
  reference/review`, proving the new diagnostics are quiet on the cleaned data.

## Decision Summary

Second-audit conclusion: the ontology is structurally healthy and the first
audit removed the worst object-boundary problems. The next meaningful work is
not a new ontology layer. It is removing stale semantic residue and forcing each
remaining broad context slug to justify its role.

## Post-Audit Data Quality Follow-Up

The next cleanup pass targeted `planner audit --full` product-source noise
without inventing missing product facts or turning amount metadata into a dose
model.

Implemented:

- added source URLs and serving notes for label-backed active products where a
  current source was available: Best Naturals ALCAR, Country Life Coenzyme
  B-Complex, Do4a creatine, Futurebiotics D3, Life Extension Only Trace
  Minerals, Primecraft/Prime Kraft LCLT, and TiM Electrolyte Caps;
- filled Country Life Coenzyme B-Complex component amounts from the official
  2-capsule Supplement Facts serving;
- added component notes for Minami's undisclosed secondary formula ingredients
  instead of inventing amounts;
- updated tadalafil to the user-confirmed 1.25 mg microdosing context;
- marked BioGrace B5, Harmony Aqua astaxanthin, unbranded L-citrulline malate,
  Tadalista tadalafil, VitaMeal vitamin C, and Vitamir magnesium glycinate as
  unresolved source/label captures in product notes;
- added `food_preferred` intake for magnesium glycinate so the mineral card is
  schedulable like the rest of the active mineral products;
- removed the duplicated generic zeaxanthin component from Jarrow MaculaPF,
  where 13 mg generic zeaxanthin was already represented as 9 mg meso-zeaxanthin
  plus 4 mg RR-zeaxanthin.

Validation:

- `uv run python -m planner audit --full` now reports `Full audit (10)`, down
  from `Full audit (19)`;
- `Product component substances missing intake: trait` is now `0`;
- missing component amounts are no longer full-audit gaps because this ontology
  is for interaction/relation review, not dose computation;
- remaining active product gaps are intentional unresolved facts: missing source
  URLs and missing brand/source identity for the unbranded citrulline card;
- generic no-form card warnings remain documented review prompts, not automatic
  remap targets.
