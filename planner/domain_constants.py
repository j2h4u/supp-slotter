"""Domain constants for card validation, scoring, and warning labels."""

from __future__ import annotations

VALID_LEVELS = {"avoid_strong", "avoid", "prefer", "prefer_strong"}
REGISTERED_NAMESPACES = {
    "intake",
    "timing",
    "is",
    "risk",
    "activity",
    "dashboard",
    "pathway",
}
SLOT_META_FIELDS = {"label", "order"}

LEVEL_SCORES = {
    "prefer_strong": 4,
    "prefer": 2,
    "avoid": -2,
    "avoid_strong": -4,
}

# A primary component's preference must always beat a secondary component's
# preference; this is half of the derived upper bound for the worst case.
SECONDARY_TRAIT_WEIGHT = (
    LEVEL_SCORES["prefer"] - LEVEL_SCORES["avoid"]
) / (4 * LEVEL_SCORES["prefer_strong"])

BALANCE_WEIGHT = 0.5
PREFER_WITH_BONUS = 3
NANOID_ALPHABET = "0123456789abcdefghijklmnopqrstuvwxyz"
STABLE_ID_SIZE = 10
SIMILAR_SUBSTANCE_THRESHOLD = 0.86
FIND_MIN_SCORE = 0.55
FIND_MIN_WORD_SCORE = 0.65

WARNING_CATEGORY_LABELS = {
    "intra_product_relation_conflict": "Component conflict inside one product",
    "intra_product_trait_conflict": "Timing conflict inside one product",
    "ambiguous_prefer_with": "Companion product is ambiguous",
    "missing_balance_substance": "Missing balancing substance",
    "missing_support_substance": "Missing supporting substance",
    "antagonizes_substance_present": "Active antagonist pairing",
    "safety_concern": "Safety concern",
    "risk_cluster_load": "Risk load",
}

REVIEW_CONTEXTS = {
    "bleeding_context": "Bleeding context",
    "blood_pressure": "Blood pressure / vasodilation",
    "cholinergic_load": "Cholinergic load",
    "intra_product_conflicts": "Intra-product conflicts",
    "missing_pairings": "Missing balance/support pairings",
    "narrow_window_minerals": "Narrow-window minerals",
    "potassium_medication": "Potassium / medication context",
    "timing_conflicts": "Timing conflicts",
    "safety_concerns": "Safety concerns",
}
