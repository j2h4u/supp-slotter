# Ontology Stress-Test Facts

This document keeps user-supplied supplement facts that stress-test the current
ontology. Its job is to show whether a fact can be expressed declaratively with
existing substance cards, traits, and relations, or whether the ontology needs a
small improvement.

This is not medical advice, an evidence review, or a source of medical truth.
Facts here are prompts for checking whether the current ontology can represent
them without inventing unnecessary structure.

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

## Encoding Status

- **Encoded active**: represented in cards and relevant to the currently active stack.
- **Encoded inactive**: represented in cards, but the relevant product/substance is currently inactive or absent from scheduled inventory.
- **Candidate**: useful fact, not fully encoded yet.
- **Model pressure**: intentionally kept as a test case for ontology grooming.

## Current Fact Mapping

| Fact | Current expression | Ontology fit | Status |
|---|---|---|---|
| Long-term zinc and copper status should be reviewed together. | `balance` in `data/relations.yaml` from `Zinc` to `Copper`. | Fits now; `plan`/`doctor` can warn when one side is active and the other is absent. | Encoded active |
| Zinc and copper can compete when co-administered. | `competes` in `data/relations.yaml` from `Zinc` to `Copper`. | Fits now; planner avoids co-slotting. | Encoded active |
| NAC is supported by selenium and molybdenum in the Doctor's Best formula context. | `supports` in `data/relations.yaml` from `Selenium` and `Molybdenum` to `N-Acetyl Cysteine`. | Fits now; `plan`/`doctor` can warn when NAC is active without its declared supporters. | Encoded inactive |
| Magnesium supports calcium homeostasis. | `supports` in `data/relations.yaml` from `Magnesium` to `Calcium`; this represents magnesium-level behavior, not a glycinate-specific claim. | Fits now. | Encoded active |
| Vitamin E can support vitamin A bioavailability/absorption. | `supports` in `data/relations.yaml` from `Vitamin E` to `Vitamin A`. | Fits now. | Encoded inactive |
| Vitamin E helps protect omega-3 PUFA from lipid peroxidation. | `supports` in `data/relations.yaml` from `Vitamin E` to `Eicosapentaenoic acid`. | Fits now. | Encoded active |
| High-dose vitamin E can antagonize vitamin K-dependent clotting factors. | `antagonizes` in `data/relations.yaml` from `Vitamin E` to `Vitamin K1` and `Vitamin K2`. | Fits now as review relation. | Encoded inactive |
| Vitamin E and vitamin K compete; separate by at least 2 hours or different meals. | `competes` if planner separation is desired; `antagonizes` if review-only functional opposition is desired. | Fits with judgement. | Candidate |
| Tocopherols and tocotrienols compete; separate them. | `competes` between vitamin E tocopherol and vitamin E tocotrienols if slot separation is desired. | Fits now. | Candidate |
| Calcium and iron compete; separate 2-4 hours, especially when calcium is 300-500 mg or more. | `competes`; dose threshold stays in `reason` because the planner does not calculate dose. | Fits now with dose limitation. | Candidate |
| Calcium and zinc compete; separate 2-4 hours. | `competes` if planner separation is desired. | Fits now. | Candidate |
| Calcium and magnesium should be separated by at least 2 hours at high doses. | `competes` only if ignoring dose threshold is acceptable; otherwise notes/review. | Model pressure: no dose model. | Model pressure |
| Calcium and vitamin D are synergistic; vitamin D improves calcium absorption. | `supports` from vitamin D to calcium if this review warning becomes useful. | Fits now. | Candidate |
| Vitamins A and E may reduce vitamin K cellular uptake/function; separate 2-3 hours. | `antagonizes` for functional opposition; `competes` only if slot separation is required. | Fits with judgement. | Candidate |
| Ashwagandha may increase thyroid hormones and cause thyrotoxic symptoms such as sinus tachycardia. | `risk:manual_review` plus `unmatched_concerns` until thyroid-specific risk is justified. | Fits now. | Encoded inactive |
| L-Lysine and L-arginine compete for transport through the BBB and mitochondrial membrane. | `competes`, with transport mechanism in `reason`. | Fits now after broadening `competes`. | Candidate |
| High-dose L-lysine can reduce L-arginine uptake. | Same lysine/arginine `competes` relation, with dose context in `reason`. | Fits now with dose limitation. | Candidate |
| Amino acids are often better on an empty stomach because food amino acids compete. | `intake:empty_preferred` on concrete amino-acid-like substance cards currently active in the stack, such as ALCAR, LCLT, and L-citrulline malate. | Fits now. | Encoded active |
| Beta-alanine is used pre-workout in this stack context. | `activity:pre_workout` on the beta-alanine substance card. | Fits now. | Encoded inactive |
| L-Arginine, L-ornithine, and L-lysine may synergize around growth hormone. | `supports` if reviewing each substance; `prefer_with` only if planner co-location is desired. | Fits with judgement. | Candidate |
| B6 is a cofactor for amino-acid transamination/deamination. | Potential `supports` from concrete B6 forms to amino acids, but broad support should be added only if useful for review. | Model pressure: broad ubiquitous cofactors can create noisy relations. | Model pressure |
| Vitamin C supports collagen synthesis through L-lysine/L-proline hydroxylation. | `supports` from vitamin C to L-lysine/L-proline collagen context, or a dashboard-cluster note. | Fits with judgement. | Candidate |
| Zinc is a cofactor for many amino-acid metabolism enzymes. | Notes/unmatched concern unless a specific target matters. | Model pressure: broad ubiquitous cofactors can create noisy relations. | Model pressure |
| Glycine, beta-alanine, and taurine compete at glycine receptors. | `competes`, with receptor context in `reason`; `antagonizes` only if functional opposition matters more than slot separation. | Fits with judgement. | Candidate |
| Vitamin E forms plus astaxanthin may synergize around keratinization / skin barrier. | `supports` if skin-barrier review becomes a concrete dashboard. | Fits with judgement. | Candidate |
| Long-term metformin can reduce vitamin B12 absorption/status, so B12 context should be reviewed when metformin is active. | `antagonizes` in `data/relations.yaml` from `Metformin` to `Vitamin B12`. | Fits now as review relation; it does not imply slot separation. | Encoded inactive |
| Metformin can increase lactate context and may matter for exercise tolerance/performance review. | Currently only suitable for notes or `unmatched_concerns`; no current trait or relation expresses medication-to-performance context. | Model pressure: external medication effects and performance context are not first-class axes. | Model pressure |

## Substances Added From These Facts

- L-Arginine
- Ashwagandha
- Beta-alanine
- Iron
- L-Lysine
- L-Ornithine
- L-Proline
- Taurine
- Metformin
- Vitamin E, tocotrienols

`L-` is used in substance names for chiral amino acids. Beta-alanine, glycine,
and taurine are not forced into `L-` naming because that would add chemical noise.

## Current Takeaways

- Broad `competes` is better than a mechanism-specific competition type because
  planner behavior is the same: avoid co-slotting. Mechanism details belong in
  `reason`.
- Dose thresholds can be documented but not computed yet.
- Ubiquitous cofactors are the main risk for relation noise; add them only when
  they create a useful review warning or dashboard explanation.
- The model does not need abstract mechanism entities for these facts.

## Ontology Improvement Queue

Use this section for model-grooming items discovered from the facts above. Each
item should point back to concrete facts, not abstract taxonomy desires.

| Pressure | Current handling | Possible improvement |
|---|---|---|
| Dose-dependent competition, for example calcium/magnesium or high-dose lysine/arginine. | Keep dose thresholds in `reason`; planner does not calculate dose. | Add dose modeling only if product amounts become reliable and scheduler decisions need it. |
| Broad cofactors, for example B6 or zinc across many amino-acid pathways. | Avoid many noisy `supports` edges unless a target-specific warning or dashboard explanation is useful. | Add relations selectively, or introduce dashboard-level explanatory support before adding broad graph edges. |
| Functional opposition versus slot separation, for example vitamin A/E/K or receptor competition. | Use `antagonizes` for review-only opposition; use `competes` only when co-slotting should be avoided. | Keep both relation types; do not add another type until a concrete fact cannot choose between them. |
| Organ/system effects, for example thyroid, skin barrier, collagen, respiratory/mucolytic support. | Keep in notes, dashboards, or `unmatched_concerns` unless planner behavior is clear. | Add a trait only when it produces a useful warning or scheduling effect. |
| External medication effects, for example metformin lowering B12 status or changing lactate context. | Represent concrete nutrient impact with `antagonizes`; keep broader medication/performance context in notes or `unmatched_concerns`. | Add medication-specific modeling only if several active review warnings need the same behavior. |

## Encoding Policy

Add relations when the fact has a clear practical consequence:

- Use `competes` only when co-slotting should be avoided.
- Use `supports` when absence of the supporter should produce a useful review
  warning.
- Use `antagonizes` for functional opposition that should be visible in review
  but does not yet need slot placement behavior.
- Keep dose thresholds inside `reason` until the project has an actual dose model.
