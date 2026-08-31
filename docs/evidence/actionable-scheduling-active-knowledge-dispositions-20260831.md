# Active structured-knowledge dispositions — 2026-08-31

## Scope and accounting

This is an evidence-only semantic adjudication of the current active shelf's
structured `knowledge` memberships. It is not runtime input, a fact catalog,
or an authorization to alter a schedule.

The active daily and training stacks contain 38 reachable substances. Their
memberships total **191** when deduplicated as `(substance_id, category,
value)`. They project to 220 composition-role occurrences because several
substances occur in more than one active product. The 191 identities are the
coverage unit below; a certificate must project each disposition to every
reachable composition role.

| Disposition | Count | Meaning in this record |
| --- | ---: | --- |
| `pressure` | 0 | No membership is itself an admitted scheduler fact or pairwise mechanism. |
| `neutral` (`N`) | 146 | A world fact or review context was assessed; it contains no direction on a scheduling axis. |
| `unresolved_without_direction` (`U`) | 24 | The exact assertion is `searched_insufficient` and records no direction. It remains visibly research-open but coverage-closed for its exact membership once its scope, provenance, and disposition validate. |
| `outside_model` (`O`) | 21 | Medication/safety/review material whose timing consequence would require prohibited clinical or treatment modelling. |

The exact category accounting is:

| Category | Total | N | U | O |
| --- | ---: | ---: | ---: | ---: |
| `kind` | 31 | 31 | 0 | 0 |
| `role` | 8 | 3 | 3 | 2 |
| `quality` | 12 | 12 | 0 | 0 |
| `effect` | 56 | 54 | 2 | 0 |
| `risk` | 19 | 0 | 0 | 19 |
| `pathway` | 27 | 27 | 0 | 0 |
| `context` | 38 | 19 | 19 | 0 |
| **Total** | **191** | **146** | **24** | **21** |

## Admission invariant

**None of the 191 memberships directly schedules.** A membership may preserve
identity, a physiological statement, a pathway, a quality, a risk, or review
context, but it has no typed temporal or pairwise consequence. It cannot enter
the objective unless a separately authored, individually adjudicated canonical
fact (or minimal pairwise world-fact mechanism) records exact applicability and
provenance, and a universal law derives one normalized pressure. In particular:

- `quality:fat_soluble` is not a `FoodEffect` and does not universally imply
  `with_food`.
- `context:sleep_recovery` is not an `AcuteSleepEffect`; `context` and
  `effect` labels do not assert acute timing.
- `context:workout_performance`, `role:ergogenic`, and
  `effect:exercise_recovery_support` do not state pre- or post-exercise timing.
- Every `risk:*` tag is medication/safety review material, not a pairwise
  separation rule or treatment model.
- The current relation vocabulary contains only passive `balance`, `supports`,
  and `co_use_context`; this matrix does not adjudicate `data/relations.yaml`.

## Exact membership matrix

Each semicolon-delimited entry is one distinct membership. `N`, `U`, and `O`
refer to the disposition table above.

```text
sub_249199f726 Astaxanthin (4): context:skin_support=U; kind:carotenoid=N; quality:fat_soluble=N; role:antioxidant=N
sub_25b049a598 Boron (2): effect:bone_mineral_metabolism_support=U; kind:mineral=N
sub_p5qxdnxu9e Calcium (5): context:workout_performance=U; effect:bone_mineral_metabolism_support=N; kind:mineral=N; pathway:vitamin_d_calcium_axis=N; quality:electrolyte=N
sub_iqjdo9gvbv Calcium (5): context:workout_performance=U; effect:bone_mineral_metabolism_support=N; kind:mineral=N; pathway:vitamin_d_calcium_axis=N; quality:electrolyte=N
sub_kwudyhex2o Choline (4): effect:cholinergic_support=N; effect:phospholipid_membrane_context=N; pathway:methylation_cycle=N; pathway:tmao_precursor=N
sub_ddf8d310d2 Chromium (2): kind:mineral=N; risk:glucose_med_interaction=O
sub_844a0cc551 Copper (6): context:connective_tissue_support=N; effect:antioxidant_enzyme_cofactor=N; effect:connective_tissue_synthesis_support=N; effect:iron_metabolism_support=N; kind:mineral=N; risk:narrow_therapeutic_window=O
sub_9c0908e7f7 Creatine (5): context:mitochondrial_health=N; context:workout_performance=N; effect:phosphocreatine_support=N; pathway:phosphocreatine_system=N; role:ergogenic=N
sub_xsqvv2fop0 Docosahexaenoic acid (7): context:skin_support=U; context:vascular_health=U; effect:platelet_aggregation_modulation=N; kind:omega3=N; pathway:omega3_eicosanoid=N; quality:fat_soluble=N; risk:bleeding_med_interaction=O
sub_66b783576c Eicosapentaenoic acid (7): context:skin_support=U; context:vascular_health=N; effect:platelet_aggregation_modulation=N; kind:omega3=N; pathway:omega3_eicosanoid=N; quality:fat_soluble=N; risk:bleeding_med_interaction=O
sub_sunkcr05vl Fish Oil Concentrate (4): kind:omega3=N; pathway:omega3_eicosanoid=N; quality:fat_soluble=N; risk:bleeding_med_interaction=O
sub_646e568f61 Krill Oil (7): context:skin_support=U; context:vascular_health=U; effect:platelet_aggregation_modulation=N; kind:omega3=N; pathway:omega3_eicosanoid=N; quality:fat_soluble=N; risk:bleeding_med_interaction=O
sub_5bd641c116 L-Carnitine (8): context:mitochondrial_health=N; context:workout_performance=U; effect:exercise_recovery_support=N; effect:mitochondrial_fatty_acid_transport=N; pathway:carnitine_shuttle=N; pathway:tmao_precursor=N; risk:tmao_cardiometabolic_review=O; role:ergogenic=U
sub_3918fe347e L-Citrulline (8): context:vascular_health=N; context:workout_performance=N; effect:nitric_oxide_support=N; effect:vasodilator=U; kind:amino=N; pathway:nitric_oxide_cgmp=N; risk:hypotension_med_interaction=O; role:ergogenic=U
sub_e3af6f78d9 Lion's Mane (4): context:neurocognitive_support=U; effect:immune_modulation_context=N; effect:neurotrophic_support=N; role:nootropic=U
sub_7e02eab0d1 Magnesium glycinate (5): context:sleep_recovery=N; effect:bone_mineral_metabolism_support=N; kind:mineral=N; pathway:vitamin_d_calcium_axis=N; quality:electrolyte=N
sub_fhl7c4skmf Magnesium citrate (5): context:workout_performance=U; effect:bone_mineral_metabolism_support=N; kind:mineral=N; pathway:vitamin_d_calcium_axis=N; quality:electrolyte=N
sub_7938ea248e Manganese (6): effect:amino_acid_metabolism_support=N; effect:antioxidant_enzyme_cofactor=N; effect:bone_mineral_metabolism_support=N; effect:carboxylase_cofactor=N; kind:mineral=N; risk:narrow_therapeutic_window=O
sub_c55378389c Molybdenum (2): effect:sulfur_amino_acid_metabolism=N; kind:mineral=N
sub_877c24aad4 Nattokinase (5): context:vascular_health=U; effect:fibrinolytic=N; kind:enzyme=N; pathway:fibrinolysis_coagulation=N; risk:bleeding_med_interaction=O
sub_396c221c31 Picamilon (5): context:neurocognitive_support=U; context:sleep_recovery=U; context:vascular_health=U; risk:manual_review=O; role:pharmaceutical=O
sub_f7780f899b Potassium (4): context:workout_performance=U; kind:mineral=N; quality:electrolyte=N; risk:hyperkalemia_med_interaction=O
sub_4j9fttkil9 Sodium (3): context:workout_performance=N; effect:fluid_balance_context=N; quality:electrolyte=N
sub_a3ec9f9c52 Tadalafil (6): context:vascular_health=N; effect:pde5_inhibition=N; effect:vasodilator=N; pathway:nitric_oxide_cgmp=N; risk:hypotension_med_interaction=O; role:pharmaceutical=O
sub_3e3b246a6f Vanadium (2): kind:mineral=N; risk:glucose_med_interaction=O
sub_230c5c820e Vitamin B1 (5): context:mitochondrial_health=N; context:neurocognitive_support=U; effect:cellular_function_support=N; kind:vitamin=N; pathway:thiamine_energy_metabolism=N
sub_157418854b Vitamin B12 (6): context:neurocognitive_support=U; effect:dna_synthesis_support=N; effect:nervous_system_support=N; effect:red_blood_cell_support=N; kind:vitamin=N; pathway:methylation_cycle=N
sub_67fc2be8aa Vitamin B2 (6): context:mitochondrial_health=N; effect:cellular_function_support=N; effect:nutrient_metabolism_support=N; kind:vitamin=N; pathway:flavin_redox=N; pathway:methylation_cycle=N
sub_6yp50f6ach Vitamin B3 (3): context:mitochondrial_health=N; kind:vitamin=N; pathway:nad_metabolism=N
sub_7628e4f478 Vitamin B5 (4): context:mitochondrial_health=N; effect:fatty_acid_metabolism_support=N; kind:vitamin=N; pathway:coa_metabolism=N
sub_799419116d Vitamin B6 (7): context:neurocognitive_support=N; effect:amino_acid_metabolism_support=N; effect:homocysteine_metabolism_support=N; effect:neurotransmitter_synthesis_support=N; kind:vitamin=N; pathway:methylation_cycle=N; risk:b6_neuropathy_long_term=O
sub_a873e428ee Vitamin B6 (7): context:neurocognitive_support=N; effect:amino_acid_metabolism_support=N; effect:homocysteine_metabolism_support=N; effect:neurotransmitter_synthesis_support=N; kind:vitamin=N; pathway:methylation_cycle=N; risk:b6_neuropathy_long_term=O
sub_meuw89u4ie Vitamin B6 (6): effect:amino_acid_metabolism_support=N; effect:homocysteine_metabolism_support=N; effect:neurotransmitter_synthesis_support=N; kind:vitamin=N; pathway:methylation_cycle=N; risk:b6_neuropathy_long_term=O
sub_fd899525d3 Vitamin B7 (4): effect:carboxylase_cofactor=N; effect:fatty_acid_metabolism_support=N; kind:vitamin=N; risk:biotin_lab_interference=O
sub_d0034bd130 Vitamin B9 (6): context:neurocognitive_support=U; effect:dna_synthesis_support=N; effect:homocysteine_metabolism_support=N; effect:red_blood_cell_support=N; kind:vitamin=N; pathway:methylation_cycle=N
sub_vcnaasc800 Vitamin C (4): context:connective_tissue_support=N; context:skin_support=N; kind:vitamin=N; role:antioxidant=N
sub_2476bf9d4b Vitamin D3 (5): effect:bone_mineral_metabolism_support=N; effect:calcium_absorption_support=N; kind:vitamin=N; pathway:vitamin_d_calcium_axis=N; quality:fat_soluble=N
sub_8ppxce3s17 Zinc (7): context:skin_support=N; effect:dna_synthesis_support=N; effect:immune_function_support=N; effect:protein_synthesis_support=N; effect:wound_healing_support=N; kind:mineral=N; risk:zinc_copper_balance_review=O
```

## Existing directed facts are separate inputs

The following four active unary pressures already have canonical typed facts
and universal law paths. They are not pressures derived from a membership in
the matrix above.

| Exact applicability | Fact | Law path |
| --- | --- | --- |
| `cmp_prd_eb6337a6dc__sub_2476bf9d4b` | `FoodEffect:bioavailability_increases` | `law_food_bioavailability_increases` -> `meal_context=with_food` |
| `cmp_prd_bb212cffc2__sub_67fc2be8aa` | `FoodEffect:bioavailability_increases` | `law_food_bioavailability_increases` -> `meal_context=with_food` |
| `cmp_prd_htuhz2s2gt__sub_sunkcr05vl` | `FoodEffect:bioavailability_increases` | `law_food_bioavailability_increases` -> `meal_context=with_food` |
| `cmp_prd_cfce0b36b6__sub_3918fe347e` | `PreExercisePerformanceEffect:performance_improves` | `law_pre_exercise_performance_improves` -> `exercise_anchor=before` |

## Excluded overlapping adjudications

The following are intentionally not decided by this record, because their
food/exercise semantics were assigned to other adjudicators. Their adjacent
memberships remain in the matrix and still do not themselves authorize a
pressure:

- Airboy nattokinase: `cmp_prd_175251bd63__sub_877c24aad4`.
- Astaxanthin: `cmp_prd_e5cc3b4e7c__sub_249199f726`,
  `cmp_prd_8mvv1w128a__sub_249199f726`, and
  `cmp_prd_w2s970gps4__sub_249199f726`.
- Psalae krill oil: `cmp_prd_w2s970gps4__sub_646e568f61`.
- Only Trace Minerals' product-level with-food instruction. It cannot be
  silently generalized to its seven component roles.
- LCLT: `cmp_prd_0e92bc1674__sub_5bd641c116`.
- All pairwise records in `data/relations.yaml`.

No disposition above implies a desired slot, pair preference, numeric weight,
or clinical/treatment advice.
