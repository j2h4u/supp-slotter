"""Ontology-backed schedule assignment projection and soft slot scoring.

Cards only declare schedule axes/values.  The ontology supplies the matching
policy and score; this module merely joins the two and evaluates the policy
effects against the observable slot fields.
"""

from __future__ import annotations

from collections.abc import Sequence

from planner.cards.substance import format_substance_name
from planner.contracts import (
    PlannerCapability,
    Product,
    ProjectedEffectTrace,
    ScheduleAssignment,
    SchedulePolicyGroup,
    ScheduleProjection,
    SchedulingPolicy,
    Slot,
    SlotCandidateTrace,
    SlotScoreTrace,
    Substance,
    TraitEffectMatch,
)
from planner.ontology.glue_capabilities import ONTOLOGY_COMPOSITE_KEY_SEPARATOR
from planner.ontology.runtime_program import RuntimeAssignmentAxis, RuntimeProgram


def _assignment_axes(program: RuntimeProgram) -> tuple[RuntimeAssignmentAxis, ...]:
    axes = tuple(sorted(program.assignment_axes, key=lambda row: (row.order, row.id)))
    if not axes or len({row.axis for row in axes}) != len(axes):
        raise ValueError("ontology assignment axes are missing or ambiguous")
    return axes


def _axis_values(source: Product | Substance, axis: RuntimeAssignmentAxis) -> tuple[str, ...]:
    values = getattr(source, axis.assignment_field, ())
    if not isinstance(values, tuple):
        raise ValueError(f"schedule field {axis.assignment_field!r} is not a tuple")
    if any(not isinstance(value, str) or not value for value in values):
        raise ValueError(f"schedule field {axis.assignment_field!r} contains an invalid value")
    return values


def _sources(
    program: RuntimeProgram, product: Product, substances: dict[str, Substance]
) -> tuple[tuple[str, str, str | None, Product | Substance], ...]:
    assignment_kinds = tuple(
        row.source_kind for row in program.source_kind_values if "assignment_source" in row.applies_to
    )
    if len(assignment_kinds) < 2:
        raise ValueError("ontology source-kind taxonomy must declare product and component assignment sources")
    product_kind, substance_kind = assignment_kinds[0], assignment_kinds[-1]
    rows: list[tuple[str, str, str | None, Product | Substance]] = [(product_kind, product.id, None, product)]
    rows.extend(
        (substance_kind, substance.id, substance.id, substance)
        for component in product.components
        if (substance := substances.get(component.substance)) is not None
    )
    return tuple(rows)


def project_schedule_assignments(
    program: RuntimeProgram,
    product: Product,
    substances: dict[str, Substance],
    policies: dict[str, SchedulingPolicy],
    capability: PlannerCapability | None = None,
) -> ScheduleProjection:
    """Project every authored card assignment to its ontology policy.

    All resolved assignments contribute a soft score. Card schedule data is
    joined directly to ontology policies; no extra runtime action is created.
    """
    del capability
    rows: list[ScheduleAssignment] = []
    for axis_row in _assignment_axes(program):
        for source_kind, source_id, component_id, source in _sources(program, product, substances):
            for slug in _axis_values(source, axis_row):
                policy_id = f"{axis_row.axis}{ONTOLOGY_COMPOSITE_KEY_SEPARATOR}{slug}"
                if policy_id not in policies:
                    continue
                rows.append(
                    ScheduleAssignment(
                        assignment_id=ONTOLOGY_COMPOSITE_KEY_SEPARATOR.join((
                            source_kind,
                            source_id,
                            axis_row.axis,
                            slug,
                        )),
                        axis=axis_row.axis,
                        policy_id=policy_id,
                        source_kind=source_kind,
                        source_card_id=source_id,
                        component_id=component_id,
                    )
                )
    if len({row.assignment_id for row in rows}) != len(rows):
        raise ValueError("schedule assignment identifiers are ambiguous")
    groups: list[SchedulePolicyGroup] = []
    for axis_row in _assignment_axes(program):
        for policy_id in sorted({row.policy_id for row in rows if row.axis == axis_row.axis}):
            assignment_ids = tuple(row.assignment_id for row in rows if row.policy_id == policy_id)
            groups.append(SchedulePolicyGroup(axis_row.axis, policy_id, assignment_ids, 1.0))
    return ScheduleProjection(tuple(rows), tuple(groups))


def slot_matches(program: RuntimeProgram, slot: Slot, match: TraitEffectMatch) -> bool:
    for key, expected in match.values:
        dimension = program.effect_match_dimensions_by_key.get(key)
        if dimension is None:
            raise ValueError(f"unknown effect match dimension {key!r}")
        if not hasattr(slot, dimension.slot_field):
            raise ValueError(f"effect match dimension {key!r} references unknown slot field")
        if getattr(slot, dimension.slot_field) != expected:
            return False
    return True


def compute_slot_score(
    program: RuntimeProgram,
    projection: ScheduleProjection,
    slot: Slot,
    policies: dict[str, SchedulingPolicy],
) -> SlotScoreTrace:
    score = 0
    effects: list[ProjectedEffectTrace] = []
    rows_by_id = {row.assignment_id: row for row in projection.assignments}
    scores = program.effect_scoring.scores_by_level
    for group in projection.groups:
        policy = policies[group.policy_id]
        source_ids = tuple(sorted(rows_by_id[item].source_card_id for item in group.assignment_ids))
        for effect in policy.effects:
            if not slot_matches(program, slot, effect.match) or effect.level is None:
                continue
            score_row = scores.get(effect.level)
            if score_row is None:
                raise ValueError(f"ontology score level {effect.level!r} is missing")
            delta = round(float(score_row.score) * group.score_weight)
            score += delta
            effects.append(
                ProjectedEffectTrace(
                    policy_id=group.policy_id,
                    assignment_ids=group.assignment_ids,
                    source_card_ids=source_ids,
                    weight=group.score_weight,
                    match=effect.match,
                    original_level=effect.level,
                    projected_level=effect.level,
                    delta=delta,
                )
            )
    return SlotScoreTrace(score, False, tuple(effects), ())


def build_substance_slot_names(
    *,
    assigned_item_ids: list[str],
    item_products: dict[str, str],
    products: dict[str, Product],
    substances: dict[str, Substance],
) -> list[str]:
    names: set[str] = set()
    for item_id in assigned_item_ids:
        product = products.get(item_products[item_id])
        if product:
            names.update(
                format_substance_name(substances[component.substance])
                for component in product.components
                if component.substance in substances
            )
    return sorted(names, key=str.casefold)


def render_slot_effects(trace: SlotScoreTrace | SlotCandidateTrace) -> list[str]:
    rows = [
        f"{effect.policy_id}: score={effect.delta:+d}; assignments={','.join(effect.assignment_ids)}; "
        f"sources={','.join(effect.source_card_ids)}"
        for effect in trace.effects
        if effect.delta != 0
    ]
    return rows or ["No strict timing driver; placed in an available compatible slot."]
