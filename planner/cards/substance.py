"""Substance cards: loading, slugs, search, similarity, validation, formatting."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, cast

from planner.cards._common import (
    connected_components,
    load_card_mapping,
    normalize_filename_part,
    normalize_similarity_text,
    similarity_score,
)
from planner.cards.search import collect_search_strings, combined_search_score
from planner.contracts import CardLoadError, Substance
from planner.io import (
    FIND_MIN_SCORE,
    SIMILAR_SUBSTANCE_THRESHOLD,
    SUBSTANCES_DIR,
    schema_errors,
)


def load_substance(path: Path) -> Substance:
    """Load a substance card into a Substance dataclass.

    Raises CardLoadError on missing file, parse error, schema violation, or
    missing required field.
    """
    data = load_card_mapping(path, "substance")
    errors = schema_errors(data, "substance", path)
    if errors:
        raise CardLoadError(path, errors[0])
    try:
        return Substance(
            id=data["id"],
            name=data["name"],
            traits=tuple(data.get("traits") or ()),
            form=data.get("form"),
            aliases=tuple(data.get("aliases") or ()),
            notes=data.get("notes"),
            unmatched_concerns=tuple(data.get("unmatched_concerns") or ()),
            prefer_with=tuple(data.get("prefer_with") or ()),
        )
    except KeyError as e:
        raise CardLoadError(path, f"{path}: missing required field {e}") from e


def substance_slug(substance: Substance) -> str:
    if substance.form:
        return normalize_filename_part(f"{substance.name} {substance.form}")
    return normalize_filename_part(substance.name)


def canonical_substance_filename(substance: Substance) -> str:
    return f"{substance_slug(substance)}__{substance.id}.yaml"


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


def substance_display_name(substance: Substance) -> str:
    return substance.name or substance.id or "Unknown substance"


def find_substance_results(query: str) -> list[tuple[float, str, str, Path]]:
    results: list[tuple[float, str, str, Path]] = []
    for path in sorted(SUBSTANCES_DIR.glob("*.yaml")):
        try:
            substance = load_substance(path)
        except CardLoadError as e:
            print(f"warning: skipping substance card: {e.message}", file=sys.stderr)
            continue
        identity_values = [
            substance.id,
            substance.name,
            substance.form or "",
            path.name,
        ]
        identity_values.extend(substance.aliases)
        full_values = collect_search_strings(substance)
        full_values.append(path.name)
        score = combined_search_score(query, identity_values, full_values)
        if score >= FIND_MIN_SCORE:
            results.append(
                (score, substance.id, format_substance_name(substance), path)
            )
    return sorted(results, key=lambda item: (-item[0], item[2].casefold(), item[1]))


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
        display_names.setdefault(name_key, substance_display_name(substance))

    if name_counts:
        best_key = sorted(
            name_counts,
            key=lambda key: (-name_counts[key], display_names[key].casefold()),
        )[0]
        return display_names[best_key]

    return substance_display_name(substances[component[0]])


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
            same_name = bool(substance_name_key(left_substance)) and (
                substance_name_key(left_substance) == substance_name_key(right_substance)
            )
            score = similarity_score(terms_by_id[left_id], terms_by_id[right_id])
            if not same_name and score < SIMILAR_SUBSTANCE_THRESHOLD:
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


def check_substances(
    substance_files: list[Path],
    trait_ids: set[str],
    *,
    prefer_with_registry: dict[str, Path] | None = None,
) -> tuple[list[str], list[str], dict[str, Path]]:
    """Returns (errors, info, substance_ids_to_path_map)."""
    errors: list[str] = []
    info: list[str] = []
    seen_ids: dict[str, Path] = {}
    prefer_with_refs: list[tuple[Path, str, str]] = []

    for sf in substance_files:
        try:
            substance = load_card_mapping(sf, "substance")
        except CardLoadError as e:
            errors.append(e.message)
            continue

        errors.extend(schema_errors(substance, "substance", sf))

        sid_raw = substance.get("id")
        if isinstance(sid_raw, str):
            sid: str = sid_raw
            name_raw = substance.get("name")
            form_raw = substance.get("form")
            expected_filename = canonical_substance_filename(
                Substance(
                    id=sid,
                    name=name_raw if isinstance(name_raw, str) else "",
                    traits=(),
                    form=form_raw if isinstance(form_raw, str) else None,
                )
            )
            if sf.name != expected_filename:
                errors.append(
                    f"{sf}: substance filename must be '{expected_filename}'"
                )
            if sid in seen_ids:
                errors.append(
                    f"{sf}: duplicate id '{sid}' (also in {seen_ids[sid]})"
                )
            else:
                seen_ids[sid] = sf

            prefer_with_raw: Any = substance.get("prefer_with") or []
            prefer_with_list = cast(list[Any], prefer_with_raw)
            for other in prefer_with_list:
                if other == sid:
                    errors.append(
                        f"{sf}: prefer_with references self ('{sid}')"
                    )
                elif isinstance(other, str):
                    prefer_with_refs.append((sf, sid, other))

            traits_raw: Any = substance.get("traits") or []
            traits_list = cast(list[Any], traits_raw)
            for tid in traits_list:
                if tid not in trait_ids:
                    errors.append(f"{sf}: trait '{tid}' not defined in traits.yaml")

            concerns_raw: Any = substance.get("unmatched_concerns") or []
            concerns_list = cast(list[Any], concerns_raw)
            for concern in concerns_list:
                info.append(f"{sf}: unmatched_concern: {concern}")

    target_ids = prefer_with_registry or seen_ids
    for sf, _source, target in prefer_with_refs:
        if target not in target_ids:
            errors.append(
                f"{sf}: prefer_with target '{target}' has no matching substance card"
            )
    return errors, info, seen_ids


def substance_names(substances: dict[str, Substance]) -> set[str]:
    return {s.name for s in substances.values() if s.name}


def collect_active_substance_names(
    substances: dict[str, Substance],
    active_substances: set[str],
) -> set[str]:
    names: set[str] = set()
    for substance_id in active_substances:
        substance = substances.get(substance_id)
        if substance is None:
            continue
        if substance.name:
            names.add(substance.name)
    return names


def substance_is_covered_by_active_name(
    substance_id: str,
    substances: dict[str, Substance],
    active_names: set[str],
) -> bool:
    substance = substances.get(substance_id)
    return substance is not None and substance.name in active_names


def load_substance_registry() -> dict[str, Substance]:
    substances: dict[str, Substance] = {}
    for sf in sorted(SUBSTANCES_DIR.glob("*.yaml")):
        try:
            substance = load_substance(sf)
        except CardLoadError as e:
            print(f"warning: skipping substance card: {e.message}", file=sys.stderr)
            continue
        substances[substance.id] = substance
    return substances


def format_substance_name(substance: Substance) -> str:
    name = substance.name or substance.id or "unknown"
    if substance.form:
        return f"{name} ({substance.form})"
    return name
