"""Ontology-derived field lists for substance-card projections."""

from __future__ import annotations

from collections.abc import Mapping
from types import MappingProxyType
from typing import cast

from planner.contracts import Substance
from planner.ontology.bundle_view import OntologyBundleView
from planner.ontology.errors import MALFORMED, OntologyInfrastructureError
from planner.ontology.glue_capabilities import IMPLEMENTED_PREDICATE_NAMESPACES
from planner.ontology.presentation import load_category_predicates, load_term_catalog


def knowledge_category_fields(bundle: OntologyBundleView) -> tuple[str, ...]:
    """Return substance ``knowledge`` fields declared by ontology categories."""

    return _decode_knowledge_category_fields(bundle)


def _decode_knowledge_category_fields(bundle: OntologyBundleView) -> tuple[str, ...]:
    fields: list[str] = []
    for predicates in load_category_predicates(bundle).values():
        fields.extend(
            predicate.removeprefix("knowledge.") for predicate in predicates if predicate.startswith("knowledge.")
        )

    return tuple(dict.fromkeys(fields))


def canonical_terms_by_predicate(bundle: OntologyBundleView) -> Mapping[str, frozenset[str]]:
    """Return the generated registry of term slugs keyed by assertion predicate.

    The runtime vocabulary is the only authorization source for card
    assertions.  A term is usable through a predicate only when the generated
    registry explicitly declares that predicate in its ``allowed_predicates``;
    malformed records are ignored, which makes the resolver fail closed.
    """

    return _decode_canonical_terms_by_predicate(bundle)


def _decode_canonical_terms_by_predicate(bundle: OntologyBundleView) -> Mapping[str, frozenset[str]]:
    terms_by_predicate: dict[str, set[str]] = {}
    for term in load_term_catalog(bundle):
        slug = term.get("slug")
        allowed_predicates = term.get("allowed_predicates")
        if not isinstance(slug, str) or not isinstance(allowed_predicates, list):
            continue
        raw_predicates = cast(list[object], allowed_predicates)
        if not all(isinstance(predicate, str) for predicate in raw_predicates):
            continue
        for predicate in cast(list[str], raw_predicates):
            terms_by_predicate.setdefault(predicate, set()).add(slug)
    return MappingProxyType({predicate: frozenset(slugs) for predicate, slugs in terms_by_predicate.items()})


def substance_trait_fields(bundle: OntologyBundleView) -> tuple[tuple[str, str], ...]:
    """Return ontology categories for review presentation.

    The first element is intentionally a generic assertion collection name;
    callers must resolve its category through the assertion records rather than
    treating an ontology category as a Python attribute.
    """

    return _decode_substance_trait_fields(bundle)


def _decode_substance_trait_fields(bundle: OntologyBundleView) -> tuple[tuple[str, str], ...]:
    categories = knowledge_category_fields(bundle)
    return tuple(("knowledge_assertions", category) for category in categories)


def allowed_predicate_fields_for_category(bundle: OntologyBundleView, category: str) -> tuple[str, ...] | None:
    """Return the authored Substance fields backing one selector category.

    Categories are vocabulary-owned.  A category may be backed by multiple
    predicates, so treating its name as a dataclass attribute is incorrect.
    ``None`` means the authored category or its predicate declaration is
    unusable and must be handled fail-closed.
    """

    try:
        predicates = load_category_predicates(bundle).get(category)
    except OntologyInfrastructureError:
        return None
    if predicates is None:
        return None
    fields_for_category: list[str] = []
    for predicate in predicates:
        namespace, separator, field = predicate.partition(".")
        if namespace not in IMPLEMENTED_PREDICATE_NAMESPACES or separator != "." or not field or "." in field:
            return None
        fields_for_category.append(field)
    unique_fields = tuple(dict.fromkeys(fields_for_category))
    return unique_fields or None


def dashboard_selector_category(bundle: OntologyBundleView, category: str) -> bool:
    """Return whether a vocabulary category is backed by knowledge assertions.

    Dashboards are review projections over ``KnowledgeAssertion`` records.
    """

    try:
        predicates = load_category_predicates(bundle).get(category)
    except OntologyInfrastructureError:
        return False
    return predicates is not None and all(predicate.startswith("knowledge.") for predicate in predicates)


def substance_terms_for_category(
    substance: Substance,
    category: str,
    bundle: OntologyBundleView,
) -> tuple[str, ...] | None:
    """Resolve authored category terms through its declared predicates.

    The return value is ``None`` for an unsupported/malformed category or an
    accessor shape mismatch.  An empty tuple is a valid category with no terms.
    """

    try:
        predicates = load_category_predicates(bundle).get(category)
    except OntologyInfrastructureError:
        return None
    if predicates is None:
        return None
    return tuple(assertion.value for assertion in substance.knowledge_assertions if assertion.category == category)


def validate_substance_schema_conformance(bundle: OntologyBundleView) -> None:
    """Fail closed when authored trait predicates cannot reach ``Substance``.

    The generated vocabulary is the ontology authority.  This guard keeps a
    newly authored category from silently becoming projection-only because its
    backing field was omitted from the Python runtime contract.
    """

    try:
        categories = load_category_predicates(bundle)
    except OntologyInfrastructureError:
        raise OntologyInfrastructureError(
            "ontology runtime vocabulary categories must be a mapping",
            code=MALFORMED,
        ) from None
    for category in categories:
        if not isinstance(category, str):
            raise OntologyInfrastructureError(
                "ontology runtime vocabulary category names must be strings",
                code=MALFORMED,
            )
        predicate_fields = allowed_predicate_fields_for_category(bundle, category)
        if predicate_fields is None or not predicate_fields:
            raise OntologyInfrastructureError(
                f"ontology category {category!r} has malformed allowed_predicates",
                code=MALFORMED,
            )
