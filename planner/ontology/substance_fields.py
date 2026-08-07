"""Ontology-derived field lists for substance-card projections."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import fields
from typing import Protocol, cast

from planner.contracts import Substance
from planner.ontology.errors import MALFORMED, OntologyInfrastructureError
from planner.ontology.glue_capabilities import IMPLEMENTED_PREDICATE_NAMESPACES
from planner.ontology.runtime_program import RuntimeProgram


class OntologyBundleLike(Protocol):
    @property
    def runtime_program(self) -> RuntimeProgram: ...

    @property
    def runtime_vocabulary(self) -> Mapping[str, object]: ...


def schedule_assignment_fields(bundle: OntologyBundleLike) -> tuple[str, ...]:
    """Return substance ``schedule`` fields controlled by assignment axes."""

    return tuple(
        row.assignment_field
        for row in sorted(bundle.runtime_program.assignment_axes, key=lambda row: (row.order, row.id))
    )


def knowledge_category_fields(bundle: OntologyBundleLike) -> tuple[str, ...]:
    """Return substance ``knowledge`` fields declared by ontology categories."""

    categories = bundle.runtime_vocabulary.get("categories")
    if not isinstance(categories, dict):
        return ()

    fields: list[str] = []
    for category, raw in categories.items():
        if not isinstance(category, str) or not isinstance(raw, dict):
            continue
        category_data = cast(dict[str, object], raw)
        allowed_predicates = category_data.get("allowed_predicates")
        if not isinstance(allowed_predicates, list):
            continue
        for predicate in allowed_predicates:
            if not isinstance(predicate, str) or not predicate.startswith("knowledge."):
                continue
            field = predicate.removeprefix("knowledge.")
            if field and "." not in field:
                fields.append(field)

    return tuple(dict.fromkeys(fields))


def substance_trait_fields(bundle: OntologyBundleLike) -> tuple[tuple[str, str], ...]:
    """Return ``(Substance field, review namespace)`` pairs from the ontology."""

    schedule_fields = tuple((field, field) for field in schedule_assignment_fields(bundle))
    knowledge_fields = tuple((field, field) for field in knowledge_category_fields(bundle))
    return cast(tuple[tuple[str, str], ...], schedule_fields + knowledge_fields)


def allowed_predicate_fields_for_category(bundle: OntologyBundleLike, category: str) -> tuple[str, ...] | None:
    """Return the authored Substance fields backing one selector category.

    Categories are vocabulary-owned.  In particular, ``schedule_rule`` is a
    category backed by several schedule fields, so treating the category as a
    dataclass attribute is incorrect.  ``None`` means the authored category
    or its predicate declaration is unusable and must be handled fail-closed.
    """

    categories = bundle.runtime_vocabulary.get("categories")
    if not isinstance(categories, dict):
        return None
    typed_categories = cast(dict[str, object], categories)
    metadata = typed_categories.get(category)
    if not isinstance(metadata, dict):
        return None
    typed_metadata = cast(dict[str, object], metadata)
    raw_predicates = typed_metadata.get("allowed_predicates")
    if not isinstance(raw_predicates, list):
        return None
    fields_for_category: list[str] = []
    for predicate in raw_predicates:
        if not isinstance(predicate, str):
            return None
        namespace, separator, field = predicate.partition(".")
        if namespace not in IMPLEMENTED_PREDICATE_NAMESPACES or separator != "." or not field or "." in field:
            return None
        fields_for_category.append(field)
    unique_fields = tuple(dict.fromkeys(fields_for_category))
    return unique_fields or None


def substance_terms_for_category(
    substance: Substance,
    category: str,
    bundle: OntologyBundleLike,
) -> tuple[str, ...] | None:
    """Resolve authored category terms through its declared predicates.

    The return value is ``None`` for an unsupported/malformed category or an
    accessor shape mismatch.  An empty tuple is a valid category with no terms.
    """

    fields_for_category = allowed_predicate_fields_for_category(bundle, category)
    if fields_for_category is None:
        return None
    terms: list[str] = []
    for field in fields_for_category:
        values = getattr(substance, field, None)
        if not isinstance(values, tuple) or any(not isinstance(value, str) for value in values):
            return None
        terms.extend(cast(tuple[str, ...], values))
    return tuple(dict.fromkeys(terms))


def validate_substance_schema_conformance(bundle: OntologyBundleLike) -> None:
    """Fail closed when authored trait predicates cannot reach ``Substance``.

    The generated vocabulary is the ontology authority.  This guard keeps a
    newly authored category from silently becoming projection-only because its
    backing field was omitted from the Python runtime contract.
    """

    substance_fields = {item.name for item in fields(Substance)}
    missing_schedule_fields = sorted(set(schedule_assignment_fields(bundle)) - substance_fields)
    if missing_schedule_fields:
        raise OntologyInfrastructureError(
            "ontology assignment axes reference Substance fields absent from the runtime contract: "
            + ", ".join(missing_schedule_fields),
            code=MALFORMED,
        )
    categories = bundle.runtime_vocabulary.get("categories")
    if not isinstance(categories, dict):
        raise OntologyInfrastructureError(
            "ontology runtime vocabulary categories must be a mapping",
            code=MALFORMED,
        )
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
        missing = sorted(set(predicate_fields) - substance_fields)
        if missing:
            raise OntologyInfrastructureError(
                f"ontology category {category!r} references Substance fields absent from the runtime contract: "
                + ", ".join(missing),
                code=MALFORMED,
            )
