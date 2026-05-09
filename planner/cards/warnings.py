"""Warning rendering: action lookup, contexts, humanization, concern collection."""

from __future__ import annotations

from typing import Any, cast

from planner.cards.product import format_product_name
from planner.cards.substance import format_substance_name
from planner.contracts import Product, Substance
from planner.io import REVIEW_CONTEXTS, WARNING_CATEGORY_LABELS


def warning_action(warning_type: str, trait: str, relation: str) -> str:
    if warning_type == "unmatched_concern":
        return "Review unresolved active concerns before treating the schedule as final."
    if warning_type == "intra_product_relation_conflict":
        return (
            "Review this product manually; competing components are inside one physical product "
            "and cannot be separated by scheduling."
        )
    if warning_type == "intra_product_trait_conflict":
        return "Review this product manually; its components have conflicting timing preferences."
    if warning_type == "ambiguous_prefer_with":
        return "Choose the intended companion product before relying on co-location."
    if warning_type == "missing_balance_substance":
        return "Review whether the paired balancing substance should be present in the active stack."
    if warning_type == "missing_support_substance":
        return "Review whether adding the supporting substance would improve this target in the active stack."
    if warning_type == "risk_cluster_load":
        return "Review this clustered risk load before treating the schedule as final."
    if trait == "risk:manual_review":
        return "Review this substance/product context manually before treating the schedule as final."
    if trait == "risk:narrow_therapeutic_window":
        return "Review total daily amount across products and avoid accidental stacking."
    if trait == "risk:hyperkalemia_med_interaction":
        return "Review potassium-related medication context before using this stack."
    if relation == "competes":
        return "Keep these substances away from the same slot when they are in separate products."
    return "Review this warning before treating the schedule as final."


def review_context_key(warning: dict[str, Any]) -> str | None:
    concern = str(warning.get("concern") or "")
    category = str(warning.get("category") or "")
    action = str(warning.get("action") or "")
    text = " ".join([concern, category, action]).lower()

    if "bleeding" in text or "fibrinolytic" in text or "antiplatelet" in text:
        return "bleeding_context"
    if "cholinergic" in text:
        return "cholinergic_load"
    if "blood-pressure" in text or "blood pressure" in text or "hypotension" in text:
        return "blood_pressure"
    if "inside one product" in text or "intra-product" in text:
        return "intra_product_conflicts"
    if "missing balance" in text or "missing support" in text or "paired" in text:
        return "missing_pairings"
    if "narrow therapeutic window" in text or "narrow-window" in text:
        return "narrow_window_minerals"
    if "potassium" in text or "hyperkalemia" in text:
        return "potassium_medication"
    if "timing conflict" in text:
        return "timing_conflicts"
    if "unmatched" in text or "unresolved active concern" in text:
        return "unmatched_concerns"
    return None


def warning_subject(warning: dict[str, Any]) -> str:
    risk = warning.get("risk")
    if isinstance(risk, str) and risk:
        return risk
    for key in ("product", "substance", "source", "target"):
        value = warning.get(key)
        if isinstance(value, str) and value:
            return value
    return "Stack"


def build_review_contexts(warnings: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, dict[str, set[str]]] = {}
    for warning in warnings:
        key = review_context_key(warning)
        if key is None:
            continue
        context = grouped.setdefault(key, {"items": set(), "actions": set()})
        context["items"].add(warning_subject(warning))
        action = warning.get("action")
        if isinstance(action, str) and action:
            context["actions"].add(action)

    return [
        {
            "context": REVIEW_CONTEXTS.get(key, key.replace("_", " ").title()),
            "items": sorted(value["items"], key=str.casefold),
            "actions": sorted(value["actions"], key=str.casefold),
        }
        for key, value in sorted(grouped.items())
    ]


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

    product_id = warning.get("product")
    if isinstance(product_id, str):
        product = products.get(product_id)
        out["product"] = format_product_name(product) if product is not None else product_id

    if warning_type == "risk_cluster_load":
        cluster = warning.get("cluster")
        if isinstance(cluster, str) and cluster:
            out["risk"] = cluster
            out["concern"] = cluster
        active_members = warning.get("active")
        if isinstance(active_members, list):
            active_members_list = cast(list[Any], active_members)
            out["active"] = [
                format_substance_name(substances[sid])
                if sid in substances else str(sid)
                for sid in active_members_list
                if isinstance(sid, str)
            ]

    substance_id = warning.get("substance")
    if isinstance(substance_id, str):
        substance = substances.get(substance_id)
        out["substance"] = (
            format_substance_name(substance) if substance is not None else substance_id
        )

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

    if warning_type == "risk_cluster_load":
        pass
    elif trait:
        out["concern"] = trait.split(":", 1)[1].replace("_", " ")
    elif relation:
        out["concern"] = relation.replace("_", " ")
    elif warning_type.startswith("missing_"):
        out["concern"] = warning_type.replace("_", " ")
    else:
        out["concern"] = warning_type.replace("_", " ")

    message = warning.get("message") or warning.get("reason")
    if isinstance(message, str) and message and "operator attention" not in message:
        out["note"] = message
    action = warning.get("action")
    out["action"] = (
        action if isinstance(action, str) and action
        else warning_action(warning_type, trait, relation)
    )
    return out


def is_generic_manual_review_warning(warning: dict[str, Any]) -> bool:
    return warning.get("trait") == "risk:manual_review"


def collect_active_unmatched_concerns(
    *,
    active_order: list[str],
    active_components: dict[str, list[str]],
    item_products: dict[str, str],
    products: dict[str, Product],
    substances: dict[str, Substance],
) -> list[dict[str, Any]]:
    warnings: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str]] = set()
    for item_id in active_order:
        product_id = item_products[item_id]
        product = products.get(product_id)
        if product is not None:
            for concern in product.unmatched_concerns:
                key = ("product", product_id, concern)
                if key in seen:
                    continue
                seen.add(key)
                warnings.append(
                    {
                        "type": "unmatched_concern",
                        "item": item_id,
                        "product": product_id,
                        "message": concern,
                    }
                )
        for substance_id in active_components[item_id]:
            substance = substances.get(substance_id)
            if substance is None:
                continue
            for concern in substance.unmatched_concerns:
                key = ("substance", substance_id, concern)
                if key in seen:
                    continue
                seen.add(key)
                warnings.append(
                    {
                        "type": "unmatched_concern",
                        "item": item_id,
                        "product": product_id,
                        "substance": substance_id,
                        "message": concern,
                    }
                )
    return warnings
