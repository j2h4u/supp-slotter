"""Typed relation-warning queries for the planner review."""

from __future__ import annotations

from collections.abc import Mapping
from typing import NotRequired, TypedDict

from planner.ontology.glue_capabilities import ontology_assertion_filter_value
from planner.ontology.runtime_program import (
    RuntimeProgram,
    RuntimeRelationPresenceStatusPolicy,
    RuntimeRelationWarningRule,
    relation_presence_policy_for_active_side,
)
from planner.query_model.data import RelationEndpoint, RelationQuery


class RelationWarningRow(TypedDict):
    type: str
    relation: str
    source_substance: str
    source_name: str
    target_substance: str
    target_name: str
    reason: str
    action: str
    severity: NotRequired[str | int]


def collect_relation_warnings(
    assertions: tuple[RelationQuery, ...],
    active_substances: set[str],
    runtime: RuntimeProgram,
) -> list[RelationWarningRow]:
    """Collect every relation warning declared by the ontology runtime policy."""
    pairs = sorted({(row.relation_kind, row.warning_type) for row in runtime.relation_warning_rules})
    warnings: list[RelationWarningRow] = []
    for relation_type, warning_type in pairs:
        warnings.extend(
            _collect_relation_warning_rules(assertions, active_substances, runtime, relation_type, warning_type)
        )
    return warnings


def _collect_relation_warning_rules(
    assertions: tuple[RelationQuery, ...],
    active_substances: set[str],
    runtime: RuntimeProgram,
    relation_type: str,
    warning_type: str,
) -> list[RelationWarningRow]:
    rules = [
        row
        for row in runtime.relation_warning_rules
        if row.relation_kind == relation_type and row.warning_type == warning_type
    ]
    if not rules:
        raise ValueError(f"ontology relation_warning_rules does not declare {relation_type!r}/{warning_type!r}")
    return _collect_relation_warnings(
        assertions,
        relation_type=relation_type,
        warning_type=warning_type,
        rules=[
            _rule_matcher(rule, active_substances, runtime.relation_presence_statuses_by_active_side) for rule in rules
        ],
    )


def _rule_matcher(
    rule: RuntimeRelationWarningRule,
    active_substances: set[str],
    relation_presence_by_active_side: Mapping[str, RuntimeRelationPresenceStatusPolicy],
) -> tuple[RuntimeRelationWarningRule, set[str], bool, bool]:
    presence = relation_presence_policy_for_active_side(rule.active_side, relation_presence_by_active_side)
    return rule, active_substances, presence.source_active, presence.target_active


def _collect_relation_warnings(
    assertions: tuple[RelationQuery, ...],
    *,
    relation_type: str,
    warning_type: str,
    rules: list[tuple[RuntimeRelationWarningRule, set[str], bool, bool]],
) -> list[RelationWarningRow]:
    rows: list[tuple[RelationEndpoint, RelationEndpoint, RelationQuery]] = []
    for rule, active, source_active, target_active in rules:
        for assertion in assertions:
            source_matches = bool(set(assertion.source.substance_ids) & active)
            target_matches = bool(set(assertion.target.substance_ids) & active)
            if (
                assertion.relation_type == rule.relation_kind
                and ontology_assertion_filter_value(
                    rule.filter_field,
                    assertion_kind=assertion.assertion_kind,
                    semantic_family=assertion.semantic_family,
                )
                == rule.filter_value
                and source_matches is source_active
                and target_matches is target_active
            ):
                source, target = (
                    (assertion.target, assertion.source)
                    if rule.reverse_output
                    else (
                        assertion.source,
                        assertion.target,
                    )
                )
                rows.append((source, target, assertion))

    seen: set[tuple[str, str, str]] = set()
    warnings: list[RelationWarningRow] = []
    for source, target, assertion in rows:
        key = (source.key, relation_type, target.key)
        if key in seen:
            continue
        seen.add(key)
        warnings.append(_warning_from_relation(source, target, assertion, warning_type, relation_type))
    return warnings


def _warning_from_relation(
    source: RelationEndpoint,
    target: RelationEndpoint,
    assertion: RelationQuery,
    warning_type: str,
    relation_type: str,
) -> RelationWarningRow:
    out: RelationWarningRow = {
        "type": warning_type,
        "relation": relation_type,
        "source_substance": source.key,
        "source_name": source.display,
        "target_substance": target.key,
        "target_name": target.display,
        "reason": assertion.reason,
        "action": assertion.action or "",
    }
    if assertion.severity is not None:
        out["severity"] = assertion.severity
    return out
