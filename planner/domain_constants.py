"""Domain constants for card validation, scoring, and warning labels."""

from __future__ import annotations

SLOT_META_FIELDS = {"label", "order"}

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
    "review_with_substance_present": "Active review pairing",
    "safety_concern": "Safety concern",
    "risk_cluster_load": "Risk load",
}
