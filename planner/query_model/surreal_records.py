"""Canonical ontology projections for the in-memory SurrealDB read model."""

from __future__ import annotations

from collections.abc import Mapping
from typing import cast

from planner.cards.product import format_product_name
from planner.cards.substance import format_substance_name
from planner.contracts import (
    Dashboard,
    OntologyAssertion,
    Product,
    Relation,
    RelationSelector,
    ScheduleGovernance,
    SchedulingConstraint,
    Substance,
)
from planner.ontology.artifacts import OntologyBundle
from planner.ontology.runtime_program import RuntimeProgram
from planner.ontology.substance_fields import knowledge_category_fields, schedule_assignment_fields
from planner.scheduling_constraint_execution import SchedulingConstraintExecutionPlan


def substance_record(substance_id: str, substance: Substance, ontology_bundle: OntologyBundle) -> dict[str, object]:
    knowledge = _knowledge_values(substance, ontology_bundle)
    return {
        "id": substance_id,
        "name": substance.name,
        **_schedule_values(substance, ontology_bundle),
        "schedule_governance": _governance_record(substance.schedule_governance),
        "knowledge": knowledge,
        **knowledge,
        "term_refs": _substance_term_refs(substance, ontology_bundle),
        "prefer_with": list(substance.prefer_with),
        **({"form": substance.form} if substance.form is not None else {}),
    }


def relation_record(
    relation: Relation,
    substances: dict[str, Substance],
    ontology_bundle: OntologyBundle,
) -> dict[str, object]:
    runtime_program = ontology_bundle.runtime_program
    src_ids = _resolve_selector_ids(relation.source_selector, substances, ontology_bundle)
    tgt_ids = _resolve_selector_ids(relation.target_selector, substances, ontology_bundle)
    return {
        "id": relation.id,
        "type": relation.type,
        "src_substances": src_ids,
        "tgt_substances": tgt_ids,
        "src_member_names": _endpoint_member_names(src_ids, substances),
        "tgt_member_names": _endpoint_member_names(tgt_ids, substances),
        "src_selector": _selector_record(relation.source_selector, runtime_program),
        "tgt_selector": _selector_record(relation.target_selector, runtime_program),
        "src_key": _selector_key(relation.source_selector),
        "tgt_key": _selector_key(relation.target_selector),
        "src_display": _selector_display(relation.source_selector, substances),
        "tgt_display": _selector_display(relation.target_selector, substances),
        "reason": relation.reason,
        "action": relation.action or "",
        **({"severity": relation.severity} if relation.severity is not None else {}),
    }


def ontology_assertion_record(
    assertion: OntologyAssertion,
    substances: dict[str, Substance],
    ontology_bundle: OntologyBundle,
) -> dict[str, object]:
    runtime_program = ontology_bundle.runtime_program
    src_ids = _resolve_selector_ids(assertion.source_selector, substances, ontology_bundle)
    tgt_ids = _resolve_selector_ids(assertion.target_selector, substances, ontology_bundle)
    return {
        "id": assertion.id,
        "type": assertion.relation_type,
        "assertion_kind": assertion.assertion_kind,
        "semantic_family": assertion.semantic_family,
        "src_substances": src_ids,
        "tgt_substances": tgt_ids,
        "src_member_names": _endpoint_member_names(src_ids, substances),
        "tgt_member_names": _endpoint_member_names(tgt_ids, substances),
        "src_selector": _selector_record(assertion.source_selector, runtime_program),
        "tgt_selector": _selector_record(assertion.target_selector, runtime_program),
        "src_key": _selector_key(assertion.source_selector),
        "tgt_key": _selector_key(assertion.target_selector),
        "src_display": _selector_display(assertion.source_selector, substances),
        "tgt_display": _selector_display(assertion.target_selector, substances),
        "reason": assertion.reason,
        "action": assertion.action or "",
        **({"severity": assertion.severity} if assertion.severity is not None else {}),
    }


def scheduling_constraint_record(
    constraint: SchedulingConstraint,
    substances: dict[str, Substance],
    ontology_bundle: OntologyBundle,
) -> dict[str, object]:
    # Keep endpoint resolution deterministic while retaining the authored
    # selectors and every governance field below for audit/read-model queries.
    runtime_program = ontology_bundle.runtime_program
    src_ids = sorted(_resolve_selector_ids(constraint.source_selector, substances, ontology_bundle))
    tgt_ids = sorted(_resolve_selector_ids(constraint.target_selector, substances, ontology_bundle))
    return {
        "id": constraint.id,
        "operation": constraint.operation,
        "enforcement": constraint.enforcement,
        "src_substances": src_ids,
        "tgt_substances": tgt_ids,
        "src_selector": _selector_record(constraint.source_selector, runtime_program),
        "tgt_selector": _selector_record(constraint.target_selector, runtime_program),
        "action": constraint.action or "",
        "rationale": constraint.rationale or "",
        "semantic_note": constraint.semantic_note or "",
        "status": constraint.status or "",
        "evidence": list(constraint.evidence),
        "owner": constraint.owner or "",
        "review_by": constraint.review_by or "",
        "assertion_type": constraint.assertion_type or "",
    }


def scheduling_constraint_execution_plan_record(
    plan: SchedulingConstraintExecutionPlan,
) -> dict[str, object]:
    """Serialize the compiled behavioral instruction, without re-evaluating governance."""
    return {
        "id": plan.id,
        "source_substances": list(plan.source_substance_ids),
        "target_substances": list(plan.target_substance_ids),
        "operation": plan.operation,
        "enforcement_mode": plan.enforcement_mode,
        "effect_role": plan.effect_role,
        "executable": plan.executable,
        "blocks_slots": plan.blocks_slots,
        "scores_advisory": plan.scores_advisory,
        "score_delta": plan.score_delta,
        "match_direction": plan.match_direction,
        "aggregation": plan.aggregation,
        "selector_resolution": plan.selector_resolution,
        "selector_resolution_outcome": plan.selector_resolution_outcome,
        "action": plan.action or "",
        "status": plan.status or "",
        "evidence": list(plan.evidence),
        "rationale": plan.rationale or "",
        "semantic_note": plan.semantic_note or "",
        "owner": plan.owner or "",
        "review_by": plan.review_by or "",
        "assertion_type": plan.assertion_type or "",
    }


def product_record(product_id: str, product: Product, ontology_bundle: OntologyBundle) -> dict[str, object]:
    return {
        "id": product_id,
        "name": product.name,
        "display_name": format_product_name(product),
        "components": [c.substance for c in product.components],
        **_schedule_values(product, ontology_bundle),
        "schedule_governance": _governance_record(product.schedule_governance),
    }


def dashboard_record(slug: str, dashboard: Dashboard) -> dict[str, object]:
    return {
        "slug": slug,
        "name": dashboard.name,
        "from_terms": [
            f"{selector.category}:{selector.term}"
            for selector in dashboard.selectors
            if selector.category is not None and selector.term is not None
        ],
    }


def _selector_record(selector: RelationSelector, runtime_program: RuntimeProgram) -> dict[str, object]:
    if selector.entity_id is not None or selector.entity_name is not None:
        return {
            "kind": runtime_program.concrete_relation_endpoint_selector_kind,
            "id": selector.entity_id,
            "name": selector.entity_name,
        }
    return {
        "kind": runtime_program.term_relation_endpoint_selector_kind,
        "category": selector.category,
        "term": selector.term,
    }


def _selector_key(selector: RelationSelector) -> str:
    return selector.entity_id or selector.entity_name or f"{selector.category}:{selector.term}"


def _selector_display(selector: RelationSelector, substances: dict[str, Substance]) -> str:
    if selector.entity_name is not None:
        return selector.entity_name
    if selector.entity_id is not None:
        substance = substances.get(selector.entity_id)
        return format_substance_name(substance) if substance is not None else selector.entity_id
    return f"{selector.category}:{selector.term}"


def _resolve_selector_ids(
    selector: RelationSelector,
    substances: dict[str, Substance],
    ontology_bundle: OntologyBundle,
) -> list[str]:
    if selector.entity_id is not None:
        return [selector.entity_id] if selector.entity_id in substances else []
    if selector.entity_name is not None:
        return [sid for sid, substance in substances.items() if substance.name == selector.entity_name]
    if selector.category is not None and selector.term is not None:
        return [
            sid
            for sid, substance in substances.items()
            if selector.term in _terms_for_category(substance, selector.category, ontology_bundle)
        ]
    return []


def _terms_for_category(substance: Substance, category: str, ontology_bundle: OntologyBundle) -> tuple[str, ...]:
    categories = ontology_bundle.runtime_vocabulary.get("categories")
    if not isinstance(categories, dict):
        return ()
    typed_categories = cast(dict[str, object], categories)
    raw_metadata = typed_categories.get(category)
    if not isinstance(raw_metadata, dict):
        return ()
    metadata = cast(dict[str, object], raw_metadata)
    fields = _allowed_predicate_fields(metadata.get("allowed_predicates"))
    if fields is None:
        return ()
    terms: list[str] = []
    for field in fields:
        values = getattr(substance, field, None)
        if not isinstance(values, tuple):
            return ()
        terms.extend(cast(tuple[str, ...], values))
    return tuple(dict.fromkeys(terms))


def _allowed_predicate_fields(raw_predicates: object) -> tuple[str, ...] | None:
    if not isinstance(raw_predicates, list):
        return None
    fields: list[str] = []
    for predicate in raw_predicates:
        if not isinstance(predicate, str):
            return None
        namespace, separator, field = predicate.partition(".")
        if not namespace or separator != "." or not field or "." in field:
            return None
        fields.append(field)
    return tuple(dict.fromkeys(fields))


def _endpoint_member_names(ids: list[str], substances: dict[str, Substance]) -> list[str]:
    return [format_substance_name(substances[sid]) for sid in ids if sid in substances]


def _substance_term_refs(substance: Substance, ontology_bundle: OntologyBundle) -> list[str]:
    refs: list[str] = []
    for category, values in _term_ref_values(substance, ontology_bundle):
        refs.extend(f"{category}:{term}" for term in values)
    return refs


def _schedule_values(card: Substance | Product, ontology_bundle: OntologyBundle) -> dict[str, list[str]]:
    return {
        field: list(cast(tuple[str, ...], getattr(card, field, ())))
        for field in schedule_assignment_fields(ontology_bundle)
    }


def _knowledge_values(substance: Substance, ontology_bundle: OntologyBundle) -> dict[str, list[str]]:
    return {
        field: list(cast(tuple[str, ...], getattr(substance, field, ())))
        for field in knowledge_category_fields(ontology_bundle)
    }


def _term_ref_values(substance: Substance, ontology_bundle: OntologyBundle) -> tuple[tuple[str, tuple[str, ...]], ...]:
    values: list[tuple[str, tuple[str, ...]]] = []
    values.extend(
        ("schedule_rule", cast(tuple[str, ...], getattr(substance, field, ())))
        for field in schedule_assignment_fields(ontology_bundle)
    )
    values.extend(
        (field, cast(tuple[str, ...], getattr(substance, field, ())))
        for field in knowledge_category_fields(ontology_bundle)
    )
    return tuple(values)


def _governance_record(value: Mapping[str, ScheduleGovernance]) -> dict[str, object]:
    """Return a stable, plain read-model projection of card governance."""
    result: dict[str, object] = {}
    for key in sorted(value):
        governance = value[key]
        normalized: dict[str, object] = {
            "status": governance.status,
            "enforcement_cap": governance.enforcement_cap,
            "scope": dict(sorted(governance.scope)),
            "evidence": [
                {
                    "source": evidence.source,
                    "supports": evidence.supports,
                    "limitations": evidence.limitations,
                }
                for evidence in governance.evidence
            ],
            "owner": governance.owner,
            "review_by": governance.review_by,
        }
        if governance.evidence_gap is not None:
            normalized["evidence_gap"] = governance.evidence_gap
        if governance.retirement_reason is not None:
            normalized["retirement_reason"] = governance.retirement_reason
        result[key] = normalized
    return result
