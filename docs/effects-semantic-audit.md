# Effects Semantic Audit

Date: 2026-05-20

Scope: `data/traits/effects.yaml` after the trait-registry split.

Follow-up status: two safe cleanup batches from this audit have been applied.
Class/source/formulation facts were removed from `effect:`, obvious
context/support pairs were merged, the melatonin sleep-onset pair was collapsed,
and high-signal definitions were enriched.

## Summary

`effect:` is structurally clean but semantically weak.

Baseline before the first cleanup batch:

- 138 registered effect slugs.
- 138/138 are used by substance cards.
- 0 unused effect slugs.
- 72/138 are used by exactly one substance.
- 138/138 descriptions and `applies_when` fields are generated placeholders.
- Only one effect currently drives dashboard membership: `cholinergic_support`.
- 90/138 slugs end in `_context`, which blurs `knowledge.effect` with dashboard
  `knowledge.context`.

Current state after the second cleanup batch:

- 127 registered effect slugs.
- 127/127 are used by substance cards.
- 0 unused effect slugs.
- 62/127 are used by exactly one substance.
- 94/127 descriptions still use generated placeholders.
- The same product concern remains: most effects are still external-agent hints,
  not dashboard or protocol machinery.

Do not split `effects.yaml` physically now. The current bottleneck is not file
size; it is low decision leverage and unclear semantics.

## Desired Boundary

Use `effect:` for reusable substance-level pharmacologic or functional facts.

Use `is:` as a nominal taxonomy: nouns or noun phrases that answer "what kind
of thing is this?" rather than "what does this do?" Borderline category nouns
such as `adaptogen`, `antioxidant`, `ergogenic`, and `nootropic` are acceptable
only as class labels; their concrete actions belong in `effect:`, `pathway:`,
`risk:`, or dashboards.

Use better homes for other fact types:

- `is:` for intrinsic class.
- `pathway:` for biochemical pathway membership.
- `risk:` for safety or interaction flags.
- `context:` / dashboards for review-cluster membership.
- product or form metadata for label/source/formulation facts.
- `concerns` for unresolved high-signal notes that are not modeled yet.

## Applied Safe Cleanup

These changes were high-confidence because they preserved the existing model
boundary while removing duplicated or ambiguous slugs.

| Candidate | Recommendation | Why |
|---|---|---|
| `ergogenic` | Removed from `effect:` usage, kept `is:ergogenic` | Direct class duplicate; only Creatine used it as an effect. |
| `omega3_source` | Removed from `effect:` usage, kept `is:omega3` | Source/class fact duplicated EPA/DHA/Krill Oil class membership. |
| `fatty_acid_metabolism_context` | Merged into `fatty_acid_metabolism_support` | Same stem; B7/B5 usage indicates one reusable axis. |
| `immune_function_context` | Merged into `immune_function_support` | Zinc forms and Vitamin E now share one reusable axis. |
| `wound_healing_context` | Merged into `wound_healing_support` | Zinc forms now share one reusable axis. |
| `sleep_onset_context` + `sleep_timing_support` | Collapsed into `sleep_onset_support` | Same card, same practical meaning. |
| `ala_source_context` | Removed from `effect:` usage | Flaxseed's ALA-source fact is preserved in aliases and notes; it is not an effect. |
| `food_matrix_context` + `phytonutrient_blend_context` | Removed from `effect:` usage | The Orchard/Garden blend is a proprietary label-backed botanical component; the blend/source fact belongs in notes. |
| `vitamin_c_food_matrix_context` | Removed from `effect:` usage | Acerola already keeps botanical/antioxidant facts plus label notes; the food-matrix phrase is not a separate effect. |
| `methylxanthine_context` | Removed from `effect:` usage | Theobromine's methylxanthine identity is preserved in notes; active review remains stimulant and vascular tone. |
| generated effect descriptions | Replaced for high-signal effects first | Registry cannot guide agents while all entries say the same thing. |

## Needs Decision

These change ontology semantics and should not be mass-applied without a policy.

| Topic | Decision Needed |
|---|---|
| `_context` suffix | Decide whether new `effect:*_context` slugs are allowed. Recommended default: no, unless the slug is a real reusable effect and not dashboard membership. |
| `_support` vs `_context` | Either define the difference or normalize obvious pairs. |
| broad axes | Decide whether `antioxidant_context`, `bone_mineral_metabolism_support`, `energy_production_support`, `glucose_metabolism_context`, `nerve_muscle_function` are effect facts, dashboards, or pathways. |
| single-use policy | Allow single-use effects when they name a distinctive action; reject them when they restate a label, source, or broad wellness claim. |
| dashboard projection | Decide which dashboards should derive from `effect:` rather than curated `context:`. |
| review output | Decide whether `planner review` should show an effect index or only surface effects through dashboards. |

## Continued Audit: `is:` / `effect:` Boundary

Current exact overlap between `is:` and `effect:` slugs: none.

The `is:` registry is now documented as nominal taxonomy. The class labels
`adaptogen`, `antioxidant`, `ergogenic`, and `nootropic` are allowed only as
category nouns. Their concrete actions belong elsewhere:

- `ergogenic` as class, not `effect:ergogenic`;
- `nootropic` as class, not a synonym for cholinergic, neurotrophic, memory, or
  alertness effects;
- `adaptogen` as category, not a generic cortisol/stress effect;
- `antioxidant` as class, while specific redox/cofactor/lipid-antioxidant facts
  may remain in `effect:` or `pathway:`.

Remaining lexical overlaps are not automatically wrong, but they should be
reviewed with the boundary test:

| Candidate | Current Assessment |
|---|---|
| `antioxidant_context` | Needs decision. It overlaps with `is:antioxidant`, but current usage also covers carotenoids/flavonoids that are not consistently tagged `is:antioxidant`. |
| `digestive_enzyme_context` | Probably keep. It differentiates digestive enzymes from systemic enzymes such as nattokinase. |
| `bone_mineral_metabolism_support` | Probably keep. It cuts across minerals plus vitamins D/K and is a functional review axis, not a class. |
| `electrolyte_adjacent_context` | Needs decision. Single-use Taurine fact; may be useful but the name is vague. |
| `hormone_vitamin_d_context` | Needs decision. Single-use Boron fact; may be better as a dashboard/pathway note if reused. |
| source/class/formulation slugs | Resolved for the obvious current cases. `ala_source_context`, `food_matrix_context`, `phytonutrient_blend_context`, `vitamin_c_food_matrix_context`, and `methylxanthine_context` were removed from `effect:` because their better home already existed in notes, aliases, or class facts. |

## Keep Stable

Do not touch these casually:

- `cholinergic_support`: used by `Cholinergic Load` dashboard.
- `vasodilator`: useful shared effect across citrulline/tadalafil.
- `pde5_inhibition`: precise mechanism for tadalafil.
- `fibrinolytic`: precise mechanism for nattokinase.
- `platelet_aggregation_modulation`: useful omega-3/bleeding-load fact, though
  it may later connect to risk dashboards.
- `mucolytic_context`, `urinary_adhesion_context`, `carnosine_buffer_context`,
  `catecholamine_precursor_context`, `neurotrophic_support`: justified
  distinctive single-use or narrow mechanisms.

## Candidate Dashboard Connections

Enrich existing dashboards before adding new ones.

| Dashboard | Candidate effect facts |
|---|---|
| Bleeding Load | `fibrinolytic`, `platelet_aggregation_modulation`, `pathway:omega3_eicosanoid`, `blood_clotting_context` |
| Hypotensive Load / Vascular Health | `vasodilator`, `nitric_oxide_support`, `pde5_inhibition`, `blood_pressure_context` |
| Methylation Support | `homocysteine_metabolism_support`, `dna_synthesis_support`, `red_blood_cell_support` |
| Mitochondrial Health | `energy_production_support`, `redox_metabolism_support`, `electron_transport_support`, `mitochondrial_fatty_acid_transport`, `phosphocreatine_support` |
| Sleep Recovery | `sleep_context`, `sleep_onset_support`, `calming_context` |

## Product Risk

The largest product risk is that effect slugs look authoritative while their
definitions do not explain what decision changes. A smart external agent can
overread vague slugs such as `cell_signaling_context`,
`nutrient_metabolism_support`, or `glucose_metabolism_context`.

The next improvement should make effect definitions more operational:

- what the fact means;
- when to apply it;
- when not to apply it;
- whether it is a dashboard axis, risk-load contributor, benefit-coverage fact,
  or mechanism note.

## Suggested Guardrails

- Add a non-blocking report for same-stem or same-usage effect overlaps.
- Add a registry-quality test that prevents generated placeholder descriptions
  from being introduced for new effect slugs.
- Consider a policy test for new `effect:*_context` slugs once the suffix rule is
  decided.

## Recommended Next Batch

1. Decide the global suffix rule for `_context` inside `effect:`.
2. Continue replacing generated placeholders, prioritizing reused effects and
   any single-use effect that names a distinctive action.
3. Decide whether broad axes such as `antioxidant_context`,
   `bone_mineral_metabolism_support`, `energy_production_support`, and
   `glucose_metabolism_context` stay as effect facts or become dashboard/pathway
   projections.
4. Connect high-signal effects to existing dashboards where the membership
   semantics are clear.
5. Add a non-blocking same-stem/same-usage report if more effect merges are
   expected.
