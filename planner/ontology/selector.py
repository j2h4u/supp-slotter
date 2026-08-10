"""Canonical selector hydration and resolution.

Selector shape and endpoint exclusivity are authored and checked by the
generated schema/SHACL contract.  This module is the single runtime seam that
turns that shape into the typed selector contract and resolves it against the
verified substance read model.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, cast

from planner.contracts import CardLoadError, RelationSelector, Substance
from planner.ontology.artifacts import OntologyBundle
from planner.ontology.errors import OntologyInfrastructureError
from planner.ontology.presentation import load_category_predicates, load_term_catalog
from planner.ontology.substance_fields import (
    allowed_predicate_fields_for_category,
    dashboard_selector_category,
    substance_terms_for_category,
)

SelectorResolutionOutcome = Literal["resolved", "empty", "malformed_selector", "unsupported_selector"]
SelectorForm = Literal["term", "entity"]
SelectorCapabilityForm = Literal["entity_id", "name", "term"]


@dataclass(frozen=True, slots=True)
class RelationTypeContract:
    """Executable endpoint and direction contract for one relation type."""

    id: str
    label: str
    order: int
    directional: bool
    source_selector_forms: frozenset[SelectorForm]
    target_selector_forms: frozenset[SelectorForm]


@dataclass(frozen=True, slots=True)
class SelectorResolution:
    """Deterministic result of resolving one normalized selector."""

    substance_ids: tuple[str, ...]
    outcome: SelectorResolutionOutcome


def load_relation_type_contracts(bundle: OntologyBundle) -> Mapping[str, RelationTypeContract]:
    """Decode the complete generated relation-type contract, failing closed."""

    source = bundle.root / "generated" / "runtime-vocabulary.yaml"
    raw_relation_types = bundle.runtime_vocabulary.get("relation_types")
    if not isinstance(raw_relation_types, Mapping) or not raw_relation_types:
        raise CardLoadError(source, "canonical runtime vocabulary has no relation_types")
    contracts: dict[str, RelationTypeContract] = {}
    allowed_fields = {
        "id",
        "label",
        "order",
        "directional",
        "source_selector_forms",
        "target_selector_forms",
    }
    for key, raw in raw_relation_types.items():
        if not isinstance(key, str) or not key.strip() or not isinstance(raw, Mapping):
            raise CardLoadError(source, "canonical runtime vocabulary has malformed relation_types")
        raw = cast(Mapping[str, object], raw)
        if set(raw) != allowed_fields:
            raise CardLoadError(source, f"relation type {key!r} has unsupported or missing metadata fields")
        relation_id = raw.get("id")
        label = raw.get("label")
        order = raw.get("order")
        directional = raw.get("directional")
        if relation_id != key or not isinstance(label, str) or not label.strip():
            raise CardLoadError(source, f"relation type {key!r} has invalid identity or label")
        if isinstance(order, bool) or not isinstance(order, int):
            raise CardLoadError(source, f"relation type {key!r} has invalid order")
        if not isinstance(directional, bool):
            raise CardLoadError(source, f"relation type {key!r} has invalid directional flag")
        source_forms = _relation_selector_forms(raw.get("source_selector_forms"), source, key, "source")
        target_forms = _relation_selector_forms(raw.get("target_selector_forms"), source, key, "target")
        contracts[key] = RelationTypeContract(
            id=key,
            label=label,
            order=order,
            directional=directional,
            source_selector_forms=source_forms,
            target_selector_forms=target_forms,
        )
    return dict(sorted(contracts.items()))


def _relation_selector_forms(raw: object, source: Path, relation_type: str, side: str) -> frozenset[SelectorForm]:
    if not isinstance(raw, (list, tuple)) or not raw:
        raise CardLoadError(source, f"relation type {relation_type!r} requires non-empty {side}_selector_forms")
    raw = cast(list[object] | tuple[object, ...], raw)
    values: list[SelectorForm] = []
    for form in raw:
        if form not in {"term", "entity"}:
            raise CardLoadError(source, f"relation type {relation_type!r} has invalid {side} selector form {form!r}")
        typed_form = cast(SelectorForm, form)
        if typed_form in values:
            raise CardLoadError(source, f"relation type {relation_type!r} duplicates {side} selector form {form!r}")
        values.append(typed_form)
    return frozenset(values)


def relation_selector_form(selector: RelationSelector) -> SelectorForm:
    """Return the canonical union branch used by a hydrated selector."""

    return "entity" if selector.entity_id is not None or selector.entity_name is not None else "term"


def selector_capability_form(selector: RelationSelector) -> SelectorCapabilityForm:
    """Return the authored runtime capability form for a normalized selector."""

    if selector.entity_id is not None:
        return "entity_id"
    if selector.entity_name is not None:
        return "name"
    return "term"


def validate_relation_selector_form(
    selector: RelationSelector,
    *,
    contract: RelationTypeContract,
    side: Literal["source", "target"],
    path: Path,
    label: str,
) -> None:
    """Enforce a relation type's source/target selector-form contract."""

    actual = relation_selector_form(selector)
    allowed = contract.source_selector_forms if side == "source" else contract.target_selector_forms
    if actual not in allowed:
        allowed_text = ", ".join(sorted(allowed))
        raise CardLoadError(
            path,
            f"{label} uses selector form {actual!r}, but relation type {contract.id!r} allows only {allowed_text}",
        )


def hydrate_selector(
    raw: object,
    *,
    path: Path,
    label: str,
    allow_entity_name: bool,
) -> RelationSelector:
    """Hydrate one schema-shaped selector into the canonical runtime DTO.

    The strict structural checks live here only.  Callers must not decode
    selector dictionaries themselves or provide endpoint aliases.
    """

    if not isinstance(raw, Mapping):
        raise CardLoadError(path, f"{label} selector must be a mapping")
    selector = cast(Mapping[object, object], raw)
    if "entity" in selector:
        if set(selector) != {"entity"}:
            raise CardLoadError(path, f"malformed {label} selector")
        entity = selector["entity"]
        if not isinstance(entity, Mapping):
            raise CardLoadError(path, f"malformed {label} entity selector")
        entity_mapping = cast(Mapping[object, object], entity)
        if not set(entity_mapping).issubset({"entity_id", "name"}):
            raise CardLoadError(path, f"malformed {label} entity selector")
        entity_id = _optional_non_empty_string(entity_mapping.get("entity_id"), path, "entity_id")
        entity_name = _optional_non_empty_string(entity_mapping.get("name"), path, "name")
        if (entity_id is None) == (entity_name is None):
            raise CardLoadError(path, "entity selector requires exactly one non-empty entity_id/name")
        if entity_name is not None and not allow_entity_name:
            raise CardLoadError(path, f"{label} entity selector requires stable entity_id")
        return RelationSelector(entity_id=entity_id, entity_name=entity_name)

    if set(selector) != {"category", "term"}:
        raise CardLoadError(path, f"{label} selector requires non-empty category and term")
    category = _optional_non_empty_string(selector.get("category"), path, "category")
    term = _optional_non_empty_string(selector.get("term"), path, "term")
    if category is None or term is None:
        raise CardLoadError(path, f"{label} selector requires non-empty category and term")
    return RelationSelector(category=category, term=term)


def resolve_selector(
    selector: RelationSelector | None,
    substances: Mapping[str, Substance],
    ontology_bundle: OntologyBundle,
) -> SelectorResolution:
    """Resolve a typed selector, failing closed on malformed/unknown terms."""

    if selector is None:
        return SelectorResolution((), "malformed_selector")
    if selector.entity_id is not None:
        return _resolve_entity_id(selector, substances)
    if selector.entity_name is not None:
        return _resolve_entity_name(selector, substances)
    if selector.category is None or selector.term is None:
        return SelectorResolution((), "malformed_selector")
    return _resolve_term_selector(selector, substances, ontology_bundle)


def selector_identity_key(
    selector: RelationSelector,
    substances: Mapping[str, Substance],
    ontology_bundle: OntologyBundle,
) -> str:
    """Return the canonical resolved identity key used by relation dedupe."""
    resolution = resolve_selector(selector, substances, ontology_bundle)
    if selector.entity_id is not None or selector.entity_name is not None:
        return f"entity:{','.join(resolution.substance_ids)}"
    return f"term:{selector.category}:{selector.term}"


def resolve_dashboard_selector(
    selector: RelationSelector | None,
    substances: Mapping[str, Substance],
    ontology_bundle: OntologyBundle,
) -> SelectorResolution:
    """Resolve a dashboard selector, which may only inspect knowledge terms."""

    if selector is None or selector.category is None or selector.term is None:
        return SelectorResolution((), "malformed_selector")
    if not dashboard_selector_category(ontology_bundle, selector.category):
        return SelectorResolution((), "unsupported_selector")
    return resolve_selector(selector, substances, ontology_bundle)


def _resolve_entity_id(selector: RelationSelector, substances: Mapping[str, Substance]) -> SelectorResolution:
    if any(value is not None for value in (selector.entity_name, selector.category, selector.term)):
        return SelectorResolution((), "malformed_selector")
    if selector.entity_id is None or not selector.entity_id.strip():
        return SelectorResolution((), "malformed_selector")
    if selector.entity_id not in substances:
        # An entity ID is a reference to a stable card identity.  An absent
        # card is not the same thing as a known card that is merely inactive in
        # the current stack; callers use this distinction to fail closed at
        # load time while retaining valid missing-active-state outcomes.
        return SelectorResolution((), "unsupported_selector")
    return SelectorResolution((selector.entity_id,), "resolved")


def _resolve_entity_name(selector: RelationSelector, substances: Mapping[str, Substance]) -> SelectorResolution:
    if any(value is not None for value in (selector.category, selector.term)):
        return SelectorResolution((), "malformed_selector")
    if selector.entity_name is None or not selector.entity_name.strip():
        return SelectorResolution((), "malformed_selector")
    ids = tuple(sorted(sid for sid, substance in substances.items() if substance.name == selector.entity_name))
    # Names are review-only aliases.  A miss must not look like an ordinary
    # empty broad selector, or a malformed assertion can disappear silently.
    return SelectorResolution(ids, "resolved" if ids else "unsupported_selector")


def _resolve_term_selector(
    selector: RelationSelector,
    substances: Mapping[str, Substance],
    ontology_bundle: OntologyBundle,
) -> SelectorResolution:
    if selector.category is None or selector.term is None:
        return SelectorResolution((), "malformed_selector")
    if not selector.category.strip() or not selector.term.strip():
        return SelectorResolution((), "malformed_selector")
    if allowed_predicate_fields_for_category(ontology_bundle, selector.category) is None:
        return SelectorResolution((), "unsupported_selector")
    if not _canonical_term_exists(selector.category, selector.term, ontology_bundle):
        return SelectorResolution((), "unsupported_selector")
    ids: list[str] = []
    for substance_id, substance in sorted(substances.items()):
        terms = substance_terms_for_category(substance, selector.category, ontology_bundle)
        if terms is None:
            return SelectorResolution((), "unsupported_selector")
        if selector.term in terms:
            ids.append(substance_id)
    result = tuple(ids)
    return SelectorResolution(result, "resolved" if result else "empty")


def _canonical_term_exists(category: str, term: str, ontology_bundle: OntologyBundle) -> bool:
    """Return whether ``category:term`` is authored by the verified bundle."""
    try:
        category_predicates = load_category_predicates(ontology_bundle).get(category)
        terms = load_term_catalog(ontology_bundle)
    except OntologyInfrastructureError:
        return False
    if category_predicates is None:
        return False
    for raw_term in terms:
        term_predicates = raw_term.get("allowed_predicates")
        if isinstance(term_predicates, (list, tuple)):
            term_predicates = cast(list[object] | tuple[object, ...], term_predicates)
        else:
            continue
        if (
            raw_term.get("semantic_category") == category
            and raw_term.get("slug") == term
            and all(isinstance(predicate, str) for predicate in term_predicates)
            and any(predicate in category_predicates for predicate in term_predicates)
        ):
            return True
    return False


def _optional_non_empty_string(value: object, path: Path, field: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        raise CardLoadError(path, f"selector {field} must be a non-empty string")
    return value


__all__ = [
    "RelationTypeContract",
    "SelectorResolution",
    "SelectorResolutionOutcome",
    "hydrate_selector",
    "load_relation_type_contracts",
    "relation_selector_form",
    "resolve_dashboard_selector",
    "resolve_selector",
    "selector_capability_form",
    "selector_identity_key",
    "validate_relation_selector_form",
]
