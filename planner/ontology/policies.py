"""Ontology assertion loading and projection helpers."""

# pyright: reportUnknownArgumentType=false

from __future__ import annotations

from dataclasses import dataclass
from typing import cast

from planner.contracts import (
    CardLoadError,
    OntologyAssertion,
    Relation,
    RelationSelector,
    RelationType,
)
from planner.ontology.artifacts import OntologyBundle
from planner.ontology.errors import MALFORMED, OntologyInfrastructureError
from planner.ontology.schema_enums import schema_enum_values
from planner.ontology.selector import hydrate_selector
from planner.paths import ROOT


def _policy_error(bundle: OntologyBundle, message: str) -> OntologyInfrastructureError:
    """Report malformed generated policy data with its immutable source."""
    source = bundle.root / "generated" / "runtime-vocabulary.yaml"
    return OntologyInfrastructureError(f"{message} [source: {source}]", code=MALFORMED, path=source)


@dataclass(frozen=True, slots=True)
class _AssertionCatalog:
    relation_types: set[object]
    assertion_kinds: frozenset[str]
    semantic_families: frozenset[str]


def load_ontology_assertions(bundle: OntologyBundle) -> tuple[OntologyAssertion, ...]:
    """Load non-blocking semantic assertions from generated canonical vocabulary."""
    vocabulary = bundle.runtime_vocabulary
    raw_assertions = vocabulary.get("ontology_assertions")
    if not isinstance(raw_assertions, dict):
        raise _policy_error(bundle, "canonical runtime vocabulary has no ontology_assertions")
    raw_relation_types = vocabulary.get("relation_types")
    if not isinstance(raw_relation_types, dict) or not raw_relation_types:
        raise _policy_error(bundle, "canonical runtime vocabulary has no relation_types")
    catalog = _AssertionCatalog(
        set(raw_relation_types),
        frozenset(schema_enum_values(bundle, "RelationAssertionKind")),
        frozenset(schema_enum_values(bundle, "RelationSemanticFamily")),
    )
    assertions_mapping = cast(dict[str, object], raw_assertions)
    return tuple(
        _load_ontology_assertion(bundle, assertion_id, raw_value, catalog)
        for assertion_id, raw_value in assertions_mapping.items()
    )


def _load_ontology_assertion(
    bundle: OntologyBundle,
    assertion_id: str,
    raw_value: object,
    catalog: _AssertionCatalog,
) -> OntologyAssertion:
    raw = _object_mapping(raw_value)
    if not isinstance(assertion_id, str) or not assertion_id.strip() or raw is None:
        raise _policy_error(bundle, f"malformed ontology assertion {assertion_id!r}")
    source, target = _load_assertion_selectors(bundle, assertion_id, raw)
    relation_type, assertion_kind, semantic_family, reason = _assertion_semantics(bundle, assertion_id, raw, catalog)
    research_state, sources = _assertion_research_metadata(bundle, assertion_id, raw)
    return OntologyAssertion(
        id=assertion_id,
        relation_type=cast(RelationType, relation_type),
        assertion_kind=assertion_kind,
        semantic_family=semantic_family,
        reason=reason,
        source_selector=source,
        target_selector=target,
        research_state=research_state,
        sources=sources,
    )


def _load_assertion_selectors(
    bundle: OntologyBundle,
    assertion_id: str,
    raw: dict[str, object],
) -> tuple[RelationSelector, RelationSelector]:
    try:
        source = _assertion_selector(raw.get("source_selector"))
        target = _assertion_selector(raw.get("target_selector"))
    except CardLoadError as error:
        raise _policy_error(bundle, f"assertion {assertion_id!r}: {error}") from error
    if source is None or target is None:
        raise _policy_error(bundle, f"assertion {assertion_id!r} has invalid selector")
    return source, target


def _assertion_semantics(
    bundle: OntologyBundle,
    assertion_id: str,
    raw: dict[str, object],
    catalog: _AssertionCatalog,
) -> tuple[object, str, str, str]:
    relation_type = raw.get("relation_type")
    assertion_kind = raw.get("assertion_kind")
    semantic_family = raw.get("semantic_family")
    reason = raw.get("reason")
    if relation_type not in catalog.relation_types:
        raise _policy_error(bundle, f"assertion {assertion_id!r} has invalid relation_type")
    if (
        not isinstance(assertion_kind, str)
        or assertion_kind not in catalog.assertion_kinds
        or not isinstance(semantic_family, str)
        or semantic_family not in catalog.semantic_families
        or not isinstance(reason, str)
    ):
        raise _policy_error(bundle, f"assertion {assertion_id!r} has invalid semantics")
    return relation_type, assertion_kind, semantic_family, reason


def _assertion_research_metadata(
    bundle: OntologyBundle,
    assertion_id: str,
    raw: dict[str, object],
) -> tuple[str, tuple[str, ...]]:
    state = raw.get("research_state")
    sources = raw.get("sources")
    state_values = frozenset(schema_enum_values(bundle, "ResearchState"))
    if not isinstance(state, str) or state not in state_values:
        raise _policy_error(bundle, f"assertion {assertion_id!r} lacks a valid explicit research_state")
    if not isinstance(sources, list) or any(not isinstance(source, str) or not source.strip() for source in sources):
        raise _policy_error(bundle, f"assertion {assertion_id!r} lacks explicit sources")
    if state != "unassessed" and not sources:
        raise _policy_error(bundle, f"assertion {assertion_id!r} requires sources for research_state {state!r}")
    return state, tuple(cast(list[str], sources))


def project_ontology_assertions(
    relations: list[Relation],
    bundle: OntologyBundle,
) -> tuple[OntologyAssertion, ...]:
    """Project only relation assertions verified in the generated catalog."""
    _validate_relation_ids_before_projection(relations)
    generated_by_id = {assertion.id: assertion for assertion in load_ontology_assertions(bundle)}
    projected: list[OntologyAssertion] = []
    for relation in relations:
        generated = generated_by_id.get(relation.id)
        if generated is None:
            raise _policy_error(bundle, f"relation assertion {relation.id!r} is absent from the generated catalog")
        authored = OntologyAssertion(
            id=relation.id,
            relation_type=relation.type,
            assertion_kind=relation.assertion_kind or "",
            semantic_family=relation.semantic_family or "",
            reason=relation.reason,
            source_selector=relation.source_selector,
            target_selector=relation.target_selector,
            research_state=relation.research_state,
            sources=relation.sources,
        )
        if authored != generated:
            raise _policy_error(bundle, f"relation assertion {relation.id!r} diverges from the generated catalog")
        projected.append(generated)
    return tuple(projected)


def _validate_relation_ids_before_projection(relations: list[Relation]) -> None:
    """Reject malformed relation identities before read-model projection.

    YAML loaders normally enforce this through the generated relation schema's
    keyed uniqueness contract.  Keep the projection boundary fail-closed for
    callers that construct typed relations directly (fixtures and integrations)
    so duplicate IDs cannot become duplicate read-model assertions.
    """
    seen: dict[str, int] = {}
    for index, relation in enumerate(relations):
        identifier = relation.id
        if not isinstance(identifier, str) or not identifier.strip():
            raise ValueError(f"relations[{index}].id must be a non-empty string")
        previous = seen.get(identifier)
        if previous is not None:
            raise ValueError(
                f"relations[{index}].id duplicates {identifier!r}; previously declared at relations[{previous}].id"
            )
        seen[identifier] = index


def _assertion_selector(raw: object) -> RelationSelector:
    return hydrate_selector(raw, path=ROOT / "ontology", label="assertion", allow_entity_name=True)


def _object_mapping(value: object) -> dict[str, object] | None:
    return cast(dict[str, object], value) if isinstance(value, dict) else None
