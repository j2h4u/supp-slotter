# Active Food-Candidate Adjudication — 2026-08-31

## Status

**Accepted semantic adjudication.** This record fixes the individual
dispositions for the named active food/empty candidates. It is an input to the
consolidated candidate map and does not itself author facts, alter the ontology,
or publish a layout.

It is governed by the [actionable scheduling knowledge coverage
boundary](actionable-scheduling-knowledge-coverage-boundary-20260831.md), the
[canonical instance and inference
boundary](canonical-instance-inference-boundary-20260822.md), and the living
[domain model](../domain-model.md). In particular, each candidate gets exactly
one disposition; an admitted direction is one unweighted pressure before
balance; and conflicting values for one product and dimension are
layout-free `Indeterminate`.

## Scope and notation

All named products are active daily products in
[`data/stacks.yaml`](../../data/stacks.yaml). A `FoodEffect` below is the
existing closed fact family:

```yaml
FoodEffect:
  subject: {composition_role: <role-id>}
  applicability: {composition_role: <same-role-id>}
  value: bioavailability_increases
```

The existing identity-free law
`law_food_bioavailability_increases` derives
`meal_context=with_food`. The selected composition-role subject and
applicability deliberately confine every formulation-sensitive fact to one
active product role.

The candidate IDs in this record are stable source-indexed adjudication
identities. They are not fact
IDs, optimizer input, placement, action, or score.

## Decisions

| Candidate ID | Active applicability | Disposition | Formal world-fact shape and law path | Provenance and reasoning |
| --- | --- | --- | --- | --- |
| `cand_food_cmp_prd_175251bd63__sub_877c24aad4_empty` | `prd_175251bd63`; `cmp_prd_175251bd63__sub_877c24aad4` | `unresolved_without_direction` | None. No `FoodEffect` is admitted. | [`nattokinase` card](../../data/substances/nattokinase__sub_877c24aad4.yaml) says oral active bioavailability and food effects remain unresolved. The earlier direct adjudication withdrew the old `empty_preferred` heuristic: there is no controlled fed-versus-fasted comparison for the active Airboy quick-release product, and the cited DSLD label is a different product. Preserve source records PMID 17520440, PMID 23709455, PMID 26109079, PMID 19358933, and NIH DSLD label 82020 as provenance for the unresolved decision, not as a pressure. |
| `cand_food_cmp_prd_e5cc3b4e7c__sub_249199f726` | `prd_e5cc3b4e7c`; `cmp_prd_e5cc3b4e7c__sub_249199f726` | `pressure` | `FoodEffect(subject=cmp_prd_e5cc3b4e7c__sub_249199f726, applicability=cmp_prd_e5cc3b4e7c__sub_249199f726, value=bioavailability_increases)` -> `law_food_bioavailability_increases` -> `meal_context=with_food`. | [`astaxanthin` card](../../data/substances/astaxanthin__sub_249199f726.yaml) records a bounded, formulation/lipid-sensitive soft food preference with human/formulation sources PMID 19734684 and PMID 12885395. The Harmony Aqua package source is incomplete, so its source-identity repair remains open; it does not turn this already-directed, role-scoped hypothesis into a substance-wide rule. |
| `cand_food_cmp_prd_8mvv1w128a__sub_249199f726` | `prd_8mvv1w128a`; `cmp_prd_8mvv1w128a__sub_249199f726` | `pressure` | `FoodEffect(subject=cmp_prd_8mvv1w128a__sub_249199f726, applicability=cmp_prd_8mvv1w128a__sub_249199f726, value=bioavailability_increases)` -> `law_food_bioavailability_increases` -> `meal_context=with_food`. | The same astaxanthin evidence supports a bounded soft direction, but this is a distinct active 12-mg softgel role and has its own candidate and fact. Provenance: astaxanthin card and PMIDs 19734684 and 12885395; product identity: [`Psalae Astaxanthin` card](../../data/products/psalae__astaxanthin__prd_8mvv1w128a.yaml). |
| `cand_food_cmp_prd_w2s970gps4__sub_249199f726` | `prd_w2s970gps4`; `cmp_prd_w2s970gps4__sub_249199f726` | `pressure` | `FoodEffect(subject=cmp_prd_w2s970gps4__sub_249199f726, applicability=cmp_prd_w2s970gps4__sub_249199f726, value=bioavailability_increases)` -> `law_food_bioavailability_increases` -> `meal_context=with_food`. | The active krill-oil product identifies the astaxanthin role. The bounded astaxanthin direction remains exact-role scoped rather than being inferred from the krill-oil instruction or generalized to other forms. Provenance: astaxanthin card, PMIDs 19734684/12885395, and [`Psalae Antarctiv Krill Oil` card](../../data/products/psalae__antarctiv_krill_oil__prd_w2s970gps4.yaml). |
| `cand_food_cmp_prd_w2s970gps4__sub_646e568f61` | `prd_w2s970gps4`; `cmp_prd_w2s970gps4__sub_646e568f61` | `pressure` | `FoodEffect(subject=cmp_prd_w2s970gps4__sub_646e568f61, applicability=cmp_prd_w2s970gps4__sub_646e568f61, value=bioavailability_increases)` -> `law_food_bioavailability_increases` -> `meal_context=with_food`. | [`krill oil` card](../../data/substances/krill_oil__sub_646e568f61.yaml) records a bounded soft food preference for the active Psalae form. The evidence is mixed across formulations, carriers, and doses, but it remains a directed hypothesis; after individual adjudication it is a single unweighted pressure, not a lower-weight vote. Provenance: PMIDs 30799231, 25884846, 26328782, NIH ODS Omega-3 fact sheet, and NCCIH Omega-3 page. |
| `cand_product_food_prd_932319251f_with_food` | product `prd_932319251f` only | `pressure` | New closed `ProductFoodInstruction(product=prd_932319251f, value=take_with_food)` -> new `law_product_food_take_with_food` -> `meal_context=with_food` for that product intake item. | The official [Life Extension product page](https://www.lifeextension.com/vitamins-supplements/item01328/only-trace-minerals), retained on the [`Only Trace Minerals` card](../../data/products/life_extension__only_trace_minerals__prd_932319251f.yaml), directs one capsule daily with food. This is an exact product instruction, not a component property. |

## Required closed addition for the product instruction

The current `CanonicalSchedulingFact` subject/applicability XOR admits only a
substance or composition role. It cannot faithfully represent the Only Trace
Minerals instruction without falsely assigning it to every component. The
smallest admissible extension is a separate, product-scoped fact family, not
an extension of `FoodEffect` and not a general instruction engine:

```yaml
ProductFoodInstruction:
  id: fact_product_food_prd_932319251f
  product: prd_932319251f
  value: take_with_food
  provenance:
    - source: src_life_extension_only_trace_minerals
      locator: https://www.lifeextension.com/vitamins-supplements/item01328/only-trace-minerals
      quotation: Take one capsule daily with food.

ProductFoodInstructionLaw:
  id: law_product_food_take_with_food
  fact_value: take_with_food
  meal_context: with_food
```

The law is universal and identity-free: every admitted
`ProductFoodInstruction(take_with_food)` derives only its own product's
`meal_context=with_food` pressure. Its closed value set contains only
`take_with_food`; any other manufacturer wording requires separate V-left
adjudication and a new accepted law. The compiler must route this fact to the
product intake item directly, never through a component role.

## Deduplication, objective, and contradiction handling

Each admitted fact reaches a normalized pressure identity
`(product_id, meal_context, with_food)`. `prd_w2s970gps4` has two independently
adjudicated food facts—its astaxanthin and krill-oil roles—but they yield the
same identity. They therefore produce **one** unique satisfied pressure, while
both fact/candidate/provenance paths remain visible in the certificate and
explanation. Sources, quotations, components, fact count, and research state
never create a second pressure or numeric weight.

Every admitted `with_food` pressure outranks squared-load balance under the
unchanged exact lexicographic objective. A later fact deriving
`(prd_w2s970gps4, meal_context, without_food)`—or any opposing value for an
item/dimension already represented here—is a direct contradiction and must
return layout-free `Indeterminate`; it must not be canceled, averaged,
weighted, or optimized around.

## Explicit exclusions

- Do not reintroduce nattokinase `empty_preferred`, translate its evidence into
  `bioavailability_decreases`, or treat unresolved evidence as neutral.
- Do not assert `fat_meal_required`, `without_food`, or a high-fat-meal
  requirement for astaxanthin or krill oil. “Extra dietary fat is not required”
  is a scope limit, not an opposite scheduling direction.
- Do not make the astaxanthin evidence substance-wide. Each admitted fact is
  limited to the three named active composition roles; it does not automatically
  reach inactive products or other astaxanthin formulations.
- Do not translate the Only Trace Minerals product instruction into a fact for
  zinc, copper, manganese, chromium, molybdenum, boron, vanadium, or any other
  component, and do not use it as evidence for another product.
- Do not add dose, treatment, diagnosis, safety, physical-capacity, placement,
  action, pairwise-preference, or numerical-evidence semantics. This decision
  records world facts and universal law paths only.
