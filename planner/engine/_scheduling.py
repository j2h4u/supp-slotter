"""Typed governed scheduling projection and slot scoring."""

from __future__ import annotations

from dataclasses import replace
from typing import Literal, cast

from planner.cards.substance import format_substance_name
from planner.contracts import (
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
    ScheduleGovernance,
    SchedulingPolicy,
    ScopeEvaluation,
    Slot,
    SlotCandidateTrace,
    SlotScoreTrace,
    Substance,
    TraitEffectMatch,
)
from planner.domain_constants import LEVEL_SCORES

Axis = Literal["intake", "timing", "activity"]
ScopePrefix = Literal["POLICY", "ASSIGNMENT"]
_AXES: tuple[Axis, ...] = ("intake", "timing", "activity")
_RANK: dict[EnforcementCap, int] = {"none": 0, "advisory": 1, "preference": 2, "block": 3}
_CAPS: tuple[EnforcementCap, ...] = ("none", "advisory", "preference", "block")


def _evaluate_scope(  # noqa: C901, PLR0912
    prefix: ScopePrefix,
    scope: tuple[tuple[str, str], ...],
    capability: PlannerCapability,
    direct: bool,
    source: Substance | Product,
) -> ScopeEvaluation:
    mismatch: list[str] = []
    limited: list[str] = []
    for key, value in sorted(scope):
        if key == "planner":
            if value != "slot_policy":
                mismatch.append(key)
        elif key == "food_model":
            if value != "binary":
                mismatch.append(key)
        elif key == "slot_model":
            if value not in capability.slot_models:
                mismatch.append(key)
        elif key == "product":
            if not direct or value != capability.product_id:
                mismatch.append(key)
        elif key == "formulation":
            if value == "unknown":
                limited.append(key)
            elif not isinstance(source, Substance) or source.form != value:
                mismatch.append(key)
        elif key in {"intended_use", "substrate"}:
            limited.append(key)
        else:
            raise ValueError(f"unknown schedule scope key: {key}")
    mismatch_keys = tuple(sorted(set(mismatch)))
    limited_keys = tuple(sorted(set(limited)))
    if mismatch_keys:
        return ScopeEvaluation(
            "mismatch", mismatch_keys, limited_keys, f"{prefix}_SCOPE_MISMATCH:{','.join(mismatch_keys)}"
        )
    if limited_keys:
        return ScopeEvaluation("limited", (), limited_keys, f"{prefix}_SCOPE_LIMITED:{','.join(limited_keys)}")
    return ScopeEvaluation("matched", (), (), f"{prefix}_SCOPE_MATCHED")


def _cap_without_authority(
    policy: SchedulingPolicy,
    governance: ScheduleGovernance,
    policy_scope: ScopeEvaluation,
    assignment_scope: ScopeEvaluation,
) -> EnforcementCap:
    ceilings = [_RANK[policy.enforcement], _RANK[governance.enforcement_cap]]
    if policy.status == "retired" or governance.status == "retired":
        ceilings.append(_RANK["none"])
    if policy.status == "review_pending" or governance.status == "review_pending":
        ceilings.append(_RANK["preference"])
    if policy_scope.outcome == "mismatch" or assignment_scope.outcome == "mismatch":
        ceilings.append(_RANK["none"])
    return _CAPS[min(ceilings)]


def _effective_cap(
    policy: SchedulingPolicy,
    governance: ScheduleGovernance,
    authority: AssignmentAuthority,
    policy_scope: ScopeEvaluation,
    assignment_scope: ScopeEvaluation,
) -> EnforcementCap:
    cap = _cap_without_authority(policy, governance, policy_scope, assignment_scope)
    if authority == "component_secondary":
        return _CAPS[min(_RANK[cap], _RANK["preference"])]
    return cap


def _assignment_id(kind: AssignmentSourceKind, card_id: str, axis: Axis, policy_id: str) -> str:
    return f"{kind}:{card_id}:{axis}:{policy_id.split(':', 1)[1]}"


def _axis_values(source: Product | Substance, axis: Axis) -> tuple[str, ...]:
    if axis == "intake":
        return source.intake
    if axis == "timing":
        return source.timing
    return source.activity


def _projection_codes(row: EffectiveAssignmentProjection, policy: SchedulingPolicy) -> tuple[str, ...]:
    codes: list[str] = []
    if row.reason_code == "PRODUCT_AXIS_OVERRIDE":
        codes.append("PRODUCT_AXIS_OVERRIDE")
    if policy.status == "retired":
        codes.append("POLICY_RETIRED")
    if row.governance.status == "retired":
        codes.append("ASSIGNMENT_RETIRED")
    if row.policy_scope.outcome == "mismatch":
        codes.append("POLICY_SCOPE_MISMATCH")
    if row.assignment_scope.outcome == "mismatch":
        codes.append("ASSIGNMENT_SCOPE_MISMATCH")
    if row.reason_code == "SECONDARY_SAME_POLICY_SHADOWED":
        codes.append("SECONDARY_SAME_POLICY_SHADOWED")
    if row.policy_scope.outcome == "limited":
        codes.append("POLICY_SCOPE_LIMITED")
    if row.assignment_scope.outcome == "limited":
        codes.append("ASSIGNMENT_SCOPE_LIMITED")
    authority_free_cap = _cap_without_authority(
        policy,
        row.governance,
        row.policy_scope,
        row.assignment_scope,
    )
    authority_ceiling_applied = (
        row.authority == "component_secondary" and _RANK[authority_free_cap] > _RANK["preference"]
    )
    if authority_ceiling_applied:
        codes.append("SECONDARY_CAPPED")
    return tuple(codes or ["ACTIVE"])


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


def _sort_diagnostics(rows: list[GovernanceDiagnostic]) -> tuple[GovernanceDiagnostic, ...]:
    unique = set(rows)
    return tuple(sorted(unique, key=lambda d: (_AXES.index(d.axis), d.code, d.policy_id, d.assignment_id)))


def project_governed_assignments(  # noqa: C901, PLR0912, PLR0914, PLR0915
    product: Product,
    substances: dict[str, Substance],
    policies: dict[str, SchedulingPolicy],
    capability: PlannerCapability,
) -> GovernedScheduleProjection:
    rows: list[EffectiveAssignmentProjection] = []
    for axis in _AXES:
        product_values = _axis_values(product, axis)
        direct_slug = product_values[0] if product_values else None
        sources: list[tuple[AssignmentSourceKind, str, str | None, AssignmentAuthority, Product | Substance, str]] = []
        if direct_slug:
            sources.append(("product", product.id, None, "product_direct", product, direct_slug))
        components = [component for component in product.components if component.substance in substances]
        has_primary = any(component.primary is True for component in components)
        for component in components:
            substance = substances[component.substance]
            values = _axis_values(substance, axis)
            if values:
                authority: AssignmentAuthority = (
                    "component_primary" if not has_primary or component.primary is True else "component_secondary"
                )
                sources.append(("substance", substance.id, substance.id, authority, substance, values[0]))
        for kind, card_id, component_id, authority, source, slug in sources:
            policy_id = f"{axis}:{slug}"
            policy = policies.get(policy_id)
            governance = source.schedule_governance.get(policy_id)
            if policy is None or governance is None:
                continue
            direct = kind == "product"
            policy_scope = _evaluate_scope("POLICY", policy.scope, capability, direct, source)
            assignment_scope = _evaluate_scope("ASSIGNMENT", governance.scope, capability, direct, source)
            effective_cap = _effective_cap(policy, governance, authority, policy_scope, assignment_scope)
            action = "active" if effective_cap != "none" else "suppressed"
            row = EffectiveAssignmentProjection(
                assignment_id=_assignment_id(kind, card_id, axis, policy_id),
                axis=axis,
                policy_id=policy_id,
                source_kind=kind,
                source_card_id=card_id,
                component_id=component_id,
                authority=authority,
                governance=governance,
                policy_scope=policy_scope,
                assignment_scope=assignment_scope,
                effective_cap=effective_cap,
                action=action,
                reason_code="ACTIVE",
            )
            codes = _projection_codes(row, policy)
            rows.append(replace(row, reason_code=codes[0]))

    direct_axes = {row.axis for row in rows if row.source_kind == "product"}
    rows = [
        replace(row, effective_cap="none", action="shadowed", reason_code="PRODUCT_AXIS_OVERRIDE")
        if row.axis in direct_axes and row.source_kind == "substance"
        else row
        for row in rows
    ]
    for key in {(row.axis, row.policy_id) for row in rows}:
        matching = [row for row in rows if (row.axis, row.policy_id) == key]
        primary_active = any(row.authority == "component_primary" and row.action == "active" for row in matching)
        if primary_active:
            rows = [
                replace(row, effective_cap="none", action="shadowed", reason_code="SECONDARY_SAME_POLICY_SHADOWED")
                if (row.axis, row.policy_id) == key
                and row.authority == "component_secondary"
                and row.action == "active"
                else row
                for row in rows
            ]

    groups: list[EffectivePolicyGroup] = []
    group_keys: set[tuple[Axis, str]] = {(row.axis, row.policy_id) for row in rows}
    for axis, policy_id in sorted(group_keys):
        same = [row for row in rows if (row.axis, row.policy_id) == (axis, policy_id)]
        applicable = [row for row in same if row.action == "active" and row.effective_cap != "none"]
        if not applicable:
            continue
        controlling = (
            [row for row in applicable if row.authority == "product_direct"]
            or [row for row in applicable if row.authority == "component_primary"]
            or applicable
        )
        cap = cast(
            EnforcementCap,
            max((row.effective_cap for row in controlling), key=lambda value: _RANK[cast(EnforcementCap, value)]),
        )
        weight = 0.25 if all(row.authority == "component_secondary" for row in controlling) else 1.0
        groups.append(
            EffectivePolicyGroup(
                axis,
                policy_id,
                tuple(row.assignment_id for row in controlling),
                tuple(row.assignment_id for row in same),
                cap,
                weight,
            )
        )

    row_by_id = {row.assignment_id: row for row in rows}
    diagnostics: list[GovernanceDiagnostic] = []
    for row in rows:
        policy = policies[row.policy_id]
        diagnostics.extend(_diagnostic(code, row, policy) for code in _projection_codes(row, policy))
    for axis in _AXES:
        axis_groups = [group for group in groups if group.axis == axis]
        related = tuple(sorted({group.policy_id for group in axis_groups}))
        if len(related) > 1:
            for group in axis_groups:
                for assignment_id in group.controlling_assignment_ids:
                    row = row_by_id[assignment_id]
                    diagnostics.append(_diagnostic("MULTI_POLICY_AXIS", row, policies[row.policy_id], related))
    rows.sort(
        key=lambda row: (
            _AXES.index(row.axis),
            row.policy_id,
            0 if row.source_kind == "product" else 1,
            row.source_card_id,
        )
    )
    return GovernedScheduleProjection(tuple(rows), tuple(groups), _sort_diagnostics(diagnostics))


def slot_matches(slot: Slot, match: TraitEffectMatch) -> bool:
    return not (
        (match.near is not None and slot.near != match.near) or (match.food is not None and slot.food != match.food)
    )


def compute_slot_score(  # noqa: C901
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
            projected_level = effect.level
            projected_block = bool(effect.block)
            action_codes: list[str] = []
            if group.effective_cap == "advisory":
                projected_level = None
                projected_block = False
                action_codes.append("ADVISORY_NO_SCORE")
            elif group.effective_cap == "preference":
                if effect.block is True:
                    projected_block = False
                    action_codes.append("PENDING_BLOCK_SUPPRESSED")
                if effect.level in {"prefer_strong", "avoid_strong"}:
                    projected_level = "prefer" if effect.level == "prefer_strong" else "avoid"
                    action_codes.append("STRONG_EFFECT_DOWNGRADED")
            if not action_codes:
                action_codes.append("ACTIVE")
            delta = round(LEVEL_SCORES.get(projected_level, 0) * group.score_weight) if projected_level else 0
            score += delta
            blocked |= projected_block
            trace = ProjectedEffectTrace(
                policy_id=group.policy_id,
                assignment_ids=group.controlling_assignment_ids,
                source_card_ids=sources,
                effective_cap=group.effective_cap,
                weight=group.score_weight,
                match=effect.match,
                original_level=effect.level,
                original_block=bool(effect.block),
                projected_level=projected_level,
                projected_block=projected_block,
                delta=delta,
                action_codes=tuple(action_codes),
            )
            effects.append(trace)
            for code in action_codes:
                if code != "ACTIVE":
                    diagnostics.extend(_diagnostic(code, row, policy) for row in controlling)
    return SlotScoreTrace(score, blocked, tuple(effects), _sort_diagnostics(diagnostics))


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
        f"{effect.policy_id}: score={effect.delta:+d}; assignments={','.join(effect.assignment_ids)}; sources={','.join(effect.source_card_ids)}; cap={effect.effective_cap}; actions={','.join(effect.action_codes)}"
        for effect in trace.effects
        if effect.delta != 0
    ]
    return rows or ["No strict timing driver; placed in an available compatible slot."]
