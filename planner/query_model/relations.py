"""Relation classification queries for the planner read model."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from planner.ontology.glue_capabilities import ontology_assertion_filter_value, relation_endpoint_selector_kind
from planner.ontology.runtime_program import (
    RuntimeProgram,
    RuntimeRelationEndpointPolicy,
    RuntimeRelationPresenceStatusPolicy,
    RuntimeRelationWarningRule,
    relation_presence_policy_for_active_side,
)
from planner.query_model.session import SurrealSession


@dataclass(frozen=True, slots=True)
class _RelationReviewContext:
    warning_rules: tuple[RuntimeRelationWarningRule, ...]
    review_statuses: Mapping[str, object] | None = None
    presence_by_status: Mapping[str, RuntimeRelationPresenceStatusPolicy] | None = None
    presence_by_active_side: Mapping[str, RuntimeRelationPresenceStatusPolicy] | None = None
    endpoint_policies_by_selector_kind: Mapping[str, RuntimeRelationEndpointPolicy] | None = None


@dataclass(frozen=True, slots=True)
class _RelationSemantics:
    relation_type: str
    assertion_kind: str
    semantic_family: str
    presence_status: str


def classify_relations(
    db: SurrealSession,
    active_substances: set[str],
    runtime: RuntimeProgram,
) -> dict[str, list[dict[str, object]]]:
    by_status: dict[str, list[dict[str, object]]] = {status: [] for status in runtime.relation_review_status_order}
    context = _RelationReviewContext(
        runtime.relation_warning_rules,
        runtime.relation_review_statuses_by_status,
        runtime.relation_presence_statuses_by_status,
        runtime.relation_presence_statuses_by_active_side,
        runtime.relation_endpoint_policies_by_selector_kind,
    )
    rows = db.query(_relation_status_projection(runtime), {"active": list(active_substances)})
    for row in rows:
        relation_type = _row_str(row, "type")
        presence_status = _row_str(row, "status")
        status = _semantic_review_status(
            relation_type,
            _row_str(row, "assertion_kind"),
            _row_str(row, "semantic_family"),
            presence_status,
            context,
        )
        by_status[status].append({
            "type": relation_type,
            "source": _row_str(row, "source"),
            "target": _row_str(row, "target"),
            "reason": _row_str(row, "reason"),
            "presence": _presence_description(presence_status, context.presence_by_status),
            "source_matches": _active_match_names(
                row,
                substance_ids_key="src_substances",
                names_key="src_member_names",
                active_substances=active_substances,
            ),
            "target_matches": _active_match_names(
                row,
                substance_ids_key="tgt_substances",
                names_key="tgt_member_names",
                active_substances=active_substances,
            ),
            "show_matches": _show_match_details(row, context.endpoint_policies_by_selector_kind),
        })
    return by_status


def _semantic_review_status(
    relation_type: str,
    assertion_kind: str,
    semantic_family: str,
    presence_status: str,
    context: _RelationReviewContext,
) -> str:
    semantics = _RelationSemantics(relation_type, assertion_kind, semantic_family, presence_status)
    presence = _declared_presence_status(presence_status, context.presence_by_status)
    if presence.active_side == "none":
        return _declared_review_status(presence.default_review_status, context.review_statuses)
    for rule in context.warning_rules:
        if _relation_rule_matches(rule, semantics, context):
            return _declared_review_status(rule.review_status, context.review_statuses)
    return _declared_review_status(presence.default_review_status, context.review_statuses)


def _declared_review_status(status: str, relation_review_statuses: Mapping[str, object] | None) -> str:
    if relation_review_statuses is not None and status not in relation_review_statuses:
        raise ValueError(f"ontology relation_review_statuses does not declare {status!r}")
    return status


def _declared_presence_status(
    status: str, relation_presence_statuses: Mapping[str, RuntimeRelationPresenceStatusPolicy] | None
) -> RuntimeRelationPresenceStatusPolicy:
    if relation_presence_statuses is None:
        raise ValueError("ontology relation_presence_statuses are required")
    try:
        return relation_presence_statuses[status]
    except KeyError as error:
        raise ValueError(f"ontology relation_presence_statuses does not declare {status!r}") from error


def _relation_rule_matches(
    rule: RuntimeRelationWarningRule,
    semantics: _RelationSemantics,
    context: _RelationReviewContext,
) -> bool:
    if rule.relation_kind != semantics.relation_type:
        return False
    field_value = _rule_filter_field_value(rule, semantics.assertion_kind, semantics.semantic_family)
    return field_value == rule.filter_value and _presence_matches_rule(
        semantics.presence_status,
        rule.active_side,
        context.presence_by_active_side,
    )


def _rule_filter_field_value(rule: RuntimeRelationWarningRule, assertion_kind: str, semantic_family: str) -> str:
    return ontology_assertion_filter_value(
        rule.filter_field,
        assertion_kind=assertion_kind,
        semantic_family=semantic_family,
    )


def _presence_matches_rule(
    presence_status: str,
    active_side: str,
    relation_presence_by_active_side: Mapping[str, RuntimeRelationPresenceStatusPolicy] | None,
) -> bool:
    if relation_presence_by_active_side is None:
        raise ValueError("ontology relation_presence_statuses are required")
    expected = relation_presence_policy_for_active_side(active_side, relation_presence_by_active_side)
    return presence_status == expected.status


def _presence_description(
    presence_status: str, relation_presence_statuses: Mapping[str, RuntimeRelationPresenceStatusPolicy] | None
) -> str:
    return _declared_presence_status(presence_status, relation_presence_statuses).description


def _active_match_names(
    row: dict[str, object],
    *,
    substance_ids_key: str,
    names_key: str,
    active_substances: set[str],
) -> list[str]:
    substance_ids = _string_list(row.get(substance_ids_key))
    names = _string_list(row.get(names_key))
    out: list[str] = []
    for index, substance_id in enumerate(substance_ids):
        if substance_id not in active_substances:
            continue
        if index < len(names):
            out.append(names[index])
        else:
            out.append(substance_id)
    return out


def _show_match_details(
    row: dict[str, object],
    endpoint_policies_by_selector_kind: Mapping[str, RuntimeRelationEndpointPolicy] | None,
) -> bool:
    if endpoint_policies_by_selector_kind is None:
        raise ValueError("ontology relation_endpoint_policies are required")
    return (
        _endpoint_policy(row.get("src_selector"), endpoint_policies_by_selector_kind).show_match_details
        or _endpoint_policy(row.get("tgt_selector"), endpoint_policies_by_selector_kind).show_match_details
    )


def _endpoint_policy(
    selector: object,
    endpoint_policies_by_selector_kind: Mapping[str, RuntimeRelationEndpointPolicy],
) -> RuntimeRelationEndpointPolicy:
    selector_kind = relation_endpoint_selector_kind(selector)
    try:
        return endpoint_policies_by_selector_kind[selector_kind]
    except KeyError as error:
        raise ValueError(f"ontology relation_endpoint_policies does not declare {selector_kind!r}") from error


def _string_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, str)]


def _row_str(row: dict[str, object], key: str) -> str:
    value = row.get(key)
    return value if isinstance(value, str) else ""


def _relation_status_projection(runtime: RuntimeProgram) -> str:
    source_and_target_status = _surreal_string_literal(
        _presence_status_for(runtime, source_active=True, target_active=True)
    )
    source_only_status = _surreal_string_literal(_presence_status_for(runtime, source_active=True, target_active=False))
    target_only_status = _surreal_string_literal(_presence_status_for(runtime, source_active=False, target_active=True))
    neither_endpoint_status = _surreal_string_literal(
        _presence_status_for(runtime, source_active=False, target_active=False)
    )
    return (
        "SELECT type, assertion_kind, semantic_family, src_display AS source, tgt_display AS target, reason, "
        "  src_substances, tgt_substances, src_member_names, tgt_member_names, "
        "  src_selector, tgt_selector, "
        "  IF src_substances ANYINSIDE $active AND tgt_substances ANYINSIDE $active "
        f"    THEN {source_and_target_status} "
        "  ELSE IF src_substances ANYINSIDE $active "
        f"    THEN {source_only_status} "
        "  ELSE IF tgt_substances ANYINSIDE $active "
        f"    THEN {target_only_status} "
        f"  ELSE {neither_endpoint_status} "
        "  END AS status "
        "FROM ontology_assertion"
    )


def _presence_status_for(runtime: RuntimeProgram, *, source_active: bool, target_active: bool) -> str:
    for row in runtime.relation_presence_statuses:
        if row.source_active is source_active and row.target_active is target_active:
            return row.status
    raise ValueError(
        "ontology relation_presence_statuses does not cover "
        f"source_active={source_active!r}/target_active={target_active!r}"
    )


def _surreal_string_literal(value: str) -> str:
    return "'" + value.replace("\\", "\\\\").replace("'", "\\'") + "'"
