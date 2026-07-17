"""Typed governed scheduling projection and slot scoring."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, replace
from typing import Literal, cast, get_args

from planner.cards.substance import format_substance_name
from planner.contracts import (
    AssignmentAction,
    AssignmentAuthority,
    AssignmentSourceKind,
    EffectiveAssignmentProjection,
    EffectivePolicyGroup,
    EnforcementCap,
    GovernanceDiagnostic,
    GovernedScheduleProjection,
    PlannerCapability,
    Product,
    ProjectedEffectTrace,
    SchedulingPolicy,
    ScopeEvaluation,
    ScopeOutcome,
    Slot,
    SlotCandidateTrace,
    SlotScoreTrace,
    Substance,
    TraitEffectMatch,
)
from planner.ontology.errors import MALFORMED, OntologyInfrastructureError
from planner.ontology.runtime_program import RuntimeAssignmentAxis, RuntimeProgram, RuntimeScopeDimension
from planner.ontology.scheduling_runtime import (
    RuntimeAssignmentAuthorityDecision,
    RuntimeCompetitionDecision,
    decide_assignment_enforcement,
    decide_competition,
    decide_effect,
    evaluate_scope,
    resolve_assignment_authority,
    resolve_capability,
    resolve_component_authority,
)

Axis = Literal["intake", "timing", "activity"]


@dataclass(frozen=True, slots=True)
class _Source:
    kind: AssignmentSourceKind
    card_id: str
    component_id: str | None
    authority_kind: str
    authority_form: str
    card: Product | Substance


@dataclass(frozen=True, slots=True)
class _ScopeResult:
    evaluation: ScopeEvaluation
    caps: tuple[str, ...]
    action_codes: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class _RowState:
    row: EffectiveAssignmentProjection
    authority: RuntimeAssignmentAuthorityDecision
    executable: bool
    action_codes: tuple[str, ...]


def _malformed(message: str) -> OntologyInfrastructureError:
    return OntologyInfrastructureError(f"plan scheduling runtime {message}", code=MALFORMED)


def _assignment_axes(program: RuntimeProgram) -> tuple[RuntimeAssignmentAxis, ...]:
    axes = tuple(sorted(program.assignment_axes, key=lambda row: (row.order, row.id)))
    if not axes:
        raise _malformed("assignment-axis table is empty")
    if len({row.axis for row in axes}) != len(axes) or len({row.order for row in axes}) != len(axes):
        raise _malformed("assignment axes or their ordering are ambiguous")
    allowed = set(get_args(Axis))
    for row in axes:
        if row.axis not in allowed:
            raise _malformed(f"assignment axis {row.axis!r} is unsupported by the projection contract")
        if row.assignment_source != "schedule" or not row.assignment_field:
            raise _malformed(f"assignment axis {row.id!r} has an unsupported source binding")
    return axes


def _axis_order(program: RuntimeProgram) -> dict[str, int]:
    return {row.axis: row.order for row in _assignment_axes(program)}


def _contract_value(value: str, contract: object, label: str) -> str:
    if value not in get_args(contract):
        raise _malformed(f"{label} {value!r} is unsupported by the projection contract")
    return value


def _axis_values(source: Product | Substance, axis: RuntimeAssignmentAxis) -> tuple[str, ...]:
    values = getattr(source, axis.assignment_field, None)
    if not isinstance(values, tuple) or any(not isinstance(value, str) or not value for value in values):
        raise _malformed(f"assignment field {axis.assignment_field!r} is not a tuple of non-empty strings")
    return values


def _assignment_id(kind: AssignmentSourceKind, card_id: str, axis: Axis, policy_id: str) -> str:
    parts = policy_id.split(":", 1)
    if len(parts) != 2 or not parts[1]:
        raise _malformed(f"policy id {policy_id!r} cannot form an assignment id")
    return f"{kind}:{card_id}:{axis}:{parts[1]}"


def _single_supported_value(values: Sequence[str], dimension: str) -> str:
    if len(values) != 1:
        raise _malformed(f"scope dimension {dimension!r} requires exactly one supported value")
    return values[0]


def _scope_facts(
    dimension: RuntimeScopeDimension,
    requested_value: str,
    capability: PlannerCapability,
    source: _Source,
    *,
    supported_slot_models: tuple[str, ...],
    product_scope: tuple[str, ...],
    formulations: tuple[str, ...],
) -> dict[str, object]:
    if dimension.key == "planner":
        return {"requested_value": requested_value, "supported_value": capability.planner}
    if dimension.key == "food_model":
        return {"requested_value": requested_value, "supported_value": capability.food_model}
    if dimension.key == "slot_model":
        return {"requested_value": requested_value, "supported_values": supported_slot_models}
    if dimension.key in {"intended_use", "substrate"}:
        return {
            "requested_value": requested_value,
            "supported_value": _single_supported_value(dimension.values, dimension.key),
        }
    if dimension.key == "product":
        scope_kind = (
            _single_supported_value(product_scope, dimension.key)
            if source.kind == "product"
            else source.authority_kind
        )
        return {
            "scope_kind": scope_kind,
            "requested_product_id": requested_value,
            "actual_product_id": capability.product_id,
        }
    if dimension.key == "formulation":
        source_form = source.card.form if isinstance(source.card, Substance) and source.card.form else "unknown"
        return {
            "requested_value": requested_value,
            "source_form": source_form,
            "supported_values": formulations,
        }
    raise _malformed(f"scope dimension {dimension.key!r} has no planner fact adapter")


def _scope_outcome(program: RuntimeProgram, outcome: str) -> tuple[int, str]:
    rows = tuple(row for row in program.scope_outcomes if row.outcome == outcome)
    if len(rows) != 1:
        raise _malformed(f"scope outcome {outcome!r} is missing or ambiguous")
    return rows[0].rank, rows[0].id


def _scope_rank_bounds(program: RuntimeProgram) -> tuple[int, int]:
    allowed = set(get_args(ScopeOutcome))
    outcomes = {row.outcome for row in program.scope_outcomes}
    if outcomes != allowed:
        raise _malformed("scope outcomes do not match the projection contract")
    ranks = tuple(row.rank for row in program.scope_outcomes)
    return min(ranks), max(ranks)


def _evaluate_scopes(
    program: RuntimeProgram,
    scope: tuple[tuple[str, str], ...],
    capability: PlannerCapability,
    source: _Source,
) -> _ScopeResult:
    resolved = resolve_capability(program, capability.planner, capability.food_model)
    supported_slot_models = tuple(sorted(capability.slot_models))
    if not scope:
        highest_rank = max(row.rank for row in program.scope_outcomes)
        rows = tuple(row for row in program.scope_outcomes if row.rank == highest_rank)
        if len(rows) != 1:
            raise _malformed("neutral scope outcome is missing or ambiguous")
        outcome = cast(ScopeOutcome, _contract_value(rows[0].outcome, ScopeOutcome, "scope outcome"))
        evaluation = ScopeEvaluation(outcome, (), (), rows[0].id)
        return _ScopeResult(evaluation, (rows[0].enforcement_cap,), (rows[0].scope_action, rows[0].id))
    if len({key for key, _value in scope}) != len(scope):
        raise _malformed("scope contains duplicate dimensions")

    decisions: list[tuple[str, int, str, str, tuple[str, ...]]] = []
    for key, value in sorted(scope):
        dimensions = tuple(row for row in program.scope_dimensions if row.key == key)
        if len(dimensions) != 1:
            raise _malformed(f"scope dimension {key!r} is missing or ambiguous")
        dimension = dimensions[0]
        facts = _scope_facts(
            dimension,
            value,
            capability,
            source,
            supported_slot_models=supported_slot_models,
            product_scope=resolved.product_scope,
            formulations=resolved.formulations,
        )
        decision = evaluate_scope(program, key, facts)
        rank, _outcome_id = _scope_outcome(program, decision.outcome)
        decisions.append(
            (key, rank, decision.outcome, decision.enforcement_cap, (*decision.reason_codes, decision.action))
        )

    worst_rank = min(rank for _key, rank, _outcome, _cap, _codes in decisions)
    worst_outcomes = {outcome for _key, rank, outcome, _cap, _codes in decisions if rank == worst_rank}
    if len(worst_outcomes) != 1:
        raise _malformed("scope decisions have ambiguous lowest-ranked outcomes")
    outcome_value = next(iter(worst_outcomes))
    outcome = cast(ScopeOutcome, _contract_value(outcome_value, ScopeOutcome, "scope outcome"))
    lowest_rank, highest_rank = _scope_rank_bounds(program)
    mismatch_keys = tuple(key for key, rank, _value, _cap, _codes in decisions if rank == lowest_rank)
    limited_keys = tuple(
        key for key, rank, _value, _cap, _codes in decisions if rank not in {lowest_rank, highest_rank}
    )
    reason_codes = tuple(code for _key, _rank, _value, _cap, codes in decisions for code in codes)
    evaluation = ScopeEvaluation(outcome, mismatch_keys, limited_keys, ";".join(reason_codes))
    return _ScopeResult(
        evaluation,
        tuple(cap for _key, _rank, _value, cap, _codes in decisions),
        reason_codes,
    )


def _diagnostic(
    code: str,
    row: EffectiveAssignmentProjection,
    policy: SchedulingPolicy,
    related: tuple[str, ...] = (),
) -> GovernanceDiagnostic:
    return GovernanceDiagnostic(
        code=code,
        axis=row.axis,
        policy_id=row.policy_id,
        policy_status=policy.status,
        policy_enforcement=policy.enforcement,
        assignment_id=row.assignment_id,
        source_card_id=row.source_card_id,
        assignment_status=row.governance.status,
        declared_cap=row.governance.enforcement_cap,
        effective_cap=row.effective_cap,
        policy_scope_reason=row.policy_scope.reason_code,
        assignment_scope_reason=row.assignment_scope.reason_code,
        related_policy_ids=related,
    )


def _sort_diagnostics(
    program: RuntimeProgram,
    rows: Sequence[GovernanceDiagnostic],
) -> tuple[GovernanceDiagnostic, ...]:
    order = _axis_order(program)
    unique = set(rows)
    return tuple(sorted(unique, key=lambda row: (order[row.axis], row.code, row.policy_id, row.assignment_id)))


def _sources(program: RuntimeProgram, product: Product, substances: dict[str, Substance]) -> tuple[_Source, ...]:
    rows: list[_Source] = [_Source("product", product.id, None, "product", "direct", product)]
    components = tuple(component for component in product.components if component.substance in substances)
    has_primary = any(component.primary is True for component in components)
    for component in components:
        component_primary = "true" if component.primary is True else "false" if component.primary is False else "unset"
        authority_form = resolve_component_authority(
            program,
            {"any_explicit_primary": has_primary, "component_primary": component_primary},
        ).outcome
        substance = substances[component.substance]
        rows.append(_Source("substance", substance.id, substance.id, "component", authority_form, substance))
    return tuple(rows)


def _build_rows(
    program: RuntimeProgram,
    product: Product,
    substances: dict[str, Substance],
    policies: dict[str, SchedulingPolicy],
    capability: PlannerCapability,
) -> list[_RowState]:
    states: list[_RowState] = []
    for axis_row in _assignment_axes(program):
        axis = cast(Axis, axis_row.axis)
        for source in _sources(program, product, substances):
            authority = resolve_assignment_authority(
                program,
                {"source_kind": source.authority_kind, "source_form": source.authority_form},
            )
            authority_value = cast(
                AssignmentAuthority,
                _contract_value(authority.authority, AssignmentAuthority, "assignment authority"),
            )
            for slug in _axis_values(source.card, axis_row):
                policy_id = f"{axis}:{slug}"
                policy = policies.get(policy_id)
                governance = source.card.schedule_governance.get(policy_id)
                if policy is None or governance is None:
                    continue
                policy_scope = _evaluate_scopes(program, policy.scope, capability, source)
                assignment_scope = _evaluate_scopes(program, governance.scope, capability, source)
                enforcement = decide_assignment_enforcement(
                    program,
                    policy.enforcement,
                    (policy.status, governance.status),
                    (
                        governance.enforcement_cap,
                        *policy_scope.caps,
                        *assignment_scope.caps,
                        authority.enforcement_cap,
                    ),
                )
                effective_cap = cast(
                    EnforcementCap,
                    _contract_value(enforcement.mode, EnforcementCap, "effective enforcement"),
                )
                action_value = "active" if enforcement.executable else "suppressed"
                action = cast(AssignmentAction, _contract_value(action_value, AssignmentAction, "assignment action"))
                action_codes = (
                    authority.action_code,
                    *authority.reason_codes,
                    *policy_scope.action_codes,
                    *assignment_scope.action_codes,
                    *enforcement.action_codes,
                )
                row = EffectiveAssignmentProjection(
                    assignment_id=_assignment_id(source.kind, source.card_id, axis, policy_id),
                    axis=axis,
                    policy_id=policy_id,
                    source_kind=source.kind,
                    source_card_id=source.card_id,
                    component_id=source.component_id,
                    authority=authority_value,
                    governance=governance,
                    policy_scope=policy_scope.evaluation,
                    assignment_scope=assignment_scope.evaluation,
                    effective_cap=effective_cap,
                    action=action,
                    reason_code=authority.action_code if enforcement.executable else enforcement.action_codes[-1],
                )
                states.append(_RowState(row, authority, enforcement.executable, action_codes))
    assignment_ids = [state.row.assignment_id for state in states]
    if len(set(assignment_ids)) != len(assignment_ids):
        raise _malformed("assignment identifiers are ambiguous")
    return states


def _competition_facts(left: _RowState, right: _RowState) -> dict[str, object]:
    return {
        "left_authority": left.row.authority,
        "right_authority": right.row.authority,
        "left_source_kind": left.row.source_kind,
        "right_source_kind": right.row.source_kind,
        "left_axis": left.row.axis,
        "right_axis": right.row.axis,
        "left_policy_id": left.row.policy_id,
        "right_policy_id": right.row.policy_id,
        "left_action": left.row.action,
        "right_action": right.row.action,
        "left_executable": left.executable,
        "right_executable": right.executable,
        "left_eligible": left.executable and left.row.action == "active",
        "right_eligible": right.executable and right.row.action == "active",
    }


def _apply_competition(program: RuntimeProgram, states: list[_RowState]) -> list[_RowState]:
    losses: dict[int, list[tuple[int, RuntimeCompetitionDecision]]] = {}
    for left_index, left_state in enumerate(states):
        for right_index in range(left_index + 1, len(states)):
            right_state = states[right_index]
            decision = decide_competition(program, _competition_facts(left_state, right_state))
            if decision.action_code == "no_action":
                continue
            if decision.action_code == "left_wins":
                loser_index = right_index
                winner_index = left_index
            elif decision.action_code == "right_wins":
                loser_index = left_index
                winner_index = right_index
            else:
                raise _malformed(f"competition action {decision.action_code!r} cannot be projected")
            losses.setdefault(loser_index, []).append((winner_index, decision))
    for loser_index, candidates in losses.items():
        highest_priority = max(states[winner_index].authority.priority for winner_index, _decision in candidates)
        winners = tuple(
            (winner_index, decision)
            for winner_index, decision in candidates
            if states[winner_index].authority.priority == highest_priority
        )
        decisions = {(decision.action_code, decision.reason_codes) for _winner_index, decision in winners}
        if len(decisions) != 1:
            raise _malformed(f"assignment {states[loser_index].row.assignment_id!r} has ambiguous competition winners")
        decision = winners[0][1]
        loser = states[loser_index]
        reason = decision.reason_codes[0] if decision.reason_codes else decision.action_code
        states[loser_index] = replace(
            loser,
            row=replace(loser.row, effective_cap="none", action="shadowed", reason_code=reason),
            action_codes=(*loser.action_codes, decision.action_code, *decision.reason_codes),
        )
    return states


def _enforcement_rank(program: RuntimeProgram, mode: str) -> int:
    rows = tuple(row for row in program.enforcement if row.mode == mode)
    if len(rows) != 1:
        raise _malformed(f"enforcement mode {mode!r} is missing or ambiguous")
    return rows[0].rank


def _build_groups(program: RuntimeProgram, states: list[_RowState]) -> list[EffectivePolicyGroup]:
    order = _axis_order(program)
    rows = [state.row for state in states]
    authority_by_id = {state.row.assignment_id: state.authority for state in states}
    keys = sorted({(row.axis, row.policy_id) for row in rows}, key=lambda key: (order[key[0]], key[1]))
    groups: list[EffectivePolicyGroup] = []
    for axis, policy_id in keys:
        same = [row for row in rows if (row.axis, row.policy_id) == (axis, policy_id)]
        applicable = [row for row in same if row.action == "active"]
        if not applicable:
            continue
        highest_control_rank = max(authority_by_id[row.assignment_id].control_rank for row in applicable)
        controlling = [
            row for row in applicable if authority_by_id[row.assignment_id].control_rank == highest_control_rank
        ]
        weights = {authority_by_id[row.assignment_id].score_weight for row in controlling}
        if len(weights) != 1:
            raise _malformed(f"policy group {(axis, policy_id)!r} has ambiguous score weights")
        highest_cap_rank = max(_enforcement_rank(program, row.effective_cap) for row in controlling)
        caps = {
            row.effective_cap
            for row in controlling
            if _enforcement_rank(program, row.effective_cap) == highest_cap_rank
        }
        if len(caps) != 1:
            raise _malformed(f"policy group {(axis, policy_id)!r} has ambiguous effective enforcement")
        groups.append(
            EffectivePolicyGroup(
                axis,
                policy_id,
                tuple(row.assignment_id for row in controlling),
                tuple(row.assignment_id for row in same),
                next(iter(caps)),
                next(iter(weights)),
            )
        )
    return groups


def _build_diagnostics(
    program: RuntimeProgram,
    states: list[_RowState],
    groups: list[EffectivePolicyGroup],
    policies: dict[str, SchedulingPolicy],
) -> list[GovernanceDiagnostic]:
    row_by_id = {state.row.assignment_id: state.row for state in states}
    diagnostics = [
        _diagnostic(code, state.row, policies[state.row.policy_id])
        for state in states
        for code in state.action_codes
    ]
    for axis_row in _assignment_axes(program):
        axis_groups = [group for group in groups if group.axis == axis_row.axis]
        related = tuple(sorted({group.policy_id for group in axis_groups}))
        if len(related) > 1:
            diagnostics.extend(
                _diagnostic("MULTI_POLICY_AXIS", row_by_id[assignment_id], policies[group.policy_id], related)
                for group in axis_groups
                for assignment_id in group.controlling_assignment_ids
            )
    return diagnostics


def project_governed_assignments(
    program: RuntimeProgram,
    product: Product,
    substances: dict[str, Substance],
    policies: dict[str, SchedulingPolicy],
    capability: PlannerCapability,
) -> GovernedScheduleProjection:
    states = _apply_competition(program, _build_rows(program, product, substances, policies, capability))
    groups = _build_groups(program, states)
    diagnostics = _build_diagnostics(program, states, groups, policies)
    order = _axis_order(program)
    states.sort(
        key=lambda state: (
            order[state.row.axis],
            state.row.policy_id,
            -state.authority.control_rank,
            state.row.source_card_id,
            state.row.assignment_id,
        )
    )
    return GovernedScheduleProjection(
        tuple(state.row for state in states),
        tuple(groups),
        _sort_diagnostics(program, diagnostics),
    )


def slot_matches(slot: Slot, match: TraitEffectMatch) -> bool:
    return not (
        (match.near is not None and slot.near != match.near) or (match.food is not None and slot.food != match.food)
    )


def compute_slot_score(
    program: RuntimeProgram,
    projection: GovernedScheduleProjection,
    slot: Slot,
    policies: dict[str, SchedulingPolicy],
) -> SlotScoreTrace:
    score = 0
    blocked = False
    effects: list[ProjectedEffectTrace] = []
    diagnostics = list(projection.diagnostics)
    row_by_id = {row.assignment_id: row for row in projection.assignments}
    for group in projection.groups:
        policy = policies[group.policy_id]
        controlling = [row_by_id[assignment_id] for assignment_id in group.controlling_assignment_ids]
        sources = tuple(sorted(row.source_card_id for row in controlling))
        for effect in policy.effects:
            if not slot_matches(slot, effect.match):
                continue
            decision = decide_effect(
                program,
                group.effective_cap,
                effect.level,
                bool(effect.block),
                group.score_weight,
            )
            delta = round(decision.score_delta)
            score += delta
            blocked |= decision.block
            effects.append(
                ProjectedEffectTrace(
                    policy_id=group.policy_id,
                    assignment_ids=group.controlling_assignment_ids,
                    source_card_ids=sources,
                    effective_cap=group.effective_cap,
                    weight=group.score_weight,
                    match=effect.match,
                    original_level=effect.level,
                    original_block=bool(effect.block),
                    projected_level=decision.level,
                    projected_block=decision.block,
                    delta=delta,
                    action_codes=decision.action_codes,
                )
            )
            diagnostics.extend(
                _diagnostic(code, row, policy)
                for code in decision.action_codes
                for row in controlling
            )
    return SlotScoreTrace(score, blocked, tuple(effects), _sort_diagnostics(program, diagnostics))


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
            for component in product.components:
                if component.substance in substances:
                    names.add(format_substance_name(substances[component.substance]))
    return sorted(names, key=str.casefold)


def render_slot_effects(trace: SlotScoreTrace | SlotCandidateTrace) -> list[str]:
    rows = [
        f"{effect.policy_id}: score={effect.delta:+d}; assignments={','.join(effect.assignment_ids)}; "
        f"sources={','.join(effect.source_card_ids)}; cap={effect.effective_cap}; "
        f"actions={','.join(effect.action_codes)}"
        for effect in trace.effects
        if effect.delta != 0
    ]
    return rows or ["No strict timing driver; placed in an available compatible slot."]
