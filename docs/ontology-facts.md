# Ontology Fact Candidates

This document captures user-supplied supplement facts before encoding them into
planner behavior. Treat these as modeling candidates, not medical advice or an
evidence review.

The preferred modeling order is KISS:

1. Use existing substance cards when possible.
2. Use `relations` when a fact is substance-to-substance.
3. Use traits only when the planner needs a reusable scheduling rule.
4. Do not create abstract mechanism entities such as `vitamin_k_cellular_uptake`.

## Current Fact Mapping

| Fact | Candidate model | Entity impact |
|---|---|---|
| Vitamin E and vitamin K compete; separate by at least 2 hours or different meals. | Likely `competes_absorption` if the planner should separate slots; possibly `antagonizes` if modeled as functional opposition. | Existing vitamin E tocopherol, K1, and K2 cards. |
| Tocopherols and tocotrienols compete; separate them. | `competes_absorption` between vitamin E tocopherol and vitamin E tocotrienols. | Added tocotrienols card. |
| Calcium and iron compete; separate 2-4 hours, especially when calcium is 300-500 mg or more. | `competes_absorption`; dose threshold remains in `reason` because the planner does not calculate dose. | Added iron card. |
| Calcium and zinc compete; separate 2-4 hours. | `competes_absorption`. | Existing calcium and zinc cards. |
| Calcium and magnesium should be separated by at least 2 hours at high doses. | Candidate `competes_absorption`, but only if we accept ignoring dose threshold. Otherwise keep as review note. | Existing calcium and magnesium cards. |
| Calcium and vitamin D are synergistic; vitamin D improves calcium absorption. | `supports` from vitamin D to calcium and `supported_by` on calcium. | Existing calcium and vitamin D3 cards. |
| Vitamins A and E may reduce vitamin K cellular uptake/function; separate 2-3 hours. | Prefer `antagonizes`/`antagonized_by` unless the planner must force slot separation. | Existing vitamin A, E, K1, and K2 cards. |
| Ashwagandha may increase thyroid hormones and cause thyrotoxic symptoms such as sinus tachycardia. | `risk:manual_review` plus `unmatched_concerns` until a thyroid-specific risk trait is justified. | Added ashwagandha card. |
| L-Lysine and L-arginine compete for transport through the BBB and mitochondrial membrane. | Candidate `competes_absorption` only if we accept using it for transporter competition beyond gut absorption; otherwise add a future relation type only when needed. | Added L-lysine and L-arginine cards. |
| High-dose L-lysine can reduce L-arginine uptake. | Same lysine/arginine relation, with dose context in `reason`. | Existing after adding L-lysine and L-arginine. |
| Amino acids are often better on an empty stomach because food amino acids compete. | `intake:empty_preferred` on concrete amino-acid substance cards. | Applied to added amino-acid cards. |
| Beta-alanine is used pre-workout in this stack context. | `activity:pre_workout` on the beta-alanine substance card. | Existing after adding beta-alanine card. |
| L-Arginine, L-ornithine, and L-lysine may synergize around growth hormone. | `supports`/`supported_by` if reviewing each substance; `prefer_with` only if the planner should co-locate active products. | Added L-arginine, L-ornithine, and L-lysine cards. |
| B6 is a cofactor for amino-acid transamination/deamination. | Potential `supports` from concrete B6 forms to amino acids, but this is broad and should be added only when it improves review. | Existing B6 cards. |
| Vitamin C supports collagen synthesis through L-lysine/L-proline hydroxylation. | `supports` from vitamin C to L-lysine/L-proline collagen context, or a goal-cluster note if this is mainly goal review. | Added L-proline card; existing vitamin C and L-lysine cards. |
| Zinc is a cofactor for many amino-acid metabolism enzymes. | Too broad for immediate relations; keep as notes/unmatched concern unless a specific target matters. | Existing zinc card. |
| Glycine, beta-alanine, and taurine compete at glycine receptors. | Functional receptor competition; likely `antagonizes` rather than `competes_absorption`. | Added beta-alanine and taurine cards; glycine exists. |
| Vitamin E forms plus astaxanthin may synergize around keratinization / skin barrier. | `supports`/`supported_by` if skin-barrier review becomes a concrete goal. | Existing astaxanthin and tocopherol; added tocotrienols. |

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

## Encoding Policy

Do not encode every row immediately as planner behavior. Add relations when the
fact has a clear practical consequence:

- Use `competes_absorption` only when co-slotting should be avoided.
- Use `supports`/`supported_by` when absence of the supporter should produce a
  useful review warning.
- Use `antagonizes`/`antagonized_by` for functional opposition that should be
  visible in review but does not yet need slot placement behavior.
- Keep dose thresholds inside `reason` until the project has an actual dose model.
