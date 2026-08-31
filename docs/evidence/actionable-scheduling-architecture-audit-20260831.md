# Actionable Scheduling Architecture Audit — 2026-08-31

## Exact-head verdict

**STOP — two Medium findings.** The executable scheduling boundary is
substantively clean: every admitted directed input reaches planning through a
typed fact and an exact universal-law path; the optimizer remains globally
lexicographic and fail-closed; and the retired catalog/coverage/grooming/notes
surfaces do not enter planning or the generated schedule. The audit cannot be
marked complete because the living domain contract still requires retired
coverage machinery, and the schedule writer retains fallback product wording.

Audited commit: `e59184d1b3e57ff470aa57e6b830cb800fc38f0e`
(`feature/actionable-scheduling-knowledge`; clean worktree before this audit
document). This is a read-only source/data audit; no test command was run.

The latest targeted witness receipt is
[`actionable-scheduling-targeted-witnesses-20260831.yaml`](actionable-scheduling-targeted-witnesses-20260831.yaml).
It records ten bounded green witnesses at `cdd275a`; `e59184d` changes only
that receipt and the recovery plan, not runtime code or input data. It is useful
supporting evidence, but is not represented here as a newly executed exact-head
test gate.

## Input to output map

| Stage | Exact admitted data | Boundary evidence |
| --- | --- | --- |
| Artifact admission | `ontology/canonical-facts.yaml`, `canonical-laws.yaml`, and `runtime-policy.yaml` compile into `ontology/generated/runtime-program.json`. | `planner/ontology/artifacts.py` verifies the generated locks/source hash; `runtime_program.py` decodes an exact shape and requires exact law coverage for every admitted family/value. The generated program contains **11 facts**, **10 laws**, three populated fact families (`FoodEffect`, `PreExercisePerformanceEffect`, `ProductFoodInstruction`), and no retired fields. |
| Scenario facts | `data/stacks.yaml` selects only the policy-declared `daily` and `training` items; product/substance cards provide identities and composition roles; `data/pillboxes.yaml` provides logical-domain slots and typed anchors. | `planner/engine/_plan_inputs.py` loads/validates these sources; `planner/engine/_plan_active_index.py` excludes non-routable partitions and derives roles exclusively from product components. It neither loads `data/relations.yaml` nor a dashboard, candidate, coverage, or receipt file. |
| Directed inference | One canonical fact has a typed subject and matching typed applicability; one exact `(family, fact_value)` law provides one dimension/value. | `validate_canonical_scheduling` checks referenced products, substances, roles, and evidence-source IDs. `execute_canonical_inference` has an exact law lookup with no item-name or open-vocabulary fallback, normalizes identities to `(item_id, dimension, value)`, and returns a conflict for opposing same-axis values. |
| Optimization | Immutable item/domain map, typed slots/anchors, normalized pressures, closed dimension values, and the exact satisfaction strategy. | `CanonicalPublicationSource` accepts successful inference only. `CanonicalOptimizerInput` contains no evidence score, candidate, relation, placement, or action field. The solver maximizes unique pressures, then minimizes integer squared load per domain, then minimizes the stable assignment key; invalidity, conflict, resource exhaustion, interruption, or proof failure returns layout-free `Indeterminate`. |
| Output | The proved assignments, objective, normalized pressure matches, fact/law/applicability/provenance trace, exact load proofs, and derived presentation grouping. | `write_schedule_file` calls the optimizer once and writes only after `Optimal`; `canonical_output.py` reconstructs every displayed pressure match from inference plus assignment. The schedule schema has no candidate, disposition, coverage, grooming, notes, stored preference, or evidence-weight field. |

### Directed-admission receipt

The generated runtime program lists all 11 facts with a typed
`subject`/`applicability`, and all 10 laws with an exact fact-family/value to
dimension/value mapping. On the current shelf, the recorded witness has 18
items, nine applicable fact derivations collapsed into eight unique normalized
pressures, exact squared load 58, and ten `balance_and_tie_break_only`
placements. The duplicate derivation is the two-role krill-oil path to one
pressure identity; it is not an extra objective weight.

This satisfies the canonical ADR’s required shape: typed world fact → universal
identity-free law → normalized pressure → exact proof. Laws contain no product,
substance, component, slot, desired placement, action, or numeric evidence
weight.

## Negative-boundary receipt

The following read-only exact-head checks were performed.

| Claim | Receipt | Result |
| --- | --- | --- |
| Retired runtime surfaces are absent | `git ls-files` and repository search for `scheduling-candidates`, `coverage-closure`, `grooming-receipts`, `candidate_catalog`, `coverage`, and `grooming`; direct existence check of the former modules/data files. | PASS: no tracked retired surface; `planner/ontology/candidate_catalog.py`, `planner/ontology/coverage.py`, `planner/engine/grooming.py`, and their three data files are absent. `5a7368c` is an ancestor of the audited HEAD and removes the cumulative surface. |
| Retired concepts cannot be consumed by the planner | Search of non-test runtime/configuration sources for `scheduling_assessment`, `prefer_with`, stored same/different-slot terms, candidate catalog, coverage certificate, grooming receipt, disposition, generic notes, or evidence weight; inspection of the only plan input loader. | PASS: no match in the scheduling runtime/configuration sources. The plan path does not import relations, dashboards, or `docs/evidence`. |
| Generic card notes cannot enter runtime | Search for an authored `notes:` key below `data/products` and `data/substances`; inspect generated product/card schemas. | PASS: no authored key. Generated schemas expose no `notes` property for product, substance, or component and use closed object definitions. |
| Offline migration evidence is not a runtime input | Inspect `docs/evidence/actionable-scheduling-note-*`, recovery baseline/difference, and targeted-witness receipts; search planner/scripts/ontology for imports of those paths. | PASS: these files are historical/offline documentation. They are not planner inputs. A canonical fact may retain typed provenance (including an old source locator or quotation); that is explicit evidence metadata on a formal fact, not a generic `notes` field, candidate disposition, or parser input. |
| No hard-coded supplement/product identity in executable planner Python | Search `planner/` and `scripts/` for concrete `prd_*`, `sub_*`, and `cmp_prd_*` literals. | PASS: none found in executable planner code; only generic identifier construction/validation remains. |
| No semantic inference fallback | Inspect canonical inference and optimizer. | PASS: law resolution is exact `(family, value)` lookup; unsupported strategy/value, missing law, malformed input, or conflict fails closed. No name, prose, synonym, relation, or candidate fallback can create a pressure. |
| Exact result remains global lexicographic | Inspect `runtime-policy.yaml`, `canonical_optimizer.py`, and the current witness receipt. | PASS: objective order is unique pressure satisfaction → exact integer squared load → stable assignment key. The solver keeps all reachable load states, independently verifies the result, and publishes no incumbent or timeout layout. |

## Findings

### M-1 — living domain contract still requires retired coverage machinery

`docs/domain-model.md` is designated by `AGENTS.md` as the living contract, but
its product invariant and “Actionable knowledge coverage boundary” still require
candidate dispositions and coverage certificates, and make incomplete coverage
`Indeterminate`. This conflicts with the accepted runtime-simplification
decision, which explicitly supersedes those runtime and user-output requirements
and with the exact HEAD where their implementations have been removed.

Impact: the written governing model gives future implementation/review work two
incompatible publication boundaries. The executable path follows the
simplification; the stated living contract does not.

Required disposition: reconcile `docs/domain-model.md` to the accepted
simplification decision, retaining historical adjudications only as offline
provenance. No runtime restoration is warranted.

### M-2 — schedule output retains generic fallback product vocabulary

`planner/canonical_output.py` formats a product as
`product.name or product.id or "unknown product"` and treats the brand
`"unknown"` specially. This is not a supplement-specific semantic ID and the
validated current cards provide labels, so it does not affect the audited
current-shelf witness or the optimizer. It nevertheless violates the required
no-fallback-vocabulary output boundary: a malformed/directly constructed
publication source could emit authored fallback wording instead of failing
closed.

Impact: the solver result remains exact, but the schedule representation is not
strictly derived from validated source facts in every callable path.

Required disposition: make canonical schedule publication reject a blank/missing
product label/brand state instead of substituting fallback text. Keep any
non-scheduling search/review display fallbacks outside this publication
boundary.

## Checklist disposition

The “Perform an exact-head data and architecture audit” item in
[`actionable-scheduling-knowledge-recovery-20260831.md`](../plans/actionable-scheduling-knowledge-recovery-20260831.md)
remains unchecked because this audit is **STOP**, not PASS. No other plan item
was changed.
