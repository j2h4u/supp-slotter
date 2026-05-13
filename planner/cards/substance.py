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
from planner.contracts import CardLoadError, Concern, Substance
from planner.io import (
    DASHBOARDS_DIR,
    FIND_MIN_SCORE,
    SIMILAR_SUBSTANCE_THRESHOLD,
    SUBSTANCES_DIR,
    schema_errors,
)


def load_substance(path: Path) -> Substance:
    """Load a substance card into a Substance dataclass (v2 nested shape only).

    Raises CardLoadError on missing file, parse error, schema violation, or
    missing required field. The schema's additionalProperties: false is the
    sole gate against flat-form (v1) keys — no explicit discriminator needed.
    """
    data = load_card_mapping(path, "substance")
    errors = schema_errors(data, "substance", path)
    if errors:
        raise CardLoadError(path, errors[0])
    sched: dict[str, Any] = cast(dict[str, Any], data.get("schedule") or {})
    know: dict[str, Any] = cast(dict[str, Any], data.get("knowledge") or {})
    try:
        return Substance(
            id=data["id"],
            name=data["name"],
            form=data.get("form"),
            aliases=tuple(data.get("aliases") or ()),
            notes=data.get("notes"),
            concerns=tuple(
                Concern(kind=cast(dict[str, Any], c)["kind"], text=cast(dict[str, Any], c)["text"])
                for c in cast(list[Any], data.get("concerns") or [])
                if isinstance(c, dict)
            ),
            intake=tuple(cast(list[Any], sched.get("intake") or ())),
            timing=tuple(cast(list[Any], sched.get("timing") or ())),
            activity=tuple(cast(list[Any], sched.get("activity") or ())),
            prefer_with=tuple(cast(list[Any], sched.get("prefer_with") or ())),
            is_=tuple(cast(list[Any], know.get("is") or ())),
            effect=tuple(cast(list[Any], know.get("effect") or ())),
            risk=tuple(cast(list[Any], know.get("risk") or ())),
            dashboard=tuple(cast(list[Any], know.get("dashboard") or ())),
            pathway=tuple(cast(list[Any], know.get("pathway") or ())),
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


def _substance_fallback_name(substance: Substance) -> str:
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
        display_names.setdefault(name_key, _substance_fallback_name(substance))

    if name_counts:
        best_key = sorted(
            name_counts,
            key=lambda key: (-name_counts[key], display_names[key].casefold()),
        )[0]
        return display_names[best_key]

    return _substance_fallback_name(substances[component[0]])


def collect_similar_substances(substances: dict[str, Substance]) -> list[str]:
    """Build connected components of substances whose primary names or aliases score above the dedup threshold, then format each component as a labelled cluster string."""
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
    """Validate substance cards for schema conformance, canonical filenames, duplicate ids, and prefer_with cross-references; returns (errors, info, id→path map).

    When `prefer_with_registry` is provided, prefer_with targets are validated against that external map of known ids; otherwise they are validated against the in-batch `seen_ids` map only.
    """
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

            # v2 shape: prefer_with lives under schedule:
            sched_raw: dict[str, Any] = cast(dict[str, Any], substance.get("schedule") or {})
            know_raw: dict[str, Any] = cast(dict[str, Any], substance.get("knowledge") or {})
            prefer_with_raw: Any = sched_raw.get("prefer_with") or []
            prefer_with_list = cast(list[Any], prefer_with_raw)
            for other in prefer_with_list:
                if other == sid:
                    errors.append(
                        f"{sf}: prefer_with references self ('{sid}')"
                    )
                elif isinstance(other, str):
                    prefer_with_refs.append((sf, sid, other))

            # Validate scheduling traits (must be registered in traits.yaml).
            for namespace in ("intake", "timing", "activity"):
                ns_raw: Any = sched_raw.get(namespace) or []
                ns_list = cast(list[Any], ns_raw)
                for slug in ns_list:
                    if not isinstance(slug, str):
                        continue
                    full_id = f"{namespace}:{slug}"
                    if full_id not in trait_ids:
                        errors.append(
                            f"{sf}: Unknown trait '{slug}' under namespace '{namespace}:' "
                            f"— register it in data/traits.yaml under '{namespace}:' first "
                            f"(with label and description)."
                        )

            # Validate reviewer traits: is: and dashboard: require registration;
            # effect:, risk:, pathway: are operator-curated — skip trait_ids lookup.
            for namespace in ("is", "dashboard"):
                ns_raw = know_raw.get(namespace) or []
                ns_list = cast(list[Any], ns_raw)
                for slug in ns_list:
                    if not isinstance(slug, str):
                        continue
                    if namespace == "dashboard":
                        if not (DASHBOARDS_DIR / f"{slug}.yaml").exists():
                            errors.append(
                                f"{sf}: Unknown dashboard cluster '{slug}' — "
                                f"create data/dashboards/{slug}.yaml first."
                            )
                    else:
                        full_id = f"{namespace}:{slug}"
                        if full_id not in trait_ids:
                            errors.append(
                                f"{sf}: Unknown trait '{slug}' under namespace '{namespace}:' "
                                f"— register it in data/traits.yaml under '{namespace}:' first "
                                f"(with label and description)."
                            )

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


def load_substance_registry() -> dict[str, Substance]:
    substances: dict[str, Substance] = {}
    paths = sorted(SUBSTANCES_DIR.glob("*.yaml"))
    skipped = 0
    for sf in paths:
        try:
            substance = load_substance(sf)
        except CardLoadError as e:
            print(f"warning: skipping substance card: {e.message}", file=sys.stderr)
            skipped += 1
            continue
        substances[substance.id] = substance
    if skipped:
        print(
            f"warning: loaded {len(substances)}/{len(paths)} substance cards; {skipped} skipped",
            file=sys.stderr,
        )
    return substances


def format_substance_name(substance: Substance) -> str:
    name = substance.name or substance.id or "unknown"
    if substance.form:
        return f"{name} ({substance.form})"
    return name
