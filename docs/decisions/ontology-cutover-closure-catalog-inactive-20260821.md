# Ontology cutover closure — catalog and inactive schedule tail — 2026-08-21

## Decision

**Catalog/data-preservation criterion: BLOCK pending one bounded B5 portability decision.**

The three former daily products are accepted as intentional shelf-state changes, and
all three product cards and component facts remain present. The inactive/unassigned
schedule tail contains no new migration-loss class and is nonblocking under cutover
Criterion 2. The sole blocker in this closure is stricter than factual catalog
preservation: the feature intentionally removes the standalone calcium
D-pantothenate substance ID, so a future form-specific query/import cannot address
that stable form as its own substance identity. Product labels and notes preserve
the disclosed chemistry, but that is not yet a stable form mapping.

This is not a medical adjudication and does not authorize mass restoration of
historical schedule heuristics. No ontology, data, or Python repair was made:
the B5 change is an explicit canonical-consolidation design (repository commit
`923c862`), not a proven accidental edit; the blocker requires a portability
contract decision (family-plus-product form mapping versus a durable form identity).

## Evidence scope and source anchors

| Item | Repository evidence |
| --- | --- |
| Baseline | `origin/main@4abac57` |
| Feature catalog comparison | `docs/decisions/ontology-catalog-migration-inventory-20260821.md` (feature tree `70940b3`) |
| Shared schedule diff | `docs/decisions/ontology-schedule-semantic-diff-20260821.md` |
| Active/episodic/training adjudication | `docs/decisions/active-reachable-scheduling-adjudication-20260821.md` |
| Supported unassigned state | `data/stacks.yaml:23-25,31-32`; history `35dc1e7` is titled “Update active supplement shelf” |
| B5 consolidation | `923c862`: creates family card, remaps two product links, and preserves exact chemistry in Product labels/notes |
| Cutover acceptance | `docs/decisions/ontology-cutover-decision-20260821.md`, Criteria 2–3 |

## Three daily → tracked-unassigned products

Commit `35dc1e7` (an ancestor of the baseline) explicitly removes these three
IDs from `daily` while adding the replacement active shelf. The repository
contract defines omission from `daily`, `training`, and `inactive` as
tracked-unassigned for depleted, not-owned, reference, or candidate cards.
Therefore these are **intentional shelf changes**, not ontology deletion. The
per-product reason (depleted versus not-owned/reference) is not encoded and is
not needed to establish data preservation.

| Product ID | Card | Components retained on feature | Closure classification |
| --- | --- | --- | --- |
| `prd_27f7b85aa6` | Best Naturals Acetyl L-Carnitine (ALCAR) | `sub_97b0ff246a` | real shelf update; tracked-unassigned; nonblocking |
| `prd_c81eb18069` | Vitamir Lion’s Mane + B6 Complex | `sub_e3af6f78d9`, `sub_a873e428ee` | real shelf update; tracked-unassigned; nonblocking |
| `prd_7f04daf970` | Nature’s Truth Antarctic Krill Oil | `sub_646e568f61`, `sub_66b783576c`, `sub_xsqvv2fop0`, `sub_249199f726` | real shelf update; tracked-unassigned; nonblocking |

The cards remain addressable by stable `prd_*` ID, and the components listed above
remain in each current product card. The Vitamir note was normalized, but its
formula and component identities remain. This closes the prior “shelf omission
versus migration loss” uncertainty without claiming that these products should
be scheduled now.

## Vitamin B5 identity/data portability

| Check | Baseline | Feature | Verdict |
| --- | --- | --- | --- |
| Main-only form card | `sub_yd7dqo36dn`, Vitamin B5, form `calcium D-pantothenate`, aliases retained | absent as standalone card | stable form identity is not portable as its own substance ID |
| Canonical family card | `sub_7628e4f478`, form `pantothenic acid` | same stable ID, now explicitly a Vitamin B5 family card | intentional canonical consolidation |
| BioGrace `prd_8eff2491b7` | same family ID; label “кальция пантотенат 15 мг” | same family ID plus label/notes | factual product chemistry preserved |
| Opti-Men `prd_io1peb9syp` | component `sub_yd7dqo36dn`, label calcium D-pantothenate | component `sub_7628e4f478`, label unchanged | form fact preserved at Product level; stable form reference changed |
| BioCoenzymated B Complex `prd_qmgu4q8ipo` | component `sub_yd7dqo36dn`, label calcium D-pantothenate | component `sub_7628e4f478`, label plus explicit preservation note | form fact preserved at Product level; stable form reference changed |

The feature card itself states that calcium pantothenate, calcium
D-pantothenate, and pantethine are chemically distinct and that exact chemistry
is Product-level. Thus **factual data preservation is PASS**, but **strict
stable-form portability is BLOCK**: neither the family card nor a canonical
relation maps `sub_yd7dqo36dn` to a durable exact-form identity. This is a
known intentional consolidation, not a new inactive schedule-loss class. A
future cutover may clear the blocker by documenting a deterministic form
mapping accepted by the importer/query contract; this artifact does not choose
that design.

## Inactive/unassigned-only schedule changes: finite groups

All 88 rows below have current reachability limited to `inactive` and/or
`unassigned`; none is active-, episodic-, or training-reachable. They cannot
change the current generated product placements. Counts sum to 88. The
transition vocabulary is finite and entirely composed of already observed
removals or strength downgrades; there is **no NEW migration-loss class**.

| Group | Transition | Rows | Existing classification | Closure result |
| --- | --- | ---: | --- | --- |
| `intake_food_neutral_removed` — Meal-state neutralization/removal | `food_neutral → none` | 26 | legacy assertion removal; likely migration loss | No new class; inactive/unassigned only |
| `intake_food_preferred_removed` — Soft food-preference removal | `food_preferred → none` | 11 | 10 likely loss; 1 explicitly assessed neutral/unknown | No new class; inactive/unassigned only |
| `intake_empty_preferred_removed` — Empty-stomach preference removal | `empty_preferred → none` | 9 | legacy assertion removal; likely migration loss | No new class; inactive/unassigned only |
| `timing_sleep_support_removed` — Sleep-timing heuristic removal | `sleep_support → none` | 8 | legacy assertion removal; likely migration loss | No new class; inactive/unassigned only |
| `timing_energy_like_removed` — Energy-timing heuristic removal | `energy_like → none` | 6 | legacy assertion removal; likely migration loss | No new class; inactive/unassigned only |
| `activity_pre_workout_removed` — Workout-placement heuristic removal | `pre_workout → none` | 4 | legacy assertion removal; likely migration loss | No new class; inactive/unassigned only |
| `intake_food_required_removed` — Required-meal assertion removal | `food_required → none` | 3 | legacy assertion removal; likely migration loss | No new class; inactive/unassigned only |
| `intake_fat_meal_required_removed` — Required-fat-meal assertion removal | `fat_meal_required → none` | 2 | legacy assertion removal; likely migration loss | No new class; inactive/unassigned only |
| `intake_fat_required_to_food_preferred` — Required-fat downgrade | `fat_meal_required → food_preferred` | 12 | unassessed semantic change | No new class; inactive/unassigned only |
| `intake_food_required_to_food_preferred` — Required-meal downgrade | `food_required → food_preferred` | 7 | unassessed semantic change | No new class; inactive/unassigned only |
| **Total** |  | **88** | 68 likely losses; 19 unassessed; 1 explicitly assessed | **Nonblocking; review if a card is reactivated** |

Interpretation is intentionally operational: “likely migration loss” preserves
the source inventory label, but the cards are not restored automatically while
inactive/unassigned. The two downgrade groups are unassessed semantic changes,
not evidence of data deletion. The one explicitly assessed row is retained as
authored. Any future reactivation should trigger row-level adjudication before
placement.

## Machine-readable exhaustive appendix

Columns preserve the original source row and add closure classification. The
source appendix remains at
`docs/decisions/ontology-schedule-semantic-diff-20260821.md`; this table is the
88-row inactive/unassigned slice with finite pattern group labels.

```tsv
substance_id	name	axis	baseline_assertion	feature_assertion	current_reachability	assessment_conclusion	assessment_policy	classification	baseline_path	feature_path	pattern_group	closure_decision	blocking
sub_0jmfcyanzv	Omeprazole	intake	food_required	-	unassigned	-	-	likely migration loss	data/substances/omeprazole__sub_0jmfcyanzv.yaml	data/substances/omeprazole__sub_0jmfcyanzv.yaml	intake_food_required_removed	retain_inactive_tail; review_before_reactivation	nonblocking_inactive_tail
sub_1hhkguyz55	Vitamin K1	intake	fat_meal_required	food_preferred	inactive	-	-	unassessed semantic change	data/substances/vitamin_k1_phylloquinone__sub_1hhkguyz55.yaml	data/substances/vitamin_k1_phylloquinone__sub_1hhkguyz55.yaml	intake_fat_required_to_food_preferred	retain_inactive_tail; adjudicate_before_reactivation	nonblocking_inactive_tail
sub_262gmd1vf1	Zeaxanthin	intake	fat_meal_required	food_preferred	inactive	-	-	unassessed semantic change	data/substances/zeaxanthin__sub_262gmd1vf1.yaml	data/substances/zeaxanthin__sub_262gmd1vf1.yaml	intake_fat_required_to_food_preferred	retain_inactive_tail; adjudicate_before_reactivation	nonblocking_inactive_tail
sub_2gjf5yx7cz	Saccharomyces boulardii	intake	food_neutral	-	unassigned	-	-	likely migration loss	data/substances/saccharomyces_boulardii__sub_2gjf5yx7cz.yaml	data/substances/saccharomyces_boulardii__sub_2gjf5yx7cz.yaml	intake_food_neutral_removed	retain_inactive_tail; review_before_reactivation	nonblocking_inactive_tail
sub_2mn1uwrzi6	Lansoprazole	intake	food_required	-	unassigned	-	-	likely migration loss	data/substances/lansoprazole__sub_2mn1uwrzi6.yaml	data/substances/lansoprazole__sub_2mn1uwrzi6.yaml	intake_food_required_removed	retain_inactive_tail; review_before_reactivation	nonblocking_inactive_tail
sub_2preozf0up	Collagen peptides	intake	food_neutral	-	unassigned	-	-	likely migration loss	data/substances/collagen_peptides_hydrolyzed__sub_2preozf0up.yaml	data/substances/collagen_peptides_hydrolyzed__sub_2preozf0up.yaml	intake_food_neutral_removed	retain_inactive_tail; review_before_reactivation	nonblocking_inactive_tail
sub_2se61pa12m	Ranitidine	intake	food_neutral	-	unassigned	-	-	likely migration loss	data/substances/ranitidine__sub_2se61pa12m.yaml	data/substances/ranitidine__sub_2se61pa12m.yaml	intake_food_neutral_removed	retain_inactive_tail; review_before_reactivation	nonblocking_inactive_tail
sub_2wbcgb78qg	Aloe vera	intake	food_neutral	-	unassigned	-	-	likely migration loss	data/substances/aloe_vera__sub_2wbcgb78qg.yaml	data/substances/aloe_vera__sub_2wbcgb78qg.yaml	intake_food_neutral_removed	retain_inactive_tail; review_before_reactivation	nonblocking_inactive_tail
sub_31a1408cad	Vitamin A	intake	food_required	food_preferred	inactive	-	-	unassessed semantic change	data/substances/vitamin_a_retinol__sub_31a1408cad.yaml	data/substances/vitamin_a_retinol__sub_31a1408cad.yaml	intake_food_required_to_food_preferred	retain_inactive_tail; adjudicate_before_reactivation	nonblocking_inactive_tail
sub_3o2ay3a5so	Valerian	timing	sleep_support	-	inactive	-	-	likely migration loss	data/substances/valerian_root_extract__sub_3o2ay3a5so.yaml	data/substances/valerian_root_extract__sub_3o2ay3a5so.yaml	timing_sleep_support_removed	retain_inactive_tail; review_before_reactivation	nonblocking_inactive_tail
sub_3rxxtq14ns	Eurycoma longifolia	timing	energy_like	-	unassigned	-	-	likely migration loss	data/substances/eurycoma_longifolia_root_extract__sub_3rxxtq14ns.yaml	data/substances/eurycoma_longifolia_root_extract__sub_3rxxtq14ns.yaml	timing_energy_like_removed	retain_inactive_tail; review_before_reactivation	nonblocking_inactive_tail
sub_40cd4f33lo	Vitamin B1	intake	fat_meal_required	-	inactive	-	-	likely migration loss	data/substances/vitamin_b1_benfotiamine__sub_40cd4f33lo.yaml	data/substances/vitamin_b1_benfotiamine__sub_40cd4f33lo.yaml	intake_fat_meal_required_removed	retain_inactive_tail; review_before_reactivation	nonblocking_inactive_tail
sub_4lwevjtf97	Deglycyrrhizinated licorice	intake	food_preferred	-	unassigned	-	-	likely migration loss	data/substances/deglycyrrhizinated_licorice__sub_4lwevjtf97.yaml	data/substances/deglycyrrhizinated_licorice__sub_4lwevjtf97.yaml	intake_food_preferred_removed	retain_inactive_tail; review_before_reactivation	nonblocking_inactive_tail
sub_5723eafac4	Vitamin E	intake	fat_meal_required	food_preferred	inactive	-	-	unassessed semantic change	data/substances/vitamin_e_tocotrienols__sub_5723eafac4.yaml	data/substances/vitamin_e_tocotrienols__sub_5723eafac4.yaml	intake_fat_required_to_food_preferred	retain_inactive_tail; adjudicate_before_reactivation	nonblocking_inactive_tail
sub_5j1kg3bmgk	DMAE	intake	food_neutral	-	inactive	-	-	likely migration loss	data/substances/dmae_bitartrate__sub_5j1kg3bmgk.yaml	data/substances/dmae_bitartrate__sub_5j1kg3bmgk.yaml	intake_food_neutral_removed	retain_inactive_tail; review_before_reactivation	nonblocking_inactive_tail
sub_5j1kg3bmgk	DMAE	timing	energy_like	-	inactive	-	-	likely migration loss	data/substances/dmae_bitartrate__sub_5j1kg3bmgk.yaml	data/substances/dmae_bitartrate__sub_5j1kg3bmgk.yaml	timing_energy_like_removed	retain_inactive_tail; review_before_reactivation	nonblocking_inactive_tail
sub_605u9zvqt2	Metformin	intake	food_required	food_preferred	unassigned	-	-	unassessed semantic change	data/substances/metformin__sub_605u9zvqt2.yaml	data/substances/metformin__sub_605u9zvqt2.yaml	intake_food_required_to_food_preferred	retain_inactive_tail; adjudicate_before_reactivation	nonblocking_inactive_tail
sub_6n5okijhqz	Zeaxanthin	intake	fat_meal_required	food_preferred	inactive	-	-	unassessed semantic change	data/substances/zeaxanthin_meso_zeaxanthin__sub_6n5okijhqz.yaml	data/substances/zeaxanthin_meso_zeaxanthin__sub_6n5okijhqz.yaml	intake_fat_required_to_food_preferred	retain_inactive_tail; adjudicate_before_reactivation	nonblocking_inactive_tail
sub_6svt59zncl	5-HTP	intake	empty_preferred	-	inactive	-	-	likely migration loss	data/substances/5_htp_griffonia_simplicifolia_seed_extract__sub_6svt59zncl.yaml	data/substances/5_htp_griffonia_simplicifolia_seed_extract__sub_6svt59zncl.yaml	intake_empty_preferred_removed	retain_inactive_tail; review_before_reactivation	nonblocking_inactive_tail
sub_6svt59zncl	5-HTP	timing	sleep_support	-	inactive	-	-	likely migration loss	data/substances/5_htp_griffonia_simplicifolia_seed_extract__sub_6svt59zncl.yaml	data/substances/5_htp_griffonia_simplicifolia_seed_extract__sub_6svt59zncl.yaml	timing_sleep_support_removed	retain_inactive_tail; review_before_reactivation	nonblocking_inactive_tail
sub_6z3m3zbxgb	Melatonin	intake	empty_preferred	-	inactive	-	-	likely migration loss	data/substances/melatonin__sub_6z3m3zbxgb.yaml	data/substances/melatonin__sub_6z3m3zbxgb.yaml	intake_empty_preferred_removed	retain_inactive_tail; review_before_reactivation	nonblocking_inactive_tail
sub_7ehuhfcly5	Whey protein	intake	food_neutral	-	unassigned	-	-	likely migration loss	data/substances/whey_protein__sub_7ehuhfcly5.yaml	data/substances/whey_protein__sub_7ehuhfcly5.yaml	intake_food_neutral_removed	retain_inactive_tail; review_before_reactivation	nonblocking_inactive_tail
sub_7emxvn1qat	Caffeine	intake	food_neutral	-	inactive	-	-	likely migration loss	data/substances/caffeine_anhydrous__sub_7emxvn1qat.yaml	data/substances/caffeine_anhydrous__sub_7emxvn1qat.yaml	intake_food_neutral_removed	retain_inactive_tail; review_before_reactivation	nonblocking_inactive_tail
sub_7ozks6pos5	Nicotinamide mononucleotide	intake	food_neutral	-	unassigned	-	-	likely migration loss	data/substances/nicotinamide_mononucleotide__sub_7ozks6pos5.yaml	data/substances/nicotinamide_mononucleotide__sub_7ozks6pos5.yaml	intake_food_neutral_removed	retain_inactive_tail; review_before_reactivation	nonblocking_inactive_tail
sub_844a87d72b	Vitamin E	intake	food_required	food_preferred	inactive,unassigned	-	-	unassessed semantic change	data/substances/vitamin_e_tocopherol__sub_844a87d72b.yaml	data/substances/vitamin_e_tocopherol__sub_844a87d72b.yaml	intake_food_required_to_food_preferred	retain_inactive_tail; adjudicate_before_reactivation	nonblocking_inactive_tail
sub_8noiw2mhhb	Chasteberry	intake	food_neutral	-	unassigned	-	-	likely migration loss	data/substances/chasteberry_fruit_extract__sub_8noiw2mhhb.yaml	data/substances/chasteberry_fruit_extract__sub_8noiw2mhhb.yaml	intake_food_neutral_removed	retain_inactive_tail; review_before_reactivation	nonblocking_inactive_tail
sub_8wi86qpvwi	Lavender	intake	food_neutral	-	inactive	-	-	likely migration loss	data/substances/lavender_flower__sub_8wi86qpvwi.yaml	data/substances/lavender_flower__sub_8wi86qpvwi.yaml	intake_food_neutral_removed	retain_inactive_tail; review_before_reactivation	nonblocking_inactive_tail
sub_8wi86qpvwi	Lavender	timing	sleep_support	-	inactive	-	-	likely migration loss	data/substances/lavender_flower__sub_8wi86qpvwi.yaml	data/substances/lavender_flower__sub_8wi86qpvwi.yaml	timing_sleep_support_removed	retain_inactive_tail; review_before_reactivation	nonblocking_inactive_tail
sub_96owcg92uf	Lycopene	intake	fat_meal_required	food_preferred	inactive	-	-	unassessed semantic change	data/substances/lycopene__sub_96owcg92uf.yaml	data/substances/lycopene__sub_96owcg92uf.yaml	intake_fat_required_to_food_preferred	retain_inactive_tail; adjudicate_before_reactivation	nonblocking_inactive_tail
sub_97b0ff246a	L-Carnitine	intake	empty_preferred	-	unassigned	-	-	likely migration loss	data/substances/l_carnitine_acetyl__sub_97b0ff246a.yaml	data/substances/l_carnitine_acetyl__sub_97b0ff246a.yaml	intake_empty_preferred_removed	retain_inactive_tail; review_before_reactivation	nonblocking_inactive_tail
sub_97b0ff246a	L-Carnitine	timing	energy_like	-	unassigned	-	-	likely migration loss	data/substances/l_carnitine_acetyl__sub_97b0ff246a.yaml	data/substances/l_carnitine_acetyl__sub_97b0ff246a.yaml	timing_energy_like_removed	retain_inactive_tail; review_before_reactivation	nonblocking_inactive_tail
sub_a873e428ee	Vitamin B6	intake	food_preferred	-	inactive,unassigned	insufficient	-	already explicitly assessed intentional change	data/substances/vitamin_b6_pyridoxine_hcl__sub_a873e428ee.yaml	data/substances/vitamin_b6_pyridoxine_hcl__sub_a873e428ee.yaml	intake_food_preferred_removed	retain_current; already_assessed	nonblocking_inactive_tail
sub_abb9604e58	Beta-alanine	activity	pre_workout	-	inactive	-	-	likely migration loss	data/substances/beta_alanine__sub_abb9604e58.yaml	data/substances/beta_alanine__sub_abb9604e58.yaml	activity_pre_workout_removed	retain_inactive_tail; review_before_reactivation	nonblocking_inactive_tail
sub_b7vnosy4h8	HICA	activity	pre_workout	-	inactive	-	-	likely migration loss	data/substances/hica_alpha_hydroxyisocaproic_acid__sub_b7vnosy4h8.yaml	data/substances/hica_alpha_hydroxyisocaproic_acid__sub_b7vnosy4h8.yaml	activity_pre_workout_removed	retain_inactive_tail; review_before_reactivation	nonblocking_inactive_tail
sub_c36e075c09	Red yeast rice	intake	food_required	-	unassigned	-	-	likely migration loss	data/substances/red_yeast_rice__sub_c36e075c09.yaml	data/substances/red_yeast_rice__sub_c36e075c09.yaml	intake_food_required_removed	retain_inactive_tail; review_before_reactivation	nonblocking_inactive_tail
sub_c9720c7240	Glycine	intake	empty_preferred	-	inactive	-	-	likely migration loss	data/substances/glycine__sub_c9720c7240.yaml	data/substances/glycine__sub_c9720c7240.yaml	intake_empty_preferred_removed	retain_inactive_tail; review_before_reactivation	nonblocking_inactive_tail
sub_dcxfwd4udf	Phosphatidylcholine	intake	fat_meal_required	-	inactive	-	-	likely migration loss	data/substances/phosphatidylcholine__sub_dcxfwd4udf.yaml	data/substances/phosphatidylcholine__sub_dcxfwd4udf.yaml	intake_fat_meal_required_removed	retain_inactive_tail; review_before_reactivation	nonblocking_inactive_tail
sub_dopjesesge	Elderberry	intake	food_neutral	-	unassigned	-	-	likely migration loss	data/substances/elderberry_extract__sub_dopjesesge.yaml	data/substances/elderberry_extract__sub_dopjesesge.yaml	intake_food_neutral_removed	retain_inactive_tail; review_before_reactivation	nonblocking_inactive_tail
sub_dznuinvc2n	Cimetidine	intake	food_neutral	-	unassigned	-	-	likely migration loss	data/substances/cimetidine__sub_dznuinvc2n.yaml	data/substances/cimetidine__sub_dznuinvc2n.yaml	intake_food_neutral_removed	retain_inactive_tail; review_before_reactivation	nonblocking_inactive_tail
sub_e6vq6f2s3n	Betaine hydrochloride	intake	food_required	food_preferred	unassigned	-	-	unassessed semantic change	data/substances/betaine_hydrochloride__sub_e6vq6f2s3n.yaml	data/substances/betaine_hydrochloride__sub_e6vq6f2s3n.yaml	intake_food_required_to_food_preferred	retain_inactive_tail; adjudicate_before_reactivation	nonblocking_inactive_tail
sub_e9e80d003a	Vitamin B3	intake	food_preferred	-	unassigned	-	-	likely migration loss	data/substances/vitamin_b3_niacin__sub_e9e80d003a.yaml	data/substances/vitamin_b3_niacin__sub_e9e80d003a.yaml	intake_food_preferred_removed	retain_inactive_tail; review_before_reactivation	nonblocking_inactive_tail
sub_edcaca3af0	Taurine	intake	empty_preferred	-	inactive	-	-	likely migration loss	data/substances/taurine__sub_edcaca3af0.yaml	data/substances/taurine__sub_edcaca3af0.yaml	intake_empty_preferred_removed	retain_inactive_tail; review_before_reactivation	nonblocking_inactive_tail
sub_ege1asrt50	Passionflower	timing	sleep_support	-	inactive	-	-	likely migration loss	data/substances/passionflower_flowering_tops_extract__sub_ege1asrt50.yaml	data/substances/passionflower_flowering_tops_extract__sub_ege1asrt50.yaml	timing_sleep_support_removed	retain_inactive_tail; review_before_reactivation	nonblocking_inactive_tail
sub_f3uf30ibq7	Vitamin K2	intake	fat_meal_required	food_preferred	inactive	-	-	unassessed semantic change	data/substances/vitamin_k2_menaquinone_4_mk_4__sub_f3uf30ibq7.yaml	data/substances/vitamin_k2_menaquinone_4_mk_4__sub_f3uf30ibq7.yaml	intake_fat_required_to_food_preferred	retain_inactive_tail; adjudicate_before_reactivation	nonblocking_inactive_tail
sub_fmuptat7pw	Betaine	intake	food_neutral	-	inactive	-	-	likely migration loss	data/substances/betaine_nitrate_no3_t__sub_fmuptat7pw.yaml	data/substances/betaine_nitrate_no3_t__sub_fmuptat7pw.yaml	intake_food_neutral_removed	retain_inactive_tail; review_before_reactivation	nonblocking_inactive_tail
sub_giy6ioeiyv	Fiber seed blend	intake	food_neutral	-	inactive	-	-	likely migration loss	data/substances/fiber_seed_blend__sub_giy6ioeiyv.yaml	data/substances/fiber_seed_blend__sub_giy6ioeiyv.yaml	intake_food_neutral_removed	retain_inactive_tail; review_before_reactivation	nonblocking_inactive_tail
sub_grely3rikd	Vitamin E	intake	food_required	food_preferred	inactive	-	-	unassessed semantic change	data/substances/vitamin_e_d_alpha_tocopheryl_succinate__sub_grely3rikd.yaml	data/substances/vitamin_e_d_alpha_tocopheryl_succinate__sub_grely3rikd.yaml	intake_food_required_to_food_preferred	retain_inactive_tail; adjudicate_before_reactivation	nonblocking_inactive_tail
sub_hpqw0esbgo	Peppermint oil	intake	food_neutral	-	unassigned	-	-	likely migration loss	data/substances/peppermint_oil__sub_hpqw0esbgo.yaml	data/substances/peppermint_oil__sub_hpqw0esbgo.yaml	intake_food_neutral_removed	retain_inactive_tail; review_before_reactivation	nonblocking_inactive_tail
sub_ivywz0q6c6	Vitamin B12	intake	food_preferred	-	inactive	-	-	likely migration loss	data/substances/vitamin_b12_cyanocobalamin__sub_ivywz0q6c6.yaml	data/substances/vitamin_b12_cyanocobalamin__sub_ivywz0q6c6.yaml	intake_food_preferred_removed	retain_inactive_tail; review_before_reactivation	nonblocking_inactive_tail
sub_j92h8kgjru	Beetroot	intake	food_neutral	-	unassigned	-	-	likely migration loss	data/substances/beetroot_extract__sub_j92h8kgjru.yaml	data/substances/beetroot_extract__sub_j92h8kgjru.yaml	intake_food_neutral_removed	retain_inactive_tail; review_before_reactivation	nonblocking_inactive_tail
sub_j92h8kgjru	Beetroot	activity	pre_workout	-	unassigned	-	-	likely migration loss	data/substances/beetroot_extract__sub_j92h8kgjru.yaml	data/substances/beetroot_extract__sub_j92h8kgjru.yaml	activity_pre_workout_removed	retain_inactive_tail; review_before_reactivation	nonblocking_inactive_tail
sub_j9dhho47sz	Theobromine	intake	food_neutral	-	inactive	-	-	likely migration loss	data/substances/theobromine__sub_j9dhho47sz.yaml	data/substances/theobromine__sub_j9dhho47sz.yaml	intake_food_neutral_removed	retain_inactive_tail; review_before_reactivation	nonblocking_inactive_tail
sub_j9dhho47sz	Theobromine	timing	energy_like	-	inactive	-	-	likely migration loss	data/substances/theobromine__sub_j9dhho47sz.yaml	data/substances/theobromine__sub_j9dhho47sz.yaml	timing_energy_like_removed	retain_inactive_tail; review_before_reactivation	nonblocking_inactive_tail
sub_jmyif2xwft	African Mango	intake	empty_preferred	-	inactive	-	-	likely migration loss	data/substances/african_mango_seed_extract_10_1__sub_jmyif2xwft.yaml	data/substances/african_mango_seed_extract_10_1__sub_jmyif2xwft.yaml	intake_empty_preferred_removed	retain_inactive_tail; review_before_reactivation	nonblocking_inactive_tail
sub_knwnyl1a9i	Probiotic blend	intake	food_neutral	-	inactive	-	-	likely migration loss	data/substances/probiotic_blend__sub_knwnyl1a9i.yaml	data/substances/probiotic_blend__sub_knwnyl1a9i.yaml	intake_food_neutral_removed	retain_inactive_tail; review_before_reactivation	nonblocking_inactive_tail
sub_kpn178y211	Vitamin B1	intake	food_preferred	-	inactive	-	-	likely migration loss	data/substances/vitamin_b1_thiamine_cocarboxylase_chloride__sub_kpn178y211.yaml	data/substances/vitamin_b1_thiamine_cocarboxylase_chloride__sub_kpn178y211.yaml	intake_food_preferred_removed	retain_inactive_tail; review_before_reactivation	nonblocking_inactive_tail
sub_lte8wzk7uj	Vitamin B7	intake	food_preferred	-	inactive	-	-	likely migration loss	data/substances/vitamin_b7_d_biotin__sub_lte8wzk7uj.yaml	data/substances/vitamin_b7_d_biotin__sub_lte8wzk7uj.yaml	intake_food_preferred_removed	retain_inactive_tail; review_before_reactivation	nonblocking_inactive_tail
sub_mgr8d35crc	Vitamin B9	intake	food_preferred	-	inactive	-	-	likely migration loss	data/substances/vitamin_b9_folic_acid__sub_mgr8d35crc.yaml	data/substances/vitamin_b9_folic_acid__sub_mgr8d35crc.yaml	intake_food_preferred_removed	retain_inactive_tail; review_before_reactivation	nonblocking_inactive_tail
sub_mvdxnlmal7	Coenzyme Q10	intake	fat_meal_required	food_preferred	inactive	-	-	unassessed semantic change	data/substances/coenzyme_q10_ubiquinone__sub_mvdxnlmal7.yaml	data/substances/coenzyme_q10_ubiquinone__sub_mvdxnlmal7.yaml	intake_fat_required_to_food_preferred	retain_inactive_tail; adjudicate_before_reactivation	nonblocking_inactive_tail
sub_mzmh95u6ak	Mastic gum	intake	food_neutral	-	unassigned	-	-	likely migration loss	data/substances/mastic_gum__sub_mzmh95u6ak.yaml	data/substances/mastic_gum__sub_mzmh95u6ak.yaml	intake_food_neutral_removed	retain_inactive_tail; review_before_reactivation	nonblocking_inactive_tail
sub_prx6ddszzi	Black cohosh	intake	food_neutral	-	unassigned	-	-	likely migration loss	data/substances/black_cohosh_root_rhizome_extract__sub_prx6ddszzi.yaml	data/substances/black_cohosh_root_rhizome_extract__sub_prx6ddszzi.yaml	intake_food_neutral_removed	retain_inactive_tail; review_before_reactivation	nonblocking_inactive_tail
sub_qktkyyla88	Vitamin B2	intake	food_preferred	-	inactive	-	-	likely migration loss	data/substances/vitamin_b2_riboflavin_5_phosphate_r5p__sub_qktkyyla88.yaml	data/substances/vitamin_b2_riboflavin_5_phosphate_r5p__sub_qktkyyla88.yaml	intake_food_preferred_removed	retain_inactive_tail; review_before_reactivation	nonblocking_inactive_tail
sub_qxek07gry7	Lemon balm	timing	sleep_support	-	inactive	-	-	likely migration loss	data/substances/lemon_balm_herb__sub_qxek07gry7.yaml	data/substances/lemon_balm_herb__sub_qxek07gry7.yaml	timing_sleep_support_removed	retain_inactive_tail; review_before_reactivation	nonblocking_inactive_tail
sub_reiybxa1p9	African Mango	intake	food_neutral	-	inactive	-	-	likely migration loss	data/substances/african_mango_whole_seed_powder__sub_reiybxa1p9.yaml	data/substances/african_mango_whole_seed_powder__sub_reiybxa1p9.yaml	intake_food_neutral_removed	retain_inactive_tail; review_before_reactivation	nonblocking_inactive_tail
sub_rewtd3ei25	Zeaxanthin	intake	fat_meal_required	food_preferred	inactive	-	-	unassessed semantic change	data/substances/zeaxanthin_rr_zeaxanthin__sub_rewtd3ei25.yaml	data/substances/zeaxanthin_rr_zeaxanthin__sub_rewtd3ei25.yaml	intake_fat_required_to_food_preferred	retain_inactive_tail; adjudicate_before_reactivation	nonblocking_inactive_tail
sub_rgbq4w0gce	Coenzyme Q10	intake	fat_meal_required	food_preferred	unassigned	-	-	unassessed semantic change	data/substances/coenzyme_q10_ubiquinol__sub_rgbq4w0gce.yaml	data/substances/coenzyme_q10_ubiquinol__sub_rgbq4w0gce.yaml	intake_fat_required_to_food_preferred	retain_inactive_tail; adjudicate_before_reactivation	nonblocking_inactive_tail
sub_rt2lr29xqs	Dehydroepiandrosterone	timing	energy_like	-	unassigned	-	-	likely migration loss	data/substances/dehydroepiandrosterone__sub_rt2lr29xqs.yaml	data/substances/dehydroepiandrosterone__sub_rt2lr29xqs.yaml	timing_energy_like_removed	retain_inactive_tail; review_before_reactivation	nonblocking_inactive_tail
sub_s7tlhuvbd0	Lutein	intake	fat_meal_required	food_preferred	inactive	-	-	unassessed semantic change	data/substances/lutein__sub_s7tlhuvbd0.yaml	data/substances/lutein__sub_s7tlhuvbd0.yaml	intake_fat_required_to_food_preferred	retain_inactive_tail; adjudicate_before_reactivation	nonblocking_inactive_tail
sub_sds0sup3nt	Vitamin A	intake	fat_meal_required	food_preferred	inactive	-	-	unassessed semantic change	data/substances/vitamin_a_beta_carotene__sub_sds0sup3nt.yaml	data/substances/vitamin_a_beta_carotene__sub_sds0sup3nt.yaml	intake_fat_required_to_food_preferred	retain_inactive_tail; adjudicate_before_reactivation	nonblocking_inactive_tail
sub_shib6nr9jc	Vitamin K2	intake	fat_meal_required	food_preferred	inactive	-	-	unassessed semantic change	data/substances/vitamin_k2_menaquinone_7_mk_7__sub_shib6nr9jc.yaml	data/substances/vitamin_k2_menaquinone_7_mk_7__sub_shib6nr9jc.yaml	intake_fat_required_to_food_preferred	retain_inactive_tail; adjudicate_before_reactivation	nonblocking_inactive_tail
sub_sterol0001	Plant sterols / stanols	intake	food_required	food_preferred	unassigned	-	-	unassessed semantic change	data/substances/plant_sterols_stanols__sub_sterol0001.yaml	data/substances/plant_sterols_stanols__sub_sterol0001.yaml	intake_food_required_to_food_preferred	retain_inactive_tail; adjudicate_before_reactivation	nonblocking_inactive_tail
sub_sxc3zqhfsy	L-Arginine	activity	pre_workout	-	unassigned	-	-	likely migration loss	data/substances/l_arginine_alpha_ketoglutarate__sub_sxc3zqhfsy.yaml	data/substances/l_arginine_alpha_ketoglutarate__sub_sxc3zqhfsy.yaml	activity_pre_workout_removed	retain_inactive_tail; review_before_reactivation	nonblocking_inactive_tail
sub_tqihchk7rd	Sulfasalazine	intake	food_required	food_preferred	unassigned	-	-	unassessed semantic change	data/substances/sulfasalazine__sub_tqihchk7rd.yaml	data/substances/sulfasalazine__sub_tqihchk7rd.yaml	intake_food_required_to_food_preferred	retain_inactive_tail; adjudicate_before_reactivation	nonblocking_inactive_tail
sub_u5q9oymhsu	GABA	intake	empty_preferred	-	inactive	-	-	likely migration loss	data/substances/gaba__sub_u5q9oymhsu.yaml	data/substances/gaba__sub_u5q9oymhsu.yaml	intake_empty_preferred_removed	retain_inactive_tail; review_before_reactivation	nonblocking_inactive_tail
sub_u5q9oymhsu	GABA	timing	sleep_support	-	inactive	-	-	likely migration loss	data/substances/gaba__sub_u5q9oymhsu.yaml	data/substances/gaba__sub_u5q9oymhsu.yaml	timing_sleep_support_removed	retain_inactive_tail; review_before_reactivation	nonblocking_inactive_tail
sub_ud7grsqvtr	Echinacea	intake	food_neutral	-	unassigned	-	-	likely migration loss	data/substances/echinacea_extract__sub_ud7grsqvtr.yaml	data/substances/echinacea_extract__sub_ud7grsqvtr.yaml	intake_food_neutral_removed	retain_inactive_tail; review_before_reactivation	nonblocking_inactive_tail
sub_ug92bkq5dh	Midazolam	intake	food_neutral	-	unassigned	-	-	likely migration loss	data/substances/midazolam__sub_ug92bkq5dh.yaml	data/substances/midazolam__sub_ug92bkq5dh.yaml	intake_food_neutral_removed	retain_inactive_tail; review_before_reactivation	nonblocking_inactive_tail
sub_vkp4f3tqf0	L-Theanine	intake	food_neutral	-	inactive	-	-	likely migration loss	data/substances/l_theanine__sub_vkp4f3tqf0.yaml	data/substances/l_theanine__sub_vkp4f3tqf0.yaml	intake_food_neutral_removed	retain_inactive_tail; review_before_reactivation	nonblocking_inactive_tail
sub_vkp4f3tqf0	L-Theanine	timing	sleep_support	-	inactive	-	-	likely migration loss	data/substances/l_theanine__sub_vkp4f3tqf0.yaml	data/substances/l_theanine__sub_vkp4f3tqf0.yaml	timing_sleep_support_removed	retain_inactive_tail; review_before_reactivation	nonblocking_inactive_tail
sub_voxdkhm3ao	Rhodiola rosea	intake	empty_preferred	-	inactive	-	-	likely migration loss	data/substances/rhodiola_rosea_root_extract_standardized_to_3_salidrosides__sub_voxdkhm3ao.yaml	data/substances/rhodiola_rosea_root_extract_standardized_to_3_salidrosides__sub_voxdkhm3ao.yaml	intake_empty_preferred_removed	retain_inactive_tail; review_before_reactivation	nonblocking_inactive_tail
sub_w6o6xv877y	Modafinil	timing	energy_like	-	unassigned	-	-	likely migration loss	data/substances/modafinil__sub_w6o6xv877y.yaml	data/substances/modafinil__sub_w6o6xv877y.yaml	timing_energy_like_removed	retain_inactive_tail; review_before_reactivation	nonblocking_inactive_tail
sub_wnyygv7y7l	Vitamin B1	intake	food_preferred	-	inactive	-	-	likely migration loss	data/substances/vitamin_b1_thiamine_hcl__sub_wnyygv7y7l.yaml	data/substances/vitamin_b1_thiamine_hcl__sub_wnyygv7y7l.yaml	intake_food_preferred_removed	retain_inactive_tail; review_before_reactivation	nonblocking_inactive_tail
sub_x8fcy5ywxe	Vitamin B3	intake	food_preferred	-	inactive	-	-	likely migration loss	data/substances/vitamin_b3_niacinamide__sub_x8fcy5ywxe.yaml	data/substances/vitamin_b3_niacinamide__sub_x8fcy5ywxe.yaml	intake_food_preferred_removed	retain_inactive_tail; review_before_reactivation	nonblocking_inactive_tail
sub_zhz9m31edv	Beta-hydroxy beta-methylbutyrate	intake	food_neutral	-	unassigned	-	-	likely migration loss	data/substances/beta_hydroxy_beta_methylbutyrate__sub_zhz9m31edv.yaml	data/substances/beta_hydroxy_beta_methylbutyrate__sub_zhz9m31edv.yaml	intake_food_neutral_removed	retain_inactive_tail; review_before_reactivation	nonblocking_inactive_tail
sub_zl8evocn9h	L-Tryptophan	timing	sleep_support	-	unassigned	-	-	likely migration loss	data/substances/l_tryptophan__sub_zl8evocn9h.yaml	data/substances/l_tryptophan__sub_zl8evocn9h.yaml	timing_sleep_support_removed	retain_inactive_tail; review_before_reactivation	nonblocking_inactive_tail
sub_zob4tacm2r	Vitamin B12	intake	food_preferred	-	inactive	-	-	likely migration loss	data/substances/vitamin_b12__sub_zob4tacm2r.yaml	data/substances/vitamin_b12__sub_zob4tacm2r.yaml	intake_food_preferred_removed	retain_inactive_tail; review_before_reactivation	nonblocking_inactive_tail
sub_zqfp9n314s	Methotrexate	intake	food_neutral	-	unassigned	-	-	likely migration loss	data/substances/methotrexate__sub_zqfp9n314s.yaml	data/substances/methotrexate__sub_zqfp9n314s.yaml	intake_food_neutral_removed	retain_inactive_tail; review_before_reactivation	nonblocking_inactive_tail
sub_zu1zthqo97	Beta-glucans	intake	empty_preferred	-	inactive	-	-	likely migration loss	data/substances/beta_glucans_beta_1_3_1_6_glucans__sub_zu1zthqo97.yaml	data/substances/beta_glucans_beta_1_3_1_6_glucans__sub_zu1zthqo97.yaml	intake_empty_preferred_removed	retain_inactive_tail; review_before_reactivation	nonblocking_inactive_tail
```

## Closure accounting

- Source shared schedule diff: 120 changed rows; 32 active/episodic/training-reachable
  rows are fully adjudicated in the active artifact; 88 rows are this inactive/
  unassigned tail.
- Inactive-tail classifications: 68 likely migration losses, 19 unassessed
  semantic changes, 1 already explicitly assessed intentional change.
- Inactive-tail pattern groups: 10; all are old-vocabulary assertion removal or
  downgrade patterns; no new migration-loss class.
- Product catalog: all 59 baseline product IDs remain; four feature-only product
  additions are recorded by the catalog inventory; three former daily products
  are intentionally tracked-unassigned.
- Overall catalog/data-preservation status remains **BLOCK** only because the
  mandatory stable-form portability requirement is unresolved for B5. There is
  no separate product-card deletion or inactive-tail blocker.
