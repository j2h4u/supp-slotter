# Ontology Pressure Points

This document keeps only current supplement facts that do not yet have a clear
home in the ontology. It is not a history log.

Remove an entry as soon as it has a clear representation in substance cards,
traits, dashboards, or `data/relations.yaml`. Past changes remain in git.

This is not medical advice, an evidence review, or a source of medical truth.
Facts here are prompts for checking whether the current ontology can represent
something without inventing unnecessary structure.

Preferred modeling order:

1. Use existing substance cards when possible.
2. Use `data/relations.yaml` when a fact is substance-to-substance.
3. Use reviewer facts (`knowledge.is`, `knowledge.effect`, `knowledge.risk`,
   `knowledge.pathway`) when the fact is reusable across cards or dashboard
   projections.
4. Use scheduling traits only when the planner needs a reusable slot-placement
   rule.
5. Do not create abstract mechanism entities such as
   `vitamin_k_cellular_uptake`.

## Open Pressure Points

| Fact | Current fit | Next useful action |
|---|---|---|
| Calcium and magnesium separation is dose-dependent. | `competes` would overstate the rule without a dose model; notes or `review_with` are safer unless typical-dose co-slotting should be blocked. | Keep thresholds in relation `reason` or notes. Add dose modeling only if scheduler decisions need reliable product amounts. |
| Metformin may matter for lactate/exercise-tolerance review. | The B12-status relation is already modeled; broader medication-performance context is not first-class. | Keep broader context in private user notes or `concerns` until repeated cases need structure. |

## Current Boundaries

- Dose thresholds may be documented in `reason`, `action`, notes, or
  `concerns`; the planner does not calculate dose, ratio, or adequacy.
- Use `competes` only when co-slotting should be avoided at typical doses.
- Use `supports` when absence of the supporter should produce a useful review
  warning.
- Use `review_with` for pairings that should produce a schedule warning when
  both endpoints are active: functional opposition, additive pharmacology,
  nutrient-status effects, medication interactions, or practical separation
  advice that is dose-dependent and cannot be computed by the planner.
- Ubiquitous cofactors should not become noisy `supports` edges. Add them only
  when the target-specific warning or dashboard explanation is useful.
- Encode a dashboard cluster when the fact is a useful review goal, not as a
  generic supplement-knowledge bucket.
- Prefer dashboard membership from reusable semantic facts (`is:`, `effect:`,
  `risk:`, `pathway:`). Use `knowledge.context: <slug>` only for explicit
  curated membership.
- Keep personal health history, actual intake history, adherence, reactions,
  and operator-specific hypotheses out of tracked ontology files; use
  gitignored `docs/private/` when needed.
