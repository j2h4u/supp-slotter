"""Plan-command schedule.yaml assembly.

Extracted from `planner.engine.plan` to keep the scheduler module focused
on search + orchestration. This module owns the conversion from a solved
assignment dict into the full `schedule` dict that gets written to disk —
benefits/risks/warnings aggregation, pillbox population, explanations,
relation warnings, and humanize-rewrite of the raw warning stream.
"""

from __future__ import annotations

from itertools import combinations
from pathlib import Path
from typing import NamedTuple, cast

from planner.cards.dashboards import build_dashboard_review
from planner.cards.pillboxes import build_empty_schedule_pillboxes
from planner.cards.product import (
    format_item_product_name,
)
from planner.cards.safety_warnings import SafetyConcernInput, collect_active_safety_concerns
from planner.cards.schedule import build_placement_notes, build_schedule_summary
from planner.cards.substance import format_substance_name
from planner.cards.warnings import humanize_warning
from planner.contracts import (
    Pillbox,
    Product,
    ScheduleProjection,
    SchedulingPolicy,
    Slot,
    SlotCandidateTrace,
    StackEntry,
    Substance,
)
from planner.engine._plan_types import ActiveIndex, AdvisorySlotEvaluation
from planner.engine._scheduling import build_substance_slot_names, render_slot_effects
from planner.ontology.artifacts import OntologyBundle
from planner.ontology.errors import MALFORMED, OntologyInfrastructureError
from planner.ontology.glue_capabilities import WARNING_EMITTER_TRAIT_REVIEW_ASSIGNMENT
from planner.ontology.policies import readable_policies
from planner.ontology.presentation import load_review_presentation
from planner.ontology.runtime_program import RuntimeProgram
from planner.ontology.warning_policy import warning_policy_for_emitter
from planner.query_model import StackReadModel
from planner.query_model.relation_warnings import RelationWarningRow
from planner.schedule_types import (
    DashboardReviewEntryWithMembers,
    DashboardReviewResult,
    ScheduleData,
    ScheduleExplanation,
    ScheduleNeutralComponent,
    SchedulePairwiseEndpoint,
    SchedulePairwiseJournalEntry,
    SchedulePillbox,
    SchedulePlacementNote,
    SchedulePolicyContribution,
    ScheduleSummary,
    ScheduleWarning,
)
from planner.scheduling_constraint_execution import (
    SchedulingConstraintExecutionPlan,
    interpret_constraint_component_pair,
)


class ScheduleOutputInput(NamedTuple):
    assignment: dict[str, str]
    slots: dict[str, Slot]
    active: ActiveIndex
    item_id_sequence: list[str]
    products: dict[str, Product]
    substances: dict[str, Substance]
    policies: dict[str, SchedulingPolicy]
    prefer_pairs: set[frozenset[str]]
    stack_entries: dict[str, StackEntry]
    dashboard_files: list[Path]
    pillboxes: dict[str, Pillbox]
    warnings_prefix: list[ScheduleWarning]
    read_model: StackReadModel
    candidate_traces_by_item: dict[str, tuple[SlotCandidateTrace, ...]]
    ontology_bundle: OntologyBundle
    advisory_by_slot: dict[str, AdvisorySlotEvaluation]
    scheduling_constraint_plans: tuple[SchedulingConstraintExecutionPlan, ...]


class _SchedulePillboxContext(NamedTuple):
    schedule: ScheduleData
    assignment: dict[str, str]
    slots: dict[str, Slot]
    active: ActiveIndex
    item_id_sequence: list[str]
    products: dict[str, Product]
    substances: dict[str, Substance]


class _ConstraintPairContext(NamedTuple):
    left_id: str
    right_id: str
    left_components: list[str]
    right_components: list[str]
    output_input: ScheduleOutputInput
    runtime_program: RuntimeProgram


def build_schedule_output(
    output_input: ScheduleOutputInput,
) -> tuple[ScheduleData, list[ScheduleWarning]]:
    """Build the complete schedule dict from a solved assignment.

    Returns the schedule dict ready to be serialised (excluding the write step).
    """
    assignment = output_input.assignment
    slots = output_input.slots
    active = output_input.active
    item_id_sequence = output_input.item_id_sequence
    products = output_input.products
    substances = output_input.substances
    policies = output_input.policies
    read_model = output_input.read_model
    schedule = _initial_schedule(output_input.pillboxes, assignment, active, products)
    pillbox_context = _SchedulePillboxContext(
        schedule=schedule,
        assignment=assignment,
        slots=slots,
        active=active,
        item_id_sequence=item_id_sequence,
        products=products,
        substances=substances,
    )
    _populate_pillbox_products(pillbox_context)
    _populate_pillbox_substances(pillbox_context)

    active_substance_ids = {
        component_id for component_ids in active.active_components.values() for component_id in component_ids
    }
    cluster_review = cast(
        DashboardReviewResult,
        build_dashboard_review(
            dashboard_files=output_input.dashboard_files,
            products=products,
            stack_entries=output_input.stack_entries,
            substances=substances,
            bundle=output_input.ontology_bundle,
        ),
    )
    schedule["benefits"] = cluster_review["benefits"]
    schedule["risks"] = cluster_review["risks"]
    schedule["warnings"].extend(cluster_review["warnings"])
    schedule["active_fact_index"] = read_model.active_fact_index(
        item_id_sequence=item_id_sequence,
        item_products=active.item_products,
    )

    _populate_explanations(schedule, output_input)
    schedule["pairwise_journal"] = _build_pairwise_journal(output_input)
    _append_intra_product_relation_conflicts(schedule, active)

    schedule["warnings"].extend(
        cast(
            list[ScheduleWarning],
            collect_active_safety_concerns(
                SafetyConcernInput(
                    active_order=item_id_sequence,
                    active_components=active.active_components,
                    item_products=active.item_products,
                    products=products,
                    runtime_program=output_input.ontology_bundle.runtime_program,
                    substances=substances,
                )
            ),
        )
    )
    schedule["warnings"].extend(output_input.warnings_prefix)
    _append_trait_warnings(schedule, active, policies, output_input.ontology_bundle)
    _append_read_model_warnings(schedule, read_model, active_substance_ids)

    raw_warnings = list(schedule["warnings"])
    schedule["warnings"] = [
        cast(
            ScheduleWarning,
            humanize_warning(
                cast(dict[str, object], warning),
                products=products,
                substances=substances,
                ontology_bundle=output_input.ontology_bundle,
            ),
        )
        for warning in schedule["warnings"]
        if not _is_excluded_review_warning(cast(dict[str, object], warning), output_input.ontology_bundle)
    ]
    schedule["placement_notes"] = cast(
        list[SchedulePlacementNote],
        build_placement_notes(cast(dict[str, object], schedule)),
    )
    schedule["summary"] = cast(ScheduleSummary, build_schedule_summary(cast(dict[str, object], schedule)))

    return schedule, raw_warnings


def _is_excluded_review_warning(warning: dict[str, object], bundle: OntologyBundle) -> bool:
    trait = warning.get("trait")
    if trait is None:
        return False
    if not isinstance(trait, str) or not trait.strip():
        raise _output_policy_error(bundle, f"warning has malformed policy id {trait!r}")
    return trait in load_review_presentation(bundle).excluded_policy_ids


def _output_policy_error(bundle: OntologyBundle, message: str) -> OntologyInfrastructureError:
    source = bundle.root / "generated" / "runtime-vocabulary.yaml"
    return OntologyInfrastructureError(f"{message} [source: {source}]", code=MALFORMED, path=source)


def _initial_schedule(
    pillboxes: dict[str, Pillbox],
    assignment: dict[str, str],
    active: ActiveIndex,
    products: dict[str, Product],
) -> ScheduleData:
    return {
        "summary": cast(ScheduleSummary, {"take": {}}),
        "placement_notes": cast(list[SchedulePlacementNote], []),
        "pillboxes": cast(dict[str, SchedulePillbox], build_empty_schedule_pillboxes(pillboxes)),
        "benefits": cast(list[DashboardReviewEntryWithMembers], []),
        "risks": cast(list[DashboardReviewEntryWithMembers], []),
        "warnings": cast(list[ScheduleWarning], []),
        "pairwise_journal": cast(list[SchedulePairwiseJournalEntry], []),
        "explanations": cast(dict[str, ScheduleExplanation], {}),
        "active_fact_index": [],
    }


def _populate_pillbox_products(context: _SchedulePillboxContext) -> None:
    for item_id in context.item_id_sequence:
        slot_name = context.assignment[item_id]
        pillbox_name = context.slots[slot_name].pillbox
        context.schedule["pillboxes"][pillbox_name]["slots"][slot_name]["products"].append(
            format_item_product_name(item_id, context.active.item_products, context.products)
        )
    for pillbox in context.schedule["pillboxes"].values():
        for slot_entry in pillbox["slots"].values():
            slot_entry["products"] = sorted(slot_entry["products"], key=str.casefold)


def _populate_pillbox_substances(context: _SchedulePillboxContext) -> None:
    for slot_name, slot in context.slots.items():
        pillbox_name = slot.pillbox
        slot_entry = context.schedule["pillboxes"][pillbox_name]["slots"][slot_name]
        slot_item_ids = [item_id for item_id in context.item_id_sequence if context.assignment[item_id] == slot_name]
        slot_entry["substances"] = build_substance_slot_names(
            assigned_item_ids=slot_item_ids,
            item_products=context.active.item_products,
            products=context.products,
            substances=context.substances,
        )


def _populate_explanations(
    schedule: ScheduleData,
    output_input: ScheduleOutputInput,
) -> None:
    for item_id in output_input.item_id_sequence:
        slot_name = output_input.assignment[item_id]
        slot = output_input.slots[slot_name]
        product_name = format_item_product_name(item_id, output_input.active.item_products, output_input.products)
        projection = output_input.active.schedule_projection_by_item[item_id]
        chosen_trace = next(
            trace for trace in output_input.candidate_traces_by_item[item_id] if trace.slot_id == slot_name
        )
        active_policy_ids = {group.policy_id for group in projection.groups}
        why_here = render_slot_effects(chosen_trace, output_input.ontology_bundle)
        advisory = output_input.advisory_by_slot.get(slot_name)
        if advisory is not None and advisory.matched_constraint_ids:
            why_here.append(
                "Advisory tradeoff: "
                f"score {advisory.penalty:+d}; matched constraints: "
                f"{', '.join(advisory.matched_constraint_ids)}."
            )
        explanation: ScheduleExplanation = {
            "components": _component_names(output_input.active.active_components[item_id], output_input.substances),
            "pillbox": slot.pillbox,
            "slot": slot_name,
            "why_here": why_here,
            "review_tags": readable_policies(active_policy_ids, output_input.policies, output_input.ontology_bundle),
            "schedule_assignments": [
                {
                    "assignment_id": row.assignment_id,
                    "policy_id": row.policy_id,
                    "source_kind": row.source_kind,
                    "source_card_id": row.source_card_id,
                    "component_id": row.component_id,
                }
                for row in sorted(projection.assignments, key=lambda value: value.assignment_id)
            ],
            "policy_contributions": _policy_contributions(chosen_trace, projection, output_input.substances),
            "neutral_components": _neutral_components(
                output_input.active.active_components[item_id],
                output_input.substances,
                output_input.ontology_bundle,
            ),
        }
        if advisory is not None and advisory.matched_constraint_ids:
            explanation["advisory_penalty"] = advisory.penalty
            explanation["advisory_constraint_ids"] = list(advisory.matched_constraint_ids)
        schedule["explanations"][product_name] = explanation


def _component_names(component_ids: list[str], substances: dict[str, Substance]) -> list[str]:
    names: list[str] = []
    for substance_id in component_ids:
        substance_dc = substances.get(substance_id)
        names.append(format_substance_name(substance_dc) if substance_dc is not None else substance_id)
    return names


def _policy_contributions(
    chosen_trace: SlotCandidateTrace,
    projection: ScheduleProjection,
    substances: dict[str, Substance],
) -> list[SchedulePolicyContribution]:
    """Aggregate chosen-slot effects while retaining every component vote."""
    # Keep the projection type local to avoid widening the output builder's
    # already large input surface; the only fields needed here are assignments.
    assignments_by_id = {row.assignment_id: row for row in projection.assignments}
    grouped: dict[str, dict[str, object]] = {}
    for effect in chosen_trace.effects:
        row = grouped.setdefault(
            effect.policy_id,
            {"assignment_ids": set(), "score": 0},
        )
        cast(set[str], row["assignment_ids"]).update(effect.assignment_ids)
        row["score"] = cast(int, row["score"]) + effect.delta

    contributions: list[SchedulePolicyContribution] = []
    for policy_id in sorted(grouped):
        row = grouped[policy_id]
        assignment_ids = cast(set[str], row["assignment_ids"])
        substance_id_set: set[str] = set()
        for assignment_id in assignment_ids:
            component_id = assignments_by_id[assignment_id].component_id
            if component_id is not None:
                substance_id_set.add(component_id)
        substance_ids = sorted(substance_id_set)
        assessment_states: dict[str, str] = {}
        for assignment_id in sorted(assignment_ids):
            assignment = assignments_by_id[assignment_id]
            component_id = assignment.component_id
            if component_id is None or component_id in assessment_states:
                continue
            substance = substances.get(component_id)
            assessment_states[component_id] = (
                next(
                    (
                        assessment.conclusion
                        for assessment in substance.scheduling_assessments
                        if assessment.axis == assignment.axis
                    ),
                    "unassessed",
                )
                if substance is not None
                else "unassessed"
            )
        contributions.append({
            "policy_id": policy_id,
            "vote_count": len(assignment_ids),
            "substance_ids": substance_ids,
            "substances": [
                format_substance_name(substances[substance_id]) if substance_id in substances else substance_id
                for substance_id in substance_ids
            ],
            "score_contribution": cast(int, row["score"]),
            "assessment_states": assessment_states,
        })
    return contributions


def _neutral_components(
    component_ids: list[str],
    substances: dict[str, Substance],
    ontology_bundle: OntologyBundle | None = None,
) -> list[ScheduleNeutralComponent]:
    neutral: list[ScheduleNeutralComponent] = []
    for substance_id in sorted(set(component_ids)):
        substance = substances.get(substance_id)
        if substance is not None and substance.schedule_assertions:
            continue
        neutral_component: ScheduleNeutralComponent = {
            "substance_id": substance_id,
            "substance": format_substance_name(substance) if substance is not None else substance_id,
            "status": "no-scheduling-fact",
            "reason": "no-scheduling-fact",
        }
        if ontology_bundle is not None:
            assessment_by_axis = (
                {assessment.axis: assessment for assessment in substance.scheduling_assessments} if substance else {}
            )
            neutral_component["assessment_states"] = {
                axis.axis: (
                    assessment_by_axis[axis.axis].conclusion if axis.axis in assessment_by_axis else "unassessed"
                )
                for axis in sorted(ontology_bundle.runtime_program.assignment_axes, key=lambda row: (row.order, row.id))
            }
        neutral.append(neutral_component)
    return neutral


def _build_pairwise_journal(output_input: ScheduleOutputInput) -> list[SchedulePairwiseJournalEntry]:
    """Project resolved prefer-with and separation decisions onto the winner.

    The search intentionally keeps hard-block diagnostics out of its hot path.
    Replaying the resolved execution grammar against the winning assignment
    here makes successful separations observable, including rules whose
    same-slot candidate was rejected before it could become a winner.
    """

    journal: list[SchedulePairwiseJournalEntry] = []
    journal.extend(_prefer_pair_journal(output_input))
    journal.extend(_separate_pair_journal(output_input))
    journal.extend(_intra_product_journal(output_input))
    return journal


def _prefer_pair_journal(output_input: ScheduleOutputInput) -> list[SchedulePairwiseJournalEntry]:
    runtime_program = output_input.ontology_bundle.runtime_program
    policy = runtime_program.prefer_with_policy
    bonus = runtime_program.effect_scoring.prefer_with_bonus
    rows: list[SchedulePairwiseJournalEntry] = []
    for pair in sorted(output_input.prefer_pairs, key=lambda item_pair: tuple(sorted(item_pair))):
        item_ids = tuple(
            sorted(
                pair,
                key=lambda item_id: format_item_product_name(
                    item_id, output_input.active.item_products, output_input.products
                ).casefold(),
            )
        )
        endpoints = _prefer_endpoints(cast(tuple[str, str], item_ids), output_input)
        product_names = [
            format_item_product_name(item_id, output_input.active.item_products, output_input.products)
            for item_id in item_ids
        ]
        slots: list[str | None] = [output_input.assignment[item_id] for item_id in item_ids]
        together = len(set(slots)) == 1
        rows.append({
            "kind": "prefer_together",
            "products": product_names,
            "endpoints": endpoints,
            "slots": slots,
            "state": "together" if together else "apart",
            "satisfied": together,
            "rule_id": policy.id,
            "source_field": policy.source_field,
            "bonus_contribution": bonus if together else 0,
        })
    return rows


def _prefer_endpoints(
    item_ids: tuple[str, str],
    output_input: ScheduleOutputInput,
) -> list[SchedulePairwiseEndpoint]:
    """Resolve the authored prefer_with edge(s) that created one item pair."""

    left_id, right_id = item_ids
    component_sets = output_input.active.active_components
    endpoints: list[SchedulePairwiseEndpoint] = []
    for source_item, target_item in ((left_id, right_id), (right_id, left_id)):
        target_components = set(component_sets[target_item])
        for source_id in component_sets[source_item]:
            source = output_input.substances.get(source_id)
            if source is None:
                continue
            for target_id in source.prefer_with:
                if target_id not in target_components:
                    continue
                endpoints.append(_pairwise_endpoint(source_item, source_id, output_input))
                endpoints.append(_pairwise_endpoint(target_item, target_id, output_input))
                return endpoints
    return endpoints


def _separate_pair_journal(output_input: ScheduleOutputInput) -> list[SchedulePairwiseJournalEntry]:
    item_ids = tuple(sorted(output_input.active.active_components))
    runtime_program = output_input.ontology_bundle.runtime_program
    rows: list[SchedulePairwiseJournalEntry] = []
    relevant_plans = tuple(
        plan
        for plan in output_input.scheduling_constraint_plans
        if plan.executable and (plan.blocks_slots or plan.scores_advisory)
    )
    for left_id, right_id in combinations(item_ids, 2):
        left_components = output_input.active.active_components[left_id]
        right_components = output_input.active.active_components[right_id]
        for plan in sorted(relevant_plans, key=lambda item: item.id):
            matched = _constraint_endpoints(
                plan,
                _ConstraintPairContext(
                    left_id,
                    right_id,
                    left_components,
                    right_components,
                    output_input,
                    runtime_program,
                ),
            )
            if matched is None:
                continue
            endpoints, ordered_slots = matched
            apart = ordered_slots[0] != ordered_slots[1]
            rows.append({
                "kind": "separate_constraint",
                "products": [
                    format_item_product_name(item_id, output_input.active.item_products, output_input.products)
                    for item_id in (left_id, right_id)
                ],
                "endpoints": endpoints,
                "slots": list(ordered_slots),
                "state": "apart" if apart else "together",
                "satisfied": apart,
                "constraint_id": plan.id,
                "disposition": "hard" if plan.blocks_slots else "advisory",
                "rationale": plan.rationale or "",
                "action": plan.action or "",
            })
    return rows


def _constraint_endpoints(
    plan: SchedulingConstraintExecutionPlan,
    context: _ConstraintPairContext,
) -> tuple[list[SchedulePairwiseEndpoint], tuple[str, str]] | None:
    """Return deterministic source/target endpoints for a matched item pair."""

    # The execution function is the single source of truth for directed versus
    # symmetric matching.  Try authored direction first, then its reverse so
    # symmetric rules still get stable endpoint labels.
    for source_item, target_item, source_components, target_components in (
        (context.left_id, context.right_id, context.left_components, context.right_components),
        (context.right_id, context.left_id, context.right_components, context.left_components),
    ):
        if not interpret_constraint_component_pair(plan, source_components, target_components, context.runtime_program):
            continue
        source_id = next((item for item in source_components if item in plan.source_substance_ids), None)
        target_id = next((item for item in target_components if item in plan.target_substance_ids), None)
        if source_id is None or target_id is None:
            continue
        return [
            _pairwise_endpoint(source_item, source_id, context.output_input),
            _pairwise_endpoint(target_item, target_id, context.output_input),
        ], (context.output_input.assignment[context.left_id], context.output_input.assignment[context.right_id])
    return None


def _intra_product_journal(output_input: ScheduleOutputInput) -> list[SchedulePairwiseJournalEntry]:
    rows: list[SchedulePairwiseJournalEntry] = []
    for item_id in sorted(output_input.active.active_components):
        conflicts = output_input.active.intra_product_relation_conflicts_by_item.get(item_id, [])
        if not conflicts:
            continue
        product_name = format_item_product_name(item_id, output_input.active.item_products, output_input.products)
        rows.extend(
            {
                "kind": "intra_product_conflict",
                "products": [product_name],
                "endpoints": [
                    _pairwise_endpoint(item_id, conflict["source_substance"], output_input),
                    _pairwise_endpoint(item_id, conflict["target_substance"], output_input),
                ],
                "slots": [output_input.assignment[item_id]],
                "state": "unresolvable",
                "satisfied": False,
                "constraint_id": conflict["constraint_id"],
                "disposition": "hard",
                "rationale": conflict["message"],
                "action": conflict["action"],
            }
            for conflict in conflicts
        )
    return rows


def _pairwise_endpoint(
    item_id: str,
    substance_id: str,
    output_input: ScheduleOutputInput,
) -> SchedulePairwiseEndpoint:
    substance = output_input.substances.get(substance_id)
    return {
        "product": format_item_product_name(item_id, output_input.active.item_products, output_input.products),
        "component": format_substance_name(substance) if substance is not None else substance_id,
        "substance_id": substance_id,
    }


def _append_intra_product_relation_conflicts(schedule: ScheduleData, active: ActiveIndex) -> None:
    for relation_conflicts in active.intra_product_relation_conflicts_by_item.values():
        for conflict in relation_conflicts:
            warning: ScheduleWarning = {
                "type": conflict["type"],
                "item": conflict["item"],
                "product": conflict["product"],
                "relation": conflict["relation"],
                "source_substance": conflict["source_substance"],
                "target_substance": conflict["target_substance"],
                "message": conflict["message"],
                "action": conflict["action"],
            }
            schedule["warnings"].append(warning)


def _append_trait_warnings(
    schedule: ScheduleData,
    active: ActiveIndex,
    policies: dict[str, SchedulingPolicy],
    ontology_bundle: OntologyBundle,
) -> None:
    runtime_program = ontology_bundle.runtime_program
    warning_policy = warning_policy_for_emitter(
        runtime_program,
        WARNING_EMITTER_TRAIT_REVIEW_ASSIGNMENT,
    )
    warning_type = warning_policy.warning_type
    for item_id, projection in active.schedule_projection_by_item.items():
        for row in projection.assignments:
            trait_def = policies.get(row.policy_id)
            if trait_def is None:
                raise _output_policy_error(
                    ontology_bundle,
                    f"schedule output references unknown policy {row.policy_id!r}",
                )
            if not trait_def.warning:
                continue
            for source in [row.source_card_id]:
                schedule["warnings"].append({
                    "type": warning_type,
                    "item": item_id,
                    "product": active.item_products[item_id],
                    "substance": source,
                    "trait": row.policy_id,
                    "message": trait_def.description or warning_policy.default_message,
                    "action": trait_def.action or "",
                })


def _append_read_model_warnings(
    schedule: ScheduleData,
    read_model: StackReadModel,
    active_substance_ids: set[str],
) -> None:
    for row in read_model.collect_relation_warnings(active_substance_ids):
        schedule["warnings"].append(_relation_warning_to_schedule_warning(row))


def _relation_warning_to_schedule_warning(row: RelationWarningRow) -> ScheduleWarning:
    warning: ScheduleWarning = {
        "type": row["type"],
        "relation": row["relation"],
        "source_substance": row["source_substance"],
        "source_name": row["source_name"],
        "target_substance": row["target_substance"],
        "target_name": row["target_name"],
        "reason": row["reason"],
        "action": row["action"],
    }
    if "severity" in row:
        warning["severity"] = row["severity"]
    return warning
