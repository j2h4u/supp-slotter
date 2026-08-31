# Actionable Scheduling Note Candidates 035--050 — 2026-08-31

## Status and scope

**Accepted semantic adjudication.** This is the complete, queue-ordered
disposition record for exactly records 35 through 50 of the
[source-span candidate queue](../evidence/actionable-scheduling-note-candidate-queue-20260831.jsonl).
It is a V-left decision only. It neither alters the queue nor authors data,
facts, laws, a schedule, a certificate, a placement, an action, a weight, or
clinical/dose semantics.

The governing contracts are the [domain model](../domain-model.md), the
[canonical-instance inference boundary](canonical-instance-inference-boundary-20260822.md),
and the [actionable-knowledge coverage boundary](actionable-scheduling-knowledge-coverage-boundary-20260831.md).
In particular, the source queue identifies every record in this slice as a
substance note with `active_shelf_reachable: false`, no composition-role IDs,
and no product IDs. That absence is preserved below; it cannot be repaired by
generalising to all roles of the substance.

`pressure` is absent from this slice. A weak direction would still be one
unweighted pressure before balance *if* it supplied exact applicability and an
admitted fact value with a universal-law path. None does: no source claim here
supports an exact, non-generalised closed fact. This conclusion does not alter
the existing role-scoped Solgar fish-oil fact or any prior food/exercise
decision.

## Complete disposition ledger

| Queue | Candidate ID | Subject and immutable source provenance | Disposition | Individual adjudication |
| ---: | --- | --- | --- | --- |
| 35 | `cand_note_2820c8320c617329ee64f9c9eb33f3e4ca2dc26a19f4d0f51d70b0395df27968` | `sub_6tk5moz0wh`; [`bromelain` notes](../../data/substances/bromelain__sub_6tk5moz0wh.yaml), lines 6--8; span `6d0e2b786757a30bc4cd4487841537fe3fc7c15cfdcf89476b6da59b5ca719d8` | `outside_model` | The empty-stomach wording is conditional on pursuing a systemic anti-inflammatory outcome, while the same span separately reports a meal-associated digestive purpose. Those intended outcomes and product practice are neither a world fact in the five closed families nor a modelled applicability selector. Encoding either would add treatment/purpose semantics and manufacture an unconditional `without_food` fact. |
| 36 | `cand_note_3cdab89e570d5a766392a5b2d2c71ec62ed1d88b88c0bef8d11a11661cf0eb96` | `sub_6tk5moz0wh`; [`bromelain` notes](../../data/substances/bromelain__sub_6tk5moz0wh.yaml), lines 6--8; same span `6d0e2b786757a30bc4cd4487841537fe3fc7c15cfdcf89476b6da59b5ca719d8` | `outside_model` | This is likewise purpose-dependent (digestive support), not a food effect with an exact applicability scope. It cannot turn the Animal Flex package instruction into a substance-wide `with_food` pressure or resolve the purpose-conditioned opposite wording in record 35. |
| 37 | `cand_note_0c26f105bf8fb918c3469fd5d5fbab23a83e011ae3f200051b807f192e42a1c0` | `sub_iqjdo9gvbv`; [`dicalcium-phosphate calcium` notes](../../data/substances/calcium_dicalcium_phosphate__sub_iqjdo9gvbv.yaml), lines 4--11; span `3df08ef1f0e850eefbfac967d933f26f8e2a3757a063b7d5e7fe4556dfb03c88` | `neutral` | The record expressly assesses this exact form as having no established form-specific schedule. The existing electrolyte exercise decision remains a distinct role-scoped `unresolved_without_direction` decision; neither result creates a pressure. |
| 38 | `cand_note_bcde71885c1365835992e502661b88f1795e4626f658dba108d89f89d388d97b` | `sub_kwudyhex2o`; [`choline bitartrate` notes](../../data/substances/choline_bitartrate__sub_kwudyhex2o.yaml), lines 3--12; span `72349237ad2978b2f466a45589b5dc7187b866caddf01e82fb70369f0d1e51d9` | `outside_model` | The asserted matter is whether a biomarker establishes clinical harm or a clinical risk threshold. Clinical risk-threshold and dose assessment are expressly outside this safety-free scheduling model; the statement itself supplies no temporal world fact. |
| 39 | `cand_note_21c3336cc1d29cc3bec40c093036a7035f31d33a96cfd3e1e80cc1b66bd6fe6d` | `sub_844a0cc551`; [`copper bisglycinate` notes](../../data/substances/copper_bisglycinate__sub_844a0cc551.yaml), lines 6--10; span `df61194942183e673ca05f1a97fa63c97dd8236349e0387bcd631dbd87b62ccb` | `neutral` | The note directly assesses and rejects a general meal, clock, or activity direction. Its zinc/copper exposure material remains passive review context under the pairwise decision; no unary or pairwise fact follows. |
| 40 | `cand_note_a4c29445b00bf66d3b403d617dadfc78f495f88561d5008409b100f3c38ac9bd` | `sub_9c0908e7f7`; [`creatine monohydrate` notes](../../data/substances/creatine_monohydrate__sub_9c0908e7f7.yaml), line 4; span `198ec784890ad1412495e9cb55213b7a4455fc30db2ef5ec4124a097fdfc0ac2` | `neutral` | This preserves the [exercise adjudication](actionable-scheduling-exercise-adjudication-20260831.md): chronic saturation and consistent intake do not establish a before/after or clock-time direction. It must not reintroduce the removed `any_workout` stored answer. |
| 41 | `cand_note_3da0895bedf599a13744fbb6550616fe1d6a117f12bd77fe94eb3b8e2221f121` | `sub_jwqo8ptntd`; [`D-ribose` notes](../../data/substances/d_ribose__sub_jwqo8ptntd.yaml), lines 4--6; span `53547e371a5e229fcaad081d2ccc668ede3ad1a36744cb6822515490bd09d487` | `unresolved_without_direction` | The note expressly retains exercise-performance material at review level rather than claiming an established benefit. It supplies neither an acute pre-exercise effect nor a post-exercise recovery effect and no exact applicability. |
| 42 | `cand_note_bd11a039cd10fc0d14e0c4547b0a117fcfe8ec6a27441606a6ff9aac2c232622` | `sub_jwqo8ptntd`; [`D-ribose` notes](../../data/substances/d_ribose__sub_jwqo8ptntd.yaml), lines 4--6; same span `53547e371a5e229fcaad081d2ccc668ede3ad1a36744cb6822515490bd09d487` | `unresolved_without_direction` | “Source checked” is provenance material, not a directed scheduling result. It is retained with record 41 rather than silently becoming neutral or a `PreExercisePerformanceEffect`. |
| 43 | `cand_note_a6542984ac42867f48fad53cfa98fdb6e774e2b83ef1de0f79c60467489074d4` | `sub_rt2lr29xqs`; [`DHEA` notes](../../data/substances/dehydroepiandrosterone__sub_rt2lr29xqs.yaml), lines 5--7; span `0a4d0c0760c23915ba9534483b9677e476faa0947355c859304111357347f93d` | `outside_model` | The candidate is only a citation within a hormone-adjacent, high-review endocrine context. Any consequent timing judgement would require excluded endocrine/clinical safety modelling; the citation is not a temporal world fact. |
| 44 | `cand_note_437a35c9b59607d8c3e89eec7a66e8f4070d6f41e7b4174725a874787aeeb43e` | `sub_xsqvv2fop0`; [`DHA` notes](../../data/substances/docosahexaenoic_acid__sub_xsqvv2fop0.yaml), line 5; span `9b44226343491de02fd63ac95ca320f16b6de68dc448833938a74c1d3284515b` | `unresolved_without_direction` | Formulation- and dose-dependence is a reason not to derive a substance-wide food fact. This source has no exact product/role target and therefore cannot select one formulation or infer `with_food`. |
| 45 | `cand_note_d9bb7a793eab2aecf9efb718abb60717a0a44b53c1e3f6e7d7163b7e1f26a3a1` | `sub_xsqvv2fop0`; [`DHA` notes](../../data/substances/docosahexaenoic_acid__sub_xsqvv2fop0.yaml), line 5; same span `9b44226343491de02fd63ac95ca320f16b6de68dc448833938a74c1d3284515b` | `unresolved_without_direction` | Absence of a universal DHA rule does not prove each formulation neutral. It preserves the prior food decision’s role-scoped facts without generalising them to DHA. |
| 46 | `cand_note_013c76f349b740764c1fb456e9032d9fb6852e5f24e7fed29224f4e15a11430b` | `sub_66b783576c`; [`EPA` notes](../../data/substances/eicosapentaenoic_acid__sub_66b783576c.yaml), line 5; span `3e62f9e674ebb3efc858ac8ae3aa1389ae4c791c13f7460d536bff73473e43a9` | `unresolved_without_direction` | “No product-independent rule” cannot discharge formulation-specific roles as neutral. It supplies no product/role applicability and must not override the separate fish-oil-concentrate fact or manufacture an EPA-wide fact. |
| 47 | `cand_note_766ea2ca981fb200e036aa8c57acb701f6c4e854190d56c102e90e174a840081` | `sub_sunkcr05vl`; [`fish-oil concentrate` notes](../../data/substances/fish_oil_concentrate_epa_dha_ethyl_esters__sub_sunkcr05vl.yaml), lines 5--14; span `2c6ce739774ff7560cdeb5cff57df648f24cff342564d6f625558e5ca2e54416` | `unresolved_without_direction` | The source describes a formulation heuristic but the queue record itself has no role applicability. The existing `fact_food_prd_htuhz2s2gt_sub_sunkcr05vl` remains independently and exactly scoped to `cmp_prd_htuhz2s2gt__sub_sunkcr05vl`; this candidate neither duplicates that pressure nor extends it to EPA, DHA, or krill oil. |
| 48 | `cand_note_551e84493e65009c8c07a399c6db54f8e323504844271387981c8648ce9062e0` | `sub_be55xf4yb7`; [`garlic` notes](../../data/substances/garlic__sub_be55xf4yb7.yaml), lines 7--8; span `87cb7bf3835898357df4720ed134cf036fdf242127120079fcbb024a68ccdec0` | `outside_model` | Antiplatelet/hypotensive effects at therapeutic exposure and bleeding-load review are medication/safety questions. This dose-dependent clinical context carries no scheduling-axis fact and is excluded without creating a separation rule. |
| 49 | `cand_note_3b55992a050a8cd6391c4d5df723b2bd0dda2224c07e948f3306ab5e672f8805` | `sub_f3vgw907ew`; [`ginger` notes](../../data/substances/ginger__sub_f3vgw907ew.yaml), lines 6--7; span `63e70e546aae0ead1c6ce6ccae42ad3037d88b7cdf4bfe03437a5387eea14d07` | `outside_model` | The higher-dose antiplatelet/bleeding-load assertion is conditional clinical-safety context; anti-inflammatory and digestive-comfort labels do not state a closed timing effect. No fact or pairwise separation is admitted. |
| 50 | `cand_note_103ad5d1c1cac1632aeea36e647d08f6b249e763047af929aa6d67b19dd87162` | `sub_c9720c7240`; [`glycine` notes](../../data/substances/glycine__sub_c9720c7240.yaml), lines 3--6; span `a658b90b4b045a213ef982423c309d0642dddf20b0e0d8018e2a0cafea592af9` | `unresolved_without_direction` | The span reports generic “sleep quality” at a studied 3 g exposure and an unsupported 1 g extrapolation. It neither identifies the closed acute-sleep value (`onset_latency_decreases` or `continuity_improves`) nor supplies an exact role applicability; a substance-wide fact would incorrectly reach both the 1 g single-ingredient product and an undisclosed blended amount. It remains an explicit open lead, not a discounted pressure or a bedtime placement. |

## Accounting and boundary consequences

The ledger contains exactly **16** queue records in original order, once each:
zero `pressure`, three `neutral`, seven `unresolved_without_direction`, and six
`outside_model`. No disposition in this record creates a direct contradiction;
therefore it does not itself yield `Indeterminate`.

No new fact/law shape is proposed because this slice admits no pressure. The
existing closed fact families and identity-free laws remain unchanged. In
particular, neither food wording, a product instruction, an intended outcome,
an evidence citation, a safety context, nor a generic sleep-quality statement
is a stored placement, pair preference, action, explanation, or numeric weight.
