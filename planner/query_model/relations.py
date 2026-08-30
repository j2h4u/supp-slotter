"""Relation classification queries for the planner read model."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from planner.contracts import OntologyAssertion, RelationSelector, Substance
from planner.ontology.artifacts import OntologyBundle
from planner.ontology.glue_capabilities import ONTOLOGY_COMPOSITE_KEY_SEPARATOR
from planner.ontology.presentation import authored_term_label
from planner.ontology.runtime_program import (
    RuntimeProgram,
    RuntimeSelectorFormCapability,
)
from planner.ontology.selector import resolve_selector, selector_capability_form
from planner.query_model.data import RelationEndpoint, RelationQuery
from planner.query_model.types import RelationReviewRow


@dataclass(frozen=True, slots=True)
class _RelationReviewContext:
    endpoint_policies_by_selector_form: Mapping[str, RuntimeSelectorFormCapability] | None = None


def resolve_relation_queries(
    assertions: tuple[OntologyAssertion, ...],
    substances: dict[str, Substance],
    ontology_bundle: OntologyBundle,
) -> tuple[RelationQuery, ...]:
    """Resolve canonical review assertions into their typed query inputs."""
    return tuple(
        RelationQuery(
            relation_type=assertion.relation_type,
            source=_relation_endpoint(assertion.id, "source", assertion.source_selector, substances, ontology_bundle),
            target=_relation_endpoint(assertion.id, "target", assertion.target_selector, substances, ontology_bundle),
            reason=assertion.reason,
            research_state=assertion.research_state,
            sources=assertion.sources,
        )
        for assertion in assertions
    )


def classify_relations(
    assertions: tuple[RelationQuery, ...],
    active_substances: set[str],
    runtime: RuntimeProgram,
) -> list[RelationReviewRow]:
    context = _RelationReviewContext(
        runtime.selector_form_capabilities_by_form,
    )
    rows: list[RelationReviewRow] = []
    for assertion in assertions:
        source_matches = _active_match_names(assertion.source, active_substances)
        target_matches = _active_match_names(assertion.target, active_substances)
        if not source_matches and not target_matches:
            continue
        review_row: RelationReviewRow = {
            "type": assertion.relation_type,
            "source": assertion.source.display,
            "target": assertion.target.display,
            "reason": assertion.reason,
            "research_state": assertion.research_state,
            "sources": list(assertion.sources),
            "source_matches": source_matches,
            "target_matches": target_matches,
            "show_matches": _show_match_details(assertion, context.endpoint_policies_by_selector_form),
        }
        rows.append(review_row)
    return rows


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
