# Interaction adjudication: implementation decision matrix

Date: 2026-08-21
Status: implementation design only; no ontology, data, Python, or generated
artifact changes are made by this document.

This is the skeptical acceptance review of:

- [ontology cutover plan](ontology-cutover-decision-20260821.md);
- [interaction evidence inventory](interaction-semantics-inventory-20260821.md);
- [catalog migration inventory](ontology-catalog-migration-inventory-20260821.md);
- [schedule semantic diff](ontology-schedule-semantic-diff-20260821.md).

## Representability verdict

All eight adjudications are representable by the current formal contract. No
new relation type, selector kind, warning type, dose model, or general-purpose
abstraction is needed.

- **Relation knowledge:** use the existing `balance` or `review_with` records
  in `data/relations.yaml`.
- **Placement policy:** use the existing
  `separate_products_same_slot` records in
  `ontology/scheduling-constraints.yaml`. Per-record
  `blocks_slots: false`, `scores_advisory: true`, and `score_delta: -1` are
  already supported; the runtime operation default remains hard only when a
  record omits the explicit fields.
- **Review-only:** use `review_with` with the existing
  `clinical_review_signal` filter. The existing runtime emits
  `review_with_substance_present` when both endpoints are active, without
  affecting placement.
- **Retired:** absence of both a relation record and a scheduling constraint is
  the canonical representation. No negative or `retired` relation record is
  required.

The generic runtime policy record
`separate_products_same_slot` in `ontology/runtime-policy.yaml` remains
unchanged. It defines the operation grammar, not the medical meaning of each
constraint. Do not add a second operation or a Python exception for any pair.

## Decision matrix

`ADD` relation IDs below are proposed stable IDs; they do not yet exist. The
existing relation IDs and constraint IDs are exact current records.

| Decision ID | Relation home and exact record action | Placement home and exact record action | Expected runtime behavior | Acceptance disposition |
| --- | --- | --- | --- | --- |
| `IS-001` zinc–copper | Keep `data/relations.yaml:rel_balance_001` as the single zinc/copper knowledge record. Do **not** add a duplicate `review_with` record; balance already owns the existing chronic status warning. | Change `sc_zinc_copper_separate_slots`: add `blocks_slots: false`, `scores_advisory: true`, `score_delta: -1`; retain symmetric selectors and rationale/action. | Separate products matched in one slot receive advisory penalty and a `pairwise_journal` row with `disposition: advisory`. Same-product components produce no intra-product hard-conflict warning. Balance emits only its existing missing-side warning, not a duplicate active-pair warning. | Advisory; no hard block. |
| `IS-002` calcium–iron | `ADD rel_review_with_016` to `data/relations.yaml`, selectors by `name: Calcium` and `name: Iron`, `assertion_kind: clinical_review_signal`, bounded dose/context reason, medium severity. | Keep `sc_calcium_iron_separate_slots` and make its explicit advisory fields the model: `blocks_slots: false`, `scores_advisory: true`, `score_delta: -1`; no 2–4 hour interval. | Two active endpoints produce one `review_with_substance_present` warning. If separate products share a slot, journal row is `separate_constraint`, `disposition: advisory`, `state: together`, `satisfied: false`; search may move them apart. No intra-product conflict warning. | Advisory; no hard block. |
| `IS-003` calcium–zinc | `ADD rel_review_with_017` with name selectors, clinical-review metadata, and bounded high-dose reason. | Change `sc_calcium_zinc_separate_slots` to explicit advisory fields (`false/true/-1`); retain symmetric operation and selectors. | Active pair gets one active-review warning. Same-slot separate products get advisory journal/penalty, not infeasibility. A blend containing both does not get a hard conflict. | Advisory; no hard block. |
| `IS-004` lysine–arginine | `ADD rel_review_with_018` as `review_with`, name selectors `L-Lysine` ↔ `L-Arginine`, `clinical_review_signal`, explicitly high-dose/transport-bounded. Name selectors intentionally cover the existing lysine and arginine forms; this is review knowledge, not form-specific placement. | No scheduling constraint. Do not add `sc_lysine_arginine_separate_slots`. | Both active endpoints produce one active-review warning, regardless of whether slots coincide. No pairwise journal row, no score penalty, and no intra-product conflict. | Review-only. |
| `IS-005` glycine–beta-alanine | `ADD rel_review_with_019` as `review_with`, name selectors `Glycine` ↔ `Beta-alanine`, `clinical_review_signal`, low-confidence mechanistic reason. | No scheduling constraint; do not restore a `competes` equivalent. | Active pair gets review warning only. Independent authored timing/activity preferences still score normally; no pairwise separation row or penalty. | Review-only. |
| `IS-006` glycine–taurine | `ADD rel_review_with_020` as `review_with`, name selectors `Glycine` ↔ `Taurine`, `clinical_review_signal`, low-confidence mechanistic reason. | No scheduling constraint. | Active pair gets review warning only; no slot feasibility, advisory penalty, or intra-product conflict behavior. | Review-only. |
| `IS-007` mineral–fat-soluble class | No relation record. Confirm no `source_class: mineral`/`target_class: fat_soluble` record is added. | No scheduling constraint. Current feature state is already the desired absence; do not introduce a class selector or generic replacement. | A mineral and fat-soluble substance have no pairwise journal or relation warning solely because of class membership. Card-level intake votes remain independent. | Retired. |
| `IS-008` tocopherol–tocotrienol | `ADD rel_review_with_021` as `review_with`, exact entity IDs `sub_844a87d72b` ↔ `sub_5723eafac4`, `clinical_review_signal`, low-confidence handling reason. Entity-ID selectors are already exact in the relation contract; do not add a scheduling-only `scope` field. Do not broaden to all `Vitamin E`. | Remove `sc_tocopherol_tocotrienol_separate_slots` from `ontology/scheduling-constraints.yaml`. | Separate active products produce an active-review warning only; no pairwise journal row or score penalty. `Toco-Sorb` (both forms in one physical product) remains schedulable and produces no intra-product hard-conflict warning. | Review-only; remove hard block. |

### ID and selector checks

The proposed relation IDs continue the existing sequence (`rel_review_with_015`
is the current last record). Before implementation, the compiler/check gate
must confirm that every proposed ID is unique and that every selector resolves.
The exact-form relation in `IS-008` must remain ID-scoped because both endpoints
have `name: Vitamin E`; a name selector would accidentally include unrelated
Vitamin E forms. For `IS-004` through `IS-006`, name selectors are intentional:
the relation is about the amino-acid family, and the current relation contract
already supports name-based entity selectors.

## Expected warning and journal contract

The distinction below is acceptance-critical:

| Situation | Relation warning | Pairwise journal | Placement |
| --- | --- | --- | --- |
| Retained `review_with`, both endpoints active | One `review_with_substance_present` / “Active review pairing” warning | None | No effect |
| Advisory constraint, separate products, same slot | Relation warning only if its separate `review_with` record is retained; otherwise none | One `separate_constraint`, `disposition: advisory`, `state: together`, `satisfied: false` | Soft penalty `-1`; candidate remains feasible |
| Advisory constraint, separate products, apart | Same relation-warning rule as above | One `separate_constraint`, `disposition: advisory`, `state: apart`, `satisfied: true` | No penalty for that slot |
| Any retained advisory relation inside one product | Active review warning if represented by `review_with` | None | Product remains feasible; no intra-product conflict warning |
| Retired mineral/fat-soluble class | None | None | Only individual card votes apply |
| Former hard constraint removed from `scheduling-constraints.yaml` | None | None | No feasibility or conflict effect |

`review_with` warnings are intentionally independent of slot co-location: they
mean “review both active endpoints,” not “separate them.” This is why a
review-only decision must not be encoded as a scheduling constraint.

## Acceptance scenarios

These are bounded implementation scenarios, not full release gates.

1. **Current active trace-mineral product (`IS-001`).** The active
   `prd_932319251f` / Only Trace Minerals contains
   `sub_8ppxce3s17` (zinc) and `sub_844a0cc551` (copper). It remains in one
   physical slot, emits no intra-product scheduling-conflict warning, and does
   not create an impossible hard placement. A standalone zinc/copper fixture
   in one slot yields advisory journal state `together` and remains feasible.
2. **Advisory calcium fixtures (`IS-002`, `IS-003`).** Separate calcium and
   iron, and separate calcium and zinc, placed together yield advisory journal
   rows and `-1` penalties; moving them apart yields `satisfied: true`. A
   product containing both components never yields a hard intra-product row.
3. **Review-only amino fixtures (`IS-004`–`IS-006`).** Active lysine/arginine,
   glycine/beta-alanine, and glycine/taurine pairs each yield their authored
   active-review warning and no journal/penalty. Removing either endpoint
   removes that warning; no absence warning is generated.
4. **Retired class neutral fixture (`IS-007`).** A generic mineral and a
   fat-soluble substance in the same slot produce no class relation warning or
   pairwise journal row. Their individual intake votes still appear in the
   normal placement explanation.
5. **Exact-form vitamin E (`IS-008`).** `Toco-Sorb`
   (`prd_9eoksvn2mt`) containing both exact IDs remains schedulable without an
   intra-product conflict. Two separate exact-form fixture products yield one
   active-review warning and no separation journal row. A different Vitamin E
   form does not match `rel_review_with_021`.
6. **Canonical-source regeneration.** After implementation, generated runtime
   vocabulary/projection artifacts contain exactly the retained relation IDs,
   the three advisory constraints, and no tocopherol constraint or mineral
   class rule. No Python file contains any of the eight pair names.

## Explicit non-goals and blockers

- Do not add dose arithmetic, elemental-dose fields, recurrence logic, or a new
  “review-only constraint” abstraction. The current contract already separates
  review warnings from placement constraints.
- Do not restore the seven former hard blockers merely to obtain parity with
  `main`; parity is not the acceptance criterion.
- Do not repair unrelated schedule-diff rows or catalog migration questions in
  this matrix. The three active daily→unassigned product moves and the B5 form
  consolidation remain the separate decisions recorded by the companion
  inventories.
- Implementation is blocked only if the existing `review_with` warning,
  advisory constraint fields, or exact-form selector semantics cannot produce
  the scenarios above without Python changes. No such blocker is present in
  the current source inspection.
