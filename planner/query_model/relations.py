"""Relation classification queries for the planner read model."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from planner.contracts import OntologyAssertion, RelationSelector, Substance
from planner.ontology.artifacts import OntologyBundle
from planner.ontology.glue_capabilities import ONTOLOGY_COMPOSITE_KEY_SEPARATOR, ontology_assertion_filter_value
from planner.ontology.runtime_program import (
    RuntimeProgram,
    RuntimeRelationPresenceStatusPolicy,
    RuntimeRelationWarningRule,
    RuntimeSelectorFormCapability,
    relation_presence_policy_for_active_side,
)
from planner.ontology.selector import resolve_selector, selector_capability_form
from planner.ontology.warning_policy import authored_term_label
from planner.query_model.data import RelationEndpoint, RelationQuery
from planner.query_model.types import RelationReviewRow


@dataclass(frozen=True, slots=True)
class _RelationReviewContext:
    warning_rules: tuple[RuntimeRelationWarningRule, ...]
    presence_by_status: Mapping[str, RuntimeRelationPresenceStatusPolicy] | None = None
    presence_by_active_side: Mapping[str, RuntimeRelationPresenceStatusPolicy] | None = None
    endpoint_policies_by_selector_form: Mapping[str, RuntimeSelectorFormCapability] | None = None


@dataclass(frozen=True, slots=True)
class _RelationSemantics:
    relation_type: str
    assertion_kind: str
    semantic_family: str
    presence_status: str


def resolve_relation_queries(
    assertions: tuple[OntologyAssertion, ...],
    substances: dict[str, Substance],
    ontology_bundle: OntologyBundle,
) -> tuple[RelationQuery, ...]:
    """Resolve canonical review assertions into their typed query inputs."""
    return tuple(
        RelationQuery(
            relation_type=assertion.relation_type,
            assertion_kind=assertion.assertion_kind,
            semantic_family=assertion.semantic_family,
            source=_relation_endpoint(assertion.id, "source", assertion.source_selector, substances, ontology_bundle),
            target=_relation_endpoint(assertion.id, "target", assertion.target_selector, substances, ontology_bundle),
            reason=assertion.reason,
            action=assertion.action,
            severity=assertion.severity,
        )
        for assertion in assertions
    )


def classify_relations(
    assertions: tuple[RelationQuery, ...],
    active_substances: set[str],
    runtime: RuntimeProgram,
) -> dict[str, list[RelationReviewRow]]:
    by_status: dict[str, list[RelationReviewRow]] = {
        status: [] for status in (row.status for row in runtime.relation_presence_statuses)
    }
    context = _RelationReviewContext(
        runtime.relation_warning_rules,
        runtime.relation_presence_statuses_by_status,
        runtime.relation_presence_statuses_by_active_side,
        runtime.selector_form_capabilities_by_form,
    )
    for assertion in assertions:
        presence_status = _presence_status_for(
            runtime,
            source_active=bool(set(assertion.source.substance_ids) & active_substances),
            target_active=bool(set(assertion.target.substance_ids) & active_substances),
        )
        warning_type = _warning_type_for_relation(
            assertion.relation_type,
            assertion.assertion_kind,
            assertion.semantic_family,
            presence_status,
            context,
        )
        review_row: RelationReviewRow = {
            "type": assertion.relation_type,
            "source": assertion.source.display,
            "target": assertion.target.display,
            "reason": assertion.reason,
            "presence": _presence_description(presence_status, context.presence_by_status),
            "warning_type": warning_type,
            "source_matches": _active_match_names(assertion.source, active_substances),
            "target_matches": _active_match_names(assertion.target, active_substances),
            "show_matches": _show_match_details(assertion, context.endpoint_policies_by_selector_form),
        }
        if assertion.action is not None:
            review_row["action"] = assertion.action
        if assertion.severity is not None:
            review_row["severity"] = assertion.severity
        by_status[presence_status].append(review_row)
    return by_status


def _warning_type_for_relation(
    relation_type: str,
    assertion_kind: str,
    semantic_family: str,
    presence_status: str,
    context: _RelationReviewContext,
) -> str | None:
    semantics = _RelationSemantics(relation_type, assertion_kind, semantic_family, presence_status)
    for rule in context.warning_rules:
        if _relation_rule_matches(rule, semantics, context):
            return rule.warning_type
    return None


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


def _active_match_names(endpoint: RelationEndpoint, active_substances: set[str]) -> list[str]:
    out: list[str] = []
    for index, substance_id in enumerate(endpoint.substance_ids):
        if substance_id not in active_substances:
            continue
        if index < len(endpoint.member_names):
            out.append(endpoint.member_names[index])
        else:
            out.append(substance_id)
    return out


def _show_match_details(
    assertion: RelationQuery,
    endpoint_policies_by_selector_form: Mapping[str, RuntimeSelectorFormCapability] | None,
) -> bool:
    if endpoint_policies_by_selector_form is None:
        raise ValueError("ontology selector_form_capabilities are required")
    return (
        _endpoint_policy(assertion.source.selector_form, endpoint_policies_by_selector_form).show_match_details
        or _endpoint_policy(assertion.target.selector_form, endpoint_policies_by_selector_form).show_match_details
    )


def _endpoint_policy(
    selector_form: str,
    endpoint_policies_by_selector_form: Mapping[str, RuntimeSelectorFormCapability],
) -> RuntimeSelectorFormCapability:
    try:
        return endpoint_policies_by_selector_form[selector_form]
    except KeyError as error:
        raise ValueError(f"ontology selector_form_capabilities does not declare {selector_form!r}") from error


def _relation_endpoint(
    assertion_id: str,
    side: str,
    selector: RelationSelector,
    substances: dict[str, Substance],
    ontology_bundle: OntologyBundle,
) -> RelationEndpoint:
    resolution = resolve_selector(selector, substances, ontology_bundle)
    if resolution.outcome not in {"resolved", "empty"}:
        raise ValueError(f"relation assertion {assertion_id!r} has unresolved {side} endpoint: {resolution.outcome}")
    substance_ids = resolution.substance_ids
    return RelationEndpoint(
        key=_selector_key(selector),
        display=_selector_display(selector, substances, ontology_bundle),
        substance_ids=substance_ids,
        member_names=tuple(_format_substance_name(substances[item]) for item in substance_ids),
        selector_form=selector_capability_form(selector),
    )


def _selector_key(selector: RelationSelector) -> str:
    if selector.entity_id is not None:
        return selector.entity_id
    if selector.entity_name is not None:
        return selector.entity_name
    if selector.category is not None and selector.term is not None:
        return f"{selector.category}{ONTOLOGY_COMPOSITE_KEY_SEPARATOR}{selector.term}"
    raise ValueError("relation selector has no endpoint identity")


def _selector_display(
    selector: RelationSelector,
    substances: dict[str, Substance],
    ontology_bundle: OntologyBundle,
) -> str:
    if selector.entity_name is not None:
        return selector.entity_name
    if selector.entity_id is not None:
        return _format_substance_name(substances[selector.entity_id])
    if selector.category is None or selector.term is None:
        raise ValueError("relation selector has no displayable authored endpoint")
    return authored_term_label(
        f"{selector.category}{ONTOLOGY_COMPOSITE_KEY_SEPARATOR}{selector.term}",
        ontology_bundle,
    )


def _format_substance_name(substance: Substance) -> str:
    name = substance.name or substance.id or "unknown"
    return f"{name} ({substance.form})" if substance.form else name


def _presence_status_for(runtime: RuntimeProgram, *, source_active: bool, target_active: bool) -> str:
    for row in runtime.relation_presence_statuses:
        if row.source_active is source_active and row.target_active is target_active:
            return row.status
    raise ValueError(
        "ontology relation_presence_statuses does not cover "
        f"source_active={source_active!r}/target_active={target_active!r}"
    )
