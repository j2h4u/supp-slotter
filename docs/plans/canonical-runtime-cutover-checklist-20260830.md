# Canonical Runtime Cutover Checklist — 2026-08-30

## Purpose

This is the living execution record for the whole-product Sol High expert-panel
audit performed after removal of embedded SurrealDB. Check an item only after
its implementation and paired V-right acceptance evidence both pass. A code
change alone is not completion.

The target is the accepted contract in
[`docs/domain-model.md`](../domain-model.md) and the governing
[`canonical-instance ADR`](../decisions/canonical-instance-inference-boundary-20260822.md).
The canonical runtime remains **NON-CONFORMING** until the Critical and High
cutover items below are complete. The spike is not finished until every item in
this document, including Medium cleanup and final acceptance, is complete.

## Status legend

- `[ ]` not completed
- `[x]` implemented and accepted by the named evidence
- `BLOCKED` means the concrete blocker is recorded next to the item

Every checked item must gain an indented `Evidence:` entry containing the
implementing commit SHA, the exact targeted acceptance command/result, and the
path to its durable test, fixture, or decision artifact. A passing broad suite
without item-specific evidence is insufficient. Evidence must be produced from
the checked commit or a descendant that contains it.

The closed families and all nine admitted values are enumerated normatively in
[`docs/domain-model.md`](../domain-model.md#closed-scheduling-fact-vocabulary).
This checklist never substitutes a summary for that source.

## Critical — canonical product behavior

- [ ] **Make canonical facts and logical topology the only scheduler inputs.**
  Activate the five closed fact families, explicit composition roles,
  applicability, provenance, and the independent slot anchors. Remove direct
  runtime scheduling from authored `schedule.*` answers.
  - Acceptance: a fixture containing only canonical facts produces pressures
    and a layout without any legacy schedule alias.
  - Acceptance: manifest/runtime inputs contain the authoritative canonical
    fact catalog and logical topology, not shadow-only schemas.

- [ ] **Implement the complete finite facts-to-pressures law table.**
  Every one of the nine admitted fact values derives the specified unary
  pressure through a generic proof-producing executor.
  - Acceptance: finite positive, negative, applicability, and boundary truth
    tables cover all admitted values.
  - Acceptance: proof nodes name typed facts, composition/applicability path,
    provenance, and law identity.

- [ ] **Normalize pressure identities and fail closed on contradictions.**
  Repeated components, witnesses, sources, or inference paths must enrich one
  `(item_id, dimension, value)` proof node and never add votes. Different values
  on one item/dimension yield layout-free `Indeterminate`.
  - Acceptance: duplicate/multiplicity tests remain one pressure and one vote.
  - Acceptance: same-dimension opposition returns diagnostics and no layout;
    cross-dimension pressures remain optimizer inputs.

- [ ] **Replace the weighted/float objective with the exact lexicographic
  optimizer.** First maximize satisfied unique pressures; then minimize exact
  integer squared loads per independent domain; then use stable item IDs and
  `(slot.order, slot_id)` for the final assignment key.
  - Acceptance: no float score, epsilon, authored weight, bonus, penalty, or
    evidence count participates in selection.
  - Acceptance: stack/YAML ordering permutations produce the same assignment.
  - Acceptance: bounded production results match an independent exhaustive
    oracle in status, objective tuple, and assignment.

- [ ] **Enforce the closed `Optimal | Indeterminate` publication boundary.**
  Publish `schedule.yaml` only after global optimality is proved. Conflicts,
  invalid inputs, interruption, timeout, or resource exhaustion publish no
  incumbent or best-so-far layout.
  - Acceptance: forced failure cases leave no layout and expose typed
    diagnostics.
  - Acceptance: a successful result records the exact objective tuple and
    proof trace.

## High — remove the superseded scheduler and split authority

- [ ] **Remove executable `prefer_with`, pair constraints, pair bonuses, and
  pair penalties.** Preserve admissible raw evidence or review annotations, but
  do not port stored pair answers into the canonical optimizer.

- [ ] **Remove component vote aggregation and legacy policy scoring.** Delete
  old runtime-policy weights, score magnitudes, balance weight, epsilon policy,
  and tests that protect those semantics.

- [ ] **Migrate logical topology from compound `near`/`food` and physical
  compartment semantics.** Use optional independent `meal_context`,
  `circadian_anchor`, and `exercise_anchor`; slots remain unbounded logical
  intake groups.

- [ ] **Give composition roles stable portable identities.** Product component
  reorder, notes, or display edits must not change the identity used by facts,
  applicability, provenance, RDF, or a future ontology backend.

- [ ] **Adjudicate the legacy evidence ledger before deleting source
  knowledge.** Resolve all `sol_adjudication` atoms into typed facts, raw
  quotations, source metadata, or explicit exclusions. Never bulk-translate a
  legacy placement into a canonical fact.
  - Current baseline: 1,786 outstanding Sol adjudications in
    `docs/migrations/legacy-atom-ledger.yaml`.
  - Acceptance: regenerate and reconcile the ledger against the current source
    head immediately before any legacy deletion and again before final cutover.
  - Acceptance: `outstanding_sol_adjudication_count` is zero and every selected
    atom has exactly one allowed final disposition.

- [ ] **Add a canonical-runtime acceptance gate.** It must cover laws,
  normalization, contradiction, exact objective stages, stable tie-break,
  exhaustive-oracle equivalence, and no-publication failures. Existing green
  legacy tests are not cutover evidence.

## High/Medium — architectural cleanup

- [ ] **Finish the SurrealDB-era cleanup.** Remove unused `ReadModelContext`
  fields, discarded dashboard/policy loading, test-only serializers, and the
  remaining stringly `dict[str, object]` assertion round-trip. Keep only narrow
  typed query functions or a genuinely useful typed facade.

- [ ] **Correct all SurrealDB documentation.** No active documentation may
  claim that the removed embedded database or SurrealQL runtime still exists.

- [ ] **Separate online runtime artifacts from offline formal verification.**
  Ordinary plan/find/review commands should load only the compact verified
  runtime contract and required card schemas. RDF/SHACL/context/projection
  validation remains an explicit ontology/release gate; RDFLib and pySHACL
  should not be production dependencies unless runtime use is demonstrated.

- [ ] **Make validation read-only.** `planner check`, plan, show, and review
  must not rename, rewrite, move, or delete canonical cards. Put normalization
  and repairs behind an explicit command and make partial failure safe.

## Medium — product and data integrity

- [ ] **Make unassigned ownership explicit.** Every tracked product belongs to
  exactly one active domain, inactive, or an explicit `tracked_unassigned`
  state with a reason. Accidental stack omission must not silently remove it
  from scheduling, warnings, and grooming.

- [ ] **Enforce pillbox/stack topology uniqueness.** A stack cannot silently be
  expanded through multiple pillboxes when the authored contract is 1:1.

- [ ] **Make non-daily presentation truthful without adding recurrence.** Use a
  neutral current-plan heading and keep episodic placements outside the claim
  that they are today's intake.

- [ ] **Align grooming with canonical migration work.** Missing required axes,
  unresolved applicability, and outstanding Sol adjudication must remain
  discoverable. Luna may collect evidence; only Sol adjudicates ontology facts.

- [ ] **Prevent product/form-specific evidence from masquerading as universal
  substance evidence.** Bind formulation-specific material to stable
  composition roles and keep only genuinely universal evidence on substances.

- [ ] **Require complete catalogs at query boundaries.** Membership and fact
  indexes must fail closed on missing products, substances, or references
  instead of returning plausible empty results.

## Medium — verification workflow

- [ ] **Add one compact read-model cutover acceptance.** Assert the normalized
  active/inactive identities, fact index, relation classes, warning identities,
  matches, ordering, and deduplication over a representative fixture.

- [ ] **Make release inventory exhaustive.** Exact-node modules must not allow
  newly added tests to be silently omitted.

- [ ] **Make the default development gate fast and product-relevant.** Include
  one bounded real-shelf runtime smoke, avoid repeated validation in combined
  recipes, and keep corpus/formal/full gates explicit for release candidates.

- [ ] **Clear the current static release blocker.** Resolve the existing
  migration-ledger type errors so the final release gate can actually complete.

## Final cutover acceptance

- [ ] Real daily, non-daily, and training scenarios use canonical facts and
  logical topology only. Durable acceptance fixtures must cover all three
  scheduling domains plus the repository's current active shelf; their expected
  result is expressed as status, pressure/objective invariants, membership, and
  anchor semantics rather than a byte-for-byte legacy golden.
- [ ] Meaningful food, wake/sleep, and before/after behavior is preserved or
  improved without requiring byte-for-byte legacy placement.
- [ ] Every published layout is proved globally `Optimal`; every conflict or
  unproved search is layout-free `Indeterminate`.
- [ ] No supplement, pair, placement, weight, or domain law is recoverable only
  from Python.
- [ ] A future TypeDB implementation can reproduce facts, applicability,
  pressures, status, objective tuple, and selected layout without extracting
  semantics from Python.
- [ ] The legacy runtime and obsolete regression tests are deleted, not retained
  as a compatibility museum.
- [ ] Targeted acceptance, runtime scenarios, static checks, and one final
  release gate are green on the same committed head. This item cannot be checked
  until every Critical, High, and Medium item above carries its own `Evidence:`
  record.
- [ ] A final independent Sol panel confirms the canonical runtime contract and
  returns `SHIP` without Critical, High, or Medium reservations. Save the panel
  prompt, reviewed commit SHA, individual findings, and convergence verdict in
  `docs/decisions/`; findings against another head do not close this item.
- [ ] **Run one final checklist auditor with no parent context.** The auditor
  must independently inspect the final committed head, walk every checkbox and
  its `Evidence:` record, reproduce or validate the named acceptance evidence,
  detect false or premature checkmarks, and confirm that no required work was
  silently dropped. Save its prompt, reviewed commit SHA, per-item verdicts,
  discrepancies, and final `COMPLETE` or `INCOMPLETE` decision in
  `docs/decisions/`. This is the last action in the plan; only `COMPLETE` closes
  the spike.

## Execution order

1. Canonical inputs and stable identities.
2. Laws, applicability, normalized pressures, and conflict result.
3. Exact optimizer and publication boundary.
4. Real-scenario cutover and deletion of the legacy scheduler.
5. Surreal residue, runtime artifact split, and read-only validation.
6. Data integrity, grooming, presentation, and test-harness cleanup.
7. Final release evidence and independent panel review.
8. Fresh-context checklist audit and final completion decision.

Within each step, schema/data identity and its negative validation fixture come
before runtime consumption; runtime implementation comes before real-scenario
cutover; targeted V-right acceptance comes before deletion of the superseded
path. No later step may compensate for missing evidence in an earlier step.

## Required item-specific evidence

The following minimum evidence is mandatory in addition to each item's own
acceptance bullets:

| Work item | Minimum targeted evidence |
| --- | --- |
| Remove pair answers and weighted legacy scoring | Architecture search proves no executable legacy field reaches feasibility/objective; real scenario and negative fixture prove review-only evidence cannot move a product. |
| Migrate logical topology | Positive/negative schema fixtures cover every independent optional anchor, missing anchors, duplicate axes, and forbidden legacy/physical fields; runtime scenario proves each anchor independently. |
| Stable composition identities | Reorder and notes-edit metamorphic tests preserve role/fact/provenance identity; dangling and mismatched references fail closed. |
| Canonical-runtime gate | Gate inventory names the finite law truth table, normalization/conflict cases, exact objective stages, oracle comparison, and no-publication failures; inventory completeness test prevents omission. |
| Surreal-era residue cleanup | Repository search and architecture test show no unused context field, test-only serializer, stringly assertion row, discarded loader, or stale Surreal documentation remains. |
| Runtime/offline artifact split | Timed plan/find/review smokes load only declared runtime artifacts; ontology/release gate still detects stale RDF/SHACL/context/projection artifacts; dependency tree reflects the split. |
| Read-only validation | Snapshot/hash test proves check/plan/show/review do not change canonical inputs; explicit normalize failure test proves all-or-nothing behavior. |
| Explicit unassigned ownership | Partition validation proves every tracked product is active, inactive, or explicitly unassigned exactly once; deletion-from-stack fixture fails without an explicit state. |
| Pillbox/stack uniqueness | Duplicate-stack positive-schema input is rejected and the valid one-to-one fixture retains separate scheduling domains. |
| Non-daily presentation | CLI and generated summary make no claim that episodic items are taken today, while retaining their slot placement and interaction participation. |
| Grooming alignment | Queue fixture surfaces missing canonical coverage and unresolved Sol work; completed cards are not repeatedly selected; Luna output cannot adjudicate facts. |
| Applicability scope | Product/form-specific fixture affects only its stable composition role; a genuinely substance-wide fixture applies to all roles. |
| Complete query catalogs | Missing product, substance, component, or assertion reference fails closed; complete catalogs preserve the expected identity sets. |
| Read-model cutover acceptance | One representative fixture asserts active/inactive IDs, facts, relation classes, warnings, matches, ordering, and deduplication together. |
| Exhaustive release inventory | Collection comparison proves every test node is either selected or explicitly excluded with a reason. |
| Fast development gate | Measured gate includes one real-shelf runtime path, performs validation once, and leaves ontology/corpus/full checks explicit. |
| Static release blocker | The canonical static recipe completes with no migration-ledger type errors on the final head. |

The canonical laws row must link to the exact truth-table test cases for every
value enumerated in the normative domain model; referring only to a broad suite
name does not satisfy it.
