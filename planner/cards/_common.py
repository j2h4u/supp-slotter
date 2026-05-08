"""Shared low-level helpers: card loading, slugs, similarity, graph utils."""

from __future__ import annotations

import secrets
from difflib import SequenceMatcher
from pathlib import Path

import yaml

from planner.io import NANOID_ALPHABET, STABLE_ID_SIZE, load_yaml


def load_card(path: Path, kind: str) -> tuple[dict | None, str | None]:
    """Load a YAML mapping card. Returns (data, error_message). Either is None."""
    if not path.exists():
        return None, f"{path}: file does not exist"
    try:
        card = load_yaml(path)
    except yaml.YAMLError as e:
        return None, f"{path}: yaml parse error: {e}"
    if card is None:
        return None, f"{path}: empty file"
    if not isinstance(card, dict):
        return None, (
            f"{path}: {kind} top-level must be a mapping, "
            f"got {type(card).__name__}"
        )
    return card, None

def normalize_filename_part(value: str) -> str:
    normalized = value.lower().replace("&", " and ").replace("'", "").replace("’", "")
    chars = [char if char.isascii() and char.isalnum() else "_" for char in normalized]
    return "_".join(part for part in "".join(chars).split("_") if part)

def normalize_similarity_text(value: str) -> str:
    normalized = value.lower().replace("&", " and ").replace("'", "").replace("’", "")
    chars = [char if char.isascii() and char.isalnum() else " " for char in normalized]
    return " ".join("".join(chars).split())

def generate_stable_id(prefix: str) -> str:
    token = "".join(secrets.choice(NANOID_ALPHABET) for _ in range(STABLE_ID_SIZE))
    return f"{prefix}_{token}"

def similarity_score(
    left_terms: list[tuple[str, bool]],
    right_terms: list[tuple[str, bool]],
) -> float:
    scores: list[float] = []
    for left, left_primary in left_terms:
        for right, right_primary in right_terms:
            if left == right:
                if left_primary or right_primary:
                    return 1.0
                continue
            if left_primary and right_primary:
                scores.append(SequenceMatcher(None, left, right).ratio())
    return max(scores) if scores else 0.0

def connected_components(edges: dict[str, set[str]]) -> list[list[str]]:
    seen: set[str] = set()
    components: list[list[str]] = []

    for node in sorted(edges):
        if node in seen:
            continue
        stack = [node]
        component: list[str] = []
        seen.add(node)
        while stack:
            current = stack.pop()
            component.append(current)
            for next_node in sorted(edges[current]):
                if next_node in seen:
                    continue
                seen.add(next_node)
                stack.append(next_node)
        if len(component) > 1:
            components.append(sorted(component))
    return components

