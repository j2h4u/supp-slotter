"""Ontology-backed schedule assignment projection and soft slot scoring.

Cards only declare schedule axes/values.  The ontology supplies the matching
policy and score; this module merely joins the two and evaluates the policy
effects against immutable ontology observations exposed by each slot.
"""

from __future__ import annotations

from planner.cards.substance import format_substance_name
from planner.contracts import (
    Product,
    ProjectedEffectTrace,
    ScheduleAssignment,
    ScheduleAssignmentSource,
    SchedulePolicyGroup,
    ScheduleProjection,
    SchedulingPolicy,
    Slot,
    SlotCandidateTrace,
    SlotScoreTrace,
    Substance,
    TraitEffectMatch,
)
from planner.ontology.artifacts import OntologyBundle
from planner.ontology.errors import MALFORMED, OntologyInfrastructureError
from planner.ontology.glue_capabilities import (
    ONTOLOGY_COMPOSITE_KEY_SEPARATOR,
    SOURCE_KIND_ROLE_ASSIGNMENT,
)
from planner.ontology.presentation import load_review_presentation
from planner.ontology.runtime_program import (
    IMPLEMENTED_AGGREGATION_MODE,
    RuntimeAssignmentAxis,
    RuntimeProgram,
    axis_cardinality_violation,
)


def _assignment_axes(program: RuntimeProgram) -> tuple[RuntimeAssignmentAxis, ...]:
    axes = tuple(sorted(program.assignment_axes, key=lambda row: (row.order, row.id)))
    if not axes or len({row.axis for row in axes}) != len(axes):
        raise OntologyInfrastructureError("ontology assignment axes are missing or ambiguous", code=MALFORMED)
    return axes


def _axis_values(source: ScheduleAssignmentSource, axis: RuntimeAssignmentAxis) -> tuple[str, ...]:
    values = tuple(assertion.value for assertion in source.assertions if assertion.axis == axis.axis)
    violation = axis_cardinality_violation(axis, len(values))
    if violation is not None:
        raise OntologyInfrastructureError(
            f"invalid schedule assignment count for axis {axis.axis!r}: {violation}", code=MALFORMED
        )
    if any(not isinstance(value, str) or not value for value in values):
        raise OntologyInfrastructureError(f"invalid schedule assignment value for axis {axis.axis!r}", code=MALFORMED)
    return values


def _sources(
    program: RuntimeProgram, product: Product, substances: dict[str, Substance]
) -> tuple[ScheduleAssignmentSource, ...]:
    assignment_kinds = tuple(
        row.source_kind for row in program.source_kind_values if SOURCE_KIND_ROLE_ASSIGNMENT in row.applies_to
    )
    if len(assignment_kinds) != 1:
        raise OntologyInfrastructureError(
            "ontology source-kind taxonomy must declare exactly one executable generic assignment source",
            code=MALFORMED,
        )
    # Source kind is intentionally metadata, not a Product/Substance dispatch
    # axis.  The projection boundary emits one uniform record shape and the
    # scheduler below only consumes that shape.
    source_kind = assignment_kinds[0]
    component_ids = [component.substance for component in product.components]
    if len(set(component_ids)) != len(component_ids):
        raise OntologyInfrastructureError(
            f"product {product.id!r} contains duplicate component substance references",
            code=MALFORMED,
        )
    rows: list[ScheduleAssignmentSource] = []
    rows.extend(
        ScheduleAssignmentSource(source_kind, substance.id, substance.id, substance.schedule_assertions)
        for component in product.components
        if (substance := substances.get(component.substance)) is not None
    )
    return tuple(rows)


def project_schedule_assignments(
    program: RuntimeProgram,
    product: Product,
    substances: dict[str, Substance],
    policies: dict[str, SchedulingPolicy],
) -> ScheduleProjection:
    """Project every authored card assignment to its ontology policy.

    All resolved assignments contribute a soft score. Card schedule data is
    joined directly to ontology policies; no extra runtime action is created.
    """
    rows: list[ScheduleAssignment] = []
    axes = _assignment_axes(program)
    sources = _sources(program, product, substances)
    _validate_source_assignments(axes, sources)
    rows.extend(_project_source_assignments(axes, sources, policies))
    if len({row.assignment_id for row in rows}) != len(rows):
        raise ValueError("schedule assignment identifiers are ambiguous")
    groups: list[SchedulePolicyGroup] = []
    for axis_row in _assignment_axes(program):
        for policy_id in sorted({row.policy_id for row in rows if row.axis == axis_row.axis}):
            assignment_ids = tuple(row.assignment_id for row in rows if row.policy_id == policy_id)
            groups.append(SchedulePolicyGroup(axis_row.axis, policy_id, assignment_ids, float(len(assignment_ids))))
    return ScheduleProjection(tuple(rows), tuple(groups))


def _validate_source_assignments(
    axes: tuple[RuntimeAssignmentAxis, ...],
    sources: tuple[ScheduleAssignmentSource, ...],
) -> None:
    declared_axes = {row.axis for row in axes}
    for source in sources:
        for assertion in source.assertions:
            if assertion.axis not in declared_axes:
                raise OntologyInfrastructureError(
                    "unknown schedule assignment: "
                    f"axis={assertion.axis!r}, slug={assertion.value!r}, "
                    f"source_kind={source.source_kind!r}, source_id={source.source_card_id!r}",
                    code=MALFORMED,
                )


def _project_source_assignments(
    axes: tuple[RuntimeAssignmentAxis, ...],
    sources: tuple[ScheduleAssignmentSource, ...],
    policies: dict[str, SchedulingPolicy],
) -> list[ScheduleAssignment]:
    rows: list[ScheduleAssignment] = []
    for axis_row in axes:
        for source in sources:
            for slug in _axis_values(source, axis_row):
                policy_id = f"{axis_row.axis}{ONTOLOGY_COMPOSITE_KEY_SEPARATOR}{slug}"
                if policy_id not in policies:
                    raise OntologyInfrastructureError(
                        "unknown schedule assignment: "
                        f"axis={axis_row.axis!r}, slug={slug!r}, "
                        f"source_kind={source.source_kind!r}, source_id={source.source_card_id!r}",
                        code=MALFORMED,
                    )
                rows.append(
                    ScheduleAssignment(
                        assignment_id=ONTOLOGY_COMPOSITE_KEY_SEPARATOR.join((
                            source.source_kind,
                            source.source_card_id,
                            axis_row.axis,
                            slug,
                        )),
                        axis=axis_row.axis,
                        policy_id=policy_id,
                        source_kind=source.source_kind,
                        source_card_id=source.source_card_id,
                        component_id=source.component_id,
                    )
                )
    return rows


def _legacy_slot_match(slot: Slot, key: str, expected: str | bool) -> bool | None:
    """Adapt the retired ``near``/``food`` policy match to logical topology.

    This is intentionally the sole legacy bridge.  It adapts policy matching
    only; authored cards and slot topology never regain the compound fields.
    ``None`` means that the key is not a legacy key.
    """
    legacy_observations = {observation.key: observation.value for observation in slot.observations}
    if len(legacy_observations) != len(slot.observations):
        raise OntologyInfrastructureError("slot observations contain duplicate keys", code=MALFORMED)
    if key == "food":
        if not isinstance(expected, bool):
            raise OntologyInfrastructureError("legacy food match must be boolean", code=MALFORMED)
        if slot.meal_context is not None:
            return slot.meal_context == ("with_food" if expected else "without_food")
        return legacy_observations.get("food") == expected
    if key != "near":
        return None
    if not isinstance(expected, str):
        raise OntologyInfrastructureError("legacy near match must be a string", code=MALFORMED)
    # Compound meal values had no independent semantics.  Preserve the old
    # policy boundary by making breakfast/day_meal deliberately non-matches.
    if expected in {"breakfast", "day_meal"}:
        return False
    axis_for_near = {
        "wake": ("circadian_anchor", "wake"),
        "sleep": ("circadian_anchor", "sleep"),
        "workout_before": ("exercise_anchor", "before"),
        "workout_after": ("exercise_anchor", "after"),
    }
    axis = axis_for_near.get(expected)
    if axis is None:
        raise OntologyInfrastructureError(f"unknown legacy near value {expected!r}", code=MALFORMED)
    actual = getattr(slot, axis[0])
    return actual == axis[1] if actual is not None else legacy_observations.get("near") == expected


def _slot_topology_match(slot: Slot, key: str, expected: str | bool) -> bool:
    """Evaluate one canonical or legacy policy match against a Slot."""
    legacy = _legacy_slot_match(slot, key, expected)
    if legacy is not None:
        return legacy
    actual: str | None
    if key == "meal_context":
        actual = slot.meal_context
    elif key == "circadian_anchor":
        actual = slot.circadian_anchor
    elif key == "exercise_anchor":
        actual = slot.exercise_anchor
    else:
        raise OntologyInfrastructureError(f"unknown ontology effect match dimension {key!r}", code=MALFORMED)
    return actual == expected


def slot_matches(program: RuntimeProgram, slot: Slot, match: TraitEffectMatch) -> bool:
    """Match a policy against independent logical slot topology axes."""
    del program  # retained in the public signature during the runtime cutover
    observations = {observation.key: observation.value for observation in slot.observations}
    if len(observations) != len(slot.observations):
        raise OntologyInfrastructureError("slot observations contain duplicate keys", code=MALFORMED)
    unknown_observations = set(observations) - {
        "near",
        "food",
        "meal_context",
        "circadian_anchor",
        "exercise_anchor",
    }
    if unknown_observations:
        raise OntologyInfrastructureError(
            "slot contains unknown ontology observations: " + ", ".join(sorted(unknown_observations)),
            code=MALFORMED,
        )
    keys: set[str] = set()
    for key, expected in match.values:
        if key in keys:
            raise OntologyInfrastructureError(f"duplicate ontology effect match key {key!r}", code=MALFORMED)
        keys.add(key)
        if not _slot_topology_match(slot, key, expected):
            return False
    return True


def compute_slot_score(
    program: RuntimeProgram,
    projection: ScheduleProjection,
    slot: Slot,
    policies: dict[str, SchedulingPolicy],
) -> SlotScoreTrace:
    if program.effect_scoring.aggregation_mode != IMPLEMENTED_AGGREGATION_MODE:
        raise OntologyInfrastructureError(
            "ontology effect scoring declares an unsupported aggregation mode",
            code=MALFORMED,
        )
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
                raise OntologyInfrastructureError(
                    f"ontology score level {effect.level!r} is missing",
                    code=MALFORMED,
                )
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
                    vote_count=len(group.assignment_ids),
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


def render_slot_effects(trace: SlotScoreTrace | SlotCandidateTrace, bundle: OntologyBundle) -> list[str]:
    presentation = load_review_presentation(bundle)
    rows = [
        f"{effect.policy_id}: score={effect.delta:+d}; assignments={','.join(effect.assignment_ids)}; "
        f"sources={','.join(effect.source_card_ids)}"
        for effect in trace.effects
        if effect.delta != 0
    ]
    if rows:
        return rows
    if presentation.zero_effect_condition != "no_nonzero_effects":
        raise OntologyInfrastructureError(
            "ontology schedule_presentation zero-effect condition is unsupported",
            code=MALFORMED,
        )
    return [presentation.zero_effect_template]
