# Decision: Minimal provenance and research state for reviewer facts and relations

**Date:** 2026-08-21  
**Status:** Design decision; not implemented  
**Scope:** KnowledgeAssertion facts on Substance cards and RelationAssertionRecord records in data/relations.yaml

## Decision

Add one closed categorical field, research_state, and one repeated scalar field,
sources, to reviewer knowledge assertions and relation assertions.

| State | Meaning | Source requirement |
| --- | --- | --- |
| unassessed | No bounded research is serialized for this exact assertion. It does not claim nobody searched outside the repository. | None |
| anecdotal | Informal, vendor, label-adjacent, or other anecdotal support without stronger independent support. | Reference when known |
| searched_insufficient | A bounded search occurred, but available evidence did not establish the assertion. | At least one searched reference |
| mechanistic_only | Mechanistic, in-vitro, animal, or plausibility support exists, without adequate direct human/clinical evidence for the conclusion. | At least one reference |
| supported | Stronger independent medical or biochemical evidence supports the exact assertion and applicability. This is not a safety approval or universal clinical recommendation. | At least one reference |

This is a categorical research/evidence state, not a numeric confidence score.
It is independent of assertion_kind, semantic_family, relation_type, and
severity: those fields describe meaning, not evidence strength. Use the best
current basis for the exact assertion. If a search finds no adequate support,
use searched_insufficient rather than anecdotal. Do not infer state from a URL
embedded in reason, vendor identity, or assertion_kind.

## Existing primitives and scope

Reuse SchedulingAssessmentRecord.sources as the repeated reference convention,
but do not reuse scheduling_assessment.conclusion. That contract is tied to one
Substance and one scheduling axis. semantic_enrichment_attempted_on is a
card-level queue marker, not fact-level state. assertion_kind and
semantic_family are semantic/runtime classifiers. reason and notes are
explanatory text, not queryable provenance.

Metadata applies to:

- KnowledgeAssertion records for reviewer knowledge.* categories: kind, effect,
  risk, context, pathway, role, quality, and future reviewer categories.
- RelationAssertionRecord records for both current assertion kinds:
  ontology_assertion and clinical_review_signal, and all relation types:
  supports, review_with, and balance.

Metadata does not apply to individual schedule.* strings: scheduling evidence
remains owned by scheduling_assessment. Concerns, product labels, and
scheduling constraints are not reusable evidence assertions and receive no new
state in this design.

## Minimal ontology shape

Add a shared ResearchState enum to ontology/model.yaml and use it only on the
two assertion classes:

~~~yaml
enums:
  ResearchState:
    permissible_values:
      unassessed:
      anecdotal:
      searched_insufficient:
      mechanistic_only:
      supported:

classes:
  KnowledgeAssertion:
    slots: [knowledge_category, knowledge_value, research_state, sources]

# ontology/relation-model.yaml
  RelationAssertionRecord:
    slots:
      - id
      - relation_type
      - assertion_kind
      - semantic_family
      - severity
      - reason
      - action
      - research_state
      - sources
      - source_selector
      - target_selector

slots:
  research_state: {range: ResearchState, multivalued: false}
  sources: {multivalued: true}
~~~

Keep the new fields optional at the raw compatibility boundary. Normalization
exposes omission as research_state: unassessed and sources: []. Canonical new
non-unassessed records require a non-empty source reference. References are
URLs, DOI/PubMed/guideline identifiers, or similarly stable locators; this is
not a source warehouse.

Existing knowledge string shorthand remains valid:

~~~yaml
# Legacy input: normalized to unassessed and empty sources
knowledge:
  kind: [mineral]

# Canonical enriched fact
knowledge:
  pathway:
    - value: methylation_cycle
      research_state: mechanistic_only
      sources: [https://pubmed.ncbi.nlm.nih.gov/example]
~~~

A relation carries the same fields without changing selectors or runtime
meaning:

~~~yaml
- id: rel_supports_004
  relation_type: supports
  assertion_kind: ontology_assertion
  semantic_family: biochemical_mechanism_assertion
  research_state: supported
  sources: [https://pubmed.ncbi.nlm.nih.gov/30541089/]
  reason: Magnesium participates in vitamin D hydroxylation and calcium homeostasis.
  source_selector: {entity: {name: Magnesium}}
  target_selector: {entity: {entity_id: sub_2476bf9d4b}}
~~~

## Query and grooming behavior

Generated projections and the read model expose research_state and sources as
ordinary assertion fields. Agents can query:

- reviewer facts with state unassessed;
- review_with or balance relations with state anecdotal or mechanistic_only;
- supports facts with state supported and their source references; and
- searched_insufficient assertions separately from never-researched facts.

A derived grooming view groups findings as follows:

1. unassessed: research gap for this exact fact or relation.
2. anecdotal/mechanistic_only: evidence-upgrade leads; never promote them
   automatically.
3. searched_insufficient: searched but unresolved; do not relabel as
   unassessed or repeatedly treat as a fresh search gap.
4. supported: no coverage gap solely due to state; retain sources for display.

State is reviewer/grooming metadata only. It never suppresses or creates a
relation warning, changes severity, affects slot assignment, creates a
scheduling constraint, or changes a planner score. There is no automatic state
promotion.

## Migration default

Do not mass-edit existing facts or infer provenance from prose. Legacy
knowledge strings and relation records lacking research_state normalize to
unassessed. This conservatively records repository state, not proof that prior
research did not happen. URLs embedded in relation reason remain readable
context until explicitly extracted into sources and assigned a state.

For new or materially revised facts, author research_state explicitly. A
bounded search with no usable conclusion is searched_insufficient. Existing
scheduling cards retain their current assessment contract and axis glossary.

## Options considered

| Option | Decision | Reason |
| --- | --- | --- |
| Reuse scheduling_assessment for every assertion | Reject | Substance/axis-specific and policy-coupled; cannot represent relation endpoints or reviewer facts. |
| Encode state in reason, notes, or semantic_family | Reject | Not reliably queryable and conflates meaning with evidence. |
| Add a generic numeric confidence score | Reject | Hides why evidence is weak, is not comparable across assertions, and is out of scope. |
| Add an EvidenceClaim/source graph with governance fields | Reject for now | A provenance warehouse and workflow would overengineer this query need. |
| Categorical research_state plus repeated sources | Recommend | Small, queryable, reuses the scheduling source convention, and leaves runtime semantics unchanged. |

## Acceptance criteria

1. Generated card and relation schemas expose the closed five-value ResearchState
   vocabulary and repeated sources only on the two assertion classes.
2. Legacy knowledge and relation inputs normalize to unassessed/empty sources;
   no bulk rewrite is required.
3. Structured facts and relations validate, project to RDF/JSON/TypeDB-compatible
   scalar attributes, and preserve source lists.
4. Non-unassessed assertions without a source are rejected; explicit
   unassessed without sources is valid.
5. Queries and grooming distinguish all five states, especially unassessed,
   searched_insufficient, and mechanistic_only.
6. Scheduling assessments, planner scores, relation warnings, and constraints
   are behaviorally unchanged.
7. Reviewer output may display state and source references without changing
   warning semantics.
8. A TypeDB/RDF smoke filters assertion nodes by state without a source entity,
   custom scalar type, or evidence graph join.

## TypeDB portability and non-goals

The shape maps to one enum-like string attribute and zero or more string source
attributes on existing assertion nodes; endpoint/reference edges remain as-is.
No nested evidence object, ordered-list semantics, numeric datatype, or custom
relation role is required.

Do not add owner, reviewer, approval, lifecycle, expiry, freshness, safety,
automatic grading, source ranking, numeric aggregation, or scheduling state.
Do not infer supported from severity, relation type, vendor identity, or a URL.
The only remaining implementation choice is whether source syntax is validated
beyond non-empty strings; the smallest portable choice is non-empty strings plus
human review.

