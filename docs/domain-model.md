# Domain model

## Product invariant

Every published layout is the globally optimal result of the canonical fact
model. A result is either `Optimal`, with a proved layout, or `Indeterminate`,
with no layout.

For the active shelf, global optimality is necessary but not sufficient:
published scheduling must also be semantically covered. Each active composition
role and applicable scheduling dimension must have a closed, reviewable
disposition before a layout can claim to be materially guided by knowledge. An
incomplete coverage record is `Indeterminate`, never an apparently neutral or
balance-only layout. This recovery contract is governed by the
[actionable-knowledge coverage decision](decisions/actionable-scheduling-knowledge-coverage-boundary-20260831.md)
and supplements, without weakening, the
[canonical instance and inference boundary](decisions/canonical-instance-inference-boundary-20260822.md).

## Canonical inputs

The authoritative inputs are:

- the five typed fact families: `FoodEffect`, `AcuteAlertnessEffect`,
  `AcuteSleepEffect`, `PreExercisePerformanceEffect`, and
  `PostExerciseRecoveryEffect`;
- typed subject, composition-role applicability, and evidence provenance for
  every fact;
- scenario membership from `data/stacks.yaml`; and
- unbounded logical slot topology from pillbox data, with optional
  `meal_context`, `circadian_anchor`, and `exercise_anchor` anchors.

Slots are logical intake groups. Their IDs, labels, and order do not encode
biological meaning, and there is no capacity or physical-fit model.

The complete universal laws map each admitted fact value to one normalized
pressure identity `(item_id, dimension, value)`. Fact applicability is exact:
a composition-role applicability reaches that role only, while a substance
applicability reaches every and only composition role with the same substance.
Sources, quotations, components, and proof paths contribute provenance only;
they do not multiply a pressure. Opposing values for one item and dimension
produce `Indeterminate`.

## Closed Scheduling Fact Vocabulary

The only scheduler facts are these five typed families and their nine admitted
values. Each fact has exactly one typed subject, explicit typed applicability
(a substance or composition role), and evidence provenance. There is no
generic predicate/value extension.

| Family | Admitted values | Derived law |
| --- | --- | --- |
| `FoodEffect` | `bioavailability_increases`, `bioavailability_decreases`, `tolerability_improves`, `tolerability_worsens` | respectively `meal_context=with_food`, `meal_context=without_food`, `meal_context=with_food`, `meal_context=without_food` |
| `AcuteAlertnessEffect` | `acute_alertness_increases` | `circadian_anchor=wake` |
| `AcuteSleepEffect` | `onset_latency_decreases`, `continuity_improves` | `circadian_anchor=sleep` |
| `PreExercisePerformanceEffect` | `performance_improves` | `exercise_anchor=before` |
| `PostExerciseRecoveryEffect` | `recovery_improves` | `exercise_anchor=after` |

The laws are complete, universal, and identity-free. They never encode an item,
product, slot, desired placement, weight, action, or explanation.

## Actionable knowledge coverage boundary

This is a V-left contract for the recovery; it does not itself adjudicate or
admit any current candidate, change the five currently admitted fact families,
or authorize a data/runtime change. Before any lower-level implementation, the
closed candidate catalog and its universal laws must be accepted with the
paired evidence in the matrix below.

### Candidate and disposition vocabulary

A **scheduling candidate** is a source-indexed claim discovered while covering
an active daily, episodic, or training composition role. Every candidate has
exactly one of these closed dispositions:

| Disposition | Meaning | Scheduler effect |
| --- | --- | --- |
| `pressure` | An individually adjudicated directed hypothesis with typed subject/applicability, provenance/research state, a closed fact or pairwise world-fact mechanism, and a universal-law path. | One derivable normalized pressure; it is never an authored placement. |
| `neutral` | An assessed in-model candidate with no directed scheduling outcome. | None; it remains accountable in coverage. |
| `unresolved_without_direction` | Evidence is incomplete and does not justify a directed hypothesis. | None; it remains visibly research-open rather than silently neutral, but closes coverage for this exact candidate once its scope, provenance, and disposition validate. |
| `outside_model` | A candidate excluded by one explicit closed reason. | None; it does not close unrelated candidates or dimensions. |

Duplicate, missing, or mutually inconsistent dispositions are invalid. A valid
`unresolved_without_direction` disposition is coverage-closed for its exact
candidate, not neutral: later evidence may reopen research, but it does not
make the current active shelf incomplete. Missing, unassessed, malformed, or
stale candidate coverage remains incomplete. A
directed hypothesis—including an anecdotal, mechanistic, or otherwise weak
one—is not made a lower-weight signal: after individual semantic adjudication,
it is one formal soft pressure through a typed fact and a universal law.
Research state, source count, quotations, witnesses, components, and proof
paths remain provenance and explanation metadata; none changes pressure
identity or objective value. Therefore every admitted pressure outranks
balance, exactly as specified by the existing optimizer.

### Contradiction and pairwise boundary

Opposing derived values for the same item and dimension are a direct
contradiction, including values derived from pairwise mechanisms. The canonical
boundary returns layout-free `Indeterminate` and routes the record to
adjudication; it must not choose, cancel, average, weight, or balance around
the conflict.

Pairwise scheduling behavior is admissible only when a minimal typed
**world fact or relation** plus a universal law entails co-location or
separation. `same_slot`, `different_slot`, pair preferences, placements, and
their UI prose are stored answers and cannot be canonical inputs. Passive
supports, balance, and contextual relations remain non-scheduling evidence
unless a separately accepted typed mechanism and law make their consequence
derivable.

### Generic-note removal boundary

Generic authored `notes` are not a canonical product, substance, or component
surface. A one-time stable source-span inventory may map each existing span to
typed identity, composition, source/provenance, candidate/evidence material, or
an explicit discard reason. After cutover, the canonical schema rejects `notes`;
there is no notes parser, NLP/keyword heuristic, compatibility field, migration
runtime, or legacy museum. Only the closed typed candidate/disposition catalog
may carry a scheduling candidate.

### Coverage certificates and publication

A coverage certificate is derived verification metadata, never an optimizer
input or stored answer. For one active composition role it records the role,
applicable dimensions, exhaustive evaluated candidate IDs, exactly-one
dispositions, each disposition's required evidence path, and exact input
hashes. A valid `unresolved_without_direction` entry is shown explicitly as
research-open and coverage-closed; it never becomes neutral or a pressure.
The certificate proves that no unadjudicated directional candidate was omitted,
not that no admitted pressure exists. A balance-and-tie-break-only explanation
must also expose any unsatisfied admitted pressure rather than claiming that no
direction exists. A balance-only item may publish only with its complete current
certificate; missing, unassessed, stale, malformed, or incomplete coverage
makes the whole result layout-free `Indeterminate`.

### Why the earlier V-model missed semantic coverage

The prior V-model proved mechanism correctness: closed facts compiled, laws
normalized them, exact optimization found the global result, and publication
failed closed. It did not impose an upper V-left obligation that every active
role and discovered candidate be semantically assessed. Useful prose,
structured memberships, and passive relations could therefore remain outside
the scheduler while all lower inference and optimizer checks passed. Semantic
coverage is now a product invariant with deterministic right-side evidence,
not a documentation aspiration.

### V-left to V-right acceptance matrix

No lower cluster starts while its upper contract is missing or disputed. After
implementation, acceptance ascends through the paired evidence in this order.

| V level | V-left contract | V-right acceptance evidence |
| --- | --- | --- |
| 1. Product invariant | A real active-shelf layout materially follows formal world facts. | Real active-shelf trace proves every placement and every balance-only certificate. |
| 2. Knowledge coverage | Every active composition role and discovered scheduling candidate has exactly one formal disposition; generic notes no longer exist in canonical cards. | Deterministic coverage manifest has zero orphan/prose-only claims and zero unassessed active candidates; schema and corpus prove zero generic notes, and the one-time source-span receipt proves no data loss. |
| 3. Ontology/admission | Every directed hypothesis, including anecdotal and mechanistic claims, compiles only through a typed fact or minimal pairwise world-fact mechanism and a universal-law path. | Compiler and inference proofs establish applicability, provenance, dimension, value, and law; passive relations have negative admission evidence. |
| 4. Objective | Every admitted pressure outranks balance while the exact global optimum and stable tie-break are unchanged. | Metamorphic and exhaustive optimizer witnesses prove pressure-before-balance and exactness. |
| 5. Publication | Incomplete coverage cannot masquerade as neutral or balance-only; direct contradictions cannot yield a layout. | Fail-closed `Indeterminate` witnesses reject absent/stale certificates and contradictions; explanations expose certified balance-only outcomes. |
| 6. Agent workflow | Grooming cannot be closed by prose, generic notes, or passive relations alone. | Workflow smoke and schema rejection prove that a candidate stays open until its typed disposition and evidence are present. |

## Exact optimizer

Across all feasible layouts, the runtime selects lexicographically:

1. the greatest number of satisfied unique pressures;
2. the smallest exact integer `sum(load(slot)^2)` within each independent
   scheduling domain; then
3. the stable assignment tuple sorted by item ID and represented as
   `(slot.order, slot_id)`.

The runtime uses exact integer comparison. A layout may be published only after
global optimality and the tie-break are proved. Interrupted, invalid, conflicted,
or resource-bounded work is `Indeterminate` and remains layout-free.

A normalized pressure `(item_id, dimension, value)` is satisfied exactly when
the selected slot's anchor at `dimension` equals `value`. An absent or different
anchor does not satisfy it.

## Migration ledger

[The migration receipt](migrations/legacy-atom-ledger.yaml) is a compact,
immutable shape-and-hash closure record for the completed scheduling migration.
Its historical generator is retired; it neither reconstructs legacy data nor
authorizes derived placements or other stored scheduling answers.

## Runtime boundary and acceptance

The ontology owns fact types, roles, applicability, universal laws, anchors,
pressure identities, and objective stages. Python provides generic loading,
validation, inference, exact optimization, proofs, and rendering. A conforming
runtime must be able to observe those inputs and reproduce the same result. The
runtime envelope and every canonical identifier are strict: malformed envelope
metadata or blank/padded IDs fail closed before inference.

Online commands load the compact closure receipt, `runtime-lock.json`; it
declares the nine executable outputs only. The formal ontology gate recompiles
authored sources and verifies the full artifact set separately. A current
`schedule.yaml` is a disposable derived layout: plan invalidates it before work,
and a successful `show` recomputes and overwrites it through plan. A failed plan
or show leaves no current layout. It is never read as an input to inference or
optimization.

Each generated placement explanation declares whether at least one normalized
pressure match is satisfied (`pressure_evidence`) or it resulted only from the
exact balance and stable tie-break stages (`balance_and_tie_break_only`). This is
derived publication metadata, never an authored product, relation, or law.

Acceptance ascends from closed schema and ledger checks, through inference-law
and exhaustive-oracle checks, to real-schedule and product-invariant evidence.
Generated schedules, diagnostics, and proof traces are projections; they never
become canonical input.
