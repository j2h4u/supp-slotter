# Canonical Runtime Cutover Checklist — 2026-08-30

## Purpose and audit boundary

This is the living execution record for the canonical-runtime cutover. A
checkmark requires both implementation and paired acceptance evidence. The
product contract is [`docs/domain-model.md`](../domain-model.md); the governing
boundary decision is the
[`canonical-instance ADR`](../decisions/canonical-instance-inference-boundary-20260822.md).

This refresh audits durable source and test paths against the clean runtime
candidate `eeb0663b5bbdea5e475f11d1f10aace2b95432f9` (`eeb0663`,
`test dashboard exclusion in runtime contract`). It is documentation-only:
the receipt below is the release result for that exact source head, not a claim
that a release recipe was rerun while updating this checklist.

## Exact release receipt (R1)

- Candidate: `eeb0663b5bbdea5e475f11d1f10aace2b95432f9`; clean HEAD; release
  exit status `0`.
- Ordered release stages: `14/37/31/54/64/236 = 436` passing tests.
- Coverage: `82%`; 6,789 statements with 970 missed; 2,268 branches with 570
  partial branches.
- CRAP: 623 functions at threshold `30`; maximum `29.40`.
- Corpus projection: conforms; `123.527165s` (PySHACL `119.570785s`).
- Import inventory: 73 files and 310 dependencies; 10 contracts kept and 0
  broken.
- The gate left the checkout clean and no repository processes remained.

Every checked item below cites R1 plus its current durable witness. The runtime
source of authority is the generic `ontology-runtime-program-v2` projection
decoded by [`planner/ontology/runtime_program.py`](../../planner/ontology/runtime_program.py),
not a legacy runtime catalog, generated migration state, or a stored scheduling
answer.

## Critical — canonical product behavior

- [x] **Canonical facts and logical topology are the only scheduler inputs.**
  The formal applicability operation is
  `exact_role_or_all_roles_with_equal_substance`.
  - Evidence: R1; `tests/test_canonical_fact_catalog_integration.py::test_plan_inputs_keeps_runtime_program_as_canonical_scheduling_authority`; `tests/test_runtime_contract_v2.py::test_v2_contract_decodes_exactly_and_excludes_retired_objective_inputs`; `tests/test_runtime_contract_v2.py::test_engine_semantic_strategies_are_closed_exact_values`; `planner/engine/_plan_inputs.py`.

- [x] **The finite facts-to-pressures law table is complete and proof-producing.**
  - Evidence: R1; `tests/test_canonical_inference.py::test_every_admitted_value_maps_to_one_pressure`; `tests/test_canonical_inference.py::test_proof_contains_law_fact_subject_path_and_provenance`; `planner/ontology/canonical_inference.py`.

- [x] **Pressure identities normalize and same-dimension contradictions fail closed.**
  Satisfaction is exactly
  `slot_anchor_at_pressure_dimension_equals_pressure_value`.
  - Evidence: R1; `tests/test_canonical_inference.py::test_duplicate_witnesses_facts_components_and_paths_normalize_to_one_pressure`; `tests/test_canonical_inference.py::test_same_dimension_values_are_layout_free_conflict`; `tests/test_runtime_contract_v2.py::test_engine_semantic_strategies_are_closed_exact_values`.

- [x] **The optimizer uses the exact lexicographic contract.**
  - Evidence: R1; `tests/test_canonical_optimizer.py::test_pressure_maximum_precedes_balance_and_keeps_only_maximum_slots`; `tests/test_canonical_optimizer.py::test_exact_squared_load_balance_is_unbounded_and_stable_by_item_id`; `tests/test_canonical_optimizer.py::test_bounded_randomized_results_match_independent_cartesian_oracle`; `planner/canonical_optimizer.py`.

- [x] **Publication is closed over proved `Optimal | Indeterminate`.**
  - Evidence: R1; `tests/test_canonical_publication.py::test_writer_owns_exact_solve_and_projects_two_items_with_squared_load_two`; `tests/test_canonical_publication.py::test_failed_or_interrupted_write_removes_stale_lease`; `tests/test_canonical_optimizer.py::test_deadline_interruption_and_state_bound_never_publish_incumbents`; `planner/schedule_writer.py`.

## High — authority and superseded scheduler removal

- [x] **Stored pair preferences and placement answers no longer reach scheduling.**
  - Evidence: R1; `tests/test_runtime_contract_v2.py::test_retired_objective_and_pair_fields_are_rejected`; `tests/test_scheduler_reviewer_authority.py::test_review_only_relation_cannot_change_command_level_schedule`; `planner/canonical_optimizer.py`.

- [x] **Vote aggregation and legacy scoring are absent from the runtime contract.**
  - Evidence: R1; `tests/test_runtime_contract_v2.py::test_v2_contract_decodes_exactly_and_excludes_retired_objective_inputs`; `planner/ontology/runtime_program.py`.

- [x] **Logical intake topology uses independent optional anchors, not physical compartments.**
  - Evidence: R1; `tests/test_logical_slot_topology.py::test_topology_axes_are_optional_and_do_not_use_label_or_order`; `tests/test_logical_slot_topology.py::test_legacy_and_physical_slot_fields_are_rejected`; `tests/test_pillbox_loader_contract.py::test_loader_projects_independent_topology_fields`.

- [x] **Composition roles have stable portable identities.**
  - Evidence: R1; `tests/test_composition_role_identity.py::test_authored_component_identity_survives_reorder_and_notes_edit`; `tests/test_composition_role_identity.py::test_product_formula_validator_rejects_dangling_mismatched_and_duplicate_roles`.

- [x] **The legacy evidence migration is retired to a compact immutable receipt.**
  - Evidence: R1; `docs/migrations/legacy-atom-ledger.yaml`; `tests/test_grooming.py::test_receipts_are_operational_and_not_a_plan_runtime_input`; no migration generator is a runtime or release input.

- [x] **The canonical-runtime acceptance inventory is explicit and release-covered.**
  - Evidence: R1; `tests/test_run_unit_gate.py::test_canonical_runtime_inventory_is_exact_stable_and_release_covered`; `scripts/run_unit_gate.py`; `tests/test_canonical_publication.py::test_invalid_source_mapping_product_domain_or_slot_publishes_nothing`.

## High/Medium — architecture and runtime boundary

- [x] **The SurrealDB-era read-model residue is removed.**
  - Evidence: R1; `tests/test_read_model_relations.py::test_partition_and_direct_relation_classification`; `tests/test_architecture_contracts.py::test_runtime_planner_has_no_linkml_compiler_symbols`; `planner/query_model/read_model.py`.

- [x] **Active documentation names the canonical runtime rather than an embedded SurrealDB runtime.**
  - Evidence: R1; `docs/domain-model.md`; `docs/decisions/canonical-instance-inference-boundary-20260822.md`.

- [x] **Online runtime artifacts are split from offline formal projection verification.**
  - Evidence: R1; `tests/test_ontology_runtime_loader.py::test_runtime_bundle_retains_no_formal_projection_artifacts_or_reads`; `planner/ontology/artifacts.py`; `planner/ontology/projection.py`.

- [x] **Validation commands are read-only; repair is explicit and failure-safe.**
  Authored inputs remain read-only; `show` recomputes and overwrites the
  disposable derived `schedule.yaml` without reading a prior schedule.
  - Evidence: R1; `tests/test_maintenance.py::test_check_succeeds_without_mutating_canonical_inputs`; `tests/test_maintenance.py::test_show_and_review_do_not_mutate_authored_inputs`; `tests/test_canonical_publication.py::test_writer_does_not_accept_forged_projection_or_precomputed_optimal`; `tests/test_maintenance.py::test_run_maintenance_rolls_back_on_partial_stage_failure`.

## Medium — product and data integrity

- [x] **Tracked-product ownership is explicit and closed.**
  Stack topology consumes the formal runtime-declared routable, excluded, and
  tracked-unassigned partitions; no Python name is a policy authority. Active
  review, grooming, relation, and dashboard paths consume
  `routable_stack_names`; a focused second-excluded-partition contract proves
  excluded membership cannot enter their active inputs. Its real dashboard
  witness executes `build_dashboard_review` and classifies the archived product
  as `on_shelf`, never `current`. The review fixture derives its complete
  canonical partition from that same runtime policy.
  - Evidence: R1; `eeb0663b5bbdea5e475f11d1f10aace2b95432f9`; `tests/test_runtime_contract_v2.py::test_authored_stack_partition_is_closed_and_reproduces_active_membership`; `tests/test_runtime_contract_v2.py::test_second_excluded_partition_cannot_enter_current_review_grooming_or_relation_inputs`; `tests/test_stack_validation.py::test_partition_names_come_from_runtime_and_unknown_names_fail_closed`; `tests/test_review_command.py::test_cmd_review_accepts_canonical_typed_selector_relation`; `planner/cards/stacks.py`; `planner/engine/_plan_active_index.py`; `planner/cards/dashboards.py::build_dashboard_review`; `planner/engine/grooming.py`; `planner/engine/review_model.py`; `planner/query_model/facts.py`; `planner/query_model/read_model.py`; `data/stacks.yaml`.

- [x] **Pillbox/stack topology is one-to-one where authored as such.**
  - Evidence: R1; `tests/test_pillbox_loader_contract.py::test_loader_rejects_multiple_pillboxes_for_one_stack`; `tests/test_logical_slot_topology.py::test_distinct_topologies_keep_distinct_stack_references`.

- [x] **Non-daily presentation is truthful without adding recurrence semantics.**
  - Evidence: R1; `tests/test_non_daily_presentation.py::test_marked_daily_product_is_an_episodic_current_plan_placement`; `planner/engine/show.py`.

- [x] **Grooming exposes canonical coverage work without becoming plan input.**
  - Evidence: R1; `tests/test_grooming.py::test_receipt_catalog_closes_the_real_active_queue`; `tests/test_grooming.py::test_receipts_are_operational_and_not_a_plan_runtime_input`; `planner/engine/grooming.py`.

- [x] **Form-specific evidence is bound to composition roles; universal evidence remains universal.**
  - Evidence: R1; `tests/test_canonical_inference.py::test_substance_applicability_reaches_each_exact_matching_role`; `tests/test_canonical_fact_catalog_integration.py::test_canonical_reference_validator_accepts_matching_composition_role_fact`.

- [x] **Catalog, strict runtime-envelope, and canonical-ID boundaries fail closed.**
  - Evidence: R1; `tests/test_read_model_relations.py::test_read_model_and_direct_classifier_reject_incomplete_references`; `tests/test_canonical_fact_catalog_integration.py::test_plan_inputs_rejects_full_canonical_scheduling_before_relation_processing`; `tests/test_runtime_contract_v2.py::test_runtime_envelope_and_canonical_ids_fail_closed`.

## Medium — verification workflow

- [x] **The read-model cutover acceptance reflects the production `classify_relations` scope.**
  It asserts partitioning and direct relation classification; it does not claim a
  deleted fact-index interface. Relations are passive review evidence, not a
  safety-decision layer or solver input.
  - Evidence: R1; `tests/test_read_model_relations.py::test_partition_and_direct_relation_classification`; `tests/test_read_model_relations.py::test_active_active_relation_is_passive_and_membership_only`; `planner/query_model/relations.py::classify_relations`; `tests/test_scheduler_reviewer_authority.py::test_reviewer_only_knowledge_does_not_change_slot_assignment`.

- [x] **Release inventory is exhaustive for its selected modules.**
  - Evidence: R1; `tests/test_run_unit_gate.py::test_release_inventory_is_bidirectional_and_rejects_unlisted_modules`; `scripts/run_unit_gate.py`.

- [x] **The default development gate is bounded and product-relevant.**
  - Evidence: R1; `tests/test_run_unit_gate.py::test_verify_composition_has_one_planner_validation_owner`; `tests/test_cutover_vertical_scenarios.py::test_real_shelf_daily_episodic_and_training_products_are_complete`; `justfile`.

- [x] **The static release blocker is removed without retaining migration-generator machinery.**
  - Evidence: R1; `tests/test_crap_gate.py`; `docs/migrations/legacy-atom-ledger.yaml`; `justfile`.

## Final cutover acceptance

- [x] **Daily, episodic, training, and current-shelf scenarios use canonical facts and logical topology.**
  - Evidence: R1; `tests/test_cutover_vertical_scenarios.py::test_real_shelf_daily_episodic_and_training_products_are_complete`; `tests/test_cutover_authored_vertical_scenarios.py::test_authored_vertical_fixture_compiles_loads_and_routes_all_runtime_anchors`.

- [x] **Food, circadian, and exercise anchors are independently routed.**
  - Evidence: R1; `tests/test_cutover_authored_vertical_scenarios.py::test_authored_vertical_fixture_compiles_loads_and_routes_all_runtime_anchors`; `tests/test_canonical_optimizer.py::test_none_anchor_never_satisfies_a_pressure`.

- [x] **Every published layout is globally proved; all unproved outcomes are layout-free `Indeterminate`.**
  - Evidence: R1; `tests/test_canonical_optimizer.py::test_bounded_randomized_results_match_independent_cartesian_oracle`; `tests/test_canonical_optimizer.py::test_invalid_proof_limits_fail_closed`; `tests/test_canonical_publication.py::test_failed_or_interrupted_write_removes_stale_lease`; `planner/canonical_optimizer_result.py`.

- [x] **No scheduling law or decision is recoverable only from Python.**
  - Evidence: R1; `tests/test_runtime_contract_v2.py::test_v2_contract_decodes_exactly_and_excludes_retired_objective_inputs`; `tests/test_canonical_law_catalog.py`; `ontology/generated/runtime-program.json`.

- [x] **A future independent backend can reproduce the canonical runtime from the v2 program.**
  The synthetic ontology-extension witness proves a newly admitted fact family
  can flow through annotations and ranges without a Python family branch.
  - Evidence: R1; `tests/test_canonical_fact_catalog_runtime.py::test_annotation_and_manifest_ranges_admit_a_new_family_without_python_changes`; `tests/test_canonical_fact_catalog_runtime.py::test_compiler_emits_one_generic_scheduling_projection_without_retired_catalog_keys`; `ontology/generated/runtime-program.json`.

- [x] **The legacy runtime and obsolete compatibility regressions are deleted.**
  Compatibility archaeology is removed: no live
  `CompositionApplicabilityPath.applicability_role`,
  `infer_canonical_pressures`, or `infer_pressures` symbol remains.
  The zero-consumer inference aliases are also removed:
  `CompositionApplicabilityPath.product_id` and `.substance_id`,
  `SameDimensionPressureConflict.pressure_identities`,
  `Success.normalized_pressures`, and `Conflict.diagnostics` /
  `.pressure_conflicts`.
  Finite Kaizen cleanup also removed 12 aliases/fallbacks. The pillbox loader
  accepts a verified `OntologyBundle` only, and `_load_slot` now projects
  already schema-validated input while malformed-boundary cases remain covered.
  - Evidence: R1; `b8bd5de0d256c211c66116b880c8db5deb7ffb98`; `a34632bedad79d8043d0efd555a7c47b54eeb96c`; `64a312d787641f02bebeceeb650c93e71d07e18f`; `planner/ontology/canonical_inference.py`; `planner/cards/pillboxes.py`; `tests/test_canonical_inference.py`; `tests/test_pillbox_loader_contract.py::test_loader_rejects_missing_or_malformed_slot_fields`; `tests/test_architecture_contracts.py::test_runtime_has_no_legacy_stored_schedule_answer_consumers`; `tests/test_runtime_contract_v2.py::test_v1_contract_is_rejected_without_compatibility_fallback`.

- [x] **Targeted acceptance, release, static quality, and corpus projection have one exact-head receipt.**
  - Evidence: R1; `scripts/run_unit_gate.py`; `tests/test_crap_gate.py`; `planner/ontology/projection.py`.

## Final review holds

- [x] **Independent Sol panel.** The independent panel reviewed the remediated
  runtime candidate and returned `SHIP` without actionable Critical, High, or
  Medium reservations.
  - Evidence: [final independent convergence](../decisions/canonical-runtime-final-convergence-20260831.md);
    documentation head `3a940d87d4028c5e251fa4436ac6dc2231114b10`; runtime
    parent and R1 `eeb0663b5bbdea5e475f11d1f10aace2b95432f9`.

- [ ] **Fresh-context final auditor.** Inspect this exact runtime candidate,
  validate every checked record and R1, then save per-item verdicts and a final
  `COMPLETE` or `INCOMPLETE` decision in `docs/decisions/`.
  - Pending on `eeb0663b5bbdea5e475f11d1f10aace2b95432f9`: remediation is
    present, but no fresh-context final-auditor report with `COMPLETE` exists.

- [x] **Repeated same-optics convergence.** The product, ontology,
  portability, and QA optics repeated on the remediated heads and each returned
  `SHIP` without an actionable reservation.
  - Evidence: [final independent convergence](../decisions/canonical-runtime-final-convergence-20260831.md);
    historical [superseded convergence](../decisions/canonical-runtime-convergence-20260831.md);
    documentation head `3a940d87d4028c5e251fa4436ac6dc2231114b10`; runtime
    parent and R1 `eeb0663b5bbdea5e475f11d1f10aace2b95432f9`.

The cutover remains open until the fresh-context final auditor independently
closes the remaining hold.
