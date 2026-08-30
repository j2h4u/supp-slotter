# Domain model

## Product invariant

Every published layout is the globally optimal result of the canonical fact
model. A result is either `Optimal`, with a proved layout, or `Indeterminate`,
with no layout.

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
pressure identity `(item_id, dimension, value)`. Sources, quotations,
components, and proof paths contribute provenance only; they do not multiply a
pressure. Opposing values for one item and dimension produce `Indeterminate`.

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

## Migration ledger

[The migration receipt](migrations/legacy-atom-ledger.yaml) is a compact,
immutable shape-and-hash closure record for the completed scheduling migration.
Its historical generator is retired; it neither reconstructs legacy data nor
authorizes derived placements or other stored scheduling answers.

## Runtime boundary and acceptance

The ontology owns fact types, roles, applicability, universal laws, anchors,
pressure identities, and objective stages. Python provides generic loading,
validation, inference, exact optimization, proofs, and rendering. A conforming
runtime must be able to observe those inputs and reproduce the same result.

Online commands load the compact closure receipt, `runtime-lock.json`; it
declares the nine executable outputs only. The formal ontology gate recompiles
authored sources and verifies the full artifact set separately. A current
`schedule.yaml` is a revocable layout lease: plan invalidates it before work,
and `show` suppresses it after a failed plan. It is never an input to inference
or optimization.

Each generated placement explanation declares whether at least one normalized
pressure match is satisfied (`pressure_evidence`) or it resulted only from the
exact balance and stable tie-break stages (`balance_and_tie_break_only`). This is
derived publication metadata, never an authored product, relation, or law.

Acceptance ascends from closed schema and ledger checks, through inference-law
and exhaustive-oracle checks, to real-schedule and product-invariant evidence.
Generated schedules, diagnostics, and proof traces are projections; they never
become canonical input.
