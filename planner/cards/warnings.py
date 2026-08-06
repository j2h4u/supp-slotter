"""Warning rendering: action lookup, contexts, humanization, concern collection."""

from __future__ import annotations

from planner.cards.product import format_product_name
from planner.cards.substance import format_substance_name
from planner.contracts import Product, Substance
from planner.ontology.artifacts import OntologyBundle
from planner.ontology.warning_policy import warning_action, warning_category_label


def _format_warning_entities(
    warning: dict[str, object],
    products: dict[str, Product],
    substances: dict[str, Substance],
) -> dict[str, object]:
    out: dict[str, object] = {}

    product_id = warning.get("product")
    if isinstance(product_id, str):
        product = products.get(product_id)
        out["product"] = format_product_name(product) if product is not None else product_id

    substance_id = warning.get("substance")
    if isinstance(substance_id, str):
        substance = substances.get(substance_id)
        out["substance"] = format_substance_name(substance) if substance is not None else substance_id

    source_id = warning.get("source_substance")
    if isinstance(source_id, str):
        source_substance = substances.get(source_id)
        out["source"] = (
            format_substance_name(source_substance)
            if source_substance is not None
            else str(warning.get("source_name") or source_id)
        )

    target_id = warning.get("target_substance")
    if isinstance(target_id, str):
        target_substance = substances.get(target_id)
        out["target"] = (
            format_substance_name(target_substance)
            if target_substance is not None
            else str(warning.get("target_name") or target_id)
        )

    return out


def _derive_concern_text(
    warning_type: str,
    trait: str,
    relation: str,
    warning: dict[str, object],
) -> str:
    """Return the human-readable concern label."""
    if trait:
        return trait.split(":", 1)[1].replace("_", " ")
    if relation:
        return relation.replace("_", " ")
    return warning_type.replace("_", " ")


def humanize_warning(
    warning: dict[str, object],
    *,
    products: dict[str, Product],
    substances: dict[str, Substance],
    ontology_bundle: OntologyBundle | None = None,
) -> dict[str, object]:
    warning_type_raw = warning.get("type")
    if not isinstance(warning_type_raw, str) or not warning_type_raw:
        raise ValueError("schedule warning is missing required ontology warning type")
    warning_type = warning_type_raw
    trait = str(warning.get("trait") or "")
    relation = str(warning.get("relation") or "")

    out: dict[str, object] = {
        "category": warning_category_label(warning_type, ontology_bundle),
    }
    out.update(_format_warning_entities(warning, products, substances))

    concern = _derive_concern_text(warning_type, trait, relation, warning)
    if concern:
        out["concern"] = concern

    message = warning.get("message") or warning.get("reason")
    if isinstance(message, str) and message and "operator attention" not in message:
        out["note"] = message
    action = warning.get("action")
    out["action"] = (
        action if isinstance(action, str) and action else warning_action(warning_type, trait, relation, ontology_bundle)
    )
    severity = warning.get("severity")
    if severity is not None:
        out["severity"] = severity
    return out
