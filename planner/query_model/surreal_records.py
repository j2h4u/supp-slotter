"""Record builders for the in-memory SurrealDB read model."""

from __future__ import annotations

from typing import Any

from planner.cards.product import format_product_name
from planner.cards.substance import format_substance_name
from planner.contracts import Dashboard, Product, Relation, Substance, TraitDef


def substance_record(substance_id: str, substance: Substance) -> dict[str, Any]:
    record: dict[str, Any] = {
        "id": substance_id,
        "name": substance.name,
        "intake": list(substance.intake),
        "timing": list(substance.timing),
        "activity": list(substance.activity),
        "is_": list(substance.is_),
        "effect": list(substance.effect),
        "risk": list(substance.risk),
        "context": list(substance.context),
        "pathway": list(substance.pathway),
        "prefer_with": list(substance.prefer_with),
        "trait_refs": _substance_trait_refs(substance),
    }
    if substance.form is not None:
        record["form"] = substance.form
    return record


def relation_record(
    relation: Relation,
    substances: dict[str, Substance],
) -> dict[str, Any]:
    src_ids = _resolve_endpoint_ids(relation, "source", substances)
    tgt_ids = _resolve_endpoint_ids(relation, "target", substances)
    src_key, src_display = _endpoint_key_and_display(relation, "source", substances)
    tgt_key, tgt_display = _endpoint_key_and_display(relation, "target", substances)
    record: dict[str, Any] = {
        "type": relation.type,
        "src_substances": src_ids,
        "tgt_substances": tgt_ids,
        "src_key": src_key,
        "tgt_key": tgt_key,
        "src_display": src_display,
        "tgt_display": tgt_display,
        "src_substance_raw": relation.source_substance,
        "src_name_raw": relation.source_name,
        "src_trait_raw": relation.source_trait,
        "src_class_raw": relation.source_class,
        "tgt_substance_raw": relation.target_substance,
        "tgt_name_raw": relation.target_name,
        "tgt_trait_raw": relation.target_trait,
        "tgt_class_raw": relation.target_class,
        "reason": relation.reason,
        "action": relation.action or "",
    }
    if relation.severity is not None:
        record["severity"] = relation.severity
    return record


def product_record(product_id: str, product: Product) -> dict[str, Any]:
    return {
        "id": product_id,
        "name": product.name,
        "display_name": format_product_name(product),
        "components": [c.substance for c in product.components],
    }


def trait_record(trait_id: str, trait: TraitDef) -> dict[str, Any]:
    return {
        "id": trait_id,
        "namespace": trait.namespace,
        "short_name": trait.short_name,
        "label": trait.label,
    }


def dashboard_record(slug: str, dashboard: Dashboard) -> dict[str, Any]:
    from_traits_pairs = [
        f"{namespace}:{short_name}"
        for namespace, short_names in dashboard.from_traits.items()
        for short_name in short_names
    ]
    return {
        "slug": slug,
        "name": dashboard.name,
        "from_traits_pairs": from_traits_pairs,
    }


def _endpoint_fields(relation: Relation, side: str) -> tuple[str | None, str | None]:
    if side == "source":
        return relation.source_substance, relation.source_name
    return relation.target_substance, relation.target_name


def _endpoint_trait(relation: Relation, side: str) -> str | None:
    if side == "source":
        return relation.source_trait
    return relation.target_trait


def _endpoint_class(relation: Relation, side: str) -> str | None:
    if side == "source":
        return relation.source_class
    return relation.target_class


def _resolve_endpoint_ids(
    relation: Relation,
    side: str,
    substances: dict[str, Substance],
) -> list[str]:
    """Resolve one relation endpoint to the substance IDs it matches."""
    exact_id, name = _endpoint_fields(relation, side)
    if exact_id is not None:
        return [exact_id] if exact_id in substances else []
    if name is not None:
        return [sid for sid, s in substances.items() if s.name == name]
    trait = _endpoint_trait(relation, side)
    if trait is not None:
        return [
            sid
            for sid, substance in substances.items()
            if trait in substance_record(sid, substance)["trait_refs"]
        ]
    return []


def _endpoint_key_and_display(
    relation: Relation,
    side: str,
    substances: dict[str, Substance],
) -> tuple[str, str]:
    """Identity and display text for warning deduplication."""
    exact_id, name = _endpoint_fields(relation, side)
    if exact_id is not None:
        substance = substances.get(exact_id)
        if substance is not None:
            return exact_id, format_substance_name(substance)
        return exact_id, exact_id
    if name is not None:
        return name, name
    trait = _endpoint_trait(relation, side)
    if trait is not None:
        return trait, trait
    class_slug = _endpoint_class(relation, side)
    if class_slug is not None:
        display = f"is:{class_slug}"
        return display, display
    return "<unknown>", "<unknown>"


_SUBSTANCE_NAMESPACES: tuple[tuple[str, str], ...] = (
    ("intake", "intake"),
    ("timing", "timing"),
    ("activity", "activity"),
    ("is", "is_"),
    ("effect", "effect"),
    ("risk", "risk"),
    ("context", "context"),
    ("pathway", "pathway"),
)


def _substance_trait_refs(substance: Substance) -> list[str]:
    """Pre-compute all namespace:slug pairs the substance carries."""
    refs: list[str] = []
    for namespace, field_name in _SUBSTANCE_NAMESPACES:
        slugs: tuple[str, ...] = getattr(substance, field_name, ())
        for slug in slugs:
            refs.append(f"{namespace}:{slug}")
    return refs
