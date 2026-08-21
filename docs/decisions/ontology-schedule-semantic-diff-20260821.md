# Ontology cutover scheduling semantic diff — 2026-08-21

This artifact compares shared substance scheduling assertions between `origin/main@4abac57` and the current feature branch `feature/executable-ontology-contract@1e26667`. It is repository-evidence-only: no new medical evidence or adjudication was performed. The artifact inventories the cutover decision surface; it does not prescribe repairs.

## Scope and machine method

- Match substance cards by stable YAML `id`, not filename or display name. The shared universe is the intersection of IDs.
- Compare only effective, non-empty `schedule.intake`, `schedule.timing`, and `schedule.activity` lists. `scheduling_assessment` is evidence of an authored assessment, not itself an executable assertion.
- Derive current reachability from `data/stacks.yaml` and product component links: daily products are `active-reachable`, daily products with `use_pattern: not_every_day` are `episodic-reachable`, training products are `training-reachable`, inactive products are `inactive`, and products/components outside all stacks are `unassigned`. Categories overlap when one substance is present in several product states.
- Classify a changed shared assertion as `already explicitly assessed intentional change` when the current card has `scheduling_assessment.<axis>`; as `likely migration loss` when the old effective assertion disappears without that assessment; otherwise as `unassessed semantic change`. `catalog/identity mismatch` is reserved for cards not matchable by shared stable ID and is listed separately.

Source files used: `data/substances/*.yaml`, `data/products/*.yaml`, `data/stacks.yaml`, and their `4abac57` versions. The decision vocabulary is from `docs/decisions/ontology-cutover-decision-20260821.md`.

## Summary

| Measure | Count |
| --- | ---: |
| Substance cards at baseline | 253 |
| Substance cards on feature branch | 255 |
| Shared substance IDs | 252 |
| Changed shared axis assertions | 120 across 110 cards |
| Changed intake assertions | 100 |
| Changed timing assertions | 15 |
| Changed activity assertions | 5 |
| Effective assertions in shared cards: baseline -> feature | 249 -> 152 |
| Current shared-card assessment axes | 78 |

| Classification | Rows | Share of changed rows |
| --- | ---: | ---: |
| already explicitly assessed intentional change | 33 | 27.5% |
| likely migration loss | 68 | 56.7% |
| unassessed semantic change | 19 | 15.8% |

## Reachability coverage

| Current category (overlapping counts) | Shared substance IDs | Changed rows | Changed cards |
| --- | ---: | ---: | ---: |
| active-reachable | 18 | 17 | 16 |
| episodic-reachable | 12 | 11 | 11 |
| training-reachable | 8 | 8 | 7 |
| inactive | 159 | 77 | 70 |
| unassigned | 95 | 44 | 42 |

Rows touching any currently reachable active/episodic/training product: **32 across 30 cards; 32 explicitly assessed, 0 not explicitly assessed.**
Rows only in inactive/unassigned reachability: **88 across 80 cards; 68 likely losses, 19 unassessed semantic changes, and 1 explicitly assessed.**

## Transition clusters

| Classification | Axis | Baseline | Feature | Rows |
| --- | --- | --- | --- | ---: |
| already explicitly assessed intentional change | activity | `any_workout` | `-` | 1 |
| already explicitly assessed intentional change | intake | `empty_preferred` | `-` | 2 |
| already explicitly assessed intentional change | intake | `fat_meal_required` | `-` | 2 |
| already explicitly assessed intentional change | intake | `fat_meal_required` | `food_preferred` | 3 |
| already explicitly assessed intentional change | intake | `food_neutral` | `-` | 2 |
| already explicitly assessed intentional change | intake | `food_neutral` | `food_preferred` | 1 |
| already explicitly assessed intentional change | intake | `food_preferred` | `-` | 21 |
| already explicitly assessed intentional change | timing | `sleep_support` | `-` | 1 |
| likely migration loss | activity | `pre_workout` | `-` | 4 |
| likely migration loss | intake | `empty_preferred` | `-` | 9 |
| likely migration loss | intake | `fat_meal_required` | `-` | 2 |
| likely migration loss | intake | `food_neutral` | `-` | 26 |
| likely migration loss | intake | `food_preferred` | `-` | 10 |
| likely migration loss | intake | `food_required` | `-` | 3 |
| likely migration loss | timing | `energy_like` | `-` | 6 |
| likely migration loss | timing | `sleep_support` | `-` | 8 |
| unassessed semantic change | intake | `fat_meal_required` | `food_preferred` | 12 |
| unassessed semantic change | intake | `food_required` | `food_preferred` | 7 |

The unassessed cluster is 12 `fat_meal_required -> food_preferred` intake changes and 7 `food_required -> food_preferred` intake changes. The likely-loss cluster is dominated by removed `food_neutral` (26), `food_preferred` (10), `empty_preferred` (9), `sleep_support` (8), `energy_like` (6), and `pre_workout` (4) assertions. Exact rows, cards, paths, reachability, and assessment fields are in the TSV appendix.

## High-salience cards and product components

These rows are surfaced for cutover review; the status is derived mechanically and is not a medical judgment.

| Salience | Substance ID | Current name/form | Current reachability | Baseline -> feature | Assessment | Status |
| --- | --- | --- | --- | --- | --- | --- |
| Vitamin B5 (intake) | `sub_7628e4f478` | Vitamin B5 | active-reachable,episodic-reachable,inactive | `food_preferred` -> `-` | insufficient | already explicitly assessed intentional change |
| Vitamin B5 (timing) | `sub_7628e4f478` | Vitamin B5 | active-reachable,episodic-reachable,inactive | `-` -> `-` | insufficient | unchanged effective assertion |
| Magnesium (intake) | `sub_7e02eab0d1` | Magnesium / glycinate | active-reachable,inactive | `food_preferred` -> `-` | insufficient | already explicitly assessed intentional change |
| Magnesium (timing) | `sub_7e02eab0d1` | Magnesium / glycinate | active-reachable,inactive | `sleep_support` -> `-` | insufficient | already explicitly assessed intentional change |
| Trace minerals: zinc (intake) | `sub_8ppxce3s17` | Zinc / monomethionine / L-OptiZinc | active-reachable,inactive | `food_preferred` -> `-` | insufficient | already explicitly assessed intentional change |
| Trace minerals: zinc (timing) | `sub_8ppxce3s17` | Zinc / monomethionine / L-OptiZinc | active-reachable,inactive | `-` -> `-` | insufficient | unchanged effective assertion |
| Trace minerals: copper (intake) | `sub_844a0cc551` | Copper / bisglycinate | active-reachable,inactive | `food_preferred` -> `-` | insufficient | already explicitly assessed intentional change |
| Trace minerals: copper (timing) | `sub_844a0cc551` | Copper / bisglycinate | active-reachable,inactive | `-` -> `-` | insufficient | unchanged effective assertion |
| Trace minerals: manganese (intake) | `sub_7938ea248e` | Manganese | active-reachable,inactive | `food_preferred` -> `-` | insufficient | already explicitly assessed intentional change |
| Trace minerals: manganese (timing) | `sub_7938ea248e` | Manganese | active-reachable,inactive | `-` -> `-` | insufficient | unchanged effective assertion |
| Trace minerals: chromium (intake) | `sub_ddf8d310d2` | Chromium | active-reachable,inactive | `food_preferred` -> `-` | insufficient | already explicitly assessed intentional change |
| Trace minerals: chromium (timing) | `sub_ddf8d310d2` | Chromium | active-reachable,inactive | `-` -> `-` | insufficient | unchanged effective assertion |
| Trace minerals: molybdenum (intake) | `sub_c55378389c` | Molybdenum | active-reachable,inactive | `food_preferred` -> `-` | insufficient | already explicitly assessed intentional change |
| Trace minerals: molybdenum (timing) | `sub_c55378389c` | Molybdenum | active-reachable,inactive | `-` -> `-` | insufficient | unchanged effective assertion |
| Trace minerals: boron (intake) | `sub_25b049a598` | Boron | active-reachable,inactive | `food_preferred` -> `-` | insufficient | already explicitly assessed intentional change |
| Trace minerals: boron (timing) | `sub_25b049a598` | Boron | active-reachable,inactive | `-` -> `-` | insufficient | unchanged effective assertion |
| Trace minerals: vanadium (intake) | `sub_3e3b246a6f` | Vanadium | active-reachable,inactive | `food_preferred` -> `-` | insufficient | already explicitly assessed intentional change |
| Trace minerals: vanadium (timing) | `sub_3e3b246a6f` | Vanadium | active-reachable,inactive | `-` -> `-` | insufficient | unchanged effective assertion |
| Vitamin C: ascorbic acid (intake) | `sub_49c7531eaf` | Vitamin C / ascorbic acid | inactive | `food_preferred` -> `food_preferred` | - | unchanged effective assertion |
| Vitamin C: calcium ascorbate (intake) | `sub_z88pld4hbv` | Vitamin C / calcium ascorbate | inactive | `food_preferred` -> `food_preferred` | - | unchanged effective assertion |
| Vitamin C: sodium ascorbate (intake) | `sub_vcnaasc800` | Vitamin C / sodium ascorbate | active-reachable | `food_preferred` -> `food_preferred` | supports_preference/food_preferred | unchanged effective assertion |
| Vitamin C: sodium ascorbate (timing) | `sub_vcnaasc800` | Vitamin C / sodium ascorbate | active-reachable | `-` -> `-` | insufficient | unchanged effective assertion |
| Vitamin C product counterion: sodium (intake) | `sub_4j9fttkil9` | Sodium | active-reachable,training-reachable | `food_neutral` -> `-` | insufficient | already explicitly assessed intentional change |
| Vitamin C product counterion: sodium (timing) | `sub_4j9fttkil9` | Sodium | active-reachable,training-reachable | `-` -> `-` | insufficient | unchanged effective assertion |
| Vitamin C product counterion: sodium (activity) | `sub_4j9fttkil9` | Sodium | active-reachable,training-reachable | `-` -> `-` | insufficient | unchanged effective assertion |

The active `Only Trace Minerals` product (`prd_932319251f`) links zinc, copper, manganese, chromium, molybdenum, boron, and vanadium; each component assertion changed from baseline `food_preferred` to no effective feature assertion and each has an explicit current assessment. The active Vitamin C product (`prd_vitamealc8`) uses sodium ascorbate plus a sodium component: sodium ascorbate remains `food_preferred` (assessment present), while the sodium counterion loses a baseline `food_neutral` assertion with an explicit assessment. Vitamin B5 and Magnesium are current active-reachable cards whose baseline food/timing assertions are explicitly assessed as no effective feature assertion.

## Catalog / identity mismatches outside the shared-ID assertion universe

These cards cannot be compared as shared substance assertions by stable ID. They are included so the 120-row assertion count is not mistaken for a full catalog parity result.

| Side | Substance ID | Name/form | Schedule assertions on that side | Current reachability | Classification | Path |
| --- | --- | --- | --- | --- | --- | --- |
| baseline only | `sub_yd7dqo36dn` | Vitamin B5 / calcium D-pantothenate | intake=food_preferred | - | catalog/identity mismatch | `data/substances/vitamin_b5_calcium_d_pantothenate__sub_yd7dqo36dn.yaml` |
| feature only | `sub_kwudyhex2o` | Choline / bitartrate | - | active-reachable | catalog/identity mismatch | `data/substances/choline_bitartrate__sub_kwudyhex2o.yaml` |
| feature only | `sub_sunkcr05vl` | Fish Oil Concentrate / EPA/DHA ethyl esters | intake=food_preferred | episodic-reachable | catalog/identity mismatch | `data/substances/fish_oil_concentrate_epa_dha_ethyl_esters__sub_sunkcr05vl.yaml` |
| feature only | `sub_t8sx7e49j7` | Phospholipids | - | active-reachable | catalog/identity mismatch | `data/substances/phospholipids__sub_t8sx7e49j7.yaml` |

The baseline-only card is the orphan `Vitamin B5 / calcium D-pantothenate` card; the BioGrace product already referenced shared `sub_7628e4f478` on baseline and still does so on the feature branch. Feature-only cards are Choline bitartrate, Fish Oil Concentrate, and Phospholipids; their product links and assessments are catalog additions, not rows in the shared semantic diff.

## Exhaustive machine-readable appendix

One row per changed shared substance ID × axis. `-` means no effective assertion or no assessment field. Paths are the exact source card paths on each side.

```tsv
substance_id	name	axis	baseline_assertion	feature_assertion	current_reachability	assessment_conclusion	assessment_policy	classification	baseline_path	feature_path
sub_0jmfcyanzv	Omeprazole	intake	food_required	-	unassigned	-	-	likely migration loss	data/substances/omeprazole__sub_0jmfcyanzv.yaml	data/substances/omeprazole__sub_0jmfcyanzv.yaml
sub_157418854b	Vitamin B12	intake	food_preferred	-	episodic-reachable,inactive,unassigned	insufficient	-	already explicitly assessed intentional change	data/substances/vitamin_b12_methylcobalamin__sub_157418854b.yaml	data/substances/vitamin_b12_methylcobalamin__sub_157418854b.yaml
sub_1hhkguyz55	Vitamin K1	intake	fat_meal_required	food_preferred	inactive	-	-	unassessed semantic change	data/substances/vitamin_k1_phylloquinone__sub_1hhkguyz55.yaml	data/substances/vitamin_k1_phylloquinone__sub_1hhkguyz55.yaml
sub_230c5c820e	Vitamin B1	intake	food_preferred	-	episodic-reachable,unassigned	insufficient	-	already explicitly assessed intentional change	data/substances/vitamin_b1_thiamine__sub_230c5c820e.yaml	data/substances/vitamin_b1_thiamine__sub_230c5c820e.yaml
sub_2476bf9d4b	Vitamin D3	intake	fat_meal_required	food_preferred	episodic-reachable,inactive	supports_preference	food_preferred	already explicitly assessed intentional change	data/substances/vitamin_d3_cholecalciferol__sub_2476bf9d4b.yaml	data/substances/vitamin_d3_cholecalciferol__sub_2476bf9d4b.yaml
sub_249199f726	Astaxanthin	intake	fat_meal_required	food_preferred	active-reachable,inactive,unassigned	supports_preference	food_preferred	already explicitly assessed intentional change	data/substances/astaxanthin__sub_249199f726.yaml	data/substances/astaxanthin__sub_249199f726.yaml
sub_25b049a598	Boron	intake	food_preferred	-	active-reachable,inactive	insufficient	-	already explicitly assessed intentional change	data/substances/boron__sub_25b049a598.yaml	data/substances/boron__sub_25b049a598.yaml
sub_262gmd1vf1	Zeaxanthin	intake	fat_meal_required	food_preferred	inactive	-	-	unassessed semantic change	data/substances/zeaxanthin__sub_262gmd1vf1.yaml	data/substances/zeaxanthin__sub_262gmd1vf1.yaml
sub_2gjf5yx7cz	Saccharomyces boulardii	intake	food_neutral	-	unassigned	-	-	likely migration loss	data/substances/saccharomyces_boulardii__sub_2gjf5yx7cz.yaml	data/substances/saccharomyces_boulardii__sub_2gjf5yx7cz.yaml
sub_2mn1uwrzi6	Lansoprazole	intake	food_required	-	unassigned	-	-	likely migration loss	data/substances/lansoprazole__sub_2mn1uwrzi6.yaml	data/substances/lansoprazole__sub_2mn1uwrzi6.yaml
sub_2preozf0up	Collagen peptides	intake	food_neutral	-	unassigned	-	-	likely migration loss	data/substances/collagen_peptides_hydrolyzed__sub_2preozf0up.yaml	data/substances/collagen_peptides_hydrolyzed__sub_2preozf0up.yaml
sub_2se61pa12m	Ranitidine	intake	food_neutral	-	unassigned	-	-	likely migration loss	data/substances/ranitidine__sub_2se61pa12m.yaml	data/substances/ranitidine__sub_2se61pa12m.yaml
sub_2wbcgb78qg	Aloe vera	intake	food_neutral	-	unassigned	-	-	likely migration loss	data/substances/aloe_vera__sub_2wbcgb78qg.yaml	data/substances/aloe_vera__sub_2wbcgb78qg.yaml
sub_31a1408cad	Vitamin A	intake	food_required	food_preferred	inactive	-	-	unassessed semantic change	data/substances/vitamin_a_retinol__sub_31a1408cad.yaml	data/substances/vitamin_a_retinol__sub_31a1408cad.yaml
sub_3918fe347e	L-Citrulline	intake	empty_preferred	-	training-reachable,inactive	insufficient	-	already explicitly assessed intentional change	data/substances/l_citrulline_malate__sub_3918fe347e.yaml	data/substances/l_citrulline_malate__sub_3918fe347e.yaml
sub_396c221c31	Picamilon	intake	food_preferred	-	episodic-reachable	supports_no_rule	-	already explicitly assessed intentional change	data/substances/picamilon__sub_396c221c31.yaml	data/substances/picamilon_sodium_nicotinoyl_gamma_aminobutyrate__sub_396c221c31.yaml
sub_3e3b246a6f	Vanadium	intake	food_preferred	-	active-reachable,inactive	insufficient	-	already explicitly assessed intentional change	data/substances/vanadium__sub_3e3b246a6f.yaml	data/substances/vanadium__sub_3e3b246a6f.yaml
sub_3o2ay3a5so	Valerian	timing	sleep_support	-	inactive	-	-	likely migration loss	data/substances/valerian_root_extract__sub_3o2ay3a5so.yaml	data/substances/valerian_root_extract__sub_3o2ay3a5so.yaml
sub_3rxxtq14ns	Eurycoma longifolia	timing	energy_like	-	unassigned	-	-	likely migration loss	data/substances/eurycoma_longifolia_root_extract__sub_3rxxtq14ns.yaml	data/substances/eurycoma_longifolia_root_extract__sub_3rxxtq14ns.yaml
sub_40cd4f33lo	Vitamin B1	intake	fat_meal_required	-	inactive	-	-	likely migration loss	data/substances/vitamin_b1_benfotiamine__sub_40cd4f33lo.yaml	data/substances/vitamin_b1_benfotiamine__sub_40cd4f33lo.yaml
sub_4j9fttkil9	Sodium	intake	food_neutral	-	active-reachable,training-reachable	insufficient	-	already explicitly assessed intentional change	data/substances/sodium__sub_4j9fttkil9.yaml	data/substances/sodium__sub_4j9fttkil9.yaml
sub_4lwevjtf97	Deglycyrrhizinated licorice	intake	food_preferred	-	unassigned	-	-	likely migration loss	data/substances/deglycyrrhizinated_licorice__sub_4lwevjtf97.yaml	data/substances/deglycyrrhizinated_licorice__sub_4lwevjtf97.yaml
sub_5723eafac4	Vitamin E	intake	fat_meal_required	food_preferred	inactive	-	-	unassessed semantic change	data/substances/vitamin_e_tocotrienols__sub_5723eafac4.yaml	data/substances/vitamin_e_tocotrienols__sub_5723eafac4.yaml
sub_5bd641c116	L-Carnitine	intake	empty_preferred	-	training-reachable	insufficient	-	already explicitly assessed intentional change	data/substances/l_carnitine_l_tartrate__sub_5bd641c116.yaml	data/substances/l_carnitine_l_tartrate__sub_5bd641c116.yaml
sub_5bd641c116	L-Carnitine	activity	any_workout	-	training-reachable	insufficient	-	already explicitly assessed intentional change	data/substances/l_carnitine_l_tartrate__sub_5bd641c116.yaml	data/substances/l_carnitine_l_tartrate__sub_5bd641c116.yaml
sub_5j1kg3bmgk	DMAE	intake	food_neutral	-	inactive	-	-	likely migration loss	data/substances/dmae_bitartrate__sub_5j1kg3bmgk.yaml	data/substances/dmae_bitartrate__sub_5j1kg3bmgk.yaml
sub_5j1kg3bmgk	DMAE	timing	energy_like	-	inactive	-	-	likely migration loss	data/substances/dmae_bitartrate__sub_5j1kg3bmgk.yaml	data/substances/dmae_bitartrate__sub_5j1kg3bmgk.yaml
sub_605u9zvqt2	Metformin	intake	food_required	food_preferred	unassigned	-	-	unassessed semantic change	data/substances/metformin__sub_605u9zvqt2.yaml	data/substances/metformin__sub_605u9zvqt2.yaml
sub_646e568f61	Krill Oil	intake	fat_meal_required	food_preferred	active-reachable,inactive,unassigned	supports_preference	food_preferred	already explicitly assessed intentional change	data/substances/krill_oil__sub_646e568f61.yaml	data/substances/krill_oil__sub_646e568f61.yaml
sub_66b783576c	Eicosapentaenoic acid	intake	fat_meal_required	-	active-reachable,episodic-reachable,inactive,unassigned	insufficient	-	already explicitly assessed intentional change	data/substances/eicosapentaenoic_acid__sub_66b783576c.yaml	data/substances/eicosapentaenoic_acid__sub_66b783576c.yaml
sub_6n5okijhqz	Zeaxanthin	intake	fat_meal_required	food_preferred	inactive	-	-	unassessed semantic change	data/substances/zeaxanthin_meso_zeaxanthin__sub_6n5okijhqz.yaml	data/substances/zeaxanthin_meso_zeaxanthin__sub_6n5okijhqz.yaml
sub_6svt59zncl	5-HTP	intake	empty_preferred	-	inactive	-	-	likely migration loss	data/substances/5_htp_griffonia_simplicifolia_seed_extract__sub_6svt59zncl.yaml	data/substances/5_htp_griffonia_simplicifolia_seed_extract__sub_6svt59zncl.yaml
sub_6svt59zncl	5-HTP	timing	sleep_support	-	inactive	-	-	likely migration loss	data/substances/5_htp_griffonia_simplicifolia_seed_extract__sub_6svt59zncl.yaml	data/substances/5_htp_griffonia_simplicifolia_seed_extract__sub_6svt59zncl.yaml
sub_6yp50f6ach	Vitamin B3	intake	food_preferred	-	episodic-reachable,inactive	insufficient	-	already explicitly assessed intentional change	data/substances/vitamin_b3_inositol_hexaniacinate__sub_6yp50f6ach.yaml	data/substances/vitamin_b3_inositol_hexaniacinate__sub_6yp50f6ach.yaml
sub_6z3m3zbxgb	Melatonin	intake	empty_preferred	-	inactive	-	-	likely migration loss	data/substances/melatonin__sub_6z3m3zbxgb.yaml	data/substances/melatonin__sub_6z3m3zbxgb.yaml
sub_7628e4f478	Vitamin B5	intake	food_preferred	-	active-reachable,episodic-reachable,inactive	insufficient	-	already explicitly assessed intentional change	data/substances/vitamin_b5_pantothenic_acid__sub_7628e4f478.yaml	data/substances/vitamin_b5__sub_7628e4f478.yaml
sub_7938ea248e	Manganese	intake	food_preferred	-	active-reachable,inactive	insufficient	-	already explicitly assessed intentional change	data/substances/manganese__sub_7938ea248e.yaml	data/substances/manganese__sub_7938ea248e.yaml
sub_799419116d	Vitamin B6	intake	food_preferred	-	episodic-reachable,inactive	insufficient	-	already explicitly assessed intentional change	data/substances/vitamin_b6_pyridoxal_5_phosphate__sub_799419116d.yaml	data/substances/vitamin_b6_pyridoxal_5_phosphate__sub_799419116d.yaml
sub_7e02eab0d1	Magnesium	intake	food_preferred	-	active-reachable,inactive	insufficient	-	already explicitly assessed intentional change	data/substances/magnesium_glycinate__sub_7e02eab0d1.yaml	data/substances/magnesium_glycinate__sub_7e02eab0d1.yaml
sub_7e02eab0d1	Magnesium	timing	sleep_support	-	active-reachable,inactive	insufficient	-	already explicitly assessed intentional change	data/substances/magnesium_glycinate__sub_7e02eab0d1.yaml	data/substances/magnesium_glycinate__sub_7e02eab0d1.yaml
sub_7ehuhfcly5	Whey protein	intake	food_neutral	-	unassigned	-	-	likely migration loss	data/substances/whey_protein__sub_7ehuhfcly5.yaml	data/substances/whey_protein__sub_7ehuhfcly5.yaml
sub_7emxvn1qat	Caffeine	intake	food_neutral	-	inactive	-	-	likely migration loss	data/substances/caffeine_anhydrous__sub_7emxvn1qat.yaml	data/substances/caffeine_anhydrous__sub_7emxvn1qat.yaml
sub_7ozks6pos5	Nicotinamide mononucleotide	intake	food_neutral	-	unassigned	-	-	likely migration loss	data/substances/nicotinamide_mononucleotide__sub_7ozks6pos5.yaml	data/substances/nicotinamide_mononucleotide__sub_7ozks6pos5.yaml
sub_844a0cc551	Copper	intake	food_preferred	-	active-reachable,inactive	insufficient	-	already explicitly assessed intentional change	data/substances/copper_bisglycinate__sub_844a0cc551.yaml	data/substances/copper_bisglycinate__sub_844a0cc551.yaml
sub_844a87d72b	Vitamin E	intake	food_required	food_preferred	inactive,unassigned	-	-	unassessed semantic change	data/substances/vitamin_e_tocopherol__sub_844a87d72b.yaml	data/substances/vitamin_e_tocopherol__sub_844a87d72b.yaml
sub_8noiw2mhhb	Chasteberry	intake	food_neutral	-	unassigned	-	-	likely migration loss	data/substances/chasteberry_fruit_extract__sub_8noiw2mhhb.yaml	data/substances/chasteberry_fruit_extract__sub_8noiw2mhhb.yaml
sub_8ppxce3s17	Zinc	intake	food_preferred	-	active-reachable,inactive	insufficient	-	already explicitly assessed intentional change	data/substances/zinc_monomethionine_l_optizinc__sub_8ppxce3s17.yaml	data/substances/zinc_monomethionine_l_optizinc__sub_8ppxce3s17.yaml
sub_8wi86qpvwi	Lavender	intake	food_neutral	-	inactive	-	-	likely migration loss	data/substances/lavender_flower__sub_8wi86qpvwi.yaml	data/substances/lavender_flower__sub_8wi86qpvwi.yaml
sub_8wi86qpvwi	Lavender	timing	sleep_support	-	inactive	-	-	likely migration loss	data/substances/lavender_flower__sub_8wi86qpvwi.yaml	data/substances/lavender_flower__sub_8wi86qpvwi.yaml
sub_96owcg92uf	Lycopene	intake	fat_meal_required	food_preferred	inactive	-	-	unassessed semantic change	data/substances/lycopene__sub_96owcg92uf.yaml	data/substances/lycopene__sub_96owcg92uf.yaml
sub_97b0ff246a	L-Carnitine	intake	empty_preferred	-	unassigned	-	-	likely migration loss	data/substances/l_carnitine_acetyl__sub_97b0ff246a.yaml	data/substances/l_carnitine_acetyl__sub_97b0ff246a.yaml
sub_97b0ff246a	L-Carnitine	timing	energy_like	-	unassigned	-	-	likely migration loss	data/substances/l_carnitine_acetyl__sub_97b0ff246a.yaml	data/substances/l_carnitine_acetyl__sub_97b0ff246a.yaml
sub_9c0908e7f7	Creatine	intake	food_neutral	food_preferred	training-reachable	supports_preference	food_preferred	already explicitly assessed intentional change	data/substances/creatine_monohydrate__sub_9c0908e7f7.yaml	data/substances/creatine_monohydrate__sub_9c0908e7f7.yaml
sub_a3ec9f9c52	Tadalafil	intake	food_neutral	-	active-reachable	supports_no_rule	-	already explicitly assessed intentional change	data/substances/tadalafil__sub_a3ec9f9c52.yaml	data/substances/tadalafil__sub_a3ec9f9c52.yaml
sub_a873e428ee	Vitamin B6	intake	food_preferred	-	inactive,unassigned	insufficient	-	already explicitly assessed intentional change	data/substances/vitamin_b6_pyridoxine_hcl__sub_a873e428ee.yaml	data/substances/vitamin_b6_pyridoxine_hcl__sub_a873e428ee.yaml
sub_abb9604e58	Beta-alanine	activity	pre_workout	-	inactive	-	-	likely migration loss	data/substances/beta_alanine__sub_abb9604e58.yaml	data/substances/beta_alanine__sub_abb9604e58.yaml
sub_b7vnosy4h8	HICA	activity	pre_workout	-	inactive	-	-	likely migration loss	data/substances/hica_alpha_hydroxyisocaproic_acid__sub_b7vnosy4h8.yaml	data/substances/hica_alpha_hydroxyisocaproic_acid__sub_b7vnosy4h8.yaml
sub_c36e075c09	Red yeast rice	intake	food_required	-	unassigned	-	-	likely migration loss	data/substances/red_yeast_rice__sub_c36e075c09.yaml	data/substances/red_yeast_rice__sub_c36e075c09.yaml
sub_c55378389c	Molybdenum	intake	food_preferred	-	active-reachable,inactive	insufficient	-	already explicitly assessed intentional change	data/substances/molybdenum__sub_c55378389c.yaml	data/substances/molybdenum__sub_c55378389c.yaml
sub_c9720c7240	Glycine	intake	empty_preferred	-	inactive	-	-	likely migration loss	data/substances/glycine__sub_c9720c7240.yaml	data/substances/glycine__sub_c9720c7240.yaml
sub_d0034bd130	Vitamin B9	intake	food_preferred	-	episodic-reachable,inactive	insufficient	-	already explicitly assessed intentional change	data/substances/vitamin_b9_methylfolate__sub_d0034bd130.yaml	data/substances/vitamin_b9_methylfolate__sub_d0034bd130.yaml
sub_dcxfwd4udf	Phosphatidylcholine	intake	fat_meal_required	-	inactive	-	-	likely migration loss	data/substances/phosphatidylcholine__sub_dcxfwd4udf.yaml	data/substances/phosphatidylcholine__sub_dcxfwd4udf.yaml
sub_ddf8d310d2	Chromium	intake	food_preferred	-	active-reachable,inactive	insufficient	-	already explicitly assessed intentional change	data/substances/chromium__sub_ddf8d310d2.yaml	data/substances/chromium__sub_ddf8d310d2.yaml
sub_dopjesesge	Elderberry	intake	food_neutral	-	unassigned	-	-	likely migration loss	data/substances/elderberry_extract__sub_dopjesesge.yaml	data/substances/elderberry_extract__sub_dopjesesge.yaml
sub_dznuinvc2n	Cimetidine	intake	food_neutral	-	unassigned	-	-	likely migration loss	data/substances/cimetidine__sub_dznuinvc2n.yaml	data/substances/cimetidine__sub_dznuinvc2n.yaml
sub_e3af6f78d9	Lion's Mane	intake	food_preferred	-	active-reachable,inactive,unassigned	insufficient	-	already explicitly assessed intentional change	data/substances/lions_mane__sub_e3af6f78d9.yaml	data/substances/lions_mane__sub_e3af6f78d9.yaml
sub_e6vq6f2s3n	Betaine hydrochloride	intake	food_required	food_preferred	unassigned	-	-	unassessed semantic change	data/substances/betaine_hydrochloride__sub_e6vq6f2s3n.yaml	data/substances/betaine_hydrochloride__sub_e6vq6f2s3n.yaml
sub_e9e80d003a	Vitamin B3	intake	food_preferred	-	unassigned	-	-	likely migration loss	data/substances/vitamin_b3_niacin__sub_e9e80d003a.yaml	data/substances/vitamin_b3_niacin__sub_e9e80d003a.yaml
sub_edcaca3af0	Taurine	intake	empty_preferred	-	inactive	-	-	likely migration loss	data/substances/taurine__sub_edcaca3af0.yaml	data/substances/taurine__sub_edcaca3af0.yaml
sub_ege1asrt50	Passionflower	timing	sleep_support	-	inactive	-	-	likely migration loss	data/substances/passionflower_flowering_tops_extract__sub_ege1asrt50.yaml	data/substances/passionflower_flowering_tops_extract__sub_ege1asrt50.yaml
sub_f3uf30ibq7	Vitamin K2	intake	fat_meal_required	food_preferred	inactive	-	-	unassessed semantic change	data/substances/vitamin_k2_menaquinone_4_mk_4__sub_f3uf30ibq7.yaml	data/substances/vitamin_k2_menaquinone_4_mk_4__sub_f3uf30ibq7.yaml
sub_f7780f899b	Potassium	intake	food_preferred	-	training-reachable,inactive	insufficient	-	already explicitly assessed intentional change	data/substances/potassium_citrate__sub_f7780f899b.yaml	data/substances/potassium_citrate__sub_f7780f899b.yaml
sub_fd899525d3	Vitamin B7	intake	food_preferred	-	episodic-reachable,inactive	insufficient	-	already explicitly assessed intentional change	data/substances/vitamin_b7_biotin__sub_fd899525d3.yaml	data/substances/vitamin_b7_biotin__sub_fd899525d3.yaml
sub_fhl7c4skmf	Magnesium	intake	food_preferred	-	training-reachable,inactive	insufficient	-	already explicitly assessed intentional change	data/substances/magnesium_citrate__sub_fhl7c4skmf.yaml	data/substances/magnesium_citrate__sub_fhl7c4skmf.yaml
sub_fmuptat7pw	Betaine	intake	food_neutral	-	inactive	-	-	likely migration loss	data/substances/betaine_nitrate_no3_t__sub_fmuptat7pw.yaml	data/substances/betaine_nitrate_no3_t__sub_fmuptat7pw.yaml
sub_giy6ioeiyv	Fiber seed blend	intake	food_neutral	-	inactive	-	-	likely migration loss	data/substances/fiber_seed_blend__sub_giy6ioeiyv.yaml	data/substances/fiber_seed_blend__sub_giy6ioeiyv.yaml
sub_grely3rikd	Vitamin E	intake	food_required	food_preferred	inactive	-	-	unassessed semantic change	data/substances/vitamin_e_d_alpha_tocopheryl_succinate__sub_grely3rikd.yaml	data/substances/vitamin_e_d_alpha_tocopheryl_succinate__sub_grely3rikd.yaml
sub_hpqw0esbgo	Peppermint oil	intake	food_neutral	-	unassigned	-	-	likely migration loss	data/substances/peppermint_oil__sub_hpqw0esbgo.yaml	data/substances/peppermint_oil__sub_hpqw0esbgo.yaml
sub_ivywz0q6c6	Vitamin B12	intake	food_preferred	-	inactive	-	-	likely migration loss	data/substances/vitamin_b12_cyanocobalamin__sub_ivywz0q6c6.yaml	data/substances/vitamin_b12_cyanocobalamin__sub_ivywz0q6c6.yaml
sub_j92h8kgjru	Beetroot	intake	food_neutral	-	unassigned	-	-	likely migration loss	data/substances/beetroot_extract__sub_j92h8kgjru.yaml	data/substances/beetroot_extract__sub_j92h8kgjru.yaml
sub_j92h8kgjru	Beetroot	activity	pre_workout	-	unassigned	-	-	likely migration loss	data/substances/beetroot_extract__sub_j92h8kgjru.yaml	data/substances/beetroot_extract__sub_j92h8kgjru.yaml
sub_j9dhho47sz	Theobromine	intake	food_neutral	-	inactive	-	-	likely migration loss	data/substances/theobromine__sub_j9dhho47sz.yaml	data/substances/theobromine__sub_j9dhho47sz.yaml
sub_j9dhho47sz	Theobromine	timing	energy_like	-	inactive	-	-	likely migration loss	data/substances/theobromine__sub_j9dhho47sz.yaml	data/substances/theobromine__sub_j9dhho47sz.yaml
sub_jmyif2xwft	African Mango	intake	empty_preferred	-	inactive	-	-	likely migration loss	data/substances/african_mango_seed_extract_10_1__sub_jmyif2xwft.yaml	data/substances/african_mango_seed_extract_10_1__sub_jmyif2xwft.yaml
sub_knwnyl1a9i	Probiotic blend	intake	food_neutral	-	inactive	-	-	likely migration loss	data/substances/probiotic_blend__sub_knwnyl1a9i.yaml	data/substances/probiotic_blend__sub_knwnyl1a9i.yaml
sub_kpn178y211	Vitamin B1	intake	food_preferred	-	inactive	-	-	likely migration loss	data/substances/vitamin_b1_thiamine_cocarboxylase_chloride__sub_kpn178y211.yaml	data/substances/vitamin_b1_thiamine_cocarboxylase_chloride__sub_kpn178y211.yaml
sub_lte8wzk7uj	Vitamin B7	intake	food_preferred	-	inactive	-	-	likely migration loss	data/substances/vitamin_b7_d_biotin__sub_lte8wzk7uj.yaml	data/substances/vitamin_b7_d_biotin__sub_lte8wzk7uj.yaml
sub_mgr8d35crc	Vitamin B9	intake	food_preferred	-	inactive	-	-	likely migration loss	data/substances/vitamin_b9_folic_acid__sub_mgr8d35crc.yaml	data/substances/vitamin_b9_folic_acid__sub_mgr8d35crc.yaml
sub_mvdxnlmal7	Coenzyme Q10	intake	fat_meal_required	food_preferred	inactive	-	-	unassessed semantic change	data/substances/coenzyme_q10_ubiquinone__sub_mvdxnlmal7.yaml	data/substances/coenzyme_q10_ubiquinone__sub_mvdxnlmal7.yaml
sub_mzmh95u6ak	Mastic gum	intake	food_neutral	-	unassigned	-	-	likely migration loss	data/substances/mastic_gum__sub_mzmh95u6ak.yaml	data/substances/mastic_gum__sub_mzmh95u6ak.yaml
sub_p5qxdnxu9e	Calcium	intake	food_preferred	-	training-reachable	insufficient	-	already explicitly assessed intentional change	data/substances/calcium_lactate__sub_p5qxdnxu9e.yaml	data/substances/calcium_lactate__sub_p5qxdnxu9e.yaml
sub_prx6ddszzi	Black cohosh	intake	food_neutral	-	unassigned	-	-	likely migration loss	data/substances/black_cohosh_root_rhizome_extract__sub_prx6ddszzi.yaml	data/substances/black_cohosh_root_rhizome_extract__sub_prx6ddszzi.yaml
sub_qktkyyla88	Vitamin B2	intake	food_preferred	-	inactive	-	-	likely migration loss	data/substances/vitamin_b2_riboflavin_5_phosphate_r5p__sub_qktkyyla88.yaml	data/substances/vitamin_b2_riboflavin_5_phosphate_r5p__sub_qktkyyla88.yaml
sub_qxek07gry7	Lemon balm	timing	sleep_support	-	inactive	-	-	likely migration loss	data/substances/lemon_balm_herb__sub_qxek07gry7.yaml	data/substances/lemon_balm_herb__sub_qxek07gry7.yaml
sub_reiybxa1p9	African Mango	intake	food_neutral	-	inactive	-	-	likely migration loss	data/substances/african_mango_whole_seed_powder__sub_reiybxa1p9.yaml	data/substances/african_mango_whole_seed_powder__sub_reiybxa1p9.yaml
sub_rewtd3ei25	Zeaxanthin	intake	fat_meal_required	food_preferred	inactive	-	-	unassessed semantic change	data/substances/zeaxanthin_rr_zeaxanthin__sub_rewtd3ei25.yaml	data/substances/zeaxanthin_rr_zeaxanthin__sub_rewtd3ei25.yaml
sub_rgbq4w0gce	Coenzyme Q10	intake	fat_meal_required	food_preferred	unassigned	-	-	unassessed semantic change	data/substances/coenzyme_q10_ubiquinol__sub_rgbq4w0gce.yaml	data/substances/coenzyme_q10_ubiquinol__sub_rgbq4w0gce.yaml
sub_rt2lr29xqs	Dehydroepiandrosterone	timing	energy_like	-	unassigned	-	-	likely migration loss	data/substances/dehydroepiandrosterone__sub_rt2lr29xqs.yaml	data/substances/dehydroepiandrosterone__sub_rt2lr29xqs.yaml
sub_s7tlhuvbd0	Lutein	intake	fat_meal_required	food_preferred	inactive	-	-	unassessed semantic change	data/substances/lutein__sub_s7tlhuvbd0.yaml	data/substances/lutein__sub_s7tlhuvbd0.yaml
sub_sds0sup3nt	Vitamin A	intake	fat_meal_required	food_preferred	inactive	-	-	unassessed semantic change	data/substances/vitamin_a_beta_carotene__sub_sds0sup3nt.yaml	data/substances/vitamin_a_beta_carotene__sub_sds0sup3nt.yaml
sub_shib6nr9jc	Vitamin K2	intake	fat_meal_required	food_preferred	inactive	-	-	unassessed semantic change	data/substances/vitamin_k2_menaquinone_7_mk_7__sub_shib6nr9jc.yaml	data/substances/vitamin_k2_menaquinone_7_mk_7__sub_shib6nr9jc.yaml
sub_sterol0001	Plant sterols / stanols	intake	food_required	food_preferred	unassigned	-	-	unassessed semantic change	data/substances/plant_sterols_stanols__sub_sterol0001.yaml	data/substances/plant_sterols_stanols__sub_sterol0001.yaml
sub_sxc3zqhfsy	L-Arginine	activity	pre_workout	-	unassigned	-	-	likely migration loss	data/substances/l_arginine_alpha_ketoglutarate__sub_sxc3zqhfsy.yaml	data/substances/l_arginine_alpha_ketoglutarate__sub_sxc3zqhfsy.yaml
sub_tqihchk7rd	Sulfasalazine	intake	food_required	food_preferred	unassigned	-	-	unassessed semantic change	data/substances/sulfasalazine__sub_tqihchk7rd.yaml	data/substances/sulfasalazine__sub_tqihchk7rd.yaml
sub_u5q9oymhsu	GABA	intake	empty_preferred	-	inactive	-	-	likely migration loss	data/substances/gaba__sub_u5q9oymhsu.yaml	data/substances/gaba__sub_u5q9oymhsu.yaml
sub_u5q9oymhsu	GABA	timing	sleep_support	-	inactive	-	-	likely migration loss	data/substances/gaba__sub_u5q9oymhsu.yaml	data/substances/gaba__sub_u5q9oymhsu.yaml
sub_ud7grsqvtr	Echinacea	intake	food_neutral	-	unassigned	-	-	likely migration loss	data/substances/echinacea_extract__sub_ud7grsqvtr.yaml	data/substances/echinacea_extract__sub_ud7grsqvtr.yaml
sub_ug92bkq5dh	Midazolam	intake	food_neutral	-	unassigned	-	-	likely migration loss	data/substances/midazolam__sub_ug92bkq5dh.yaml	data/substances/midazolam__sub_ug92bkq5dh.yaml
sub_vkp4f3tqf0	L-Theanine	intake	food_neutral	-	inactive	-	-	likely migration loss	data/substances/l_theanine__sub_vkp4f3tqf0.yaml	data/substances/l_theanine__sub_vkp4f3tqf0.yaml
sub_vkp4f3tqf0	L-Theanine	timing	sleep_support	-	inactive	-	-	likely migration loss	data/substances/l_theanine__sub_vkp4f3tqf0.yaml	data/substances/l_theanine__sub_vkp4f3tqf0.yaml
sub_voxdkhm3ao	Rhodiola rosea	intake	empty_preferred	-	inactive	-	-	likely migration loss	data/substances/rhodiola_rosea_root_extract_standardized_to_3_salidrosides__sub_voxdkhm3ao.yaml	data/substances/rhodiola_rosea_root_extract_standardized_to_3_salidrosides__sub_voxdkhm3ao.yaml
sub_w6o6xv877y	Modafinil	timing	energy_like	-	unassigned	-	-	likely migration loss	data/substances/modafinil__sub_w6o6xv877y.yaml	data/substances/modafinil__sub_w6o6xv877y.yaml
sub_wnyygv7y7l	Vitamin B1	intake	food_preferred	-	inactive	-	-	likely migration loss	data/substances/vitamin_b1_thiamine_hcl__sub_wnyygv7y7l.yaml	data/substances/vitamin_b1_thiamine_hcl__sub_wnyygv7y7l.yaml
sub_x8fcy5ywxe	Vitamin B3	intake	food_preferred	-	inactive	-	-	likely migration loss	data/substances/vitamin_b3_niacinamide__sub_x8fcy5ywxe.yaml	data/substances/vitamin_b3_niacinamide__sub_x8fcy5ywxe.yaml
sub_xsqvv2fop0	Docosahexaenoic acid	intake	fat_meal_required	-	active-reachable,episodic-reachable,inactive,unassigned	insufficient	-	already explicitly assessed intentional change	data/substances/docosahexaenoic_acid__sub_xsqvv2fop0.yaml	data/substances/docosahexaenoic_acid__sub_xsqvv2fop0.yaml
sub_zhz9m31edv	Beta-hydroxy beta-methylbutyrate	intake	food_neutral	-	unassigned	-	-	likely migration loss	data/substances/beta_hydroxy_beta_methylbutyrate__sub_zhz9m31edv.yaml	data/substances/beta_hydroxy_beta_methylbutyrate__sub_zhz9m31edv.yaml
sub_zl8evocn9h	L-Tryptophan	timing	sleep_support	-	unassigned	-	-	likely migration loss	data/substances/l_tryptophan__sub_zl8evocn9h.yaml	data/substances/l_tryptophan__sub_zl8evocn9h.yaml
sub_zob4tacm2r	Vitamin B12	intake	food_preferred	-	inactive	-	-	likely migration loss	data/substances/vitamin_b12__sub_zob4tacm2r.yaml	data/substances/vitamin_b12__sub_zob4tacm2r.yaml
sub_zqfp9n314s	Methotrexate	intake	food_neutral	-	unassigned	-	-	likely migration loss	data/substances/methotrexate__sub_zqfp9n314s.yaml	data/substances/methotrexate__sub_zqfp9n314s.yaml
sub_zu1zthqo97	Beta-glucans	intake	empty_preferred	-	inactive	-	-	likely migration loss	data/substances/beta_glucans_beta_1_3_1_6_glucans__sub_zu1zthqo97.yaml	data/substances/beta_glucans_beta_1_3_1_6_glucans__sub_zu1zthqo97.yaml
```

### Machine-accounting checks

- Appendix rows: 120; classification totals: {'likely migration loss': 68, 'already explicitly assessed intentional change': 33, 'unassessed semantic change': 19}; axis totals: {'intake': 100, 'timing': 15, 'activity': 5}.
- Shared IDs: 252; baseline effective assertions: 249; feature effective assertions: 152.
- Current assessment axes across shared cards: 78; changed rows with assessment coverage: 33.
- Reachability and classification are intentionally source-derived; no ontology, data, Python, or schedule file was modified for this inventory.
