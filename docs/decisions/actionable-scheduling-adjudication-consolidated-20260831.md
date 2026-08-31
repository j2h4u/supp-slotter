# Actionable Scheduling Adjudication — Consolidated — 2026-08-31

## Status and authority

**Accepted V-left reconciliation.** This is the authoritative, nonduplicative
map for the 50 source-indexed note candidates, the six named food candidates,
the eight named exercise candidates, and all 34 current pairwise relations. It
consolidates—not replaces—the source receipts and the three partition records:

- [queue 001–017](actionable-scheduling-note-candidates-001-017-20260831.md),
  [018–034](actionable-scheduling-note-candidates-018-034-20260831.md), and
  [035–050](actionable-scheduling-note-candidates-035-050-20260831.md);
- [food](actionable-scheduling-food-adjudication-20260831.md),
  [exercise](actionable-scheduling-exercise-adjudication-20260831.md), and
  [pairwise](actionable-scheduling-pairwise-adjudication-20260831.md)
  adjudications; and
- the [recovery baseline](../evidence/actionable-scheduling-recovery-baseline-20260831.yaml),
  [active structured-knowledge dispositions](../evidence/actionable-scheduling-active-knowledge-dispositions-20260831.md),
  [coverage boundary](actionable-scheduling-knowledge-coverage-boundary-20260831.md),
  [canonical-instance ADR](canonical-instance-inference-boundary-20260822.md),
  and [living domain model](../domain-model.md).

It is not an implementation authorization. A candidate disposition is never a
stored desired slot, pair preference, dose, safety statement, treatment,
action, numerical evidence weight, or schedule. An admitted directed
hypothesis is exactly one unweighted pressure before balance; provenance
strength, source count, and fact count do not change that objective.

## Reconciled totals

There are **64 unique candidate IDs**, each with one closed disposition:

| Candidate set | IDs | Pressure | Neutral | Unresolved | Outside |
| --- | ---: | ---: | ---: | ---: | ---: |
| 50 queued note candidates | 50 | 2 | 4 | 7 | 37 |
| Named food candidates | 6 | 5 | 0 | 1 | 0 |
| Named exercise candidates | 8 | 1 | 1 | 6 | 0 |
| **All candidate records** | **64** | **8** | **5** | **14** | **37** |

The eight `pressure` *records* normalize to **six unique pressure identities**:
Vitamin D3, Only Trace Minerals, Harmony Aqua astaxanthin, Psalae
astaxanthin, Psalae Antarctiv Krill Oil, and citrulline. Two records are
intentional aliases of an already-normalized pressure:

1. queue `cand_note_atom_1c927da88dbdc33d0578c5e0` and
   `cand_product_food_prd_932319251f_with_food` are two evidence candidates
   for the one Only Trace Minerals product pressure; and
2. the astaxanthin and krill-oil candidates for `prd_w2s970gps4` each require
   a distinct exact-role fact but derive one `(prd_w2s970gps4,
   meal_context, with_food)` pressure.

These are evidence/proof-path duplicates only. They must remain visible in a
coverage certificate and explanation, but cannot multiply the pressure or add
weight.

## Canonical pressure map and exact delta from current HEAD

| Normalized pressure identity | Candidate records | Current HEAD state | Required canonical fact/law result |
| --- | --- | --- | --- |
| `(prd_eb6337a6dc, meal_context, with_food)` | queue 006 | Existing `fact_food_prd_eb6337a6dc_sub_2476bf9d4b` and `law_food_bioavailability_increases` | No new fact or law. Queue provenance is exact to the product candidate but must not by itself enlarge the existing fact's independently supported applicability. |
| `(prd_bb212cffc2, meal_context, with_food)` | none in this candidate inventory | Existing riboflavin fact/law | No change. No queue candidate may enlarge or duplicate it. |
| `(prd_htuhz2s2gt, meal_context, with_food)` | queue 047 is related but unresolved | Existing fish-oil-concentrate fact/law | No change. Queue 047 lacks exact active role applicability and cannot generalize the existing exact fish-oil fact to EPA, DHA, or krill oil. |
| `(prd_cfce0b36b6, exercise_anchor, before)` | named exercise citrulline | Existing citrulline fact/law | No new fact or law. Its low-confidence direction still beats balance; it has no evidence-derived weight. |
| `(prd_e5cc3b4e7c, meal_context, with_food)` | named food Harmony Aqua astaxanthin | Absent | Add `FoodEffect` `fact_food_prd_e5cc3b4e7c_sub_249199f726`, exact subject/applicability `cmp_prd_e5cc3b4e7c__sub_249199f726`, value `bioavailability_increases`, through existing `law_food_bioavailability_increases`. |
| `(prd_8mvv1w128a, meal_context, with_food)` | named food Psalae astaxanthin | Absent | Add `FoodEffect` `fact_food_prd_8mvv1w128a_sub_249199f726`, exact subject/applicability `cmp_prd_8mvv1w128a__sub_249199f726`, value `bioavailability_increases`, through the existing food law. |
| `(prd_w2s970gps4, meal_context, with_food)` | named food astaxanthin and krill oil | Absent | Add two exact-role `FoodEffect` facts: `fact_food_prd_w2s970gps4_sub_249199f726` for `cmp_prd_w2s970gps4__sub_249199f726`, and `fact_food_prd_w2s970gps4_sub_646e568f61` for `cmp_prd_w2s970gps4__sub_646e568f61`; both use the existing food law and deduplicate at this normalized identity. |
| `(prd_932319251f, meal_context, with_food)` | queue 011; named food Only Trace Minerals | Absent | Add one exact product fact `fact_product_food_prd_932319251f` in a new closed `ProductFoodInstruction` family, value `take_with_food`, and one new identity-free `law_product_food_take_with_food`. It targets the product intake item directly, never its seven component roles. |

Therefore the exact V-left delta beyond current HEAD is:

1. four role-scoped `FoodEffect` fact instances named in the table, all using
   the existing `law_food_bioavailability_increases`;
2. one new narrow product-only fact family, `ProductFoodInstruction`, with
   only `take_with_food` currently admitted; one fact instance
   `fact_product_food_prd_932319251f`; and one universal identity-free law
   `law_product_food_take_with_food`; and
3. no pairwise fact, pairwise law, clock law, sleep law, exercise law, stored
   placement, general product-instruction engine, or new objective weight.

The new product family is necessary because the current subject/applicability
XOR cannot truthfully encode an instruction for the Only Trace Minerals intake
item without falsely assigning it to zinc, copper, manganese, chromium,
molybdenum, boron, vanadium, or another component. It is a single closed
product fact/law path, not an instruction abstraction.

## Complete candidate map

`P` is a candidate that reaches one of the normalized identities above. `N`,
`U`, and `O` mean `neutral`, `unresolved_without_direction`, and
`outside_model`. All rows retain the exact source locator in their partition
record or the mechanical queue; this table intentionally avoids copying those
receipts.

### Queue candidates

| Queue | Candidate ID | Disposition | Reconciled outcome |
| ---: | --- | :---: | --- |
| 001 | `cand_note_atom_fd37f7f908d068d2b18962b3` | O | Inactive Animal Flex product instruction; no active applicability. |
| 002 | `cand_note_atom_835810b98faf4445eff0cd31` | O | Inactive NRT product instruction; no component transfer. |
| 003 | `cand_note_atom_de0a8698539edb7185f5c85d` | O | Inactive Core Daily-1 product instruction; no component transfer. |
| 004 | `cand_note_atom_a7c7c4166e180b9b69c30696` | O | Inactive NAC product instruction; no component transfer. |
| 005 | `cand_note_atom_4e19e8f62b675c92063a78df` | O | Inactive R-lipoic-acid instruction; no `without_food` fact. |
| 006 | `cand_note_atom_c8bca12f5f4b1916f0ded21f` | P | Existing Vitamin D3 normalized pressure only; no duplicate fact. |
| 007 | `cand_note_atom_d08ea852acc0fbcb332d33c3` | O | Inactive food-or-beverage instruction has no closed singular value. |
| 008 | `cand_note_atom_a4ca5c059c8060afcbdaead7` | O | Inactive MaculaPF instruction; oil/formulation does not transfer. |
| 009 | `cand_note_atom_2cda37dce342473de60904de` | O | Inactive Toco-Sorb product instruction. |
| 010 | `cand_note_atom_b051cc6731178a9bc87fb665` | O | Inactive melatonin label; no general bedtime fact. |
| 011 | `cand_note_atom_1c927da88dbdc33d0578c5e0` | P | Evidence alias for the one product-scoped Only Trace Minerals pressure. |
| 012 | `cand_note_atom_8afee17053d97509c5f1cc86` | O | Inactive D/K formulation; cannot enlarge Vitamin D3. |
| 013 | `cand_note_atom_208ac8f9565ca312aa109a67` | O | Inactive sleep-product instruction; no general sleep anchor. |
| 014 | `cand_note_atom_3bdff61186e82bac54622515` | O | Inactive calcium blend instruction. |
| 015 | `cand_note_atom_e177bb1e91075deed3bf9914` | O | Distinct receipt for the same inactive calcium blend; no multiplicity. |
| 016 | `cand_note_atom_ab93da362c70f41f2f497ebe` | O | Inactive magnesium formulation; no transfer to active magnesium glycinate. |
| 017 | `cand_note_atom_ded07c466df0813b2c7893bc` | O | Inactive potassium formulation; no active applicability. |
| 018 | `cand_note_atom_d6bf51068f62436dc6cd70b7` | O | Inactive Opti-Men product instruction. |
| 019 | `cand_note_atom_a18bb194433094d309383705` | O | Inactive, unmodelled before-meal interval. |
| 020 | `cand_note_atom_68873823f036180733d28432` | O | Inactive Zinc/Copper product instruction. |
| 021 | `cand_note_atom_d15b7b2add87da3299b2cc82` | O | Inactive Skin/Nails/Hair product instruction. |
| 022 | `cand_note_atom_2f8951d77973833f8d1e06bc` | O | Inactive Ultra Mag product instruction. |
| 023 | `cand_note_atom_73af4987a89dea44bbfeaf8f` | O | Inactive krill product does not reopen active krill/astaxanthin facts. |
| 024 | `cand_note_atom_71d8483b3d39fa56f7896489` | O | Inactive tocotrienol product instruction. |
| 025 | `cand_note_atom_e30c5b6e15d7f580ee2f5e3b` | O | Inactive pre-workout label is not an exact performance fact. |
| 026 | `cand_note_atom_09c98117040ef16436a2e1b7` | N | Product-composition boundary; D3 is not a component. |
| 027 | `cand_note_dcf05847619838d9f01423a0d95f63d71f50beb41348c2685f23c28537e310a7` | O | Inactive, unmodelled before-meal interval. |
| 028 | `cand_note_1e935a7665f93fdc17c0925c677fadeb154a49cb6f2cc1905335523896738f49` | O | Inactive digestive-support context. |
| 029 | `cand_note_733d87f39ad61bd3f7224f84a2af3040981e623da05c7198d45971a6dcfa8d4c` | O | Inactive form-limited nitrate/exercise context. |
| 030 | `cand_note_c4e6324eacce70c13c0a0ec9ab4592f069232d8032cd32b9cd3c155fdafcabf1` | O | Inactive pre-workout prose, no typed outcome. |
| 031 | `cand_note_f61c436e56d7d766ac34ffd2a50c4a5a3b44a86ddfeeaa2d65fee172054abe3c` | O | Inactive dose-dependent beta-alanine review. |
| 032 | `cand_note_f3d58d83411d0e8c4fb99ffdab18c207487e58e37386fa1b1fbeb4977e567cca` | O | Inactive provenance-only HMB note. |
| 033 | `cand_note_d81564e08e85ca68806eb8f3bffebb45f40e52a44a897f6250c13a85092a8baf` | O | Inactive intended pre-workout context. |
| 034 | `cand_note_0b6624033909105acf7b5e025f6b0aa37ff8bb185cbe62b3c9dd332f571d1b5b` | O | Inactive bromelain safety/purpose context. |
| 035 | `cand_note_2820c8320c617329ee64f9c9eb33f3e4ca2dc26a19f4d0f51d70b0395df27968` | O | Purpose-conditioned bromelain wording is outside closed applicability. |
| 036 | `cand_note_3cdab89e570d5a766392a5b2d2c71ec62ed1d88b88c0bef8d11a11661cf0eb96` | O | Digestive purpose does not yield a food pressure. |
| 037 | `cand_note_0c26f105bf8fb918c3469fd5d5fbab23a83e011ae3f200051b807f192e42a1c0` | N | No established form-specific calcium schedule. |
| 038 | `cand_note_bcde71885c1365835992e502661b88f1795e4626f658dba108d89f89d388d97b` | O | Clinical risk-threshold assessment is excluded. |
| 039 | `cand_note_21c3336cc1d29cc3bec40c093036a7035f31d33a96cfd3e1e80cc1b66bd6fe6d` | N | Copper has no general meal/clock/activity direction. |
| 040 | `cand_note_a4c29445b00bf66d3b403d617dadfc78f495f88561d5008409b100f3c38ac9bd` | N | Chronic creatine saturation is not an exercise anchor. |
| 041 | `cand_note_3da0895bedf599a13744fbb6550616fe1d6a117f12bd77fe94eb3b8e2221f121` | U | No exact D-ribose exercise outcome/applicability. |
| 042 | `cand_note_bd11a039cd10fc0d14e0c4547b0a117fcfe8ec6a27441606a6ff9aac2c232622` | U | Provenance-only D-ribose note remains open. |
| 043 | `cand_note_a6542984ac42867f48fad53cfa98fdb6e774e2b83ef1de0f79c60467489074d4` | O | Endocrine/clinical context is excluded. |
| 044 | `cand_note_437a35c9b59607d8c3e89eec7a66e8f4070d6f41e7b4174725a874787aeeb43e` | U | DHA has no exact product/role food applicability. |
| 045 | `cand_note_d9bb7a793eab2aecf9efb718abb60717a0a44b53c1e3f6e7d7163b7e1f26a3a1` | U | No universal DHA rule; role-specific facts remain separate. |
| 046 | `cand_note_013c76f349b740764c1fb456e9032d9fb6852e5f24e7fed29224f4e15a11430b` | U | EPA cannot generalize fish-oil/krill facts. |
| 047 | `cand_note_766ea2ca981fb200e036aa8c57acb701f6c4e854190d56c102e90e174a840081` | U | Fish-oil formulation heuristic lacks exact role applicability. |
| 048 | `cand_note_551e84493e65009c8c07a399c6db54f8e323504844271387981c8648ce9062e0` | O | Garlic bleeding/safety context is excluded. |
| 049 | `cand_note_3b55992a050a8cd6391c4d5df723b2bd0dda2224c07e948f3306ab5e672f8805` | O | Ginger bleeding/safety context is excluded. |
| 050 | `cand_note_103ad5d1c1cac1632aeea36e647d08f6b249e763047af929aa6d67b19dd87162` | U | Generic glycine sleep-quality claim lacks value and exact role scope. |

### Named food and exercise candidates

| Candidate ID | Disposition | Reconciled outcome |
| --- | :---: | --- |
| `cand_food_cmp_prd_175251bd63__sub_877c24aad4_empty` | U | Nattokinase evidence remains unresolved; do not restore `empty_preferred`. |
| `cand_food_cmp_prd_e5cc3b4e7c__sub_249199f726` | P | New exact-role Harmony Aqua astaxanthin food fact. |
| `cand_food_cmp_prd_8mvv1w128a__sub_249199f726` | P | New exact-role Psalae astaxanthin food fact. |
| `cand_food_cmp_prd_w2s970gps4__sub_249199f726` | P | New exact-role astaxanthin fact; shares the Psalae krill product pressure. |
| `cand_food_cmp_prd_w2s970gps4__sub_646e568f61` | P | New exact-role krill-oil fact; shares the same product pressure. |
| `cand_product_food_prd_932319251f_with_food` | P | Evidence alias for the one new product-only Only Trace fact. |
| `cand_exercise_lclt_cmp_prd_0e92bc1674__sub_5bd641c116` | U | Recovery context does not establish an after-exercise direction. |
| `cand_exercise_creatine_cmp_prd_2ca842627a__sub_9c0908e7f7` | N | Assessed chronic-saturation result, no anchor direction. |
| `cand_exercise_citrulline_cmp_prd_cfce0b36b6__sub_3918fe347e` | P | Existing exact-role pre-exercise pressure. |
| `cand_exercise_electrolyte_sodium_cmp_prd_20bf2df267__sub_4j9fttkil9` | U | Conditional hydration context lacks modelled conditions. |
| `cand_exercise_electrolyte_potassium_cmp_prd_20bf2df267__sub_f7780f899b` | U | Conditional hydration context lacks modelled conditions. |
| `cand_exercise_electrolyte_magnesium_cmp_prd_20bf2df267__sub_fhl7c4skmf` | U | Conditional hydration context lacks modelled conditions. |
| `cand_exercise_electrolyte_calcium_dcp_cmp_prd_20bf2df267__sub_iqjdo9gvbv` | U | Conditional hydration context lacks modelled conditions. |
| `cand_exercise_electrolyte_calcium_lactate_cmp_prd_20bf2df267__sub_p5qxdnxu9e` | U | Conditional hydration context lacks modelled conditions. |

## Pairwise relation map

All **34** relation records are closed and none creates a scheduling pressure,
co-location, separation, score, feasibility restriction, or placement. Their
separate accounting is **15 neutral/context, 3 unresolved, and 16 outside
model**.

| Disposition | Relation IDs |
| --- | --- |
| neutral/context | `rel_balance_001`, `rel_balance_002`, `rel_supports_002`, `rel_supports_003`, `rel_supports_004`, `rel_supports_007`, `rel_supports_009`, `rel_co_use_context_016`, `rel_co_use_context_017`, `rel_co_use_context_018`, `rel_co_use_context_019`, `rel_co_use_context_020`, `rel_co_use_context_021`, `rel_co_use_context_022`, `rel_co_use_context_023` |
| unresolved_without_direction | `rel_supports_001`, `rel_supports_005`, `rel_supports_008` |
| outside_model | `rel_supports_010`, `rel_co_use_context_001`, `rel_co_use_context_002`, `rel_co_use_context_003`, `rel_co_use_context_004`, `rel_co_use_context_005`, `rel_co_use_context_006`, `rel_co_use_context_007`, `rel_co_use_context_008`, `rel_co_use_context_009`, `rel_co_use_context_010`, `rel_co_use_context_011`, `rel_co_use_context_012`, `rel_co_use_context_013`, `rel_co_use_context_014`, `rel_co_use_context_015` |

No pairwise admission is pending from this corpus. A future admission needs an
exact source and target, a minimal typed world-fact mechanism, and an
identity-free universal law; passive `balance`, `supports`, and
`co_use_context` records may not be adapted into scheduler behavior.

## Overlap reconciliation, overrides, and blockers

No candidate yields opposing values for the same normalized item and
dimension, so this consolidated record creates no direct `Indeterminate`
outcome. The following safeguards resolve the apparent overlaps:

- **Astaxanthin and krill oil:** their four facts have exact composition-role
  applicability. The two facts on `prd_w2s970gps4` deliberately deduplicate
  to one product/dimension/value pressure. Queue 023 is inactive and does not
  alter either fact.
- **Vitamin D3:** queue 006 is an evidence candidate for the existing D3
  pressure, not permission to derive a second pressure or to transfer its
  product-label wording. The current substance-scoped fact remains valid only
  to the extent that its own cited evidence supports that scope; implementation
  must not use queue 006's product label as support for a broader applicability.
- **Riboflavin:** the existing B2 pressure has no queue-derived duplicate. The
  inactive Core Daily-1 receipt (queue 003) cannot expand it.
- **Fish-oil concentrate, EPA, and DHA:** queue 047 remains unresolved and
  queues 044–046 have no exact applicability. None may override or generalize
  the existing exact fish-oil-concentrate fact, nor become a krill-oil fact.
- **Citrulline:** the one existing exact-role pressure remains; no electrolyte,
  creatine, or LCLT candidate entails an opposing exercise value.
- **Only Trace Minerals:** queue 011 and the named food candidate consolidate
  to one product fact and one pressure. Component-level material is excluded
  from the instruction path.

**Explicit override:** queue 006's earlier wording that its product note is
“already covered” is constrained here to *normalized-pressure deduplication*.
It must not be read as source/applicability equivalence between the product
note and the existing substance-scoped D3 fact. Retain its `pressure`
disposition, but preserve its own product receipt and validate the broader
fact's cited scope independently. No other partition disposition is changed.

The only implementation blocker is this V-left scope rule plus the required
closed Only Trace fact/law family. If either is absent, if a required exact
provenance identity cannot be resolved, if two facts produce opposite values
for one item/dimension, or if a coverage certificate is incomplete, publication
must be layout-free `Indeterminate`. The 14 unresolved candidates are closed
as unresolved—not neutral—and require a later individual adjudication before a
future model expansion.
