"""Canonical ontology projections for the in-memory SurrealDB read model."""

from __future__ import annotations

from planner.cards.product import format_product_name
from planner.cards.substance import format_substance_name
from planner.contracts import (
    Dashboard,
    OntologyAssertion,
    Product,
    Relation,
    RelationSelector,
    SchedulingConstraint,
    Substance,
)
from planner.ontology.artifacts import OntologyBundle
from planner.ontology.glue_capabilities import ONTOLOGY_COMPOSITE_KEY_SEPARATOR
from planner.ontology.runtime_program import RuntimeProgram
from planner.ontology.selector import resolve_selector, selector_capability_form
from planner.ontology.warning_policy import authored_term_label
from planner.scheduling_constraint_execution import SchedulingConstraintExecutionPlan


def substance_record(substance_id: str, substance: Substance, ontology_bundle: OntologyBundle) -> dict[str, object]:
    return {
        "id": substance_id,
        "name": substance.name,
        "knowledge_assertions": [
            {"knowledge_category": row.category, "knowledge_value": row.value} for row in substance.knowledge_assertions
        ],
        "schedule_assertions": [
            {"schedule_axis": row.axis, "schedule_value": row.value} for row in substance.schedule_assertions
        ],
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
    src_ids = list(resolve_selector(relation.source_selector, substances, ontology_bundle).substance_ids)
    tgt_ids = list(resolve_selector(relation.target_selector, substances, ontology_bundle).substance_ids)
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
        "src_display": _selector_display(relation.source_selector, substances, ontology_bundle),
        "tgt_display": _selector_display(relation.target_selector, substances, ontology_bundle),
        "reason": relation.reason,
        **({"action": relation.action} if relation.action is not None else {}),
        **({"severity": relation.severity} if relation.severity is not None else {}),
    }


def ontology_assertion_record(
    assertion: OntologyAssertion,
    substances: dict[str, Substance],
    ontology_bundle: OntologyBundle,
) -> dict[str, object]:
    runtime_program = ontology_bundle.runtime_program
    source_resolution = resolve_selector(assertion.source_selector, substances, ontology_bundle)
    target_resolution = resolve_selector(assertion.target_selector, substances, ontology_bundle)
    src_ids = list(source_resolution.substance_ids)
    tgt_ids = list(target_resolution.substance_ids)
    return {
        "id": assertion.id,
        "type": assertion.relation_type,
        "assertion_kind": assertion.assertion_kind,
        "semantic_family": assertion.semantic_family,
        "src_substances": src_ids,
        "tgt_substances": tgt_ids,
        "src_selector_resolution": source_resolution.outcome,
        "tgt_selector_resolution": target_resolution.outcome,
        "src_member_names": _endpoint_member_names(src_ids, substances),
        "tgt_member_names": _endpoint_member_names(tgt_ids, substances),
        "src_selector": _selector_record(assertion.source_selector, runtime_program),
        "tgt_selector": _selector_record(assertion.target_selector, runtime_program),
        "src_key": _selector_key(assertion.source_selector),
        "tgt_key": _selector_key(assertion.target_selector),
        "src_display": _selector_display(assertion.source_selector, substances, ontology_bundle),
        "tgt_display": _selector_display(assertion.target_selector, substances, ontology_bundle),
        "reason": assertion.reason,
        **({"action": assertion.action} if assertion.action is not None else {}),
        **({"severity": assertion.severity} if assertion.severity is not None else {}),
    }


def scheduling_constraint_record(
    constraint: SchedulingConstraint,
    substances: dict[str, Substance],
    ontology_bundle: OntologyBundle,
) -> dict[str, object]:
    # Keep endpoint resolution deterministic while retaining authored selectors.
    runtime_program = ontology_bundle.runtime_program
    src_ids = sorted(resolve_selector(constraint.source_selector, substances, ontology_bundle).substance_ids)
    tgt_ids = sorted(resolve_selector(constraint.target_selector, substances, ontology_bundle).substance_ids)
    return {
        "id": constraint.id,
        "operation": constraint.operation,
        "src_substances": src_ids,
        "tgt_substances": tgt_ids,
        "src_selector": _selector_record(constraint.source_selector, runtime_program),
        "tgt_selector": _selector_record(constraint.target_selector, runtime_program),
        "action": constraint.action or "",
        "rationale": constraint.rationale or "",
    }


def scheduling_constraint_execution_plan_record(
    plan: SchedulingConstraintExecutionPlan,
) -> dict[str, object]:
    """Serialize the compiled behavioral instruction."""
    return {
        "id": plan.id,
        "source_substances": list(plan.source_substance_ids),
        "target_substances": list(plan.target_substance_ids),
        "operation": plan.operation,
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
        "rationale": plan.rationale or "",
    }


def product_record(product_id: str, product: Product, ontology_bundle: OntologyBundle) -> dict[str, object]:
    return {
        "id": product_id,
        "name": product.name,
        "display_name": format_product_name(product),
        "components": [c.substance for c in product.components],
    }


def dashboard_record(
    dashboard: Dashboard,
    ontology_bundle: OntologyBundle | None = None,
) -> dict[str, object]:
    context_labels = (
        [authored_term_label(f"context:{term}", ontology_bundle) for term in dashboard.declares_context]
        if ontology_bundle is not None
        else []
    )
    record: dict[str, object] = {
        "id": dashboard.id,
        "name": dashboard.name,
        "from_terms": [
            f"{selector.category}{ONTOLOGY_COMPOSITE_KEY_SEPARATOR}{selector.term}"
            for selector in dashboard.selectors
            if selector.category is not None and selector.term is not None
        ],
        "declares_context": list(dashboard.declares_context),
        "declares_context_labels": context_labels,
    }
    if dashboard.source_path is not None:
        # Diagnostic provenance only; never use this value as a key or
        # selector.  In particular, renaming the file must not change id.
        record["source_path"] = str(dashboard.source_path)
    return record


def _selector_record(selector: RelationSelector, runtime_program: RuntimeProgram) -> dict[str, object]:
    form = selector_capability_form(selector)
    try:
        capability = runtime_program.selector_form_capabilities_by_form[form]
    except KeyError as error:
        raise ValueError(f"ontology selector_form_capabilities does not declare {form!r}") from error
    if form == "term":
        return {
            "form": form,
            "kind": capability.endpoint_kind,
            "category": selector.category,
            "term": selector.term,
        }
    return {
        "form": form,
        "kind": capability.endpoint_kind,
        "id": selector.entity_id,
        "name": selector.entity_name,
    }


def _selector_key(selector: RelationSelector) -> str:
    return (
        selector.entity_id
        or selector.entity_name
        or f"{selector.category}{ONTOLOGY_COMPOSITE_KEY_SEPARATOR}{selector.term}"
    )


def _selector_display(
    selector: RelationSelector,
    substances: dict[str, Substance],
    ontology_bundle: OntologyBundle,
) -> str:
    if selector.entity_name is not None:
        return selector.entity_name
    if selector.entity_id is not None:
        substance = substances.get(selector.entity_id)
        return format_substance_name(substance) if substance is not None else selector.entity_id
    if selector.category is None or selector.term is None:
        raise ValueError("relation selector has no displayable authored endpoint")
    return authored_term_label(
        f"{selector.category}{ONTOLOGY_COMPOSITE_KEY_SEPARATOR}{selector.term}",
        ontology_bundle,
    )


def _endpoint_member_names(ids: list[str], substances: dict[str, Substance]) -> list[str]:
    return [format_substance_name(substances[sid]) for sid in ids if sid in substances]


def _substance_term_refs(substance: Substance, ontology_bundle: OntologyBundle) -> list[str]:
    refs: list[str] = []
    for category, values in _term_ref_values(substance, ontology_bundle):
        refs.extend(f"{category}{ONTOLOGY_COMPOSITE_KEY_SEPARATOR}{term}" for term in values)
    return refs


def _term_ref_values(substance: Substance, ontology_bundle: OntologyBundle) -> tuple[tuple[str, tuple[str, ...]], ...]:
    del ontology_bundle
    values: list[tuple[str, tuple[str, ...]]] = []
    by_axis: dict[str, list[str]] = {}
    for assertion in substance.schedule_assertions:
        by_axis.setdefault(assertion.axis, []).append(assertion.value)
    values.extend((axis, tuple(items)) for axis, items in by_axis.items())
    by_category: dict[str, list[str]] = {}
    for assertion in substance.knowledge_assertions:
        by_category.setdefault(assertion.category, []).append(assertion.value)
    values.extend((category, tuple(items)) for category, items in by_category.items())
    return tuple((key, tuple(items)) for key, items in values)
