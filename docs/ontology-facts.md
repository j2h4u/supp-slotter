# Ontology Stress-Test Facts

This document keeps user-supplied supplement facts that stress-test the current
ontology. Its job is to show whether a fact can be expressed declaratively with
existing substance cards, traits, and relations, or whether the ontology needs a
small improvement.

This is not medical advice or an evidence review.

The preferred modeling order is KISS:

1. Use existing substance cards when possible.
2. Use `relations` when a fact is substance-to-substance.
3. Use traits only when the planner needs a reusable scheduling rule.
4. Do not create abstract mechanism entities such as `vitamin_k_cellular_uptake`.

## Fit Classes

- **Fits now**: can be encoded with existing `relations`, traits, notes, or
  `unmatched_concerns`.
- **Fits with judgement**: current model can represent it, but the exact relation
  type depends on the practical behavior we want from the planner.
- **Model pressure**: the fact exposes a missing distinction or a possible future
  model improvement.

## Current Fact Mapping

| Fact | Current expression | Ontology fit |
|---|---|---|
| Long-term zinc and copper status should be reviewed together. | `balance` on zinc and copper cards. | Fits now; `plan`/`doctor` can warn when one side is active and the other is absent. |
| Zinc and copper can compete when co-administered. | `competes` on zinc and copper cards. | Fits now; planner avoids co-slotting. |
| NAC is supported by selenium and molybdenum in the Doctor's Best formula context. | `supported_by` on NAC; `supports` on selenium and molybdenum forms. | Fits now; `plan`/`doctor` can warn when NAC is active without its declared supporters. |
| Magnesium supports calcium homeostasis. | `supports` on magnesium glycinate; `supported_by` on calcium. | Fits now. |
| Vitamin E can support vitamin A bioavailability/absorption. | `supports` from vitamin E tocopherol to vitamin A. | Fits now. |
| Vitamin E helps protect omega-3 PUFA from lipid peroxidation. | `supports` from vitamin E tocopherol to EPA. | Fits now. |
| High-dose vitamin E can antagonize vitamin K-dependent clotting factors. | `antagonizes` on vitamin E; `antagonized_by` on K1 and K2. | Fits now as review relation. |
| Vitamin E and vitamin K compete; separate by at least 2 hours or different meals. | `competes` if planner separation is desired; `antagonizes` if review-only functional opposition is desired. | Fits with judgement. |
| Tocopherols and tocotrienols compete; separate them. | `competes` between vitamin E tocopherol and vitamin E tocotrienols. | Fits now. |
| Calcium and iron compete; separate 2-4 hours, especially when calcium is 300-500 mg or more. | `competes`; dose threshold stays in `reason` because the planner does not calculate dose. | Fits now with dose limitation. |
| Calcium and zinc compete; separate 2-4 hours. | `competes`. | Fits now. |
| Calcium and magnesium should be separated by at least 2 hours at high doses. | `competes` only if ignoring dose threshold is acceptable; otherwise notes/review. | Model pressure: no dose model. |
| Calcium and vitamin D are synergistic; vitamin D improves calcium absorption. | `supports` from vitamin D to calcium and `supported_by` on calcium. | Fits now. |
| Vitamins A and E may reduce vitamin K cellular uptake/function; separate 2-3 hours. | `antagonizes` for functional opposition; `competes` only if slot separation is required. | Fits with judgement. |
| Ashwagandha may increase thyroid hormones and cause thyrotoxic symptoms such as sinus tachycardia. | `risk:manual_review` plus `unmatched_concerns` until thyroid-specific risk is justified. | Fits now. |
| L-Lysine and L-arginine compete for transport through the BBB and mitochondrial membrane. | `competes`, with transport mechanism in `reason`. | Fits now after broadening `competes`. |
| High-dose L-lysine can reduce L-arginine uptake. | Same lysine/arginine `competes` relation, with dose context in `reason`. | Fits now with dose limitation. |
| Amino acids are often better on an empty stomach because food amino acids compete. | `intake:empty_preferred` on concrete amino-acid substance cards. | Fits now. |
| Beta-alanine is used pre-workout in this stack context. | `activity:pre_workout` on the beta-alanine substance card. | Fits now. |
| L-Arginine, L-ornithine, and L-lysine may synergize around growth hormone. | `supports`/`supported_by` if reviewing each substance; `prefer_with` only if planner co-location is desired. | Fits with judgement. |
| B6 is a cofactor for amino-acid transamination/deamination. | Potential `supports` from concrete B6 forms to amino acids, but broad support should be added only if useful for review. | Model pressure: broad ubiquitous cofactors can create noisy relations. |
| Vitamin C supports collagen synthesis through L-lysine/L-proline hydroxylation. | `supports` from vitamin C to L-lysine/L-proline collagen context, or a goal-cluster note. | Fits with judgement. |
| Zinc is a cofactor for many amino-acid metabolism enzymes. | Notes/unmatched concern unless a specific target matters. | Model pressure: broad ubiquitous cofactors can create noisy relations. |
| Glycine, beta-alanine, and taurine compete at glycine receptors. | `competes`, with receptor context in `reason`; `antagonizes` only if functional opposition matters more than slot separation. | Fits with judgement. |
| Vitamin E forms plus astaxanthin may synergize around keratinization / skin barrier. | `supports`/`supported_by` if skin-barrier review becomes a concrete goal. | Fits with judgement. |

## Substances Added From These Facts

- L-Arginine
- Ashwagandha
- Beta-alanine
- Iron
- L-Lysine
- L-Ornithine
- L-Proline
- Taurine
- Vitamin E, tocotrienols

`L-` is used in substance names for chiral amino acids. Beta-alanine, glycine,
and taurine are not forced into `L-` naming because that would add chemical noise.

## Current Takeaways

- Broad `competes` is better than a mechanism-specific competition type because
  planner behavior is the same: avoid co-slotting. Mechanism details belong in
  `reason`.
- Dose thresholds can be documented but not computed yet.
- Ubiquitous cofactors are the main risk for relation noise; add them only when
  they create a useful review warning or goal explanation.
- The model does not need abstract mechanism entities for these facts.

## Ontology Improvement Queue

Use this section for model-grooming items discovered from the facts above. Each
item should point back to concrete facts, not abstract taxonomy desires.

| Pressure | Current handling | Possible improvement |
|---|---|---|
| Dose-dependent competition, for example calcium/magnesium or high-dose lysine/arginine. | Keep dose thresholds in `reason`; planner does not calculate dose. | Add dose modeling only if product amounts become reliable and scheduler decisions need it. |
| Broad cofactors, for example B6 or zinc across many amino-acid pathways. | Avoid many noisy `supports` edges unless a target-specific warning or goal explanation is useful. | Add relations selectively, or introduce goal-level explanatory support before adding broad graph edges. |
| Functional opposition versus slot separation, for example vitamin A/E/K or receptor competition. | Use `antagonizes` for review-only opposition; use `competes` only when co-slotting should be avoided. | Keep both relation types; do not add another type until a concrete fact cannot choose between them. |
| Organ/system effects, for example thyroid, skin barrier, collagen, respiratory/mucolytic support. | Keep in notes, goals, or `unmatched_concerns` unless planner behavior is clear. | Add a trait only when it produces a useful warning or scheduling effect. |

## Encoding Policy

Add relations when the fact has a clear practical consequence:

- Use `competes` only when co-slotting should be avoided.
- Use `supports`/`supported_by` when absence of the supporter should produce a
  useful review warning.
- Use `antagonizes`/`antagonized_by` for functional opposition that should be
  visible in review but does not yet need slot placement behavior.
- Keep dose thresholds inside `reason` until the project has an actual dose model.
