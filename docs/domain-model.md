# Domain Model

This is the living semantic contract for `supp-slotter`. The accepted target is
a canonical authored instance model that records the world and operator state,
not a precomputed scheduling answer. The governing decision is
[Canonical Instance and Inference Boundary](decisions/canonical-instance-inference-boundary-20260822.md).

## Status

**Accepted target; migration required.** The repository does not yet conform.
The current ontology, data, legacy runtime-context representation, and
regression tests still protect stored schedule traits, `prefer_with`, pair
constraints, numeric weights, actions, explanation prose, and other parts of
the previous model. Scenario facts are valid target inputs; the problem is the
legacy representation that couples them to stored answers. Existing green tests
demonstrate the current implementation, not acceptance of this contract.

Until migration is complete, every change must distinguish:

- the target contract in this document;
- legacy behavior retained temporarily for migration; and
- derived runtime output, which is never canonical input.

Do not describe the target as shipped until the full V-model acceptance matrix
passes.

## Product Invariant

Given the same reusable ontology/world facts, scenario-scoped operator/runtime
facts, and universal laws, the system must produce a deterministic schedule and
a proof trace without relying on an authored desired placement, pair decision,
score, action, or explanation.

Changing a supplement, pair, or schedule must be possible by changing facts or
a genuinely universal law. It must not require supplement-specific or
pair-specific Python.

## Canonical Instance Boundary

Canonical input has two ownership layers:

1. **Reusable ontology/world facts** are cross-scenario entities, observations,
   evidence-backed facts and relations, applicability conditions, stable
   identifiers, and provenance.
2. **Scenario-scoped operator/runtime facts** describe the current scenario,
   including active shelf state, possession, stack and pillbox selection,
   available slots, and capacity. They are owned by the operator/scenario and
   expire or change with it; they are not promoted into reusable ontology facts.

Both layers pass the same facts-only gate. Neither layer may contain:

- desired placements or slot assignments;
- pair preferences, including `prefer_with`, `prefer_same`, or `prefer_apart`;
- pair-specific decisions, operations, or scores;
- weights, bonuses, penalties, or optimizer objectives attached to domain
  instances;
- prescribed actions;
- semantic UI prose such as explanations, reasons, recommendations, or warning
  text; or
- any inferred result, pressure, ranking, schedule, proof trace, or other
  derived answer.

The gate for every proposed field in either layer is: **world or scenario
fact/relation, or stored answer?** If it is a stored answer, it does not belong
in canonical input.

Identifiers, source locators, quotations or raw immutable source material, and
operator-entered labels are not semantic UI prose. They still require an
explicit owning object and provenance.

## Core Objects

The exact schemas will be settled during migration, but their ownership is
already fixed:

- **Entity** represents a real product, substance or form, physical organizer,
  slot, source, or other in-scope thing with stable identity.
- **Observed state** records label-backed composition and other measurements or
  observations attributable to a source.
- **Operator state** records facts the operator controls or reports, such as
  possession, active/inactive tracking, available organizers, and declared
  scenario context. It does not prescribe a placement.
- **Fact** is an evidence-backed proposition about one entity.
- **Relation** is an evidence-backed proposition connecting entities. A
  relation states what is true; it does not encode what the optimizer should do
  with a named pair.
- **Applicability** states when a fact or relation applies. It is factual scope,
  not an authored scheduling action.
- **Provenance** links an assertion to source material and its bounded evidence
  state.

Products and substances remain separate identities: the product records the
physical label-backed item, while substances and forms carry reusable facts.
Stable authored IDs are identity; filenames and generated IRIs are transport or
source-path details.

## Trait Ontology

The target vocabulary expresses reusable factual predicates, not planner
commands. A term is admissible only when its meaning can be stated and tested
without naming a desired slot, preferred partner, action, or score.

Before adding or retaining a term:

1. State the world proposition it represents.
2. Identify its subject, value or object, applicability, and provenance.
3. Show that it is reusable beyond one product pair or one generated schedule.
4. Define how universal inference laws may consume it without embedding the
   expected result in the instance.

Current scheduling traits and context-shaped fields are migration inputs, not
automatically valid target facts. Each must be retained as a factual assertion,
re-expressed through reusable facts and applicability, or removed.

## Universal Inference Laws

Scheduling behavior emerges from a small set of declarative laws. A law:

- is universal over typed facts and relations;
- contains no supplement, product, or concrete pair identity;
- derives ephemeral pressures and a proof step, not a canonical assertion;
- has explicit applicability and conflict behavior; and
- is independently testable with finite positive, negative, and boundary
  examples.

`prefer_same` and `prefer_apart` are examples of derived pressures, never
authored instance relations. A law may infer one of those pressures from facts
and relations in the two canonical input layers, with the contributing
assertions recorded in the proof trace.

## Runtime Boundary

The runtime flow keeps the two inputs separate and is one-way:

```text
reusable ontology/world facts -----------\
                                          -> universal declarative inference laws
scenario-scoped operator/runtime facts --/     -> ephemeral pressures and proof trace
                                                -> generic optimizer
                                                -> generated layout and explanation
```

Derived pressures, proof steps, candidate scores, layouts, and explanations are
ephemeral or generated output. They must never feed back into canonical input,
directly or through a generated artifact treated as authority.

Python may implement only generic mechanics:

- loading and validating canonical instances and laws;
- compiling and executing the declarative laws;
- resolving typed identities and joins;
- optimizing over derived pressures and operator-provided capacity;
- rendering a generated layout, warnings, proof trace, and explanation; and
- serializing derived output.

Python must not contain supplement- or pair-specific semantics. A Python
branch, constant, handler, or renderer rule that names or recognizes a
particular supplement or pair violates the boundary.

## Scheduling Semantics

The schedulable unit comes from reusable entity facts plus scenario-scoped
active-shelf and possession facts. Stack/pillbox selection, available slots,
and capacity are scenario-scoped facts. Feasibility and desirability are
inferred at runtime. The optimizer receives only those inputs, deterministic
tie-breaking rules, and ephemeral pressures produced by the law executor.

The optimizer is generic. It may choose any implementation that satisfies the
declared objective and deterministic observable contract. It cannot invent
domain meaning, and it cannot read legacy placement traits or pair preferences
as hidden answers.

The renderer explains the selected layout from the proof trace. Explanation
text is generated from typed facts, law identifiers, and outcomes; it is not
authored per supplement, pair, constraint, or warning.

Generated `schedule.yaml` and any future read model are disposable projections.
They are not edited directly and are not evidence for a new canonical fact.

## Evidence and Prose Migration

Legacy `reason`, `action`, `rationale`, and `notes` content must not be bulk
deleted. Before removal, inventory every entry, atomize its claims, and record a
disposition for each atom:

- retain as a reusable fact or relation with provenance;
- retain only as source locator, quotation, or immutable raw material;
- send to a Sol-only expert panel when it is important but cannot be expressed
  faithfully; or
- exclude it from the working model when it is not an in-scope reusable fact.

Extend the model only when the missing concept is a reusable, in-scope fact or
relation. Do not add a field merely to preserve prose, a one-off pair decision,
or an expected UI sentence.

The target working ontology contains zero authored semantic prose. Historical
decision documents and immutable source material may preserve prose as
evidence; they are not executable instance data.

## V-Model Delivery Contract

Every feature, panel, and refactor follows the same V. The left side is written
top-down before implementation:

1. product invariant;
2. canonical boundary;
3. required facts and relations;
4. universal inference laws; and
5. runtime design.

Each level must define its paired evidence before work proceeds lower. After
implementation, verification ascends in this order:

1. unit checks for the runtime design and fact contracts;
2. inference-law checks with finite truth tables and proof traces;
3. architecture conformance showing no stored answers, domain-specific Python,
   or derived-to-canonical feedback;
4. real-schedule checks over accepted scenarios; and
5. product-invariant acceptance.

No lower implementation begins while an upper contract or its paired evidence
is missing. Expert adjudication and model changes use Sol-only panels. Luna is
limited to evidence collection, mechanical implementation, and checks.

## Acceptance Matrix

| Left-side contract | Evidence defined before implementation | Right-side acceptance |
| --- | --- | --- |
| Product invariant | Real scenarios and deterministic expected properties | Real schedules, then final product-invariant acceptance |
| Canonical boundary | Allowed/forbidden field inventory and feedback-path audit | Architecture conformance |
| Facts and relations | Schema fixtures, provenance cases, and migration dispositions | Unit checks for fact contracts |
| Universal laws | Positive, negative, conflict, and boundary truth tables | Inference-law checks and proof traces |
| Runtime design | Generic component contracts and deterministic observables | Runtime unit checks |

Migration is complete only when every row passes and no legacy test protects a
forbidden authored answer.

## Ownership Rules

- Reusable ontology/world sources own cross-scenario entities, facts,
  relations, applicability, and provenance. Their lifecycle is evidence- and
  model-driven, independent of one schedule run.
- The current operator/scenario owns active shelf state, possession,
  stack/pillbox selection, available slots, capacity, and other scenario facts.
  This layer is created, updated, and retired with the scenario and must not be
  promoted into reusable ontology facts or populated from derived output.
- Both canonical input layers own facts only and pass the same stored-answer
  prohibition.
- Universal law sources own reusable inference semantics.
- Python owns generic execution and rendering mechanics only.
- Generated projections own nothing and may be rebuilt.
- Historical documents preserve evidence but do not override this living
  contract.

## Non-Goals

This contract does not add medical recommendation authority, dosage or
recurrence semantics, an external database, or a second scheduler. It does not
authorize deletion of raw evidence or historical decisions. It defines the
boundary and acceptance path for the required migration.
