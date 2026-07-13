"""Canonical ontology projections for the in-memory SurrealDB read model."""

from __future__ import annotations

from planner.cards.product import format_product_name
from planner.cards.substance import format_substance_name
from planner.contracts import Dashboard, Product, Relation, RelationSelector, SchedulingConstraint, Substance


def substance_record(substance_id: str, substance: Substance) -> dict[str, object]:
    knowledge = {
        "kind": list(substance.kind),
        "role": list(substance.role),
        "quality": list(substance.quality),
        "effect": list(substance.effect),
        "risk": list(substance.risk),
        "context": list(substance.context),
        "pathway": list(substance.pathway),
    }
    return {
        "id": substance_id,
        "name": substance.name,
        "intake": list(substance.intake),
        "timing": list(substance.timing),
        "activity": list(substance.activity),
        "knowledge": knowledge,
        "context": knowledge["context"],
        "effect": knowledge["effect"],
        "kind": knowledge["kind"],
        "role": knowledge["role"],
        "quality": knowledge["quality"],
        "term_refs": _substance_term_refs(substance),
        "prefer_with": list(substance.prefer_with),
        **({"form": substance.form} if substance.form is not None else {}),
    }


def relation_record(relation: Relation, substances: dict[str, Substance]) -> dict[str, object]:
    src_ids = _resolve_selector_ids(relation.source_selector, substances)
    tgt_ids = _resolve_selector_ids(relation.target_selector, substances)
    return {
        "id": relation.id,
        "type": relation.type,
        "src_substances": src_ids,
        "tgt_substances": tgt_ids,
        "src_member_names": _endpoint_member_names(src_ids, substances),
        "tgt_member_names": _endpoint_member_names(tgt_ids, substances),
        "src_selector": _selector_record(relation.source_selector),
        "tgt_selector": _selector_record(relation.target_selector),
        "src_key": _selector_key(relation.source_selector),
        "tgt_key": _selector_key(relation.target_selector),
        "src_display": _selector_display(relation.source_selector, substances),
        "tgt_display": _selector_display(relation.target_selector, substances),
        "reason": relation.reason,
        "action": relation.action or "",
        **({"severity": relation.severity} if relation.severity is not None else {}),
    }


def scheduling_constraint_record(
    constraint: SchedulingConstraint,
    substances: dict[str, Substance],
) -> dict[str, object]:
    src_ids = _resolve_selector_ids(constraint.source_selector, substances)
    tgt_ids = _resolve_selector_ids(constraint.target_selector, substances)
    return {
        "id": constraint.id,
        "effect": constraint.effect,
        "enforcement": constraint.enforcement,
        "src_substances": src_ids,
        "tgt_substances": tgt_ids,
        "action": constraint.action or "",
    }


def product_record(product_id: str, product: Product) -> dict[str, object]:
    return {
        "id": product_id,
        "name": product.name,
        "display_name": format_product_name(product),
        "components": [c.substance for c in product.components],
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


def _selector_record(selector: RelationSelector) -> dict[str, object]:
    if selector.entity_id is not None or selector.entity_name is not None:
        return {"kind": "entity", "id": selector.entity_id, "name": selector.entity_name}
    return {"kind": "term", "category": selector.category, "term": selector.term}


def _selector_key(selector: RelationSelector) -> str:
    return selector.entity_id or selector.entity_name or f"{selector.category}:{selector.term}"


def _selector_display(selector: RelationSelector, substances: dict[str, Substance]) -> str:
    if selector.entity_name is not None:
        return selector.entity_name
    if selector.entity_id is not None:
        substance = substances.get(selector.entity_id)
        return format_substance_name(substance) if substance is not None else selector.entity_id
    return f"{selector.category}:{selector.term}"


def _resolve_selector_ids(selector: RelationSelector, substances: dict[str, Substance]) -> list[str]:
    if selector.entity_id is not None:
        return [selector.entity_id] if selector.entity_id in substances else []
    if selector.entity_name is not None:
        return [sid for sid, substance in substances.items() if substance.name == selector.entity_name]
    if selector.category is not None and selector.term is not None:
        return [
            sid
            for sid, substance in substances.items()
            if selector.term in _terms_for_category(substance, selector.category)
        ]
    return []


def _terms_for_category(substance: Substance, category: str) -> tuple[str, ...]:
    fields = {
        "kind": substance.kind,
        "role": substance.role,
        "quality": substance.quality,
        "effect": substance.effect,
        "risk": substance.risk,
        "context": substance.context,
        "pathway": substance.pathway,
    }
    return fields.get(category, ())


def _endpoint_member_names(ids: list[str], substances: dict[str, Substance]) -> list[str]:
    return [format_substance_name(substances[sid]) for sid in ids if sid in substances]


def _substance_term_refs(substance: Substance) -> list[str]:
    refs: list[str] = []
    for category, values in (
        ("schedule_rule", substance.intake),
        ("schedule_rule", substance.timing),
        ("schedule_rule", substance.activity),
        ("kind", substance.kind),
        ("role", substance.role),
        ("quality", substance.quality),
        ("effect", substance.effect),
        ("risk", substance.risk),
        ("context", substance.context),
        ("pathway", substance.pathway),
    ):
        refs.extend(f"{category}:{term}" for term in values)
    return refs
