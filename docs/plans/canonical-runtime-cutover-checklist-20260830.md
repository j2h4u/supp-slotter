# Canonical Runtime Cutover Checklist — 2026-08-30

## Purpose

This is the living execution record for the whole-product Sol High expert-panel
audit performed after removal of embedded SurrealDB. Check an item only after
its implementation and paired V-right acceptance evidence both pass. A code
change alone is not completion.

The target is the accepted contract in
[`docs/domain-model.md`](../domain-model.md) and the governing
[`canonical-instance ADR`](../decisions/canonical-instance-inference-boundary-20260822.md).
The canonical runtime remains **NON-CONFORMING** until the Critical and High
cutover items below are complete. The spike is not finished until every item in
this document, including Medium cleanup and final acceptance, is complete.

## Status legend

- `[ ]` not completed
- `[x]` implemented and accepted by the named evidence
- `BLOCKED` means the concrete blocker is recorded next to the item

Every checked item must gain an indented `Evidence:` entry containing the
implementing commit SHA, the exact targeted acceptance command/result, and the
path to its durable test, fixture, or decision artifact. A passing broad suite
without item-specific evidence is insufficient. Evidence must be produced from
the checked commit or a descendant that contains it.

The closed families and all nine admitted values are enumerated normatively in
[`docs/domain-model.md`](../domain-model.md#closed-scheduling-fact-vocabulary).
This checklist never substitutes a summary for that source.

## v2 integration evidence status

The commit-range and `just release` results recorded below are historic v1
evidence only; they do not describe this uncommitted v2 cutover and must not be
used as its release claim. The v2 acceptance boundary is the generated
`ontology-runtime-program-v2`, its generic `canonical_scheduling` projection,
and `Slot.anchors`. The current integration records its exact command results
in the handoff rather than running a release recipe; the three independent
final-review boxes at the end deliberately remain open.

## Critical — canonical product behavior

- [x] **Make canonical facts and logical topology the only scheduler inputs.**
  Activate the five closed fact families, explicit composition roles,
  applicability, provenance, and the independent slot anchors. Remove direct
  runtime scheduling from authored `schedule.*` answers.
  - Acceptance: a fixture containing only canonical facts produces pressures
    and a layout without any legacy schedule alias.
  - Acceptance: manifest/runtime inputs contain the authoritative canonical
    fact catalog and logical topology, not shadow-only schemas.
  - Evidence: `cdc33c5f7a013b151516a9e58beff4b0a21715e3` through
    `6bc4d9fba7bdb73f31cb6a0add0db460d2a2e59a`; `just canonical-runtime` ->
    17 passed on the committed ancestor/equivalent runtime, and final-head
    `just release` -> exit 0 (smoke 23; ontology A/B/C 50/34/60; runtime 71).
    Witnesses: `tests/test_canonical_fact_catalog_integration.py::test_plan_inputs_carries_verified_canonical_scheduling`,
    `tests/test_cutover_authored_vertical_scenarios.py::test_authored_vertical_fixture_compiles_loads_and_routes_all_runtime_anchors`,
    `ontology/canonical-facts.yaml`, `ontology/generated/runtime-program.json`.

- [x] **Implement the complete finite facts-to-pressures law table.**
  Every one of the nine admitted fact values derives the specified unary
  pressure through a generic proof-producing executor.
  - Acceptance: finite positive, negative, applicability, and boundary truth
    tables cover all admitted values.
  - Acceptance: proof nodes name typed facts, composition/applicability path,
    provenance, and law identity.
  - Evidence: `cdc33c5f7a013b151516a9e58beff4b0a21715e3` through
    `6bc4d9fba7bdb73f31cb6a0add0db460d2a2e59a`; `just canonical-runtime` ->
    17 passed; final-head `just release` -> exit 0, ontology A 50 and runtime
    71. Witnesses: `tests/test_canonical_law_catalog.py::test_every_annotated_family_value_has_exactly_one_generic_law`,
    `tests/test_canonical_inference.py::test_every_admitted_value_maps_to_one_pressure`,
    `tests/test_canonical_inference.py::test_proof_contains_law_fact_subject_path_and_provenance`,
    `docs/domain-model.md`, `ontology/runtime-policy.yaml`.

- [x] **Normalize pressure identities and fail closed on contradictions.**
  Repeated components, witnesses, sources, or inference paths must enrich one
  `(item_id, dimension, value)` proof node and never add votes. Different values
  on one item/dimension yield layout-free `Indeterminate`.
  - Acceptance: duplicate/multiplicity tests remain one pressure and one vote.
  - Acceptance: same-dimension opposition returns diagnostics and no layout;
    cross-dimension pressures remain optimizer inputs.
  - Evidence: `6bc4d9fba7bdb73f31cb6a0add0db460d2a2e59a`; `just canonical-runtime`
    -> 17 passed; final-head `just release` -> exit 0, runtime 71. Witnesses:
    `tests/test_canonical_inference.py::test_duplicate_witnesses_facts_components_and_paths_normalize_to_one_pressure`,
    `tests/test_canonical_inference.py::test_same_dimension_values_are_layout_free_conflict`,
    `tests/test_canonical_inference.py::test_cross_dimension_pressures_coexist`,
    `planner/ontology/canonical_inference.py`.

- [x] **Replace the weighted/float objective with the exact lexicographic
  optimizer.** First maximize satisfied unique pressures; then minimize exact
  integer squared loads per independent domain; then use stable item IDs and
  `(slot.order, slot_id)` for the final assignment key.
  - Acceptance: no float score, epsilon, authored weight, bonus, penalty, or
    evidence count participates in selection.
  - Acceptance: stack/YAML ordering permutations produce the same assignment.
  - Acceptance: bounded production results match an independent exhaustive
    oracle in status, objective tuple, and assignment.
  - Evidence: `ca8b323561ba667522f6d4e96db77bfbf989e523` through
    `6bc4d9fba7bdb73f31cb6a0add0db460d2a2e59a`; `just canonical-runtime` ->
    17 passed; final-head `just release` -> exit 0, smoke 23 and runtime 71.
    Witnesses: `tests/test_canonical_optimizer.py::test_pressure_maximum_precedes_balance_and_keeps_only_maximum_slots`,
    `tests/test_canonical_optimizer.py::test_exact_squared_load_balance_is_unbounded_and_stable_by_item_id`,
    `tests/test_canonical_optimizer.py::test_tie_break_uses_slot_id_after_order_and_is_domain_independent`,
    `tests/test_canonical_optimizer.py::test_bounded_randomized_results_match_independent_cartesian_oracle`,
    `planner/canonical_optimizer.py`.

- [x] **Enforce the closed `Optimal | Indeterminate` publication boundary.**
  Publish `schedule.yaml` only after global optimality is proved. Conflicts,
  invalid inputs, interruption, timeout, or resource exhaustion publish no
  incumbent or best-so-far layout.
  - Acceptance: forced failure cases leave no layout and expose typed
    diagnostics.
  - Acceptance: a successful result records the exact objective tuple and
    proof trace.
  - Evidence: `ca8b323561ba667522f6d4e96db77bfbf989e523` through
    `6bc4d9fba7bdb73f31cb6a0add0db460d2a2e59a`; `just canonical-runtime` ->
    17 passed; final-head `just release` -> exit 0, smoke 23 and runtime 71.
    Witnesses: `tests/test_canonical_publication.py::test_publication_boundary_refuses_indeterminate_and_legacy_documents`,
    `tests/test_canonical_publication.py::test_successful_publication_replaces_lease_with_complete_optimal_document`,
    `tests/test_canonical_publication.py::test_canonical_document_contains_typed_proofs_and_no_legacy_explanations`,
    `tests/test_canonical_optimizer.py::test_deadline_interruption_and_state_bound_never_publish_incumbents`,
    `planner/schedule_writer.py`, `planner/canonical_optimizer_result.py`.

## High — remove the superseded scheduler and split authority

- [x] **Remove executable `prefer_with`, pair constraints, pair bonuses, and
  pair penalties.** Preserve admissible raw evidence or review annotations, but
  do not port stored pair answers into the canonical optimizer.
  - Evidence: `ca8b323561ba667522f6d4e96db77bfbf989e523` through
    `6bc4d9fba7bdb73f31cb6a0add0db460d2a2e59a`; final-head `just release` ->
    exit 0, ontology B 34 and runtime 71. Witnesses:
    `tests/test_canonical_scheduling_migration.py::test_no_runtime_consumer_reads_the_removed_card_fields`,
    `tests/test_runtime_contract_v2.py::test_retired_objective_and_pair_fields_are_rejected`,
    `docs/migrations/legacy-atom-ledger.yaml`, `planner/canonical_optimizer.py`,
    `tests/test_scheduler_reviewer_authority.py::test_review_only_relation_cannot_change_command_level_schedule`.

- [x] **Remove component vote aggregation and legacy policy scoring.** Delete
  old runtime-policy weights, score magnitudes, balance weight, epsilon policy,
  and tests that protect those semantics.
  - Evidence: `0af132e002a0dcb962e28c06ad67ba2828596ec0` through
    `6bc4d9fba7bdb73f31cb6a0add0db460d2a2e59a`; final-head `just release` ->
    exit 0, ontology C 60 and runtime 71. Witnesses:
    `tests/test_runtime_contract_v2.py::test_v2_contract_decodes_exactly_and_excludes_retired_objective_inputs`,
    `tests/test_runtime_contract_v2.py::test_retired_objective_and_pair_fields_are_rejected`,
    `tests/test_canonical_inference.py::test_duplicate_witnesses_facts_components_and_paths_normalize_to_one_pressure`,
    `ontology/runtime-policy.yaml`.

- [x] **Migrate logical topology from compound `near`/`food` and physical
  compartment semantics.** Use optional independent `meal_context`,
  `circadian_anchor`, and `exercise_anchor`; slots remain unbounded logical
  intake groups.
  - Evidence: `cdc33c5f7a013b151516a9e58beff4b0a21715e3` through
    `6bc4d9fba7bdb73f31cb6a0add0db460d2a2e59a`; final-head `just release` ->
    exit 0, smoke 23, ontology B 34, and CRAP 237. Witnesses:
    `tests/test_logical_slot_topology.py::test_topology_axes_are_optional_and_do_not_use_label_or_order`,
    `tests/test_logical_slot_topology.py::test_legacy_and_physical_slot_fields_are_rejected`,
    `tests/test_cutover_authored_vertical_scenarios.py::test_authored_vertical_fixture_compiles_loads_and_routes_all_runtime_anchors`,
    `tests/test_pillbox_loader_contract.py::test_loader_projects_independent_topology_fields`.

- [x] **Give composition roles stable portable identities.** Product component
  reorder, notes, or display edits must not change the identity used by facts,
  applicability, provenance, RDF, or a future ontology backend.
  - Evidence: `cdc33c5f7a013b151516a9e58beff4b0a21715e3` through
    `6bc4d9fba7bdb73f31cb6a0add0db460d2a2e59a`; final-head `just release` ->
    exit 0, ontology A 50 and B 34. Witnesses:
    `tests/test_composition_role_identity.py::test_authored_component_identity_survives_reorder_and_notes_edit`,
    `tests/test_composition_role_identity.py::test_product_formula_validator_rejects_dangling_mismatched_and_duplicate_roles`,
    `tests/test_canonical_fact_catalog_integration.py::test_canonical_reference_validator_rejects_dangling_or_inconsistent_references`,
    `docs/domain-model.md`.

- [x] **Close the legacy evidence ledger before deleting source
  knowledge.** Resolve all `sol_adjudication` atoms into typed facts, raw
  quotations, source metadata, or explicit exclusions. Never bulk-translate a
  legacy placement into a canonical fact.
  - Closure receipt: Git-derived reconstruction covers the original 2,161
    atoms, including 1,786 originally routed to Sol: 1,129 retained unchanged,
    771 explicit exclusions, 255 source-metadata rows, and six typed facts.
    The receipt records deterministic crosswalk and classification-ruleset
    hashes; the complete row crosswalk is generated, verified, and discarded in
    a temporary directory rather than checked in as a museum.
  - Acceptance: the receipt reconstructs every original atom and every selected
    scheduling atom has exactly one permitted final disposition before source
    deletion; no pending Sol queue is retained as runtime state.
  - Evidence: `9050ca70ea2eaff6c92dc86612219634a985fb90` and
    `cdc33c5f7a013b151516a9e58beff4b0a21715e3` through
    `6bc4d9fba7bdb73f31cb6a0add0db460d2a2e59a`; final-head `just release` ->
    exit 0, ontology B 34. Witnesses:
    `tests/test_canonical_scheduling_migration.py::test_compact_receipt_reconstructs_and_closes_every_original_atom`,
    `tests/test_canonical_scheduling_migration.py::test_card_deletion_has_no_collateral_semantic_change`,
    `docs/migrations/legacy-atom-ledger.yaml`, `scripts/generate_migration_ledger.py`.

- [x] **Add a canonical-runtime acceptance gate.** It must cover laws,
  normalization, contradiction, exact objective stages, stable tie-break,
  exhaustive-oracle equivalence, and no-publication failures. Existing green
  legacy tests are not cutover evidence.
  - Evidence: `cdc33c5f7a013b151516a9e58beff4b0a21715e3` through
    `6bc4d9fba7bdb73f31cb6a0add0db460d2a2e59a`; `just canonical-runtime` ->
    17 passed, and final-head `just release` -> exit 0 with the owning complete
    modules covered (smoke 23; runtime 71; CRAP 237). Inventory witness:
    `tests/test_run_unit_gate.py::test_canonical_runtime_inventory_is_exact_stable_and_release_covered`;
    capability nodes and release inclusion: `scripts/run_unit_gate.py`.

## High/Medium — architectural cleanup

- [x] **Finish the SurrealDB-era cleanup.** Remove unused `ReadModelContext`
  fields, discarded dashboard/policy loading, test-only serializers, and the
  remaining stringly `dict[str, object]` assertion round-trip. Keep only narrow
  typed query functions or a genuinely useful typed facade.
  - Evidence: `cdc33c5f7a013b151516a9e58beff4b0a21715e3` through
    `6bc4d9fba7bdb73f31cb6a0add0db460d2a2e59a`; final-head `just release` ->
    exit 0, ontology B 34/C 60 and CRAP 237. Witnesses:
    `tests/test_read_model_relations.py::test_typed_read_model_projects_complete_partition_facts_relations_and_warnings`,
    `tests/test_architecture_contracts.py::test_runtime_planner_has_no_linkml_compiler_symbols`,
    `planner/query_model/read_model.py`, `planner/query_model/types.py`.

- [x] **Correct all SurrealDB documentation.** No active documentation may
  claim that the removed embedded database or SurrealQL runtime still exists.
  - Evidence: `cdc33c5f7a013b151516a9e58beff4b0a21715e3`; final-head
    `just release` -> exit 0, static checks clean. Repository documentation
    search at `6bc4d9fba7bdb73f31cb6a0add0db460d2a2e59a` finds no active
    SurrealDB/SurrealQL claim outside this historical checklist. Durable
    replacement boundary: `docs/domain-model.md`, `docs/decisions/canonical-instance-inference-boundary-20260822.md`.

- [x] **Separate online runtime artifacts from offline formal verification.**
  Ordinary plan/find/review commands should load only the compact verified
  runtime contract and required card schemas. RDF/SHACL/context/projection
  validation remains an explicit ontology/release gate; RDFLib and pySHACL
  should not be production dependencies unless runtime use is demonstrated.
  - Evidence: `cdc33c5f7a013b151516a9e58beff4b0a21715e3` through
    `6bc4d9fba7bdb73f31cb6a0add0db460d2a2e59a`; final-head `just release` ->
    exit 0, ontology A/B/C 50/34/60 and corpus projection conforms true.
    Witnesses: `tests/test_ontology_runtime_loader.py::test_runtime_bundle_retains_no_formal_projection_artifacts_or_reads`,
    `tests/test_architecture_contracts.py::test_runtime_planner_has_no_linkml_compiler_symbols`,
    `tests/test_scheduler_reviewer_authority.py::test_runtime_commands_read_only_declared_runtime_outputs_and_command_data`,
    `justfile`, `planner/ontology/runtime_program.py`.

- [x] **Make validation read-only.** `planner check`, plan, show, and review
  must not rename, rewrite, move, or delete canonical cards. Put normalization
  and repairs behind an explicit command and make partial failure safe.
  - Evidence: `6bc4d9fba7bdb73f31cb6a0add0db460d2a2e59a`; final-head
    `just release` -> exit 0, smoke 23 and CRAP 237. Witnesses:
    `tests/test_maintenance.py::test_check_succeeds_without_mutating_canonical_inputs`,
    `tests/test_maintenance.py::test_plan_succeeds_without_mutating_canonical_inputs`,
    `tests/test_maintenance.py::test_show_and_review_do_not_mutate_authored_inputs`,
    `tests/test_maintenance.py::test_run_maintenance_rolls_back_on_partial_stage_failure`,
    `planner/maintenance.py`.

## Medium — product and data integrity

- [x] **Make unassigned ownership explicit.** Every tracked product belongs to
  exactly one active domain, inactive, or an explicit `tracked_unassigned`
  state with a reason. Accidental stack omission must not silently remove it
  from scheduling, warnings, and grooming.
  - Evidence: `cdc33c5f7a013b151516a9e58beff4b0a21715e3` through
    `6bc4d9fba7bdb73f31cb6a0add0db460d2a2e59a`; final-head `just release` ->
    exit 0, ontology C 60, runtime 71, and CRAP 237. Witnesses:
    `tests/test_runtime_contract_v2.py::test_authored_stack_partition_is_closed_and_reproduces_active_membership`,
    `tests/test_read_model_relations.py::test_typed_read_model_projects_complete_partition_facts_relations_and_warnings`,
    `tests/test_grooming.py::test_receipt_catalog_closes_the_real_active_queue`, `data/stacks.yaml`.

- [x] **Enforce pillbox/stack topology uniqueness.** A stack cannot silently be
  expanded through multiple pillboxes when the authored contract is 1:1.
  - Evidence: `cdc33c5f7a013b151516a9e58beff4b0a21715e3` through
    `6bc4d9fba7bdb73f31cb6a0add0db460d2a2e59a`; final-head `just release` ->
    exit 0, CRAP 237. Witnesses:
    `tests/test_pillbox_loader_contract.py::test_loader_rejects_multiple_pillboxes_for_one_stack`,
    `tests/test_pillbox_loader_contract.py::test_generated_contract_resolves_stack_references_from_validation_context`,
    `tests/test_logical_slot_topology.py::test_distinct_topologies_keep_distinct_stack_references`,
    `data/pillboxes.yaml`.

- [x] **Make non-daily presentation truthful without adding recurrence.** Use a
  neutral current-plan heading and keep episodic placements outside the claim
  that they are today's intake.
  - Evidence: `ca8b323561ba667522f6d4e96db77bfbf989e523` through
    `6bc4d9fba7bdb73f31cb6a0add0db460d2a2e59a`; final-head `just release` ->
    exit 0, smoke 23 and runtime 71. Witnesses:
    `tests/test_non_daily_presentation.py::test_marked_daily_product_is_an_episodic_current_plan_placement`,
    `tests/test_canonical_publication.py::test_not_every_day_is_a_presentation_group_for_the_proved_assignment`,
    `tests/test_cutover_vertical_scenarios.py::test_real_shelf_daily_episodic_and_training_products_are_complete`,
    `planner/ontology/presentation.py`. The generated `placement_basis` marker
    distinguishes pressure evidence from balance/tie-break-only placements.

- [x] **Align grooming with canonical migration work.** Missing required axes,
  unresolved applicability, and outstanding Sol adjudication must remain
  discoverable. Luna may collect evidence; only Sol adjudicates ontology facts.
  - Evidence: `6bc4d9fba7bdb73f31cb6a0add0db460d2a2e59a`; final-head
    `just release` -> exit 0, runtime 71 and CRAP 237. Witnesses:
    `tests/test_grooming.py::test_receipt_catalog_closes_the_real_active_queue`,
    `tests/test_grooming.py::test_removing_then_restoring_an_active_receipt_reopens_then_closes_its_role`,
    `tests/test_grooming.py::test_receipts_are_operational_and_not_a_plan_runtime_input`,
    `docs/evidence-coverage-grooming.md`.

- [x] **Prevent product/form-specific evidence from masquerading as universal
  substance evidence.** Bind formulation-specific material to stable
  composition roles and keep only genuinely universal evidence on substances.
  - Evidence: `cdc33c5f7a013b151516a9e58beff4b0a21715e3` through
    `6bc4d9fba7bdb73f31cb6a0add0db460d2a2e59a`; final-head `just release` ->
    exit 0, ontology A 50 and runtime 71. Witnesses:
    `tests/test_canonical_inference.py::test_substance_applicability_reaches_each_exact_matching_role`,
    `tests/test_canonical_fact_catalog_integration.py::test_canonical_reference_validator_accepts_matching_composition_role_fact`,
    `tests/test_composition_role_identity.py::test_product_formula_validator_rejects_dangling_mismatched_and_duplicate_roles`,
    `ontology/canonical-facts.yaml`.

- [x] **Require complete catalogs at query boundaries.** Membership and fact
  indexes must fail closed on missing products, substances, or references
  instead of returning plausible empty results.
  - Evidence: `6bc4d9fba7bdb73f31cb6a0add0db460d2a2e59a`; final-head
    `just release` -> exit 0, ontology B 34 and CRAP 237. Witnesses:
    `tests/test_read_model_relations.py::test_typed_read_model_rejects_every_incomplete_reference`,
    `tests/test_canonical_fact_catalog_integration.py::test_plan_inputs_rejects_full_canonical_scheduling_before_relation_processing`,
    `tests/test_canonical_fact_catalog_integration.py::test_canonical_reference_validator_rejects_dangling_or_inconsistent_references`,
    `planner/ontology/canonical_facts.py`.

## Medium — verification workflow

- [x] **Add one compact read-model cutover acceptance.** Assert the normalized
  active/inactive identities, fact index, relation classes, warning identities,
  matches, ordering, and deduplication over a representative fixture.
  - Evidence: `70b6dc53d49ab7bfa067f26a678045589d8d677e` through
    `6bc4d9fba7bdb73f31cb6a0add0db460d2a2e59a`; final-head `just release` ->
    exit 0, CRAP 237. Witness: `tests/test_read_model_relations.py::test_typed_read_model_projects_complete_partition_facts_relations_and_warnings`;
    fixture and typed facade: `planner/query_model/read_model.py`.

- [x] **Make release inventory exhaustive.** Exact-node modules must not allow
  newly added tests to be silently omitted.
  - Evidence: `cdc33c5f7a013b151516a9e58beff4b0a21715e3` through
    `6bc4d9fba7bdb73f31cb6a0add0db460d2a2e59a`; final-head `just release` ->
    exit 0 (smoke 23; ontology A/B/C 50/34/60; runtime 71; CRAP 237).
    Witnesses: `tests/test_run_unit_gate.py::test_release_inventory_is_bidirectional_and_rejects_unlisted_modules`,
    `tests/test_run_unit_gate.py::test_canonical_runtime_inventory_is_exact_stable_and_release_covered`,
    `scripts/run_unit_gate.py`.

- [x] **Make the default development gate fast and product-relevant.** Include
  one bounded real-shelf runtime smoke, avoid repeated validation in combined
  recipes, and keep corpus/formal/full gates explicit for release candidates.
  - Evidence: `cdc33c5f7a013b151516a9e58beff4b0a21715e3` through
    `6bc4d9fba7bdb73f31cb6a0add0db460d2a2e59a`; `just current-shelf-smoke` ->
    1 passed on the committed ancestor/equivalent runtime; final-head `just
    release` -> exit 0, smoke 23 and corpus projection conforms true.
    Witnesses: `tests/test_run_unit_gate.py::test_verify_composition_has_one_planner_validation_owner`,
    `tests/test_cutover_vertical_scenarios.py::test_real_shelf_daily_episodic_and_training_products_are_complete`,
    `justfile`.

- [x] **Clear the current static release blocker.** Resolve the existing
  migration-ledger type errors so the final release gate can actually complete.
  - Evidence: `6bc4d9fba7bdb73f31cb6a0add0db460d2a2e59a`; final-head `just
    release` -> exit 0, static checks clean and release CRAP 237; `just
    crap-check` final release report -> 707 functions, zero at CRAP >=30,
    coverage 82%. Durable boundary: `scripts/generate_migration_ledger.py`,
    `docs/migrations/legacy-atom-ledger.yaml`, `justfile`.

## Final cutover acceptance

- [x] Real daily, non-daily, and training scenarios use canonical facts and
  logical topology only. Durable acceptance fixtures must cover all three
  scheduling domains plus the repository's current active shelf; their expected
  result is expressed as status, pressure/objective invariants, membership, and
  anchor semantics rather than a byte-for-byte legacy golden.
  - Evidence: `cdc33c5f7a013b151516a9e58beff4b0a21715e3` through
    `6bc4d9fba7bdb73f31cb6a0add0db460d2a2e59a`; `just current-shelf-smoke` ->
    1 passed on the committed ancestor/equivalent runtime; final-head `just
    release` -> exit 0, smoke 23 and runtime 71. Witnesses:
    `tests/test_cutover_authored_vertical_scenarios.py::test_authored_vertical_fixture_compiles_loads_and_routes_all_runtime_anchors`,
    `tests/test_cutover_vertical_scenarios.py::test_real_shelf_daily_episodic_and_training_products_are_complete`
    (current-shelf exact witness: four satisfied pressures and fourteen
    balance-and-tie-break-only explanations).
- [x] Meaningful food, wake/sleep, and before/after behavior is preserved or
  improved without requiring byte-for-byte legacy placement.
  - Evidence: `cdc33c5f7a013b151516a9e58beff4b0a21715e3` through
    `6bc4d9fba7bdb73f31cb6a0add0db460d2a2e59a`; `just canonical-runtime` ->
    17 passed; final-head `just release` -> exit 0, smoke 23 and runtime 71.
    Witnesses: `tests/test_cutover_authored_vertical_scenarios.py::test_authored_vertical_fixture_compiles_loads_and_routes_all_runtime_anchors`,
    `tests/test_canonical_inference.py::test_every_admitted_value_maps_to_one_pressure`,
    `tests/test_cutover_vertical_scenarios.py::test_real_shelf_daily_episodic_and_training_products_are_complete`.
- [x] Every published layout is proved globally `Optimal`; every conflict or
  unproved search is layout-free `Indeterminate`.
  - Evidence: `ca8b323561ba667522f6d4e96db77bfbf989e523` through
    `6bc4d9fba7bdb73f31cb6a0add0db460d2a2e59a`; `just canonical-runtime` ->
    17 passed; final-head `just release` -> exit 0, smoke 23 and runtime 71.
    Witnesses: `tests/test_canonical_optimizer.py::test_bounded_randomized_results_match_independent_cartesian_oracle`,
    `tests/test_canonical_publication.py::test_publication_boundary_refuses_indeterminate_and_legacy_documents`,
    `tests/test_canonical_optimizer_plan_integration.py`, `planner/schedule_types.py`.
- [x] No supplement, pair, placement, weight, or domain law is recoverable only
  from Python.
  - Evidence: `0af132e002a0dcb962e28c06ad67ba2828596ec0` through
    `6bc4d9fba7bdb73f31cb6a0add0db460d2a2e59a`; final-head `just release` ->
    exit 0, ontology A/B/C 50/34/60. Witnesses:
    `tests/test_runtime_contract_v2.py::test_v2_contract_decodes_exactly_and_excludes_retired_objective_inputs`,
    `tests/test_canonical_law_catalog.py::test_every_annotated_family_value_has_exactly_one_generic_law`,
    `ontology/runtime-policy.yaml`, `ontology/canonical-facts.yaml`.
- [x] A future TypeDB implementation can reproduce facts, applicability,
  pressures, status, objective tuple, and selected layout without extracting
  semantics from Python.
  - Evidence: `cdc33c5f7a013b151516a9e58beff4b0a21715e3` through
    `6bc4d9fba7bdb73f31cb6a0add0db460d2a2e59a`; final-head `just release` ->
    exit 0, ontology A/B/C 50/34/60, runtime 71, and corpus projection conforms
    true. Witnesses: `tests/test_runtime_contract_v2.py::test_v1_contract_is_rejected_without_compatibility_fallback`,
    `tests/test_canonical_fact_catalog_runtime.py::test_decoder_types_facts_once_with_family_as_data`,
    `ontology/generated/runtime-program.json`, `docs/domain-model.md`.
- [x] The legacy runtime and obsolete regression tests are deleted, not retained
  as a compatibility museum.
  - Evidence: `ca8b323561ba667522f6d4e96db77bfbf989e523` through
    `6bc4d9fba7bdb73f31cb6a0add0db460d2a2e59a`; final-head `just release` ->
    exit 0, ontology B 34 and runtime 71. Witnesses:
    `tests/test_canonical_scheduling_migration.py::test_no_runtime_consumer_reads_the_removed_card_fields`,
    `tests/test_runtime_contract_v2.py::test_retired_objective_and_pair_fields_are_rejected`,
    deletion inventory in `git show --stat ca8b323`.
- [x] Targeted acceptance, runtime scenarios, static checks, and one final
  release gate are green on the same committed head. This item cannot be checked
  until every Critical, High, and Medium item above carries its own `Evidence:`
  record.
  - Evidence: `6bc4d9fba7bdb73f31cb6a0add0db460d2a2e59a`; `just release` ->
    exit 0 on that exact head: static clean; smoke 23; ontology A/B/C 50/34/60;
    runtime 71; CRAP 237; corpus projection conforms true; CRAP report 707
    functions with zero >=30 and coverage 82%. Targeted ancestor/equivalent
    commands: `just canonical-runtime` -> 17 passed; `just current-shelf-smoke`
    -> 1 passed; `just runtime-scenarios` -> 63 passed.
- [ ] A final independent Sol panel confirms the canonical runtime contract and
  returns `SHIP` without Critical, High, or Medium reservations. Save the panel
  prompt, reviewed commit SHA, individual findings, and convergence verdict in
  `docs/decisions/`; findings against another head do not close this item.
  - Pending: no independent final Sol-panel report with a `SHIP` verdict exists
    for `6bc4d9fba7bdb73f31cb6a0add0db460d2a2e59a` in `docs/decisions/`.
- [ ] **Run one final checklist auditor with no parent context.** The auditor
  must independently inspect the final committed head, walk every checkbox and
  its `Evidence:` record, reproduce or validate the named acceptance evidence,
  detect false or premature checkmarks, and confirm that no required work was
  silently dropped. Save its prompt, reviewed commit SHA, per-item verdicts,
  discrepancies, and final `COMPLETE` or `INCOMPLETE` decision in
  `docs/decisions/`. Only `COMPLETE` allows the final convergence panel to run.
  - Pending: no fresh-context final-checklist auditor report with `COMPLETE`
    exists for `6bc4d9fba7bdb73f31cb6a0add0db460d2a2e59a` in `docs/decisions/`.
- [ ] **Repeat the original expert-panel review as the final convergence
  check.** Use the same product, ontology, architecture, portability, data-loss,
  and complexity optics as the panel that produced this checklist. Give the
  panel the original findings, this completed checklist and its item-specific
  evidence, the fresh-context auditor report, and the exact committed head.
  Require it to compare the original and current problem sets, state which
  severities and problem classes disappeared or remain, and decide whether the
  work is demonstrably converging rather than merely producing different
  findings. Save the prompt, reviewed commit SHA, individual model findings,
  comparison, and convergence verdict in `docs/decisions/`. If the panel finds
  any actionable problem, append every recommendation to this document as a
  new unchecked item with acceptance criteria and required evidence, then keep
  the checklist open for another implementation, audit, and convergence-review
  cycle. The spike closes only when this panel confirms convergence and returns
  `SHIP` without actionable reservations.
  - Pending: no repeated original same-optics expert-panel convergence report
    with `SHIP` exists for `6bc4d9fba7bdb73f31cb6a0add0db460d2a2e59a` in
    `docs/decisions/`.

## Execution order

1. Canonical inputs and stable identities.
2. Laws, applicability, normalized pressures, and conflict result.
3. Exact optimizer and publication boundary.
4. Real-scenario cutover and deletion of the legacy scheduler.
5. Surreal residue, runtime artifact split, and read-only validation.
6. Data integrity, grooming, presentation, and test-harness cleanup.
7. Final release evidence and independent panel review.
8. Fresh-context checklist audit and `COMPLETE` decision.
9. Same-optics expert-panel review, convergence comparison, and either `SHIP`
   or another explicitly checklisted remediation cycle.

Within each step, schema/data identity and its negative validation fixture come
before runtime consumption; runtime implementation comes before real-scenario
cutover; targeted V-right acceptance comes before deletion of the superseded
path. No later step may compensate for missing evidence in an earlier step.

## Required item-specific evidence

The following minimum evidence is mandatory in addition to each item's own
acceptance bullets:

| Work item | Minimum targeted evidence |
| --- | --- |
| Remove pair answers and weighted legacy scoring | Architecture search proves no executable legacy field reaches feasibility/objective; real scenario and negative fixture prove review-only evidence cannot move a product. |
| Migrate logical topology | Positive/negative schema fixtures cover every independent optional anchor, missing anchors, duplicate axes, and forbidden legacy/physical fields; runtime scenario proves each anchor independently. |
| Stable composition identities | Reorder and notes-edit metamorphic tests preserve role/fact/provenance identity; dangling and mismatched references fail closed. |
| Canonical-runtime gate | Gate inventory names the finite law truth table, normalization/conflict cases, exact objective stages, oracle comparison, and no-publication failures; inventory completeness test prevents omission. |
| Surreal-era residue cleanup | Repository search and architecture test show no unused context field, test-only serializer, stringly assertion row, discarded loader, or stale Surreal documentation remains. |
| Runtime/offline artifact split | Timed plan/find/review smokes load only declared runtime artifacts; ontology/release gate still detects stale RDF/SHACL/context/projection artifacts; dependency tree reflects the split. |
| Read-only validation | Snapshot/hash test proves check/plan/show/review do not change canonical inputs; explicit normalize failure test proves all-or-nothing behavior. |
| Explicit unassigned ownership | Partition validation proves every tracked product is active, inactive, or explicitly unassigned exactly once; deletion-from-stack fixture fails without an explicit state. |
| Pillbox/stack uniqueness | Duplicate-stack positive-schema input is rejected and the valid one-to-one fixture retains separate scheduling domains. |
| Non-daily presentation | CLI and generated summary make no claim that episodic items are taken today, while retaining their slot placement and interaction participation. |
| Grooming alignment | Queue fixture surfaces missing canonical coverage and unresolved Sol work; completed cards are not repeatedly selected; Luna output cannot adjudicate facts. |
| Applicability scope | Product/form-specific fixture affects only its stable composition role; a genuinely substance-wide fixture applies to all roles. |
| Complete query catalogs | Missing product, substance, component, or assertion reference fails closed; complete catalogs preserve the expected identity sets. |
| Read-model cutover acceptance | One representative fixture asserts active/inactive IDs, facts, relation classes, warnings, matches, ordering, and deduplication together. |
| Exhaustive release inventory | Collection comparison proves every test node is either selected or explicitly excluded with a reason. |
| Fast development gate | Measured gate includes one real-shelf runtime path, performs validation once, and leaves ontology/corpus/full checks explicit. |
| Static release blocker | The canonical static recipe completes with no migration-ledger type errors on the final head. |

The canonical laws row must link to the exact truth-table test cases for every
value enumerated in the normative domain model; referring only to a broad suite
name does not satisfy it.
