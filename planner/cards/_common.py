"""Shared low-level helpers: card loading, slugs, similarity, graph utils."""

from __future__ import annotations

import secrets
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

import yaml

from planner.contracts import CardLoadError
from planner.io import NANOID_ALPHABET, STABLE_ID_SIZE, load_yaml_mapping


def load_card_mapping(path: Path, kind: str) -> dict[str, Any]:
    """Load a YAML card and return its top-level mapping.

    Raises CardLoadError on any failure (missing file, parse error, non-mapping).
    """
    if not path.exists():
        raise CardLoadError(path, f"{path}: file does not exist")
    try:
        return load_yaml_mapping(path)
    except yaml.YAMLError as e:
        raise CardLoadError(path, f"{path}: yaml parse error: {e}") from e
    except CardLoadError as e:
        raise CardLoadError(
            path, f"{path}: {kind} top-level must be a mapping, {e.message}"
        ) from e


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
    """Return the max SequenceMatcher ratio across primary-term pairs; returns 1.0 on exact match of any term where at least one side is primary."""
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
    """Return non-trivial connected components of an undirected graph (singletons are dropped).

    The graph is given as an adjacency dict mapping node → set of neighbors. Each
    returned component is a sorted list of node names; only components with more
    than one node are returned.
    """
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
