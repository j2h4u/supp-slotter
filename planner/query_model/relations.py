"""Relation classification queries for the planner read model."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from planner.ontology.runtime_program import RuntimeProgram, RuntimeRelationWarningRule
from planner.query_model.session import SurrealSession

_RELATION_STATUS_PROJECTION = (
    "SELECT type, assertion_kind, semantic_family, src_display AS source, tgt_display AS target, reason, "
    "  src_substances, tgt_substances, src_member_names, tgt_member_names, "
    "  src_endpoint_kind, tgt_endpoint_kind, "
    "  IF src_substances ANYINSIDE $active AND tgt_substances ANYINSIDE $active "
    "    THEN 'both_active' "
    "  ELSE IF src_substances ANYINSIDE $active "
    "    THEN 'missing_target' "
    "  ELSE IF tgt_substances ANYINSIDE $active "
    "    THEN 'missing_source' "
    "  ELSE 'neither_active' "
    "  END AS status "
    "FROM ontology_assertion"
)


@dataclass(frozen=True, slots=True)
class _RelationReviewContext:
    warning_rules: tuple[RuntimeRelationWarningRule, ...]
    review_statuses: Mapping[str, object] | None = None


def classify_relations(
    db: SurrealSession,
    active_substances: set[str],
    runtime: RuntimeProgram,
) -> dict[str, list[dict[str, object]]]:
    by_status: dict[str, list[dict[str, object]]] = {status: [] for status in runtime.relation_review_status_order}
    context = _RelationReviewContext(runtime.relation_warning_rules, runtime.relation_review_statuses_by_status)
    rows = db.query(_RELATION_STATUS_PROJECTION, {"active": list(active_substances)})
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
            "presence": _presence_description(presence_status),
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
            "show_matches": _show_match_details(row),
        })
    return by_status


def _semantic_review_status(
    relation_type: str,
    assertion_kind: str,
    semantic_family: str,
    presence_status: str,
    context: _RelationReviewContext,
) -> str:
    if presence_status == "neither_active":
        return _declared_review_status("inactive", context.review_statuses)
    if any(
        _relation_rule_matches(rule, relation_type, assertion_kind, semantic_family, presence_status)
        for rule in context.warning_rules
    ):
        return _declared_review_status("actionable_now", context.review_statuses)
    if presence_status == "both_active":
        return _declared_review_status("active_pair_present", context.review_statuses)
    return _declared_review_status("latent_one_side_present", context.review_statuses)


def _declared_review_status(status: str, relation_review_statuses: Mapping[str, object] | None) -> str:
    if relation_review_statuses is not None and status not in relation_review_statuses:
        raise ValueError(f"ontology relation_review_statuses does not declare {status!r}")
    return status


def _relation_rule_matches(
    rule: RuntimeRelationWarningRule,
    relation_type: str,
    assertion_kind: str,
    semantic_family: str,
    presence_status: str,
) -> bool:
    if rule.relation_kind != relation_type:
        return False
    field_value = _rule_filter_field_value(rule, assertion_kind, semantic_family)
    return field_value == rule.filter_value and _presence_matches_rule(presence_status, rule.active_side)


def _rule_filter_field_value(rule: RuntimeRelationWarningRule, assertion_kind: str, semantic_family: str) -> str:
    if rule.filter_field == "assertion_kind":
        return assertion_kind
    if rule.filter_field == "semantic_family":
        return semantic_family
    raise ValueError(f"ontology relation_warning_rules has unsupported filter_field {rule.filter_field!r}")


def _presence_matches_rule(presence_status: str, active_side: str) -> bool:
    return (
        (active_side == "both" and presence_status == "both_active")
        or (active_side == "source" and presence_status == "missing_target")
        or (active_side == "target" and presence_status == "missing_source")
    )


def _presence_description(presence_status: str) -> str:
    if presence_status == "both_active":
        return "both endpoints active"
    if presence_status == "missing_source":
        return "target active, source absent"
    if presence_status == "missing_target":
        return "source active, target absent"
    return "both endpoints absent"


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


def _show_match_details(row: dict[str, object]) -> bool:
    broad_endpoint_kinds = {"trait"}
    return (
        str(row.get("src_endpoint_kind") or "") in broad_endpoint_kinds
        or str(row.get("tgt_endpoint_kind") or "") in broad_endpoint_kinds
    )


def _string_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, str)]


def _row_str(row: dict[str, object], key: str) -> str:
    value = row.get(key)
    return value if isinstance(value, str) else ""
