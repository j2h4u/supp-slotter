# Ontology Facts Authoring Guide

This is the current guide for admitting canonical scheduling facts. It is
facts-only and is not a queue, coverage checklist, grooming workflow, or
source of stored scheduling answers.

## Closed fact boundary

The runtime accepts only these six typed fact families and their currently
admitted values:

| Family | Admitted values | Universal law target |
|---|---|---|
| `FoodEffect` | `bioavailability_increases`, `bioavailability_decreases`, `tolerability_improves`, `tolerability_worsens` | `meal_context=with_food` or `without_food` |
| `AcuteAlertnessEffect` | `acute_alertness_increases` | `circadian_anchor=wake` |
| `AcuteSleepEffect` | `onset_latency_decreases`, `continuity_improves` | `circadian_anchor=sleep` |
| `PreExercisePerformanceEffect` | `performance_improves` | `exercise_anchor=before` |
| `PostExerciseRecoveryEffect` | `recovery_improves` | `exercise_anchor=after` |
| `ProductFoodInstruction` | `take_with_food` | `meal_context=with_food` |

Each fact has one typed subject, exact applicability (a reusable substance or
composition role, or the product intake item where the product family
requires it), and evidence provenance. A universal law maps one closed family
and value to one dimension and value. Laws are identity-free: they do not name
products, slots, desired placements, actions, explanations, or weights.

## Authoring procedure

1. Confirm the claim is a world fact or relation, not a desired placement,
   pair preference, action, explanation, candidate assessment, or inferred
   result.
2. Reuse the existing typed identity and exact composition role where one
   exists. Preserve source and provenance on the fact; do not copy evidence
   into a generic card field.
3. Admit only a value in the table above and add or reuse its universal law.
   Product-specific food instructions target the product intake item directly;
   they do not transfer to component roles.
4. If the claim needs a new family, value, dimension, applicability kind, or
   law shape, stop. Write and obtain a new accepted V-left contract before
   changing ontology sources or runtime code. Do not extend this vocabulary
   by convention.
5. Run the applicable `just` ontology/runtime checks after an approved source
   change. Generated schedules and explanations are derived outputs, never
   authoring inputs.

## Explicit exclusions

- Do not author generic `notes` as a product, substance, or component surface.
  Route identity, composition, and provenance to their typed destinations;
  leave unresolved research in offline evidence or gitignored
  `docs/private/`, outside runtime inputs.
- Do not create scheduling traits, slot-blocking constraints, pairwise
  placement rules, capacity or physical-fit semantics, dose/frequency/clock
  semantics, candidate or coverage records, grooming state, dashboards, or
  numeric evidence weights as canonical facts.
- Passive relations and review memberships remain outside inference unless a
  future accepted V-left contract makes a typed fact/law path for them.
- Absence of a fact means no derived pressure. Opposing values on one item and
  dimension produce layout-free `Indeterminate`; they are not reconciled by
  weighting or compromise.

Historical adjudications and migration receipts may explain why a fact was
admitted or omitted, but they are offline provenance only and cannot authorize
new runtime inputs.
