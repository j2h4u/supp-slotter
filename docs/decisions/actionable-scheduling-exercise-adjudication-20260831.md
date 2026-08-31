# Exercise Candidate Adjudication — 2026-08-31

## Status

**Accepted semantic adjudication.** This record applies the
[actionable-scheduling knowledge coverage boundary](actionable-scheduling-knowledge-coverage-boundary-20260831.md), the governing
[canonical-instance inference boundary](canonical-instance-inference-boundary-20260822.md), and the living
[domain model](../domain-model.md). It is a V-left decision record only: it
does not itself add a card field, canonical fact, law, schedule, certificate,
or runtime behavior.

## Scope and decision rule

The active training products are `prd_20bf2df267`, `prd_cfce0b36b6`,
`prd_2ca842627a`, and `prd_0e92bc1674`. Each candidate below is assigned
exactly one closed disposition. Candidate IDs are established here because the
current repository has no candidate/disposition catalog from which to reuse an
ID.

An exercise context, training-stack membership, product name, old schedule
trait, passive relation, or recovery outcome alone is not an exercise-anchor
direction. A directed claim is admissible only when it has a typed
subject/applicability, evidence provenance, and one of the existing universal
law paths. Once admitted, a weak, mechanistic, or anecdotal direction is one
unweighted pressure and outranks balance; evidence strength is provenance, not
an objective weight.

## Candidate dispositions

| Candidate ID | Exact applicability | Disposition | Decision |
| --- | --- | --- | --- |
| `cand_exercise_lclt_cmp_prd_0e92bc1674__sub_5bd641c116` | `cmp_prd_0e92bc1674__sub_5bd641c116` | `unresolved_without_direction` | No canonical fact is admitted. |
| `cand_exercise_creatine_cmp_prd_2ca842627a__sub_9c0908e7f7` | `cmp_prd_2ca842627a__sub_9c0908e7f7` | `neutral` | No canonical fact is admitted. |
| `cand_exercise_citrulline_cmp_prd_cfce0b36b6__sub_3918fe347e` | `cmp_prd_cfce0b36b6__sub_3918fe347e` | `pressure` | Admit the pre-exercise performance fact below. |
| `cand_exercise_electrolyte_sodium_cmp_prd_20bf2df267__sub_4j9fttkil9` | `cmp_prd_20bf2df267__sub_4j9fttkil9` | `unresolved_without_direction` | No canonical fact is admitted. |
| `cand_exercise_electrolyte_potassium_cmp_prd_20bf2df267__sub_f7780f899b` | `cmp_prd_20bf2df267__sub_f7780f899b` | `unresolved_without_direction` | No canonical fact is admitted. |
| `cand_exercise_electrolyte_magnesium_cmp_prd_20bf2df267__sub_fhl7c4skmf` | `cmp_prd_20bf2df267__sub_fhl7c4skmf` | `unresolved_without_direction` | No canonical fact is admitted. |
| `cand_exercise_electrolyte_calcium_dcp_cmp_prd_20bf2df267__sub_iqjdo9gvbv` | `cmp_prd_20bf2df267__sub_iqjdo9gvbv` | `unresolved_without_direction` | No canonical fact is admitted. |
| `cand_exercise_electrolyte_calcium_lactate_cmp_prd_20bf2df267__sub_p5qxdnxu9e` | `cmp_prd_20bf2df267__sub_p5qxdnxu9e` | `unresolved_without_direction` | No canonical fact is admitted. |

## Admitted citrulline fact and law path

The admitted fact is a world-fact assertion, not a desired slot, treatment
instruction, dose, weight, action, or inferred result.

```yaml
id: fact_pre_exercise_performance_prd_cfce0b36b6_sub_3918fe347e
subject:
  composition_role: cmp_prd_cfce0b36b6__sub_3918fe347e
applicability:
  composition_role: cmp_prd_cfce0b36b6__sub_3918fe347e
value: performance_improves
provenance:
  - source: src_pubmed_17953788
    locator: https://pubmed.ncbi.nlm.nih.gov/17953788/
  - source: src_pubmed_39662304
    locator: https://pubmed.ncbi.nlm.nih.gov/39662304/
  - source: src_pmc_13304508
    locator: https://pmc.ncbi.nlm.nih.gov/articles/PMC13304508/
```

`law_pre_exercise_performance_improves` universally normalizes this fact to the
single pressure identity
`(prd_cfce0b36b6, exercise_anchor, before)`. The law names neither a product
nor a slot. It derives an anchor pressure only; the exact optimizer remains the
sole source of a layout.

The supporting evidence is an admitted low-confidence direction and
applicability is limited: the active product is an unbranded 5 g
citrulline-malate component with unresolved citrulline:malate ratio, while the
acute evidence includes known-ratio or pure L-citrulline interventions. The
canonical fact retains the exact source provenance above; the confidence and
applicability qualification belongs to this adjudication record, not a new fact
field or objective weight. The limitation does not turn an admitted directed
hypothesis into balance or a lesser-weighted pressure. The evidence does not
admit an opposing `after` fact, so it does not create a
same-item/same-dimension contradiction.

## Reasons for non-pressure dispositions

### L-Carnitine L-Tartrate

The active role has evidence that multiweek L-carnitine L-tartrate
supplementation can affect post-exercise recovery outcomes, including
[PMID 17313301](https://pubmed.ncbi.nlm.nih.gov/17313301/) and
[PMID 34684429](https://pubmed.ncbi.nlm.nih.gov/34684429/). This is an
exercise/recovery context, not evidence that *post-exercise use* improves
recovery for the exact active role. The product's prior evidence assessment
also found no direct pre-/post-exercise placement comparison and does not make
the studied protocols transferable to the active label exposure. The candidate
therefore remains `unresolved_without_direction`, rather than becoming a
`PostExerciseRecoveryEffect` or a neutral closure.

### Creatine monohydrate

The exact active form is well-supported as ergogenic, but the relevant outcome
is explained by chronic saturation and consistent use rather than by a
before-/after-exercise administration direction. The candidate is therefore an
assessed in-model `neutral`: there is no admitted
`PreExercisePerformanceEffect` or `PostExerciseRecoveryEffect`. The removed
legacy `any_workout` assertion is neither an admitted fact family nor a
universal-law path and is not evidence of direction.

### TiM electrolyte roles

Sodium, potassium, magnesium citrate, dicalcium phosphate, and calcium lactate
are genuine composition/world facts, but their exercise relevance depends on
conditions absent from the canonical model: for example duration, environment,
sweat, fluid, and individual loss. The topology exposes only `before` and
`after`; it does not represent the conditional hydration circumstances that
would be needed to turn those facts into a directed exercise claim. Each role
is consequently `unresolved_without_direction`, not a blanket `outside_model`
exclusion and not a pressure.

## Contradictions and exclusions

No opposing values for any one item and scheduling dimension are admitted in
this decision. Accordingly, it produces no direct contradiction and no
`Indeterminate` outcome on its own. No pairwise mechanism, co-location,
separation, preference, placement, weight, dosage, safety/treatment claim, or
semantic UI prose is admitted. Contextual memberships and passive relations
remain non-executable unless separately adjudicated into a minimal world fact
with a universal-law path.
