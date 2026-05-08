"""Multi-word search and similarity scoring helpers."""

from __future__ import annotations

from difflib import SequenceMatcher
from pathlib import Path

from planner.io import FIND_MIN_WORD_SCORE, display_path
from planner.cards._common import normalize_similarity_text


def collect_search_strings(value: object) -> list[str]:
    strings: list[str] = []
    if isinstance(value, str):
        strings.append(value)
    elif isinstance(value, dict):
        for child in value.values():
            strings.extend(collect_search_strings(child))
    elif isinstance(value, list):
        for child in value:
            strings.extend(collect_search_strings(child))
    return strings

def search_words(values: list[str]) -> set[str]:
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
        if (
            length_ratio >= 0.65
            and (query_word in candidate_word or candidate_word in query_word)
        ):
            scores.append(0.9)
        else:
            scores.append(SequenceMatcher(None, query_word, candidate_word).ratio())
    return max(scores) if scores else 0.0

def search_score(query: str, values: list[str]) -> float:
    query_text = normalize_similarity_text(query)
    query_words = query_text.split()
    if not query_words:
        return 0.0

    candidate_text = normalize_similarity_text(" ".join(values))
    candidate_words = search_words(values)
    word_scores = [
        word_match_score(query_word, candidate_words)
        for query_word in query_words
    ]
    if min(word_scores) < FIND_MIN_WORD_SCORE:
        return 0.0
    score = sum(word_scores) / len(word_scores)
    if query_text and query_text in candidate_text:
        score = max(score, 0.98)
    return score

def combined_search_score(
    query: str,
    identity_values: list[str],
    full_values: list[str],
) -> float:
    identity_score = search_score(query, identity_values)
    full_score = search_score(query, full_values)
    if identity_score > 0:
        return max(identity_score, full_score)
    return full_score * 0.75

def format_find_result(score: float, card_id: str, label: str, path: Path) -> str:
    return f"  {score:.2f}  {card_id}  {label}\n        {display_path(path)}"

