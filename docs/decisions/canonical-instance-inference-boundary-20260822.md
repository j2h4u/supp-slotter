# Canonical Instance and Inference Boundary — 2026-08-22

## Status

**Accepted.** The living contract is [the domain model](../domain-model.md).

## Decision

Scheduler-consumable input is restricted to six typed canonical fact families:
`FoodEffect`, `AcuteAlertnessEffect`, `AcuteSleepEffect`,
`PreExercisePerformanceEffect`, `PostExerciseRecoveryEffect`, and
`ProductFoodInstruction`. Every fact
has typed subject and applicability roles plus evidence provenance.

`stacks.yaml` selects scenario items and domains. Pillbox data supplies
unbounded logical intake groups with independent optional meal, circadian, and
exercise anchors. Labels, identifiers, and chronology do not create biological
meaning.

Universal laws derive a set of normalized unary pressures
`(item_id, dimension, value)`. Provenance is retained on the proof node without
changing pressure identity or objective value. Conflicting values in the same
dimension yield layout-free `Indeterminate`.

The optimizer considers all feasible layouts and first maximizes satisfied
unique pressures, then minimizes exact integer squared slot loads, and finally
uses the stable item-ID and `(slot.order, slot_id)` assignment tuple. Only a
proved global optimum is `Optimal`; every other outcome is layout-free
`Indeterminate`.

The [migration receipt](../migrations/legacy-atom-ledger.yaml) is the immutable
closure record for the completed transition. It preserves the fixed closure
commit and does not encode a scheduling result; its historical generator is
retired.

## Consequences

The ontology exposes the complete portable semantic contract; Python executes
generic validation, inference, optimization, proof handling, and rendering.
Generated schedules, diagnostics, and proof traces are outputs and never
canonical evidence. Evidence and model decisions require their paired V-right
acceptance: closed schemas and ledger, complete law checks and normalization,
then exhaustive-oracle and product-invariant validation.
