"""Substance duplicate/similarity clustering."""

from __future__ import annotations

from itertools import combinations

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
    return _deduplicate_similarity_terms(_raw_similarity_terms(substance))


def _raw_similarity_terms(substance: Substance) -> list[tuple[str, bool]]:
    primary = f"{substance.name} {substance.form}" if substance.form else substance.name
    return [(primary, True), *((alias, False) for alias in substance.aliases)]


def _deduplicate_similarity_terms(terms: list[tuple[str, bool]]) -> list[tuple[str, bool]]:
    return list(
        dict.fromkeys(
            (normalized, is_primary) for term, is_primary in terms if (normalized := normalize_similarity_text(term))
        )
    )


def substance_name_key(substance: Substance) -> str:
    return normalize_similarity_text(substance.name)


def substance_cluster_label(substances: dict[str, Substance], component: list[str]) -> str:
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
    substance_items = sorted(substances.items())
    edges = _similarity_edges(substance_items)
    return sorted(
        (_format_similarity_cluster(substances, component) for component in connected_components(edges)),
        key=lambda cluster: cluster.splitlines()[0].casefold(),
    )


def _similarity_edges(items: list[tuple[str, Substance]]) -> dict[str, set[str]]:
    terms_by_id = {substance_id: substance_similarity_terms(substance) for substance_id, substance in items}
    edges: dict[str, set[str]] = {substance_id: set() for substance_id, _ in items}
    for (left_id, left_substance), (right_id, right_substance) in combinations(items, 2):
        if _is_similar_pair(left_id, right_id, left_substance, right_substance, terms_by_id):
            edges[left_id].add(right_id)
            edges[right_id].add(left_id)
    return edges


def _is_similar_pair(
    left_id: str,
    right_id: str,
    left: Substance,
    right: Substance,
    terms_by_id: dict[str, list[tuple[str, bool]]],
) -> bool:
    return similarity_score(
        terms_by_id[left_id], terms_by_id[right_id]
    ) >= SIMILAR_SUBSTANCE_THRESHOLD and not _is_expected_form_variant_pair(left, right)


def _format_similarity_cluster(substances: dict[str, Substance], component: list[str]) -> str:
    label = substance_cluster_label(substances, component)
    entries = sorted(
        (format_substance_candidate(substance_id, substances[substance_id]) for substance_id in component),
        key=str.casefold,
    )
    return "\n".join([label, *(f"    - {entry}" for entry in entries)])


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
    return _forms_are_expected_variants(left_name, right_name, left_form, right_form)


def _forms_are_expected_variants(left_name: str, right_name: str, left_form: str, right_form: str) -> bool:
    if not left_form or not right_form:
        return False
    if left_name == right_name:
        return left_form != right_form
    return similarity_score([(left_name, True)], [(right_name, True)]) < SIMILAR_SUBSTANCE_THRESHOLD
