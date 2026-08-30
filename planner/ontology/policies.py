"""Ontology assertion loading and projection helpers."""

# pyright: reportUnknownArgumentType=false

from __future__ import annotations

from typing import cast

from planner.contracts import (
    CardLoadError,
    OntologyAssertion,
    Relation,
    RelationSelector,
    RelationType,
    Severity,
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


def load_ontology_assertions(bundle: OntologyBundle) -> tuple[OntologyAssertion, ...]:
    """Load non-blocking semantic assertions from generated canonical vocabulary."""
    vocabulary = bundle.runtime_vocabulary
    raw_assertions = vocabulary.get("ontology_assertions")
    if not isinstance(raw_assertions, dict):
        raise _policy_error(bundle, "canonical runtime vocabulary has no ontology_assertions")
    raw_relation_types = vocabulary.get("relation_types")
    if not isinstance(raw_relation_types, dict) or not raw_relation_types:
        raise _policy_error(bundle, "canonical runtime vocabulary has no relation_types")
    relation_types = set(raw_relation_types)
    severity_values = frozenset(schema_enum_values(bundle, "Severity"))
    assertions_mapping = cast(dict[str, object], raw_assertions)
    return tuple(
        _load_ontology_assertion(bundle, assertion_id, raw_value, relation_types, severity_values)
        for assertion_id, raw_value in assertions_mapping.items()
    )


def _load_ontology_assertion(
    bundle: OntologyBundle,
    assertion_id: str,
    raw_value: object,
    relation_types: set[object],
    severity_values: frozenset[str],
) -> OntologyAssertion:
    raw = _object_mapping(raw_value)
    if not isinstance(assertion_id, str) or not assertion_id.strip() or raw is None:
        raise _policy_error(bundle, f"malformed ontology assertion {assertion_id!r}")
    source, target = _load_assertion_selectors(bundle, assertion_id, raw)
    relation_type, assertion_kind, semantic_family, reason = _assertion_semantics(
        bundle, assertion_id, raw, relation_types
    )
    action, severity = _assertion_metadata(bundle, assertion_id, raw, severity_values)
    return OntologyAssertion(
        id=assertion_id,
        relation_type=cast(RelationType, relation_type),
        assertion_kind=assertion_kind,
        semantic_family=semantic_family,
        reason=reason,
        source_selector=source,
        target_selector=target,
        action=action,
        severity=cast(Severity | None, severity),
        research_state=cast(str, raw.get("research_state", "unassessed")),
        sources=tuple(item for item in cast(list[object], raw.get("sources", [])) if isinstance(item, str)),
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
    relation_types: set[object],
) -> tuple[object, str, str, str]:
    relation_type = raw.get("relation_type")
    assertion_kind = raw.get("assertion_kind")
    semantic_family = raw.get("semantic_family")
    reason = raw.get("reason")
    if relation_type not in relation_types:
        raise _policy_error(bundle, f"assertion {assertion_id!r} has invalid relation_type")
    if not isinstance(assertion_kind, str) or not isinstance(semantic_family, str) or not isinstance(reason, str):
        raise _policy_error(bundle, f"assertion {assertion_id!r} has invalid semantics")
    return relation_type, assertion_kind, semantic_family, reason


def _assertion_metadata(
    bundle: OntologyBundle,
    assertion_id: str,
    raw: dict[str, object],
    severity_values: frozenset[str],
) -> tuple[str | None, object]:
    action, severity = raw.get("action"), raw.get("severity")
    if action is not None and (not isinstance(action, str) or not action.strip()):
        raise _policy_error(bundle, f"assertion {assertion_id!r} has invalid action")
    if severity is not None and severity not in severity_values:
        raise _policy_error(bundle, f"assertion {assertion_id!r} has invalid severity")
    return (action if isinstance(action, str) else None), severity


def project_ontology_assertions(
    relations: list[Relation],
    bundle: OntologyBundle,
) -> tuple[OntologyAssertion, ...]:
    """Project exactly the loaded relation catalog through verified semantics.

    The generated artifact is the authority for an authored assertion's
    semantics, but it must not inject the production catalog into an isolated
    data root. Fixture-only assertions remain valid only when their YAML
    supplies the explicit semantic fields; no behaviour is inferred from a
    relation type.
    """
    _validate_relation_ids_before_projection(relations)
    generated_by_id = {assertion.id: assertion for assertion in load_ontology_assertions(bundle)}
    projected: list[OntologyAssertion] = []
    for relation in relations:
        generated = generated_by_id.get(relation.id)
        if generated is not None:
            projected.append(generated)
            continue
        if relation.assertion_kind is None or relation.semantic_family is None:
            raise _policy_error(bundle, f"fixture assertion {relation.id!r} lacks explicit semantics")
        projected.append(
            OntologyAssertion(
                id=relation.id,
                relation_type=relation.type,
                assertion_kind=relation.assertion_kind,
                semantic_family=relation.semantic_family,
                reason=relation.reason,
                source_selector=relation.source_selector,
                target_selector=relation.target_selector,
                action=relation.action,
                severity=relation.severity,
                research_state=relation.research_state,
                sources=relation.sources,
            )
        )
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
