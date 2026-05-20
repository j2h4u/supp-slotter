"""Substance duplicate/similarity clustering."""

from __future__ import annotations

from planner.cards._common import (
    connected_components,
    normalize_similarity_text,
    similarity_score,
)
from planner.cards.substance import format_substance_name
from planner.contracts import Substance
from planner.domain_constants import SIMILAR_SUBSTANCE_THRESHOLD


def format_substance_candidate(substance_id: str, substance: Substance) -> str:
    return f"{substance_id} {format_substance_name(substance)}"


def substance_similarity_terms(substance: Substance) -> list[tuple[str, bool]]:
    terms: list[tuple[str, bool]] = []
    if substance.form:
        terms.append((f"{substance.name} {substance.form}", True))
    else:
        terms.append((substance.name, True))
    for alias in substance.aliases:
        terms.append((alias, False))

    normalized_terms: list[tuple[str, bool]] = []
    for term, is_primary in terms:
        normalized = normalize_similarity_text(term)
        normalized_entry = (normalized, is_primary)
        if normalized and normalized_entry not in normalized_terms:
            normalized_terms.append(normalized_entry)
    return normalized_terms


def substance_name_key(substance: Substance) -> str:
    return normalize_similarity_text(substance.name)


def substance_cluster_label(
    substances: dict[str, Substance], component: list[str]
) -> str:
    name_counts: dict[str, int] = {}
    display_names: dict[str, str] = {}
    for substance_id in component:
        substance = substances[substance_id]
        name_key = substance_name_key(substance)
        if not name_key:
            continue
        name_counts[name_key] = name_counts.get(name_key, 0) + 1
        display_names.setdefault(name_key, _substance_fallback_name(substance))

    if name_counts:
        best_key = sorted(
            name_counts,
            key=lambda key: (-name_counts[key], display_names[key].casefold()),
        )[0]
        return display_names[best_key]

    return _substance_fallback_name(substances[component[0]])


def collect_similar_substances(substances: dict[str, Substance]) -> list[str]:
    clusters: list[str] = []
    substance_items = sorted(substances.items())
    terms_by_id = {
        substance_id: substance_similarity_terms(substance)
        for substance_id, substance in substance_items
    }
    edges: dict[str, set[str]] = {substance_id: set() for substance_id in substances}

    for index, (left_id, left_substance) in enumerate(substance_items):
        for right_id, right_substance in substance_items[index + 1 :]:
            score = similarity_score(terms_by_id[left_id], terms_by_id[right_id])
            if score < SIMILAR_SUBSTANCE_THRESHOLD:
                continue
            if _is_expected_form_variant_pair(left_substance, right_substance):
                continue
            edges[left_id].add(right_id)
            edges[right_id].add(left_id)

    for component in connected_components(edges):
        label = substance_cluster_label(substances, component)
        entries = [
            format_substance_candidate(substance_id, substances[substance_id])
            for substance_id in component
        ]
        cluster_lines = [label]
        cluster_lines.extend(f"    - {entry}" for entry in sorted(entries, key=str.casefold))
        clusters.append("\n".join(cluster_lines))

    return sorted(clusters, key=lambda cluster: cluster.splitlines()[0].casefold())


def _substance_fallback_name(substance: Substance) -> str:
    return substance.name or substance.id or "Unknown substance"


def _is_expected_form_variant_pair(
    left: Substance,
    right: Substance,
) -> bool:
    left_name = substance_name_key(left)
    right_name = substance_name_key(right)
    left_form = normalize_similarity_text(left.form or "")
    right_form = normalize_similarity_text(right.form or "")
    if not left_form or not right_form:
        return False

    if left_name == right_name:
        return left_form != right_form

    name_score = similarity_score([(left_name, True)], [(right_name, True)])
    return name_score < SIMILAR_SUBSTANCE_THRESHOLD
