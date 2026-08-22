# Canonical Instance and Inference Boundary — 2026-08-22

## Status

**Accepted target; migration required.** The repository is currently
non-conforming. Stored schedule traits, `prefer_with`, authored constraints and
weights, actions, semantic explanation prose, the legacy runtime-context
representation, and regression tests still protect the previous model. Scenario
facts themselves are valid target inputs; the non-conformance is their coupling
to stored answers. This decision does not claim that the target has been
implemented.

## Decision

Canonical input has two ownership layers:

1. **Reusable ontology/world facts** store cross-scenario entities, stable
   identities, observations, evidence-backed facts and relations,
   applicability, and provenance.
2. **Scenario-scoped operator/runtime facts** store the current active shelf,
   possession, stack and pillbox selection, available slots, capacity, and
   other facts owned by the current operator/scenario. They change or expire
   with the scenario and are not reusable ontology facts.

Both layers pass the same facts-only gate. Neither stores a desired placement,
pair preference, optimizer score or weight, prescribed action, semantic UI
prose, pressure, schedule, proof trace, or other derived answer. In particular,
`prefer_with`, `prefer_same`, and `prefer_apart` are not authored instance facts.
Pair-specific decisions and scores are forbidden.

Concrete behavior is produced dynamically:

```text
reusable ontology/world facts -----------\
                                          -> small universal declarative inference laws
scenario-scoped operator/runtime facts --/     -> ephemeral pressures and proof trace
                                                -> generic optimizer
                                                -> generated layout and explanation
```

Universal laws contain no supplement or concrete-pair identity. Python is
limited to generic loading, validation, compilation, rule execution,
optimization, proof-trace handling, and rendering. Derived output never feeds
canonical input.

The field gate in both layers is: **world or scenario fact/relation, or stored
answer?** Only a fact or relation is admissible canonical input.

## Rationale

The previous ontology-first boundary moved many values out of Python but still
authored scheduling answers in instance data. A named placement trait, pair
preference, constraint action, or score predetermines what the scheduler should
do instead of describing the world from which behavior can be inferred.

Separating facts, universal laws, and generic optimization makes ownership
testable. New supplements and pairs can enter through evidence-backed facts
without new pair-specific policy or Python. Proof traces can explain a layout
without preserving hand-written explanation text in the executable model.

## Scope

This decision governs canonical ontology instances, repository data, inference
laws, runtime compilation and execution, optimization inputs, generated
schedules, explanations, tests, and future panels or refactors that touch those
surfaces.

The living contract is [docs/domain-model.md](../domain-model.md). It may refine
schema details while preserving this boundary.

## Non-goals

This decision does not:

- add medical recommendation authority, dosage, or recurrence semantics;
- select an external database or require TypeDB;
- require a particular optimizer algorithm;
- authorize deletion of immutable source material or historical evidence; or
- claim that the current implementation conforms.

Identifiers, source locators, quotations, and raw immutable source material are
not semantic UI prose. They remain governed by identity, provenance, and source
ownership rules.

## Evidence-Prose Migration

Before deleting legacy `reason`, `action`, `rationale`, or `notes` content:

1. inventory every entry;
2. atomize it into individual claims;
3. disposition each atom as a reusable fact/relation with provenance, immutable
   source material, Sol-panel adjudication, or exclusion; and
4. verify that no important evidence was silently converted into generated UI
   text or lost.

Important content that cannot be expressed faithfully goes to a Sol-only expert
panel. Extend the model only for a reusable, in-scope fact or relation.
Otherwise exclude it from the working ontology. The target executable ontology
contains zero authored semantic prose.

## V-Model Acceptance

The left descent is mandatory before implementation:

1. product invariant;
2. canonical boundary;
3. facts and relations;
4. universal inference laws; and
5. runtime design.

Each level defines its paired evidence before work moves lower. Verification
then ascends: unit checks -> inference-law checks -> architecture conformance ->
real schedules -> product-invariant acceptance. No lower implementation begins
before the upper contract and its evidence are accepted.

| Left-side contract | Required evidence | Right-side acceptance |
| --- | --- | --- |
| Product invariant | Accepted real scenarios and deterministic properties | Real-schedule checks, then product-invariant acceptance |
| Canonical boundary | Allowed/forbidden inventory and feedback-path audit | Architecture conformance |
| Facts and relations | Schema fixtures, provenance cases, migration dispositions | Unit checks for fact contracts |
| Universal laws | Positive, negative, conflict, and boundary truth tables | Inference-law checks with proof traces |
| Runtime design | Generic component contracts and observable results | Runtime unit checks |

All expert panels for adjudication or model decisions are Sol-only. Luna may
collect evidence, perform mechanical implementation, and run checks.

## Current Audit Status

The migration has not begun in this documentation cluster. Known
non-conforming surfaces include:

- authored schedule traits and desired-placement semantics;
- `prefer_with` and stored same/apart pair decisions;
- authored scheduling constraints, operations, weights, bonuses, and penalties;
- `reason`, `action`, `rationale`, and other semantic prose in working data;
- the legacy runtime-context representation and Python paths coupled to the
  previous authored answers; scenario facts themselves remain required target
  inputs; and
- tests and generated artifacts that assert the previous model.

These surfaces require inventory and V-model migration. Passing current tests
is current-state evidence only.

## Supersession

This ADR supersedes only the semantic-ownership and source-of-truth clauses of
[Ontology-first versus Python-first spike closure](ontology-cutover-decision-20260821.md).
That document's historical observations, commands, test results, and release
evidence remain valid records of the branch it assessed.

[Execution-Engine Boundary Audit](execution-engine-boundary-audit-20260821.md)
also remains historical current-state evidence. Its proposed protocol remedy is
not the governing target where it conflicts with this decision.
