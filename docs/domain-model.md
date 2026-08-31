# Domain model

## Product invariant

Every published layout is the globally optimal result of the canonical fact
model. A result is either `Optimal`, with a proved layout, or `Indeterminate`,
with no layout.

The canonical result is determined by typed world facts and universal laws.
Absence of a fact means absence of a derived pressure, not a runtime
completeness failure. A balance-and-tie-break-only placement is therefore valid
when no admitted pressure applies. This contract is governed by the
[canonical instance and inference boundary](decisions/canonical-instance-inference-boundary-20260822.md)
and the accepted
[runtime simplification decision](decisions/actionable-scheduling-runtime-simplification-20260831.md).

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

## Inference boundary

Every admitted directed claim is a typed world fact with exact subject and
applicability, an evidence/provenance path, and one matching universal law.
The law derives a normalized pressure `(item_id, dimension, value)`. Historical
semantic adjudications and migration receipts may document why a fact was
admitted, but they are offline provenance only and are never runtime inputs.

An admitted pressure, including one supported by weak or anecdotal evidence,
outranks balance. Evidence has no numeric weight and cannot multiply, cancel,
average, or weaken a pressure. A future fact family or law requires a new
accepted V-left contract; no generic relation or open-vocabulary inference is
implied here.

### Contradiction and passive-relation boundary

Opposing derived values for the same item and dimension are a direct
contradiction. The canonical boundary returns layout-free `Indeterminate`; it
must not choose, cancel, average, weight, or balance around the conflict.

Pairwise, supports, balance, contextual, and other passive relations have no
scheduling effect unless a future accepted typed world fact and universal law
derive a pressure. Desired co-location or separation, preferences, placements,
actions, and their UI prose are stored answers and cannot be canonical inputs.
The published trace does not enumerate passive-relation non-effects.

### Generic-note removal boundary

Generic authored `notes` are not a canonical product, substance, or component
surface. The one-time migration mapped existing spans to typed identity,
composition, provenance, or an explicit discard reason. After cutover, the
canonical schema rejects `notes`; there is no notes parser, NLP/keyword
heuristic, compatibility field, or migration runtime. Migration receipts remain
historical provenance and do not restore a runtime input.

### V-left to V-right acceptance matrix

No lower cluster starts while its upper contract is missing or disputed. After
implementation, acceptance ascends through the paired evidence in this order.

| V level | V-left contract | V-right acceptance evidence |
| --- | --- | --- |
| 1. Product invariant | A real active-shelf layout materially follows formal world facts. | Real active-shelf trace proves every placement and the exact objective. |
| 2. Ontology/admission | Every directed claim compiles only through a typed fact and universal-law path. | Compiler and inference proofs establish applicability, provenance, dimension, value, and law; passive relations have no admission path. |
| 3. Objective | Every admitted pressure outranks balance while exact global optimum and stable tie-break remain unchanged. | Metamorphic and exhaustive optimizer witnesses prove pressure-before-balance and exactness. |
| 4. Publication | Contradictions and any inability to prove the exact result produce layout-free `Indeterminate`; absent facts do not. | Fail-closed contradiction/resource/proof witnesses and derived balance-only explanations. |
| 5. Canonical schema | Generic notes and stored scheduling answers cannot enter canonical inputs. | Closed schemas and migration receipt prove typed destinations or explicit discard, with no notes compatibility surface. |

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
