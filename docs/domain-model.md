# Domain Model

This is the living semantic contract for `supp-slotter`. The governing decision
is [Canonical Instance and Inference Boundary](decisions/canonical-instance-inference-boundary-20260822.md).

## Status

**Accepted target; NON-CONFORMING implementation.** The repository does not yet
implement this contract. Current ontology, data, runtime paths, generated
artifacts, and regression tests still encode legacy schedule aliases, authored
preferences, scores, actions, prose, and other stored answers. A green current
test suite proves only the current implementation. It is not acceptance evidence
for this target.

This document fixes the V-left contract. No implementation cluster may describe
the migration as complete until all V-right evidence in this document passes.

## Product Invariant

Given the same typed evidence facts, explicit applicability and provenance,
scenario-selected items, logical slot topology, and universal laws, the system
must either:

- return the one deterministically selected **globally Optimal** layout with a
  proof trace; or
- return **Indeterminate** and no layout when the facts conflict or global
  optimality cannot be proved.

The result must not depend on an authored desired placement, pair preference,
weight, magnitude, action, explanation, label, or domain rule hidden in Python.
Adding an item must require facts in the closed vocabulary, not item-specific or
pair-specific scheduler code.

## Canonical Boundary

Canonical input has three separately owned parts:

1. **Reusable evidence** owns stable item, substance, component, and source
   identities; explicit composition roles; the five closed fact families below;
   applicability; and provenance.
2. **Scenario selection** owns which items participate in which scheduling
   domain. `data/stacks.yaml` is the current scenario-selection surface.
3. **Logical slot topology** owns the available logical intake groups and their
   anchors. `data/pillboxes.yaml` is the current topology surface.

Scenario selection and topology are separate inputs. Membership in a stack does
not assert a placement, and a topology does not select an item. Neither may be
promoted into reusable evidence or populated from generated output.

The gate for every authored field is: **world/scenario fact or stored answer?**
Only a fact admitted by this contract is canonical. The following are forbidden
canonical inputs:

- `schedule.*` aliases or any desired slot/placement;
- `prefer_with`, `prefer_same`, `prefer_apart`, assessments, pair constraints,
  pair scores, or pair-specific operations;
- weights, magnitudes, bonuses, penalties, float objectives, or epsilon policy;
- prescribed actions, recommendations, reasons, rationales, semantic UI prose,
  or a sentence intended to appear in an explanation;
- dose, frequency, recurrence, disease, diagnosis, or patient-state semantics;
- inferred pressures, rankings, layouts, proof traces, or other generated
  answers; and
- a generic EAV predicate/value escape hatch or an authorable scheduling DSL.

Stable IDs, explicit type tags, source locators, and raw quotations are not
semantic prose, but a quotation is evidence material rather than an executable
fact. It cannot create a pressure until it has been adjudicated into one of the
closed families.

## Closed Scheduling Fact Vocabulary

The executable scheduling vocabulary contains exactly five fact families. Each
assertion has a typed subject role, one of the enumerated values, explicit
applicability, and provenance. There is no `name/value` extension mechanism.

| Fact family | Admitted value | Meaning |
| --- | --- | --- |
| `FoodEffect` | `bioavailability_increases` | With food, bioavailability increases relative to without food. |
| `FoodEffect` | `bioavailability_decreases` | With food, bioavailability decreases relative to without food. |
| `FoodEffect` | `tolerability_improves` | With food, tolerability improves relative to without food. |
| `FoodEffect` | `tolerability_worsens` | With food, tolerability worsens relative to without food. |
| `AcuteAlertnessEffect` | `acute_alertness_increases` | A proven acute increase in alertness occurs in the stated applicability. |
| `AcuteSleepEffect` | `onset_latency_decreases` | Sleep-onset latency decreases in the stated applicability. |
| `AcuteSleepEffect` | `continuity_improves` | Sleep continuity improves in the stated applicability. |
| `PreExercisePerformanceEffect` | `performance_improves` | Pre-exercise use improves performance in the stated applicability. |
| `PostExerciseRecoveryEffect` | `recovery_improves` | Post-exercise use improves recovery in the stated applicability. |

“Proven” here means accepted evidence after the repository's evidence and Sol
adjudication process; it is not inferred from a marketing category, product
name, or legacy placement. Strength, probability, dose dependence, and effect
magnitude are deliberately not represented.

An assertion may be made about a typed substance/component and apply to a
schedulable item only through explicit composition roles and applicability.
Product, substance, and component identities stay distinct. Source and witness
records preserve evidence lineage; they do not duplicate the resulting fact.
No other trait, assessment, free-form relation, or pair relation is a scheduler
input under this contract.

## Logical Slots and Anchors

A slot is an **unbounded logical intake group**, not a compartment or physical
capacity model. It has stable identity and display order plus zero or one value
on each independent anchor dimension:

| Dimension | Closed values |
| --- | --- |
| `meal_context` | `with_food`, `without_food` |
| `circadian_anchor` | `wake`, `sleep` |
| `exercise_anchor` | `before`, `after` |

The dimensions are independent. For example, an exercise slot may also have a
meal context; no value on one axis implies a value on another. Missing means
unspecified, not a default. Slot labels, IDs, and order carry no biological
meaning. Labels are presentation only; IDs identify; order participates only in
the final deterministic tie-break.

There is no slot capacity and no tablet, capsule, milligram, serving, liquid
volume, package, or physical-fit model. Any future introduction of such a model
requires a new V-left decision; it must not be smuggled in through a label,
count, weight, or optimizer bound.

Current `near`/`food` fields and physical-container wording are legacy
representations to migrate, not alternative authority for these anchors.

## Universal Laws and Normalized Pressures

The universal laws are exhaustive and identity-free:

| Evidence fact | Derived pressure |
| --- | --- |
| `FoodEffect.bioavailability_increases` | `(item_id, meal_context, with_food)` |
| `FoodEffect.bioavailability_decreases` | `(item_id, meal_context, without_food)` |
| `FoodEffect.tolerability_improves` | `(item_id, meal_context, with_food)` |
| `FoodEffect.tolerability_worsens` | `(item_id, meal_context, without_food)` |
| `AcuteAlertnessEffect.acute_alertness_increases` | `(item_id, circadian_anchor, wake)` |
| `AcuteSleepEffect.onset_latency_decreases` | `(item_id, circadian_anchor, sleep)` |
| `AcuteSleepEffect.continuity_improves` | `(item_id, circadian_anchor, sleep)` |
| `PreExercisePerformanceEffect.performance_improves` | `(item_id, exercise_anchor, before)` |
| `PostExerciseRecoveryEffect.recovery_improves` | `(item_id, exercise_anchor, after)` |

A normalized unary pressure has identity
`(item_id, dimension, value)`. The runtime takes the set of these identities.
Multiple witnesses, sources, quotations, applicable components, inference paths,
or repeated assertions producing the same identity add provenance to one proof
node; they never add votes or objective value.

If one item derives different values for the same dimension, the input is
conflicted. The only valid result is `Indeterminate`, with the conflicting facts
and provenance in diagnostics and no layout. Pressures on different dimensions
are not conflicts. They remain independent optimizer inputs and may create a
cross-dimension tradeoff when the topology has no slot satisfying all of them.

These mappings are the complete domain inference laws. Their typed form, roles,
applicability, and provenance must be inspectable and portable. They must not be
implemented as item-name checks, special pairs, or otherwise hidden Python
semantics. This decision does not select a generic rule DSL.

## Exact Optimization Contract

A feasible layout assigns every scenario-selected item to exactly one logical
slot in its selected scheduling domain. Slots are unbounded, so feasibility has
no capacity constraint. A pressure is satisfied exactly when the assigned slot
has the matching value on that pressure's dimension; an unspecified slot anchor
does not satisfy it.

Over **all** feasible layouts, selection is lexicographic:

1. maximize the number of satisfied unique normalized pressures;
2. subject to step 1, minimize the exact integer sum of squared slot loads,
   `sum(load(slot)^2)`, within every independent scheduling domain (equivalently
   their sum because items cannot move between domains); and
3. subject to steps 1 and 2, choose the lexicographically smallest assignment
   tuple obtained by sorting items by stable `item_id` and recording each
   assigned slot as `(slot.order, slot_id)`.

`load(slot)` is the integer count of assigned items. It is a balance objective,
not a physical-capacity claim. All comparisons are exact integers. Floats,
epsilon comparisons, authored weights, weighted witnesses, and approximate
score equality are forbidden.

The observable solver status is closed:

- `Optimal`: global optimality and the deterministic tie-break are proved; a
  layout and proof trace may be published.
- `Indeterminate`: facts conflict, input is invalid, search is interrupted,
  times out, exhausts a resource bound, or otherwise cannot prove the global
  optimum; no layout is published.

No `Feasible`, local optimum, incumbent, best-so-far, or timeout layout may cross
the publication boundary. Production pruning is permitted only when it is sound:
it must preserve the selected result and proof of optimality under the full
objective. Each production implementation must be accepted against a bounded,
independent exhaustive oracle that enumerates all layouts and applies the same
objective without sharing production pruning or search code.

## Generated Output

Generated `schedule.yaml`, explanations, diagnostics, proof traces, and future
read models are disposable projections. They never feed canonical input and are
not evidence for a new fact. Explanations are rendered only from typed facts,
law identities, anchor matches, conflict diagnostics, and optimization outcomes.

Exact reproduction of a legacy layout is not an acceptance requirement.
Meaningful with-food/without-food, wake/sleep, and before/after semantics are.
When no accepted fact distinguishes breakfast from another daytime meal, those
slots may tie and the exact deterministic objective decides; legacy
breakfast/day placement is not authority.

## Evidence Migration

Legacy aliases and authored answers do not migrate merely because current code
or tests consume them. This includes `schedule.*`, `prefer_with`, assessments,
pair constraints, pair scores, actions, reasons, rationales, notes, and semantic
explanation prose.

Before deleting any legacy evidence-bearing entry, atomize it and record exactly
one explicit disposition for every evidence atom:

1. typed fact in one of the five families, with roles, applicability, and
   provenance;
2. raw quotation linked to its source, non-executable;
3. source/locator metadata, non-executable;
4. Sol-only adjudication required; or
5. explicit exclusion with a reason.

Nothing is silently translated into a placement, preference, score, or generated
sentence. Immutable raw evidence and historical decisions are preserved. The
number of quotations, sources, witnesses, or applicable components never
multiplies a normalized pressure.

## Runtime and Portability Boundary

TypeDB runtime selection, import design, and deployment are outside the current
cluster. Portability in this contract means that another conforming runtime can
observe explicit fact-family types, subject/component roles, applicability,
provenance, slot anchors, derived pressure identities, and objective values and
obtain the same status and selected layout.

Python may provide generic loading, validation, inference execution, exact
optimization, proof handling, and rendering. It may not be the only place where
a domain mapping, enum meaning, applicability rule, conflict rule, or objective
stage exists. No item or pair name may select domain behavior.

## Three Implementation Clusters and V-Right Acceptance

Implementation follows three downstream clusters. They may be developed in
parallel only after this V-left contract is accepted, and each must preserve the
NON-CONFORMING status until its acceptance evidence passes.

### Cluster 1: canonical facts and migration

Own the five explicit fact-family schemas, typed roles, applicability,
provenance, the independent slot-anchor schema, scenario/topology separation,
and the atom-by-atom migration ledger. It does not own inference or layout
choice.

V-right acceptance:

- positive and negative schema fixtures prove the vocabulary is closed and has
  no EAV/DSL, stored answer, capacity, dose/frequency/disease, or semantic-prose
  escape hatch;
- every migrated atom has one allowed disposition and raw evidence is retained;
- architecture checks prove `stacks.yaml` selection and `pillboxes.yaml`
  topology remain separate; and
- a hidden-semantics audit finds no domain meaning recoverable only from Python,
  names, labels, IDs, or order.

### Cluster 2: inference and pressure normalization

Own the exhaustive universal mappings, applicability traversal, provenance-rich
proof nodes, pressure set normalization, and same-dimension conflict result. It
does not own solver heuristics or migration adjudication.

V-right acceptance:

- finite positive, negative, boundary, and conflict truth tables pass for every
  admitted fact value;
- duplicate witnesses, sources, inference paths, and components produce one
  pressure identity and one vote;
- same-dimension opposing values return `Indeterminate` with no layout while
  cross-dimension pressures remain optimizer inputs; and
- proof traces identify every contributing typed assertion and law.

### Cluster 3: exact optimizer and publication boundary

Own feasibility, the three-stage exact objective, deterministic tie-breaking,
sound production pruning, closed statuses, and generated-output publication. It
does not infer biological meaning.

V-right acceptance:

- exact unit cases cover pressure maximization, per-domain squared-load
  minimization, stable-ID/`(order, slot ID)` tie-breaking, and unbounded slots;
- bounded randomized and exhaustive cases match an independently implemented
  exhaustive oracle in status, objective values, and assignment;
- forced conflict, timeout, interruption, and resource-bound scenarios publish
  `Indeterminate` and no incumbent layout;
- real schedules demonstrate meaningful meal, circadian, and exercise anchors
  without requiring exact legacy placement; and
- final architecture and product-invariant acceptance proves deterministic
  `Optimal` or layout-free `Indeterminate` end to end.

## Non-Goals

This contract does not add medical recommendation authority, dose or recurrence
semantics, a physical pillbox model, TypeDB runtime/import, a generic authoring
language, or a second scheduler. It does not authorize deletion of raw evidence
or historical decisions.
