# Canonical Instance and Inference Boundary — 2026-08-22

## Status

**Accepted target; NON-CONFORMING implementation.** This ADR fixes the V-left
decision. Current ontology, data, runtime, generated artifacts, and tests still
encode parts of the superseded model. This decision does not claim an
implemented migration or a conforming release.

## Context

The earlier ontology-first cutover removed some policy from Python, but authored
schedule traits, pair preferences, constraints, scores, actions, and prose still
stored answers in instance data. The previous slot representation also mixed
biological anchors, display chronology, and a physical-container metaphor.
Counting evidence paths or applying weighted/approximate optimization would
make results depend on representation accidents rather than accepted facts.

The product needs a boundary that is closed enough to audit, portable without
hidden Python meaning, and strong enough to decide when no schedule may be
published.

## Decision

The full normative contract is [docs/domain-model.md](../domain-model.md). This
ADR establishes these governing choices:

1. **Closed facts.** Scheduler-consumable evidence is limited to five explicit
   families: `FoodEffect` (only bioavailability increases/decreases or
   tolerability improves/worsens with food), `AcuteAlertnessEffect` (proven
   acute increase), `AcuteSleepEffect` (onset latency decreases or continuity
   improves), `PreExercisePerformanceEffect`, and
   `PostExerciseRecoveryEffect`. Every assertion has typed roles,
   applicability, and provenance. There is no generic EAV predicate/value
   extension, scheduling DSL, magnitude, weight, dose, frequency, or disease
   model.
2. **Separate scenario and topology.** `stacks.yaml` selects scenario items and
   scheduling domains. `pillboxes.yaml` supplies logical slot topology. A slot
   is an unbounded logical intake group, not a physical compartment. Its three
   independent optional anchors are `meal_context` (`with_food`/
   `without_food`), `circadian_anchor` (`wake`/`sleep`), and `exercise_anchor`
   (`before`/`after`). Labels, IDs, and order carry no biology. There is no
   capacity, tablet, capsule, mass, or volume model.
3. **Normalized unary pressures.** Universal identity-free laws map accepted
   facts to a set of `(item_id, dimension, value)` pressures. Witness, source,
   quotation, component, assertion, and inference-path multiplicity contributes
   provenance but never extra votes. Different values for one item and one
   dimension yield `Indeterminate` and no layout. Different dimensions remain
   independent optimizer inputs.
4. **Exact global result.** Across all feasible layouts, first maximize
   satisfied unique pressures; then minimize the exact integer sum of squared
   slot loads within each independent domain; then choose the lexicographically
   smallest assignment ordered by stable item ID and recording `(slot.order,
   slot ID)`. Floats, epsilon, weights, incumbents, local optima, and
   best-so-far publication are forbidden. The runtime returns only `Optimal`
   with a proved global layout, or `Indeterminate` without a layout. Production
   pruning must be sound and must match a bounded independent exhaustive oracle.
5. **No answer migration.** `schedule.*`, `prefer_with`, other pair
   preferences, assessments, pair constraints/scores, actions, reasons,
   rationales, notes, and semantic prose never migrate as answers. Before any
   evidence-bearing legacy entry is deleted, each atom receives one explicit
   disposition: typed closed-family fact, raw quotation, source metadata,
   Sol-only adjudication, or exclusion.
6. **Portable semantics, deferred backend.** TypeDB runtime/import is outside
   this cluster. Portability requires explicit types, roles, applicability,
   provenance, anchors, pressure identities, conflict behavior, and objective
   stages. Domain semantics may not exist only in Python.

Generated schedules, proof traces, diagnostics, and explanations are disposable
outputs and never feed canonical input. Exact legacy placement is not an
acceptance condition. Meaningful food, wake/sleep, and before/after semantics
are required; breakfast and another daytime meal may tie when no accepted fact
distinguishes them.

## Rationale

A closed vocabulary prevents a new alias from reintroducing a desired answer
under a factual-looking name. The five families cover the accepted scheduling
semantics without pretending to model dosage, chronic effects, disease, or
effect strength. Explicit roles, applicability, and provenance preserve the
evidence boundary and make another runtime capable of reproducing inference.

Independent slot axes prevent labels such as “morning”, “breakfast”, or
“workout” from becoming hidden biology. Treating slots as unbounded logical
groups keeps balanced presentation while avoiding a fictional physical-fit
claim.

Set-normalized pressures make the objective invariant to how many sources,
witnesses, components, or paths happen to encode the same accepted proposition.
Failing closed on a same-dimension contradiction is safer and more explainable
than silently choosing a side. Cross-dimension pressures remain legitimate
tradeoffs because they represent different propositions.

The exact lexicographic objective separates biological satisfaction, neutral
load balance, and presentation determinism. A closed `Optimal`/`Indeterminate`
status prevents a timeout or incumbent from masquerading as a canonical answer.
The independent exhaustive oracle checks the observable invariant rather than
the production algorithm.

## Rejected Alternatives

- **Generic EAV facts or an authorable rule DSL:** too easy to encode a stored
  placement or pair decision outside the reviewed vocabulary.
- **Named traits, pair preferences, assessments, or scores:** they store the
  answer and make new items depend on hand-authored scheduling policy.
- **Weighted or evidence-count voting:** representation multiplicity and source
  count are not biological magnitude or confidence.
- **Capacity or dose-aware placement:** no accepted fact model supports physical
  fit, tablet count, mass, volume, dose, or recurrence.
- **Greedy/local optimization or incumbent publication:** cannot satisfy the
  global product invariant.
- **Legacy layout as the golden result:** it would preserve hidden semantics;
  only accepted anchors and the exact objective govern the target result.
- **Selecting TypeDB now:** backend/import work does not resolve the semantic
  boundary and is deferred.

## V-Model Delivery

The V-left descent is now fixed: product invariant -> canonical boundary ->
closed facts and topology -> exhaustive inference laws -> exact runtime
contract. Each implementation cluster must ascend through its paired evidence:

| Implementation cluster | V-right acceptance |
| --- | --- |
| Canonical facts and migration | Closed-schema fixtures, complete atom dispositions, scenario/topology separation, and architecture audit for forbidden/hidden semantics |
| Inference and normalization | Complete truth tables, proof traces, multiplicity deduplication, same-dimension conflict failure, and cross-dimension preservation |
| Exact optimizer and publication | Exact objective unit cases, independent exhaustive-oracle equivalence, sound-pruning evidence, fail-closed status cases, real schedules, and final product-invariant acceptance |

The detailed ownership and acceptance criteria are normative in the living
contract. Sol-only panels adjudicate evidence and model decisions. Collection,
mechanical migration, and checks may be delegated separately.

## Migration Consequences

The implementation remains NON-CONFORMING until all three clusters pass their
V-right evidence. In particular, current `near`/`food` topology, physical
pillbox wording, schedule aliases, `prefer_with`, constraints, weights,
assessments, prose, Python behavior, generated artifacts, and regression
expectations are migration inventory, not target authority.

Raw evidence and historical documents remain immutable. A migration ledger must
exist before legacy evidence-bearing fields are removed. Current green tests are
useful current-state evidence only; they do not override this ADR.

## Supersession

This ADR supersedes the semantic-ownership, canonical-instance, trait, slot,
constraint, scoring, optimization, and target-layout clauses of
[Ontology-first versus Python-first spike closure](ontology-cutover-decision-20260821.md).
That document's historical observations, commands, test results, and release
evidence remain valid records of the branch it assessed.

[Execution-Engine Boundary Audit](execution-engine-boundary-audit-20260821.md)
also remains historical current-state evidence. Its proposed protocol remedy,
legacy traits, and any local/weighted scoring assumptions are not governing
where they conflict with this ADR.

This ADR refines and supersedes the broader provisional wording in its own
earlier revision: in particular, generic facts/relations, operator-provided
capacity, unspecified optimizer choice, and open-ended universal laws are no
longer part of the accepted target.
