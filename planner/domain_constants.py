"""Domain constants for card validation, scoring, and warning labels."""

from __future__ import annotations

SLOT_META_FIELDS = {"label", "order"}

NANOID_ALPHABET = "0123456789abcdefghijklmnopqrstuvwxyz"
STABLE_ID_SIZE = 10
SIMILAR_SUBSTANCE_THRESHOLD = 0.86
FIND_MIN_SCORE = 0.55
FIND_MIN_WORD_SCORE = 0.65
