"""Warning rendering: action lookup, contexts, humanization, concern collection."""

from __future__ import annotations

from typing import Any, cast

from planner.cards.product import format_product_name
from planner.cards.substance import format_substance_name
from planner.cards.warning_actions import warning_action
from planner.contracts import Product, Substance
from planner.domain_constants import WARNING_CATEGORY_LABELS


def _format_warning_entities(
    warning: dict[str, Any],
    products: dict[str, Product],
    substances: dict[str, Substance],
) -> dict[str, Any]:
    out: dict[str, Any] = {}

    product_id = warning.get("product")
    if isinstance(product_id, str):
        product = products.get(product_id)
        out["product"] = format_product_name(product) if product is not None else product_id

    if str(warning.get("type") or "") == "risk_cluster_load":
        cluster = warning.get("cluster")
        if isinstance(cluster, str) and cluster:
            out["risk"] = cluster
            out["concern"] = cluster
        active_members = warning.get("active")
        if isinstance(active_members, list):
            active_members_list = cast(list[Any], active_members)
            out["active"] = [
                format_substance_name(substances[sid]) if sid in substances else str(sid)
                for sid in active_members_list
                if isinstance(sid, str)
            ]

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
    warning: dict[str, Any],
) -> str:
    """Return the human-readable concern label, or "" to defer to the caller.

    Sentinel contract: when warning_type == "risk_cluster_load", the `concern`
    field is already populated by `_format_warning_entities` (sourced from the
    `cluster` field). Returning "" here signals `humanize_warning` to keep that
    pre-populated value rather than overwriting it.
    """
    if warning_type == "risk_cluster_load":
        return ""
    if trait:
        return trait.split(":", 1)[1].replace("_", " ")
    if relation:
        return relation.replace("_", " ")
    return warning_type.replace("_", " ")


def humanize_warning(
    warning: dict[str, Any],
    *,
    products: dict[str, Product],
    substances: dict[str, Substance],
) -> dict[str, Any]:
    warning_type = str(warning.get("type") or "review")
    trait = str(warning.get("trait") or "")
    relation = str(warning.get("relation") or "")

    out: dict[str, Any] = {
        "category": WARNING_CATEGORY_LABELS.get(warning_type, "Review"),
    }
    out.update(_format_warning_entities(warning, products, substances))

    concern = _derive_concern_text(warning_type, trait, relation, warning)
    if concern:
        out["concern"] = concern

    message = warning.get("message") or warning.get("reason")
    if isinstance(message, str) and message and "operator attention" not in message:
        out["note"] = message
    action = warning.get("action")
    out["action"] = action if isinstance(action, str) and action else warning_action(warning_type, trait, relation)
    severity = warning.get("severity")
    if severity is not None:
        out["severity"] = severity
    return out


def is_generic_manual_review_warning(warning: dict[str, Any]) -> bool:
    return warning.get("trait") == "risk:manual_review"
