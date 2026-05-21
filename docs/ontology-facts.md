# Ontology Stress-Test Facts

This document keeps user-supplied supplement facts that still stress-test the
current ontology. Its job is to surface where the model needs judgement,
extension, or a deliberate decision — not to archive everything we have ever
encoded.

Once a fact has a clear home in `data/relations.yaml`, a dashboard cluster, or
a substance trait, it leaves this document. The source of truth for what is
modeled lives in those files and in `data/substances/*.yaml`; git history
preserves the trajectory. The **Decided: not encoding** section below keeps a
short trail of facts we deliberately chose not to model, so we don't re-debate
them.

This is not medical advice, an evidence review, or a source of medical truth.
Facts here are prompts for checking whether the current ontology can represent
them without inventing unnecessary structure.

The preferred modeling order is KISS:

1. Use existing substance cards when possible.
2. Use `relations` when a fact is substance-to-substance.
3. Use reviewer facts (`knowledge.is`, `knowledge.effect`, `knowledge.risk`,
   `knowledge.pathway`) when the fact is reusable across cards or dashboard
   projections.
4. Use scheduling traits only when the planner needs a reusable slot-placement
   rule.
5. Do not create abstract mechanism entities such as `vitamin_k_cellular_uptake`.

## Fit Classes

- **Fits with judgement**: current model can represent it, but the exact
  relation type or destination depends on the practical behavior we want from
  the planner.
- **Model pressure**: the fact exposes a missing distinction or a possible
  future model improvement.
- **Deferred**: the fact already fits the model, but encoding it now would not
  change planner behavior given the active stack; revisit when the relevant
  product becomes active or a co-located product appears.

## Open Facts

| Fact | Possible expression | Ontology fit | Notes |
|---|---|---|---|
| Calcium and magnesium should be separated by at least 2 hours at high doses. | `competes` only if ignoring the dose threshold is acceptable; otherwise notes/review. | Model pressure: no dose model. | Threshold goes into `reason` if encoded; defer until we decide whether the absorption case justifies blanket co-slot avoidance at typical doses. |
| Metformin can increase lactate context and may matter for exercise tolerance/performance review. | Notes or `concerns` (kind: model_gap); no current trait or relation expresses medication-to-performance context. | Model pressure: external medication effects and performance context are not first-class axes. | Add medication-specific modeling only if several active review warnings need the same behavior. |

## Decided: Not Encoding

Short trail to prevent re-debate. Each entry: the fact, the decision, and
where the fact lives now (if anywhere).

| Fact | Decision | Where it lives |
|---|---|---|
| Vitamin E and vitamin K compete; separate by 2 hours / different meals. | Use `antagonizes` only — review-warning is sufficient. Do not promote to `competes` until a dose model exists; the operator does not use mega-doses, so slot separation would always be overkill. ✓ `antagonizes` now emits `antagonizes_substance_present` when both endpoints are active. | `data/relations.yaml` `antagonizes`: Vit E → Vit K1, Vit E → Vit K2. |
| Vitamins A and E may reduce vitamin K cellular uptake/function; separate 2-3 hours. | Same policy as Vit E / Vit K above — `antagonizes` only. ✓ `antagonizes` now emits `antagonizes_substance_present` when both endpoints are active. | `data/relations.yaml` `antagonizes`: Vit A → Vit K1, Vit A → Vit K2 (Vit E → Vit K already encoded). |
| L-Arginine, L-ornithine, and L-lysine may synergize around growth hormone. | Park as dashboard membership, not a relation. The cluster is "useful coverage if pursued", not "absence-of-A warns about B". Use semantic `effect:` facts where possible and `knowledge.context: workout_performance` only for curated membership that is not reducible to a cleaner axis. | `data/dashboards/workout_performance.yaml` via `from_traits:`. |
| Vitamin C supports collagen synthesis through L-lysine/L-proline hydroxylation. | Encode as dashboard membership, not a `supports` relation. Connective-tissue review is a legitimate operator goal. Use `effect:` projections for collagen/connective-tissue facts and `knowledge.context: connective_tissue_support` only as explicit curated membership. | `data/dashboards/connective_tissue_support.yaml` via `from_traits:`. |
| Vitamin E forms plus astaxanthin may synergize around keratinization / skin barrier; skin review also benefits from vitamin C, zinc, omega-3, and MSM context. | Encode as `skin_support` dashboard membership, not a `supports` relation. This is broader than barrier-only review, but narrower than all connective-tissue support. Use semantic projections first and `knowledge.context: skin_support` only for curated membership. | `data/dashboards/skin_support.yaml` via `from_traits:`. |
| B6 is a cofactor for amino-acid transamination/deamination across many pathways. | Do not encode at all — broad ubiquitous cofactor. Stays as substance-card notes if needed. No `supports` edges, no dashboard. | Substance notes only. |
| Zinc is a cofactor for many amino-acid metabolism enzymes. | Same as B6 — broad ubiquitous cofactor. No edges, no dashboard. | Substance notes only. |
| Adaptogen × SSRI/SNRI/MAOI adverse-event interaction (e.g., Ashwagandha + escitalopram/sertraline/paroxetine reports per PMC10565488). | Defer concrete `antagonizes` encoding until any 5-HT-active medication enters the stack; the conditional trigger lives in the dashboard risk text and substance `concerns` (kind: safety). Cluster membership is projected from `risk: serotonergic_med_interaction` on relevant substance cards. | `data/dashboards/serotonergic_load.yaml` + Ashwagandha substance `concerns[kind=safety]`. |
| High-dose vitamin D (>60,000 IU/day chronic) atrial-fibrillation risk (review-level). | Skip permanently — user does not use mega-doses; threshold is orders of magnitude above any product in the stack. | Not encoded; relies on user-context memory rather than ontology. |
| Post-nicotine residual vascular fragility as a separate dashboard cluster. | Skip — user-context narrative, not an ontology axis. Existing `vascular_health` and `bleeding_load` dashboards already cover the relevant axes; a user-narrative dashboard would not change planner output. (`vasodilation_no_pathway` deleted in Phase 08 — strict subset of `vascular_health`.) | Memory only (`memory/user_health_vascular.md`). |

## Current Takeaways

- Broad `competes` is better than a mechanism-specific competition type because
  planner behavior is the same: avoid co-slotting. Mechanism details belong in
  `reason`.
- Dose thresholds can be documented but not computed yet.
- Ubiquitous cofactors are the main risk for relation noise; add them only when
  they create a useful review warning or dashboard explanation.
- The model does not need abstract mechanism entities for these facts.
- `antagonizes` is the right level for dose-dependent functional opposition:
  the planner emits an `antagonizes_substance_present` schedule warning when
  both endpoints are active, and the relation also appears in substance-card
  review output. Slot separation (`competes`) still requires a dose model the
  project does not have and does not want.

## Ontology Improvement Queue

Use this section for model-grooming items discovered from the facts above. Each
item should point back to concrete facts, not abstract taxonomy desires.

| Pressure | Current handling | Possible improvement |
|---|---|---|
| Dose-dependent competition, for example calcium/magnesium or high-dose lysine/arginine. | Keep dose thresholds in `reason`; planner does not calculate dose. | Add dose modeling only if product amounts become reliable and scheduler decisions need it. |
| Broad cofactors, for example B6 or zinc across many amino-acid pathways. | Avoid noisy `supports` edges and speculative dashboards; keep as substance notes. | Add relations selectively, or introduce a focused dashboard, only if a target-specific warning becomes useful. |
| Functional opposition versus slot separation, for example vitamin A/E/K or receptor competition. | Use `antagonizes` for opposition where both-endpoints-active warrants a schedule warning (`antagonizes_substance_present`); use `competes` only when co-slotting should be avoided at typical doses. Slot placement for antagonizes remains unchanged — the warning is informational. | Keep both relation types; do not add another type until a concrete fact cannot choose between them. |
| Organ/system effects, for example thyroid, skin barrier, collagen, respiratory/mucolytic support. | Encode as dashboard clusters when an operator review goal is stated; otherwise keep in notes or `concerns` (kind: model_gap). | Add a trait only when it produces a useful warning or scheduling effect. |
| External medication effects, for example metformin lowering B12 status or changing lactate context. | Represent concrete nutrient impact with `antagonizes`; keep broader medication/performance context in notes or `concerns` (kind: model_gap). | Add medication-specific modeling only if several active review warnings need the same behavior. |

## from_traits Semantics

`from_traits: { is: [antioxidant] }` is intensional — open-world: any future substance that acquires `is: antioxidant` automatically joins the cluster without editor intervention. `from_traits: { context: [foo] }` is extensional — closed curation: only substances explicitly tagged `knowledge.context: foo` are members. The choice of projection key encodes the operator's intent about future membership growth. Both forms are valid; mixing namespaces in one `from_traits` widens membership (union), never narrows it.

Resolution is union (logical OR) across the entire `from_traits` object. A substance is a member if there exists at least one (namespace, slug) pair in `from_traits` that matches the substance's per-namespace field. There is NO AND semantic across namespace groups.

## Decided: Not Solving

Short trail of design limitations we accept deliberately — to prevent re-debating them.

| Limitation | Decision | Mitigation |
|---|---|---|
| Substance renamed or repurposed but its `knowledge.context:` tag remains structurally valid (matches an existing `data/dashboards/<slug>.yaml`). No automatic detection is possible — a schema check cannot distinguish a stale tag from deliberate continued membership (rename-ghost risk). | Accept as known limitation. The risk is narrower now because dashboards should prefer semantic `is:` / `effect:` / `risk:` / `pathway:` projections and use `context:` only as explicit curated membership. | Operator hygiene + occasional review via `review-substance` output. `planner audit` surfaces empty dashboards but cannot distinguish stale membership from deliberate membership. |

## Encoding Policy

Add relations when the fact has a clear practical consequence:

- Use `competes` only when co-slotting should be avoided at typical doses.
- Use `supports` when absence of the supporter should produce a useful review
  warning.
- Use `antagonizes` for functional opposition that should produce a schedule
  warning when both endpoints are simultaneously active, or when the practical
  separation advice is dose-dependent and the planner cannot compute dose. The
  planner now emits an `antagonizes_substance_present` warning whenever both
  endpoints are active; slot placement is still unchanged (no forced separation).
- Use the optional `severity` field to mark exceptional relations: `critical`,
  `high`, `medium`, or `low`. Severity is orthogonal to relation type — any
  relation type may carry it. Bias toward leaving severity unset; mark only
  relations where the operator needs a triage signal above baseline. When set,
  severity flows through to the humanized warning output in `schedule.yaml`.
- Encode a dashboard cluster when the fact is a "cluster of usefulness" that
  matches a stated operator review goal — not as a generic supplement-knowledge
  bucket. Prefer membership from reusable semantic facts (`is:`, `effect:`,
  `risk:`, `pathway:`). Use `knowledge.context: <slug>` only for explicit
  curated membership; the dashboard yaml declares `from_traits:` as its
  projection rule, not an explicit member list.
- Keep dose thresholds inside `reason` until the project has an actual dose model.
