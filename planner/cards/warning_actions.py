"""Default operator actions for schedule warnings."""

from __future__ import annotations

_ACTION_BY_TYPE: dict[str, str] = {
    "safety_concern": ("Review this safety concern before treating the schedule as final."),
    "intra_product_relation_conflict": (
        "Review this product manually; competing components are inside one physical product "
        "and cannot be separated by scheduling."
    ),
    "intra_product_trait_conflict": (
        "Review this product manually; its components have conflicting timing preferences."
    ),
    "ambiguous_prefer_with": ("Choose the intended companion product before relying on co-location."),
    "missing_balance_substance": (
        "Review whether the paired balancing substance should be present in the active stack."
    ),
    "missing_support_substance": (
        "Review whether adding the supporting substance would improve this target in the active stack."
    ),
    "review_with_substance_present": (
        "Review this active pairing; the planner surfaces it for operator review and does not separate it by slot."
    ),
}

_ACTION_BY_TRAIT: dict[str, str] = {
    "risk:manual_review": ("Review this substance/product context manually before treating the schedule as final."),
    "risk:narrow_therapeutic_window": ("Review total daily amount across products and avoid accidental stacking."),
    "risk:hyperkalemia_med_interaction": ("Review potassium-related medication context before using this stack."),
}

_ACTION_BY_RELATION: dict[str, str] = {
    "competes": ("Keep these substances away from the same slot when they are in separate products."),
}


def warning_action(warning_type: str, trait_id: str, relation_type: str) -> str:
    if warning_type in _ACTION_BY_TYPE:
        return _ACTION_BY_TYPE[warning_type]
    if trait_id in _ACTION_BY_TRAIT:
        return _ACTION_BY_TRAIT[trait_id]
    if relation_type in _ACTION_BY_RELATION:
        return _ACTION_BY_RELATION[relation_type]
    return "Review this warning before treating the schedule as final."
