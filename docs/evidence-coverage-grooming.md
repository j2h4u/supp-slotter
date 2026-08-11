# Evidence Coverage Grooming

> **Status: Small read-only subset implemented; broader proposal deferred.**
> Substance cards now carry optional per-axis scheduling assessment states with
> sources and summaries. The generated schedule journal exposes deterministic
> `unassessed` versus researched conclusions for components without scheduling
> facts, while assessment metadata is isolated from scheduler scoring and
> placement. EvidenceQuestion catalogs, coverage scoring, grooming queues, and
> workflow/task machinery remain deferred and are not implemented here.

## Why the broader proposal is deferred

This is separate from the MVP and would take multiple days of design, pilot
annotation, and reader validation. The current slotter remains dose-agnostic:
its scheduling rules describe placement preferences and constraints, not dose,
treatment, or clinical recommendations. Evidence grading must not enter current
scheduling. A complete evidence record, or its absence, must not silently add,
remove, strengthen, or weaken a scheduling rule in the MVP.

## Problem to solve

Periodically identify active Substance and Product cards that are
under-researched for scheduling-relevant questions about biochemical and medical
evidence. The target is evidence coverage, not formal field presence and not
whether a manufacturer instruction happens to be present.

The following distinctions are essential:

- **Unassessed** means the question has not been investigated for this card.
- **Searched but insufficient** means the question was investigated and the
  available evidence did not justify a useful conclusion. It is still covered
  as a reviewed question, and must not be reported as unassessed.
- Card coverage, claim certainty, and scheduling-rule strength are different
  dimensions. None is a proxy for either of the others.
- A high-quality card may conclude `supports_no_rule`: the evidence can be good
  while supporting no meal, timing, or exercise rule.
- Vendor/manufacturer evidence is lower priority than independent medical
  evidence. A label can describe a formulation accurately without establishing
  a general timing effect.

This proposal borrows concepts from evidence and gap-mapping practice, but is
not a GRADE implementation. See the [Cochrane GRADE chapter](https://training.cochrane.org/handbook/current/chapter-14),
[CDC GRADE criteria](https://www.cdc.gov/acip-grade-handbook/hcp/chapter-7-grade-criteria-determining-certainty-of-evidence/index.html),
and [Campbell evidence and gap mapping context](https://www.campbellcollaboration.org/evidence/).

## Evidence hierarchy

Use this as a review ordering and explanation aid, not as an automatic numeric
weighting system:

1. Systematic reviews and clinical or professional guidelines.
2. Good controlled human studies and pharmacokinetic studies.
3. Observational human evidence.
4. Mechanistic, animal, or in-vitro evidence.
5. Independent expert synthesis.
6. Official product label or manufacturer instructions.
7. Marketing material.

Official labels are useful mainly for formulation, composition, serving, and
carrier facts. They are weak evidence for timing tie-breakers unless independent
evidence supports the same claim. Marketing is useful, if at all, only as a
lead to investigate.

## Minimal future ontology proposal

This is a deliberately small starting point, not a final design. Add an
`EvidenceQuestion` catalog with these question IDs:

- `meal_absorption`
- `meal_tolerability`
- `day_phase`
- `exercise_relation`
- `coadministration`
- `formulation_dependence`

Questions should be applicable to a product or substance only when the card's
carrier, matrix, chemical form, or formulation makes the question meaningful.
Record product applicability, including carrier and matrix, rather than
assuming that substance-level evidence transfers to every product.

Represent an assessment at claim level with the smallest useful fields:

- `coverage`: `unassessed`, `assessed`, or `not_applicable`;
- `conclusion`: `supports_preference`, `supports_no_rule`, `conflicting`, or
  `insufficient`;
- `certainty`: `high`, `moderate`, `low`, or `very_low`;
- applicability and the applicable Substance/Product, form, carrier, or matrix;
- evidence references, evidence type, and an independence indicator.

Each assessment has a stable assessment ID and links exactly one card to exactly
one `EvidenceQuestion`. It may aggregate multiple evidence claims and sources.
Conclusion and certainty aggregation is an explicit human or agent synthesis;
it is not automatic averaging of claims, source counts, or certainty labels.

Applicability must be a small structured value, not an ambiguous boolean:

```yaml
applicability:
  level: substance | formulation | product
  target: stable-id       # optional when the linked card is the target
  reason: text explaining the scope
```

At source level, `independence` is one of `independent`, `manufacturer`, or
`unknown`. Evidence `type` remains separate (for example, systematic review,
controlled human study, label, or marketing); independence must not be inferred
from the type string.

An assessment can record that literature was searched with no usable finding
(for example, a `searched_no_evidence` note) and conclude `insufficient`. That
state is different from `unassessed`. Avoid adding owner, reviewer, lifecycle,
`review_pending`, or governance fields in this first proposal; those would be a
separate workflow decision.

### Normative assessment states

| State | Meaning | Coverage numerator | Coverage denominator |
|---|---|---:|---:|
| `unassessed` | No assessment exists for an applicable question. | No | Yes |
| `assessed + supports_preference` | Evidence supports a preference, with stated certainty. | Yes | Yes |
| `assessed + supports_no_rule` | Evidence is assessed but supports no scheduling rule. | Yes | Yes |
| `assessed + insufficient` / `searched_no_evidence` | The question was searched, but evidence is insufficient for a conclusion. | Yes | Yes |
| `assessed + conflicting` | Relevant claims conflict and the synthesis preserves that conflict. | Yes | Yes |
| `not_applicable` | The question does not apply at the stated substance, formulation, or product scope. | No | No |

`searched_no_evidence` is a searched-result note or rendering label for an
`assessed + insufficient` state, not a second form of `unassessed`. Coverage is
therefore the proportion of applicable questions with an assessment, including
assessed-but-insufficient and assessed-but-conflicting questions.

## Derived coverage and grooming

For a card with at least one applicable question:

```text
coverage_score = assessed applicable questions / applicable questions
```

An assessed question whose conclusion is `insufficient` counts as covered. Do
not average certainty, and do not call `coverage_score` a medical quality
score. If no question is applicable, report that explicitly rather than
manufacturing a zero. No card-level score may affect the planner score.

Evidence metadata initially powers only grooming, explanations, and audit.
For this proposal, **active cards** are cards reachable from current
stacks/products through the existing runtime data. This definition adds no new
lifecycle or status vocabulary. The derived grooming view should include active
cards with:

- unassessed scheduling-relevant questions;
- scheduling assertions without a corresponding assessment;
- hard constraints supported only by low-certainty evidence;
- conflicting evidence; or
- a product formulation that prevents applicability from being established.

The generated per-product scheduling explanation journal (`schedule.yaml`) is
also a read-only grooming input. Components with no scheduling assertion,
repeated mixed or dissenting scheduling votes, or placements that are weakly
explained are candidates for card research or enrichment. A missing scheduling
fact is not proof that a card is incomplete: the substance may genuinely be
scheduling-neutral. Grooming must adjudicate neutral versus unknown using
medically grounded or biochemical evidence, not manufacturer directions;
product instructions may be considered, but rank below that grounded evidence.
This signal is review-only: it must not block or change scheduling, create
lifecycle/owner/reviewer machinery, or invent scheduling facts.

Hard-constraint grooming requires an explicit evidence-assessment link. A
missing link is a grooming gap, not automatic invalidation and not scheduler
behavior. The current planner remains unchanged.

This is a derived queue, not a new action entity and not an automatic task,
review assignment, or scheduler input. Priority should explain which condition
put a card in the view; it should not rank cards by a medical score.

## Illustrative cases

- **B5:** a card can have high coverage and still conclude
  `supports_no_rule` for the scheduling questions. High coverage is not a
  reason to invent a timing preference.
- **Astaxanthin:** substance-level evidence may be moderate and formulation-
  dependent, while applicability for a particular Product remains unassessed.
  The substance result must not be copied onto every product.
- **Krill Oil:** oil composition and carrier are formulation-specific, and
  vendor evidence is weak. A label can establish what the product contains;
  independent evidence is needed for a general scheduling assertion.

Recent layout investigation is context only, not a current ontology change:
generic B-vitamin meal rules are often unsupported; omega/astaxanthin evidence
is formulation-dependent; mineral interactions are pair- and dose-specific;
and product labels are lower-evidence sources for timing claims.

## Future invariants and tests

Any implementation must preserve these invariants:

- Evidence completeness never changes placement.
- `searched_no_evidence` / `insufficient` is observably different from
  `unassessed`.
- Not all cards become incomplete merely because a question catalog exists;
  applicability must be explicit.
- Unknown certainty cannot synthesize a scheduling rule.
- Vendor evidence cannot override stronger independent evidence.
- The formal source remains portable to TypeDB; implementation details must not
  make the source contract depend on one storage engine.

Tests should cover these cases, plus the denominator-zero (`not_applicable`)
case, substance-to-product applicability boundaries, conflicting claims,
certainty rendering, and the proof that planner output is unchanged when
coverage metadata is added or removed.

## Scope guardrails and stop conditions

The first MVP must not include a dose engine, treatment recommendation,
evidence warehouse, automated clinical-grade GRADE implementation, freshness
workflow, owner/reviewer workflow, numerical medical quality score, or automatic
rule strength derived from completeness. It must also not infer a hard rule from
an evidence count or from a vendor label.

Stop the work if the pilot requires any of those systems, if applicability
cannot be explained to a reader, or if evidence fields begin changing planner
placement. Re-scope to a read-only report when a proposed change cannot prove
that the current scheduler is behaviorally identical.

## Suggested finite implementation phases

1. **Question catalog and schema.** Define the six questions, claim fields,
   applicability semantics, source references, and serialization with no
   planner read path.
2. **Five-to-ten-card pilot.** Annotate a deliberately mixed sample, including
   B5, astaxanthin, Krill Oil, a mineral interaction, and cards with no useful
   evidence. Record why each question is applicable, unassessed, or
   insufficient.
3. **Derived report.** Produce a deterministic grooming view and explanations;
   prove it cannot alter schedule output and has no action entities.
4. **Reader/UAT.** Give the report to a fresh reader and verify that they can
   distinguish coverage, certainty, applicability, and rule strength without
   conversation context.
5. **Only then consider constraint admission.** Any link from certainty to
   constraint admission requires a new explicit decision, stronger tests, and
   evidence that the planner remains conservative. Any future
   constraint-admission policy is outside this proposal and requires separate
   user approval.

Acceptance for the pilot is: every annotated card has an applicability reason;
unassessed and searched-but-insufficient states render differently; all
references are auditable; no coverage or certainty field changes a generated
schedule; and a reader can explain why a high-coverage `supports_no_rule` card
is not incomplete. If any acceptance condition fails, stop at the read-only
report.

## Open decisions for a future user

- Are vendor labels display-only, or may they be a weak product-level
  tie-breaker when independent evidence is absent? This is an open future
  decision only; it has zero MVP behavior.
- For an unknown formulation, should the default be no rule or a conservative
  soft preference?
- Should hard constraints later require a minimum certainty level?
- Which five to ten cards form the pilot, and who validates their applicability
  and references?
