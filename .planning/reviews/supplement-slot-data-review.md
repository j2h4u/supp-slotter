# Supplement Slot Data Review

Дата: 2026-05-05

Scope: независимый доменный review текущего `schedule.yaml` и YAML-карточек. Цель - понять, насколько хорошо декларативные данные описывают реальность приема, а не оценить качество алгоритма планера. Это не медицинская рекомендация.

## Panel

- Sports nutrition / timing: проверял тренировочные слоты, креатин, электролиты, fat-soluble intake.
- Clinical pharmacy / interactions: проверял лекарственные и safety-взаимодействия.
- Data ontology: проверял, каких осей не хватает в trait/slot model.

## Current Slot Read

Текущая раскладка в целом разумна для грубых правил `food` / `empty stomach` / `workout`, но качество данных заметно отстает от содержимого `notes` и `unmatched_concerns`. Планер не видит самые важные доменные факты: vasodilation/hypotension, bleeding/fibrinolytic risk, hyperkalemia medication context, dose ceilings, fat-containing meal, hydration context, bedtime adjacency.

Иными словами: проблема не в том, что планер "плохо раскидал"; проблема в том, что карточки не дают ему достаточно измерений.

## High Priority Data Changes

1. Do not leave `tadalafil` trait-empty.

   Current: `data/products/tadalafil.yaml` has `traits: []`, while notes already describe PDE5 inhibition, vasodilation, long half-life, and nitrate contraindication.

   Recommended traits:

   ```yaml
   traits:
     - "class:pde5_inhibitor"
     - "mechanism:vasodilator"
     - "risk:hypotension_stack"
   ```

   If the operator intentionally suppresses generic `risk:manual_review`, keep that as an inventory override, not as an empty substance card.

2. Add vascular risk traits instead of relying on slot separation.

   Same-day overlap matters for `tadalafil` + `l_citrulline_malate` because tadalafil is long-acting. Slot separation alone cannot model additive hypotension.

   Recommended additions:

   ```yaml
   "mechanism:no_precursor"
   "mechanism:vasodilator"
   "risk:hypotension_stack"
   ```

   Apply at least to:

   - `tadalafil`
   - `l_citrulline_malate`
   - `picamilon` if reactivated

3. Split bleeding risk out of `risk:manual_review`.

   `nattokinase` and `krill_oil` are qualitatively different from "manual review" noise. They need machine-readable risk classes.

   Recommended traits:

   ```yaml
   "mechanism:fibrinolytic"
   "risk:fibrinolytic_bleeding"
   "risk:antiplatelet_bleeding"
   ```

   Apply:

   - `nattokinase`: `mechanism:fibrinolytic`, `risk:fibrinolytic_bleeding`
   - `krill_oil`: `risk:antiplatelet_bleeding` if active or co-used with nattokinase

4. Verify `nattokinase` inventory dose.

   Current inventory says `13000 FU`, while the product card itself says typical use is often around `2000 FU/day`. This may be label wording, serving-size ambiguity, or a typo.

   Recommended edit:

   ```yaml
   risk:high_dose_manual_review
   ```

   only if the value is confirmed and intentionally retained.

5. Add potassium-specific medication risk.

   `potassium_citrate` and `electrolyte_caps` currently collapse ACEi/ARB/K-sparing diuretic context into generic manual review.

   Recommended trait:

   ```yaml
   "risk:hyperkalemia_med_interaction"
   ```

   Apply to:

   - `potassium_citrate`
   - `electrolyte_caps`

6. Add dose-ceiling / narrow-therapeutic-window traits.

   `vitamin_d3` at `10000 IU` is slot-reasonable with food, but dose-sensitive enough to deserve an inventory-level review marker. NIH ODS lists the adult vitamin D UL as `4000 IU/day`.

   Recommended traits:

   ```yaml
   "risk:dose_monitoring"
   "risk:narrow_therapeutic_window"
   ```

   Apply:

   - `vitamin_d3` inventory row: `risk:dose_monitoring`
   - `trace_minerals`: `risk:narrow_therapeutic_window`
   - `se_methyl_l_selenocysteine`: selenium-specific narrow-window marker if activated
   - `copper`: narrow-window marker if activated

## Slot-Specific Findings

### `morning_empty`: ALCAR + tadalafil

Acceptable as a coarse placement: ALCAR has morning/empty-stomach rationale, tadalafil is not strongly food-constrained. The issue is not this slot; the issue is that tadalafil scores `0` because the card lacks traits.

Recommended card changes:

- Add PDE5/vasodilator traits to `tadalafil`.
- Add `risk:hypotension_stack` relation with NO precursors.
- Keep low-dose operator preference in `inventory.yaml`, not by erasing pharmacology from the product card.

### `morning_food`: B-complex + trace minerals + potassium + Lion's Mane/B6

Reasonable for tolerance and morning nootropic preference, but risk classes are too generic.

Recommended changes:

- `trace_minerals`: add `risk:multi_mineral_competition`, `risk:thyroid_med_interaction`, `risk:glucose_modulating`.
- Add `family:copper_like`; do not blindly add all mineral families to `trace_minerals` unless the planner can distinguish intra-product components.
- `potassium_citrate`: add `risk:hyperkalemia_med_interaction`.

### `day_food`: D3 + astaxanthin + B5

Good current placement, but `food: true` is too weak for fat-soluble products. D3 and astaxanthin want a fat-containing meal, not just any food.

Recommended slot/card changes:

```yaml
fat_containing_meal: true
```

and a trait such as:

```yaml
"intake:requires_fat_containing_meal"
```

Apply to `vitamin_d3`, `astaxanthin`, and inactive oil/carotenoid cards if used later.

### `evening_empty`: magnesium glycinate + nattokinase

This is the most nuanced current co-location, not a hard conflict. If the fourth physical slot means "immediately before sleep", magnesium fits that slot well. The concern is semantic: nattokinase's main rule is "away from food", while magnesium's main rule is "bedtime-adjacent". The current slot name `evening_empty` happens to satisfy both, but the data model cannot tell whether it is optimizing for bedtime, empty stomach, or both.

Given the current constraint of four fixed physical slots, do not add another physical slot just for this. Instead, annotate the existing fourth slot more precisely.

Recommended model change:

- Add `bedtime_adjacent: true` to the existing fourth slot.
- Keep `magnesium_glycinate` there because the real target is bedtime proximity.
- Keep `nattokinase` there only if the slot is also reliably separated from the previous meal.
- Consider changing nattokinase from `intake:prefers_empty_stomach` to `intake:separate_from_food`.

### `pre_workout`: citrulline + creatine

Citrulline pre-workout is well-matched. Creatine is not wrong here, especially for habit/convenience, but the `intake:prefers_empty_stomach` trait is too strong.

Recommended changes:

- Remove or downgrade `intake:prefers_empty_stomach` from `creatine`.
- Add `intake:food_neutral` or `intake:carb_optional`.
- Keep `prefer_with` as a soft convenience relation, not a hard domain rule.

Suggested future shape:

```yaml
prefer_with:
  - substance: l_citrulline_malate
    context: pre_workout
    strength: prefer
    reason: "operator stack convenience / performance cluster"
```

### `post_workout`: electrolytes + LCLT

Plausible. The issue is schema mismatch: `electrolyte_caps` has `intake:prefers_food`, but `post_workout` is `food: false`. In practice hydration/water context is more important than food for this slot.

Recommended changes:

```yaml
fluid_context: high
workout_phase: post
```

and a trait such as:

```yaml
"intake:with_water_or_food"
```

## Ontology Additions

Recommended first pass:

```yaml
"mechanism:vasodilator"
"mechanism:no_precursor"
"mechanism:fibrinolytic"
"risk:hypotension_stack"
"risk:fibrinolytic_bleeding"
"risk:antiplatelet_bleeding"
"risk:hyperkalemia_med_interaction"
"risk:narrow_therapeutic_window"
"risk:dose_monitoring"
"risk:thyroid_med_interaction"
"risk:glucose_modulating"
"risk:multi_mineral_competition"
"family:copper_like"
"intake:requires_fat_containing_meal"
"intake:with_water_or_food"
"intake:food_neutral"
```

Recommended slot fields:

```yaml
fat_containing_meal: true
fluid_context: normal | high
workout_phase: pre | intra | post
bedtime_adjacent: true
meal_anchor: breakfast | lunch | dinner | none
```

## Relationship Model Improvements

Current `separate_from` is enough for same-slot mineral conflicts, but not for:

- Cu/Zn antagonism with a time gap.
- Intra-product competition inside a multi-mineral product.
- Long-duration pharmacology such as tadalafil + citrulline.
- Risk synergy such as bleeding/fibrinolytic stacking.

Suggested future shape:

```yaml
separate_from:
  - trait: "family:zinc_like"
    scope: slot
    min_gap_hours: 2
    reason: "competitive absorption"
    strength: prefer
```

Do not overload `separate_from` for safety warnings. Use a separate warning relation:

```yaml
caution_with:
  - trait: "mechanism:vasodilator"
    risk: "risk:hypotension_stack"
```

## Recommended Implementation Order

1. Add risk/mechanism traits for tadalafil, citrulline, nattokinase, potassium/electrolytes.
2. Add `fat_containing_meal`, `fluid_context`, and `bedtime_adjacent` slot fields.
3. Add `bedtime_adjacent: true` to the fourth physical slot and treat nattokinase's constraint as `separate_from_food`, not as generic evening timing.
4. Downgrade creatine's empty-stomach trait.
5. Split `risk:manual_review` into specific risk traits while keeping `risk:manual_review` only as broad fallback.
6. Add structured `prefer_with` / `caution_with` relation objects after the simple trait pass.

## Sources

- NIH ODS Vitamin D fact sheet: adult UL context and dose-monitoring anchor. https://ods.od.nih.gov/factsheets/VitaminD-HealthProfessional/
- DailyMed CIALIS/tadalafil label: nitrate contraindication, blood-pressure cautions, and food effect anchor. https://dailymed.nlm.nih.gov/dailymed/drugInfo.cfm?setid=bcd8f8ab-81a2-4891-83db-24a0b0e25895
- NIH ODS Potassium fact sheet: ACE inhibitor / ARB / potassium-sparing diuretic hyperkalemia context. https://ods.od.nih.gov/factsheets/Potassium-HealthProfessional/
- NIH ODS Zinc fact sheet: high-dose zinc can inhibit copper absorption. https://ods.od.nih.gov/factsheets/Zinc-HealthProfessional/
- NIH ODS Omega-3 fact sheet: anticoagulant / bleeding context for omega-3 products. https://ods.od.nih.gov/factsheets/Omega3FattyAcids-HealthProfessional/
- ISSN creatine position stand: creatine is a daily ergogenic supplement; timing is not the main scheduling constraint. https://jissn.biomedcentral.com/articles/10.1186/s12970-017-0173-z
- PubMed vitamin D meal/fat absorption studies: support for modeling fat-containing meal separately from generic food. https://pubmed.ncbi.nlm.nih.gov/24853643/ and https://pubmed.ncbi.nlm.nih.gov/23427007/
- PubMed review on dietary supplements and bleeding: broader anchor for bleeding-risk classification. https://pubmed.ncbi.nlm.nih.gov/36304597/
