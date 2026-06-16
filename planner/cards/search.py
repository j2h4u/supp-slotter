"""Multi-word search and similarity scoring helpers."""

from __future__ import annotations

import dataclasses
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any, cast

from planner.cards._common import normalize_similarity_text
from planner.domain_constants import FIND_MIN_WORD_SCORE
from planner.paths import display_path

SUBSTRING_MATCH_MIN_LENGTH_RATIO = 0.65
EXACT_TEXT_MATCH_SCORE = 0.98
SECONDARY_FIELD_ONLY_SCORE_WEIGHT = 0.75


def collect_search_strings(value: object) -> list[str]:
    """Recursively collect all string leaf values from a dataclass, dict, list, or tuple — used to build a flat search corpus."""
    strings: list[str] = []
    if isinstance(value, str):
        strings.append(value)
    elif dataclasses.is_dataclass(value) and not isinstance(value, type):
        for field in dataclasses.fields(value):
            strings.extend(collect_search_strings(getattr(value, field.name)))
    elif isinstance(value, dict):
        for child in cast(dict[Any, Any], value).values():
            strings.extend(collect_search_strings(child))
    elif isinstance(value, (list, tuple)):
        for child in cast(list[Any] | tuple[Any, ...], value):
            strings.extend(collect_search_strings(child))
    return strings


def search_words(values: list[str]) -> set[str]:
    """Tokenise each value via `normalize_similarity_text` and return the union of all words for word-level search matching."""
    words: set[str] = set()
    for value in values:
        words.update(normalize_similarity_text(value).split())
    return words


def word_match_score(query_word: str, candidate_words: set[str]) -> float:
    if query_word in candidate_words:
        return 1.0

    scores: list[float] = []
    for candidate_word in candidate_words:
        shorter = min(len(query_word), len(candidate_word))
        longer = max(len(query_word), len(candidate_word))
        length_ratio = shorter / longer if longer else 0
        if length_ratio >= SUBSTRING_MATCH_MIN_LENGTH_RATIO and (
            query_word in candidate_word or candidate_word in query_word
        ):
            scores.append(0.9)
        else:
            scores.append(SequenceMatcher(None, query_word, candidate_word).ratio())
    return max(scores) if scores else 0.0


def search_score(query: str, values: list[str]) -> float:
    """Score how well query matches values using AND-gate word semantics.

    Returns 0.0 if any single query word scores below FIND_MIN_WORD_SCORE — the result is
    not an average over partial matches. All words in the query must individually match
    above the threshold for a non-zero score to be returned.
    """
    query_text = normalize_similarity_text(query)
    query_words = query_text.split()
    if not query_words:
        return 0.0

    candidate_text = normalize_similarity_text(" ".join(values))
    candidate_words = search_words(values)
    word_scores = [word_match_score(query_word, candidate_words) for query_word in query_words]
    if min(word_scores) < FIND_MIN_WORD_SCORE:
        return 0.0
    score = sum(word_scores) / len(word_scores)
    if query_text and query_text in candidate_text:
        score = max(score, EXACT_TEXT_MATCH_SCORE)
    return score


def combined_search_score(
    query: str,
    identity_values: list[str],
    full_values: list[str],
) -> float:
    """Combine identity-field score and full-field score with an asymmetric penalty.

    When identity_score > 0: returns max(identity_score, full_score) — full context can
    only help, never hurt.
    When identity_score == 0: returns full_score * 0.75 — a 25% penalty applied to
    matches that hit only secondary fields (notes, aliases, components) without matching
    the primary identity fields (id, name).
    """
    identity_score = search_score(query, identity_values)
    full_score = search_score(query, full_values)
    if identity_score > 0:
        return max(identity_score, full_score)
    return full_score * SECONDARY_FIELD_ONLY_SCORE_WEIGHT


def format_find_result(score: float, card_id: str, label: str, path: Path) -> str:
    return f"  {score:.2f}  {card_id}  {label}\n        {display_path(path)}"
