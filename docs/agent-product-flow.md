# Agent Product Flow

This document is the guided product workflow for agents using this repository with a real person. It is for structured supplement-stack thinking and data maintenance. It is not medical advice.

It is the single authoritative lifecycle workflow for adding a Product, adding a
Substance, or improving an existing Substance card. [docs/domain-model.md](domain-model.md)
owns semantic meaning and field ownership; [SKILL.md](../SKILL.md) is the short
operator entrypoint. [Evidence Coverage Grooming](evidence-coverage-grooming.md)
documents the implemented minimal read-only queue and the deferred
broader-coverage design; it is not a replacement for this workflow.

## Authoritative Card Lifecycle

Use this pipeline for every new or changed Product, Substance, form, or related
domain fact. The three event playbooks below choose the starting point and the
applicable questions; they do not skip the common stages.

1. **Capture the physical source first.** Transcribe the label, product,
   manufacturer, source URL, component labels/forms, amounts, serving details,
   and other material label facts losslessly. Keep `Product.name` a concise
   bottle-facing/commercial title: do not append a chemical form, dose or
   strength, package count, or ontology qualifier merely to make it complete.
   Route those details to `substance.form`, `component.label`,
   `component.amount`, product `notes`, or substance knowledge as appropriate.
2. **Search and reuse identities.** Run `uv run python -m planner find` for
   the product, substance, aliases, and form. Reuse an existing Product or
   concrete Substance/form identity when it matches; do not create a duplicate
   parent taxonomy card or a second form identity for spelling variation.
3. **Inspect ontology placement for new active substances.** A new card is not
   complete merely because its schema validates. Inspect existing vocabulary,
   neighboring forms, mechanisms, dashboard selectors, relations, and active
   stack matches. Prefer existing terms and choose deliberately among
   `schedule`, `knowledge`, concerns, relations, and dashboards.
4. **Research cards holistically, then adjudicate.** The substance card is the
   unit of grooming work. The CLI supplies one priority card by default. An
   orchestrator may assign one additional card only when current output shows
   a concrete shared relation, exact repeated claim, or clearly shared narrow
   evidence context; predicate/category equality alone is insufficient. Both
   assigned cards receive a complete holistic pass over meaningful unresolved
   knowledge assertions and relation leads, as well as applicable scheduling
   questions; do not turn assertion rows into separate jobs. A Luna/evidence worker collects sources
   and candidate claims, and Sol/the expert adjudicates what is admitted
   against the repository's conservative threshold. Luna may implement only
   admitted facts. Manufacturer instructions establish
   formulation/composition and can be useful leads, but do not outrank
   independent medical or biochemical evidence for general scheduling or
   recommendations.
5. **Formalize each admitted result in its proper layer.** Use Product cards for
   label/formulation facts; Substance `knowledge` for reusable substance
   knowledge; Substance `schedule` for executable meal/time/activity assertions;
   `scheduling_assessment` for the review state of each applicable axis;
   `data/relations.yaml` for cross-substance links; dashboards for review
   surfaces; `concerns` for bounded high-signal prose without a better
   executable home; and no change when no admitted fact exists.
6. **Validate behavior, not just structure.** Run the relevant bounded `just`
   validation recipe, inspect real planner output, review warnings, relations,
   dashboards, and the per-product schedule explanations. A balance or tie slot
   is a technical placement outcome, never evidence that timing is optimal.
7. **Preserve research state.** Record negative or insufficient research so the
   same question is not repeatedly rediscovered. `insufficient`,
   `supports_no_rule`, and `conflicting` are assessed states; an omitted axis
   is `unassessed`, not a claim of neutrality or support. Knowledge and
   relation `research_state` plus `sources` remain provenance on assertions;
   they do not split the card into assertion-level queue tasks.
8. **Clean and commit the coherent cluster.** Inspect `git diff` and
   `git status`, keep generated output separate from source edits, remove
   temporary artifacts, and commit the complete related documentation/data
   cluster only after the acceptance checklist below passes.

### Event playbooks

#### New Product using existing substances

Capture the exact physical label and product identity, search/reuse the Product
and every concrete Substance/form, then verify that the existing facts actually
apply to the labelled form, carrier, and formulation. Do not blindly inherit a
generic or form-mismatched scheduling or review claim. Add the product card,
preserve non-scheduler label details in the correct fields, choose its stack
state, validate, and inspect explanations. If no new substance or admitted
fact is involved, do not manufacture enrichment merely to fill fields.

#### New Product introducing new substances or forms

Capture the exact minimal identity first: concise product name, component label,
amount, and exact form. Create the missing concrete Substance/form only after
identity reuse has been checked; let `planner check` assign stable IDs. For an
active product, perform the mandatory bounded semantic enrichment attempt:
inspect ontology placement and applicable evidence questions, separate Luna's
search from Sol's adjudication, and record admitted knowledge, schedule facts,
assessments, relations, dashboards, or concerns in their proper layers. Product
creation is not blocked when evidence is unavailable, but the resulting
`unassessed` or `insufficient` state must remain visible for grooming. Leave
unsupported claims out.

#### Improve or groom an existing Substance

Start from a concrete signal: a journal `no-scheduling-fact` or assessment
state, weak explanation, mixed votes, warning, active dashboard goal, or an
explicit user question. Treat the card as one holistic work item: inspect all
meaningful unresolved knowledge assertions and relation leads in the same
bounded pass, alongside scheduling applicability for the substance/form/product.
Update provenance and assessed states even when the conclusion is
`insufficient`, `supports_no_rule`, or `conflicting`; do not reopen an assessed
assertion without new evidence or changed applicability. Add an executable
`schedule.*` fact only when an adjudicated same-axis result supports it, then
inspect the planner's actual explanation and any global balance effects.

#### Practical evidence calibration

This practical slotter may use weak but transparent scheduling heuristics. Direct
human fed-versus-fasted, clock-time, or activity comparisons are preferred, but
their absence does not by itself require deleting a useful soft heuristic. A
soft preference may be admitted when lower-tier evidence converges on a coherent
direction that applies to the exact substance, form, and product: for example, a
plausible mechanism together with formulation facts, established practice, or
manufacturer guidance. Manufacturer guidance is corroborating lower-tier support,
never decisive by itself, and the independent-grounded-evidence-over-vendor
hierarchy remains in force.

Material changes to this calibration standard or to a product's form, carrier,
dose disclosure, or applicability trigger re-review of affected soft
preferences; they do not silently rewrite existing scheduling facts.

The `scheduling_assessment` sources and summary must disclose the evidence basis,
limitations, applicability, and whether the preference is mechanistic or
heuristic. Weak evidence can justify only a soft preference; it never justifies a
hard constraint, safety claim, universal medical recommendation, or dose-derived
planner weight. Keep `insufficient` when mechanisms point both ways, formulation
is materially unknown, or no direction can be justified; `insufficient` is not
proven neutrality. Remove or narrow an existing heuristic when it is clearly
wrong, form-inapplicable, mechanistically direction-ambiguous without
convergence, or contradicted by stronger evidence.

A coherent, applicable weak heuristic may be more useful than leaving an axis
without guidance, but it does not override stronger contrary evidence or resolve
genuinely bidirectional evidence or unknown-form mechanisms. This focused
reconsideration does not imply an automatic or broad re-review.

For example, a nattokinase enzyme/gastric rationale is not automatically
directional: acid buffering, proteases, gastric emptying, enteric versus
quick-release formulation, and uncertain absorption can compete. This example
sets the evidence boundary, not a final card decision.

### Mandatory completion handoff

For every new active Substance or card-level grooming run, the task/commit
report must include this finite handoff. It is procedural state, not a new
repository artifact or entity:

- label and exact Product/Substance/form identity captured;
- ontology neighbors, existing terms, mechanisms, dashboards, relations, and
  active-stack matches checked;
- cards completed and the bounded research questions/axes named for each,
  including applicability boundaries;
- Luna's independent evidence packet and search limits;
- Sol's admitted and rejected claims and relation leads, with the reason for
  each boundary;
- exact routing destinations for every admitted result, or an explicit no-change
  decision;
- every omitted/unassessed axis named;
- targeted bounded checks run; and
- real planner output, schedule journal, and explanation inspected.

Tooling does not and cannot prove that research occurred: the schema validates
only serialized outcomes. The Luna -> Sol -> Luna sequence is mandatory
procedural policy for this workflow but is not tooling-enforced. The
orchestrator must enforce this handoff; do not create approval IDs,
owner/reviewer/lifecycle fields, evidence files, or new schemas to simulate it.

### Fact routing and semantic stop rules

- `schedule.*` is only for evidence-adjudicated meal, time, or activity facts
  that deliberately affect slots. Dose-specific evidence does not become an
  unconditional timing warning or rule; the current scheduler is dose-agnostic.
- `scheduling_assessment` separates `unassessed`, `insufficient`,
  `supports_no_rule`, `conflicting`, and `supports_preference`.
  `supports_preference` must correspond to an executable same-axis fact.
- `knowledge.effect` describes reusable functional/pharmacological effects;
  `knowledge.pathway` biochemical pathway context; `knowledge.risk` safety or
  interaction flags; `knowledge.context` curated review membership;
  `knowledge.role` a contextual reviewer role; `knowledge.kind` an intrinsic
  class; and `knowledge.quality` the quality of an authored assertion or data.
  Prefer existing ontology terms over new slugs. Use
  [domain-model.md#trait-ontology](domain-model.md#trait-ontology) for exact
  cardinality and vocabulary.
- Put cross-substance links in `data/relations.yaml`. Conditional support
  recommendations are valid expected planner behavior when evidence-backed;
  target a specific substance or mechanism, not a broad marketing category such
  as `role:nootropic`. Wording must not assert deficiency or mandatory
  supplementation when those conditions are unobserved.
- Dashboards are review/load/candidate surfaces, not automatic recommendations
  or scheduling inputs. Concerns are bounded prose for high-signal facts that
  lack a better executable home.
- Product/manufacturer instructions may establish composition and formulation
  and serve as research leads. They do not outrank independent evidence for a
  general scheduling or recommendation claim.

### Current scheduling-assessment contract

The current formal card contract is authored in
[ontology/model.yaml](../ontology/model.yaml) and emitted in the generated
[card schema](../ontology/generated/card.schema.json). The loader also checks
that a `supports_preference` policy matches a schedule assertion on the same
axis. A current shape example contains one admitted preference and one
insufficient result:

```yaml
schedule:
  intake:
  - food_preferred
scheduling_assessment:
  intake:
    conclusion: supports_preference
    policy: food_preferred
    sources:
    - https://doi.org/10.1002/jps.2600550305
    summary: Human fed and meal-absorption evidence supports a soft food preference for this form.
  timing:
    conclusion: insufficient
    sources:
    - https://ods.od.nih.gov/factsheets/VitaminB12-HealthProfessional/
    summary: The bounded search did not establish a general clock-time preference.
```

The generated schema/loader enforce the closed conclusion set
`supports_preference`, `supports_no_rule`, `insufficient`, and `conflicting`,
non-empty `sources` and `summary`, and the same-axis policy match for
`supports_preference`; `policy` is forbidden for the other conclusions. An
omitted axis is `unassessed`; no
`scheduling_assessment` block means no scheduling question was researched.
Assessment metadata never contributes a score. Only the matching executable
`schedule.*` assertion behind `supports_preference` contributes the ordinary
planner score.

### Card grooming command

Run `uv run python -m planner groom`. It returns one deterministic,
active-reachable whole-card dossier. Luna collects all card evidence; Sol
adjudicates; Luna implements; then run the targeted check/recomputation against
actual output and rerun `groom` for the next card. There is no public state
filter, batch selector, manual limit, or competing queue.
The authoritative ownership and ROI boundary is [Domain Model](domain-model.md#core-objects).

The dossier is the card acceptance unit, not an assertion or relation task.
An optional second card is allowed only for a concrete shared relation, exact
repeated claim, or clearly shared narrow evidence context; predicate/category
equality alone is insufficient. Both cards must be completed holistically, and
each relation has one owner. Assertion-level `research_state` and `sources`
remain internal provenance; `searched_insufficient` is valid completion.

### Research-state glossary

- **`unassessed`** — no assessment was serialized for the axis. It has no
  scheduler score effect and does not establish neutrality.
- **`insufficient`** — the axis was searched, but evidence did not justify a
  conclusion. It has no scheduler score effect and adds no schedule fact.
- **`supports_no_rule`** — evidence was assessed and supports no executable
  meal/time/activity rule. It has no scheduler score effect and adds no schedule
  fact.
- **`conflicting`** — relevant claims conflict and the synthesis preserves that
  conflict. It has no scheduler score effect and adds no schedule fact.
- **`supports_preference`** — adjudicated evidence supports a same-axis
  executable preference. The assessment itself has no score effect; its matching
  `schedule.*` assertion receives the normal policy contribution.
- **`no-scheduling-fact`** — a generated journal observation that a component
  has no authored scheduling assertion. It is not an assessment conclusion and
  is not proof of neutrality; it contributes no schedule score.

### Semantic-completion anti-example

A card containing only `name` and `notes` can pass structural validation, but it
is not semantically complete for active use. Attempt the bounded enrichment
workflow and report the outcome, or explicitly report each applicable axis as
unassessed. Never invent ontology facts, timing rules, or relations merely to
satisfy completion.

### Lifecycle stack-state glossary

Use these terms for Product lifecycle state; the semantic ownership details are
cross-referenced in [docs/domain-model.md](domain-model.md). Do not duplicate
the generated dashboard state catalog here.

- **`daily`** — active ordinary recurring stack.
- **`training`** — active workout-adjacent stack.
- **`inactive`** — on-shelf/owned and tracked, but not scheduled.
- **`tracked-unassigned`** — Product card outside all stacks: depleted,
  reference, candidate, or otherwise not currently scheduled.

### Acceptance checklist for a changed active Product/Substance

- [ ] Label facts are lossless, and names are clean and correctly routed.
- [ ] Product/Substance/form identity reuse was searched and recorded by the
      resulting diff or review note.
- [ ] Applicable axes/questions were researched, or are visibly unassessed.
- [ ] Evidence collection and expert adjudication are distinguishable.
- [ ] Ontology placement was chosen intentionally using existing vocabulary.
- [ ] No unsupported facts, broad relations, deficiency claims, or generic
      marketing categories were added.
- [ ] The schedule journal explains votes, assessment/no-effect placement, and
      any `no-scheduling-fact` state.
- [ ] Real planner output and explanations were inspected; balance/tie placement
      was not described as optimal timing.
- [ ] Validation uses the correct bounded `just` recipe; no full release gate is
      added to a small documentation/card loop.
- [ ] Stack state is correct according to the [lifecycle stack-state
      glossary](#lifecycle-stack-state-glossary).

### Compact illustrative example: Choline

A label-only Choline card can be structurally valid yet semantically incomplete.
The routing example is to research and, only if adjudicated, admit an
acetylcholine-precursor/cholinergic-context fact in the appropriate knowledge
layer; do not accept a generic “supports all nootropics” relation. Do not add
AM/PM, food, or activity rules without comparative evidence or convergent,
applicable lower-tier support documented under Practical evidence calibration.
Preserve `insufficient` assessments when the search does not establish a rule,
and use a mechanism-specific conditional review only when the evidence supports
it.
This example describes the decision boundary, not current accepted Choline
facts; check and adjudicate current evidence before writing any card.

## Decision Loop

Treat the product as a guided decision loop, not as a YAML editor:

```text
user concerns -> concern clusters -> axes to cover -> minimal stack proposal -> schedule/warnings -> next iteration
```

Use this mode when the user asks how to improve a stack, what to add next, how to address health goals, or how another person should start using the system. Start with the person's goals and constraints before touching cards.

## Intake Before Data Edits

Ask one compact intake round before proposing supplements:

- top concerns or goals in plain language, not supplement names;
- already active supplements, prescription medications, and relevant procedures;
- constraints: budget, pill burden, frequency, tolerated forms, risk tolerance, and maximum new changes this round;
- available data: labs, diagnoses, clinician guidance, wearable metrics, or none yet;
- avoidances: bleeding risk, blood pressure concerns, glucose meds, surgery, pregnancy, allergies, or other safety constraints.

If the user gives health history, frame it as reported context and hypotheses. Do not diagnose, treat, or imply causality. For prescription medication, dose changes, serious symptoms, or high-risk interactions, mark the item as "discuss with physician" rather than an action.

## Private User Context

Persist user-reported personal context only under `docs/private/`. This directory is intentionally gitignored. Use it for intake notes, health history, symptoms, labs, medications, goals, constraints, review notes, candidate proposals, and decision rationale tied to a specific person.

Do not put user-specific health information into tracked docs, examples, data cards, dashboards, traits, or relations unless the user explicitly asks for that exact information to become tracked project data.

Tracked YAML should separate reusable catalog knowledge (substances) from user stack state (products, stacks, dashboards, and generated outputs). Keep sensitive context in `docs/private/`.

Recommended filenames:

- `docs/private/intake-YYYY-MM-DD.md` for the current user profile and goals;
- `docs/private/proposal-YYYY-MM-DD.md` for candidate stack proposals;
- `docs/private/stack-review-YYYY-MM.md` for review or optimization-session outputs.

Each private note should preserve reported facts, assumptions, uncertainties, concern clusters, axes considered, candidate changes, approved active changes, safety questions, lab/clinician follow-ups, and the next iteration agenda.

## Concern Clusters And Axes

Translate intake into 2-5 concern clusters. A concern cluster is a product-facing problem area, not a dashboard file by default.

Examples:

- vascular/endothelial support;
- fibrinolysis or clotting review;
- mitochondrial energy and lactate handling;
- lipid/cholesterol support;
- skin barrier/collagen/inflammation support;
- age-range prevention.

For each cluster, capture what the user said, what would make it safer or more measurable, and which claims should stay uncertain.

For stack recommendations, pick axes before products. An axis is a reusable biological/review dimension that substances can cover: `kind:`, `effect:`, `risk:`, `pathway:`, relation types in `data/relations.yaml`, or dashboard projections. For product ingestion, start from the physical label and components first, then add reusable axes only when the label or review task exposes a real fact. Use `context:` only for explicit curated review membership when a cleaner reusable axis would over-include, under-include, or force an artificial trait.

Do not create a new axis just because it sounds product-friendly. Add or refine an axis only when it helps multiple cards, improves review output, or makes planner/audit behavior more accurate.

## Knowledge Growth

Guided product work should surface new substances, forms, mechanisms, cofactors, risks, relations, and candidate products. Treat this as normal knowledge-base growth, not scope creep.

When a new fact or candidate appears:

1. Search first with `uv run python -m planner find "<name form alias>"`.
2. Prefer enriching an existing concrete card when it already represents the substance/form.
3. Create a new substance card when a real substance/form is missing, even if it is not active.
4. Keep knowledge-only substance cards when they contain reusable knowledge.
5. Add reusable facts to tracked cards only when they are about the substance/product itself.
6. Put user-specific rationale, symptoms, hypotheses, and decision history in `docs/private/`.

Good enrichment targets: aliases, concrete forms, label-specific component notes, `knowledge.kind:`, `knowledge.effect:`, `knowledge.risk:`, `knowledge.pathway:`, scheduling facts that affect slot assignment, relations, product URLs, label notes, and component amounts.

Do not attempt one-shot full enrichment of the whole ontology. Enrich opportunistically as product work reveals a concrete need, then run validation.

## Minimal Stack Proposal

Prefer a small first proposal over broad coverage. Default to one clear active change; batch a few low-risk changes only when they belong together and the user accepts batching. Larger batches require explicit user request.

Rank candidate additions by safety, relevance to concern clusters, evidence-to-impact ratio, overlap across multiple axes, cofactor/synergy support, low antagonism, low redundancy, and low pill burden.

Use existing active products first. If a useful substance is not on the shelf, treat it as a candidate and possible knowledge-base enrichment, not an automatic stack edit. Use the [lifecycle stack-state glossary](#lifecycle-stack-state-glossary) for `daily`, `training`, `inactive`, and `tracked-unassigned` placement.

Proposal structure:

```text
Concern -> Axis -> Current stack state -> Candidate change -> Why this is minimal -> Safety/review flags -> What to check next
```

Guardrails:

- Do not add 10-20 substances in one step.
- Do not optimize for maximum dashboard membership at the expense of safety, simplicity, or interpretability.
- Do not treat knowledge-only substance cards as cleanup trash.
- Do not convert product-facing concern clusters into dashboards unless the user wants persistent tracking and membership can be expressed cleanly.
- Do not edit stack data after a product intake/proposal unless the user explicitly approves the concrete changes.
- Always separate candidate to discuss/research from active stack change.

## Testing The Guided Protocol

Test the product protocol at three levels:

1. Private founder-user smoke: use the real first user while shaping the flow. Save reported health context under `docs/private/intake-YYYY-MM-DD.md`, generate a proposal under `docs/private/proposal-YYYY-MM-DD.md`, and confirm `git status --short` does not show those files.
2. Skill-behavior regression: use synthetic personas only for shareable, non-private regression examples or future automated checks.
3. Repo behavior test: after approved stack/card edits, run the normal validation contract.

A passing guided-protocol test keeps user-reported facts labeled and private, separates concern clusters from dashboards, makes axes explicit, limits candidate changes, shows safety/lab follow-ups, and makes no active stack change without explicit approval.

## Onboard A New Stack

Use this when a user cloned or forked the repository for their own supplements. Assume current files in `data/` may describe the original owner's real stack, not neutral sample data. Do not mix a new user's stack into existing data unless explicitly asked.

Default quick start for a new user: keep the existing substance catalog as reusable reference knowledge, clear user-specific stack data, and then add the new user's cards into `data/stacks.yaml`. Run planner/review only after that to avoid optimizing against the original owner's stack.

Start with one short onboarding pass:

- Ask whether the user wants read-only orientation, extension, reference-only use, or replacement of current stack data.
- Ask for the product list: brand, product name, source URL, and label photo/text when available.
- Treat the product name as a concise bottle-facing/commercial title. Do not synthesize it from chemical form, dose/strength, package count, or ontology qualifiers; route those to `substance.form`/`component.label`, `component.amount`, product `notes`, and substance `knowledge`/notes respectively. Preserve genuine commercial names that inherently contain a form term.
- Ask where each product belongs, using the [lifecycle stack-state glossary](#lifecycle-stack-state-glossary), including intentionally unstacked (`tracked-unassigned`) products.
- Ask whether dashboards should be created now or skipped until the first schedule exists.
- Ask whether web research is allowed. Prefer official product pages, labels, or store pages, and save useful sources in product `urls`.
- Ask about user-specific constraints that should become review warnings. Do not make medical decisions.

Onboarding modes:

| Mode | Use when | Data behavior |
|---|---|---|
| Read-only orientation | The user only wants to understand the repo. | Do not edit data. Run read-only commands only. |
| Extend current data | The user wants to add their products to the current catalog. | Add new cards and stack entries without deleting existing data. |
| Clean personal start | The user wants to replace the current shelf profile with their own. | Keep `data/substances/` intact; clear `data/products/` and `data/dashboards/`, reset `data/stacks.yaml` to the empty stack shape, and regenerate `schedule.yaml` from the new cards. |
| Use as reference | The user wants the current substance catalog and maybe examples, but not active replacement. | Move original active product IDs from `daily` and `training` to `inactive`, keep old product cards, then add the new user's products. |
| Replace catalog | The user wants a personal-only or full replacement catalog. | Destructive path only: show exact paths to clear (`data/substances/` plus any personal stack files), require explicit approval, and prefer doing this on a branch. |

Practical quick start:

1. Save private intake notes under `docs/private/intake-YYYY-MM-DD.md` if the user shares goals, symptoms, medications, labs, or constraints.
2. For clean personal starts, clear user-specific stack data before adding new cards:
   - `data/products/`
   - reset `data/stacks.yaml` to the empty stack shape
   - `data/dashboards/`
   - generated `schedule.yaml` (for the next run)

   For reference-style starts, keep product cards and only move `daily` and `training` IDs to `inactive`.
3. Search before creating each ingredient: `uv run python -m planner find "<name form alias>"`. Reuse existing substance cards whenever they match the product label.
4. Keep `data/substances/` unless the user explicitly asks for catalog replacement. Create missing substance cards only for real missing label components or forms.
5. Create one product card per physical product from [schema/templates/product.yaml](../schema/templates/product.yaml), using a concise bottle-facing/commercial `name`; do not append technical form, dose/strength, package count, or ontology qualifiers merely for completeness. Route those details to `substance.form`/`component.label`, `component.amount`, product `notes`, and substance `knowledge`/notes. Preserve genuine commercial names that inherently contain a form term. Link each component to a concrete `sub_*` ID or draft it with an exact substance name+form, alias, or filename stem. `uv run python -m planner check` rewrites unique matches to `sub_*` and fails on unknown or ambiguous names. Save source URLs or label notes when available. For each newly created substance used by an active product, follow the bounded evidence-enrichment attempt in [Authoritative Card Lifecycle](agent-product-flow.md#authoritative-card-lifecycle): capture label identity/form first, research applicable scheduling axes and important review/interaction context, and keep any `insufficient` or unassessed state visible for grooming. Do not treat balance placement as an optimal slot.
6. Add only the new user's products to `daily`, `training`, `inactive`, or leave products intentionally `tracked-unassigned` by omitting them from all stacks in `data/stacks.yaml`.
7. Run `uv run python -m planner check`, then `uv run python -m planner` after at least one non-inactive product exists.
8. Run `uv run python -m planner review` before stack recommendations. Use `uv run python -m planner check` to validate source-data references.

For a confirmed clean start, clear only user-specific stack data and preserve the reusable catalog:
Keep `planner/`, `schema/`, `tests/`, `docs/`, `SKILL.md`, `README.md`, `data/pillboxes.yaml`, `data/substances/`, and `ontology/`.
Clear `data/products/` and `data/dashboards/` unless a mode explicitly keeps reference data. Reset `data/stacks.yaml` to the empty stack shape.

For an empty stack:

```yaml
daily: []
training: []
inactive: []
```

First pass target: create one product card per physical product, create substance cards only for known label components that are missing from the catalog, link components by exact substance names or IDs, place products into a stack when active/owned or leave intentionally unstacked when not on shelf, leave unknown planning facts empty instead of guessing, and run `uv run python -m planner check` to normalize draft refs.

Run `uv run python -m planner` after at least one non-inactive product exists. Enrich later with amounts, aliases, forms, URLs, label notes, traits, relations, dashboards, and review warnings.
