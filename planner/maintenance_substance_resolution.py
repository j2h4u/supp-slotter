"""Resolve draft product component substance names to stable substance IDs."""

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

from planner.card_ids import is_substance_id
from planner.cards._common import load_card_mapping, normalize_similarity_text
from planner.cards.search import search_score
from planner.contracts import CardLoadError
from planner.paths import strip_root_prefix


@dataclass(frozen=True, slots=True)
class SubstanceIdentity:
    substance_id: str
    label: str
    path: Path
    terms: tuple[str, ...]


def product_has_draft_component_ref(product: dict[str, Any]) -> bool:
    for component_obj in cast(list[Any], product.get("components") or []):
        if not isinstance(component_obj, dict):
            continue
        component = cast(dict[str, Any], component_obj)
        ref = component.get("substance")
        if isinstance(ref, str) and not is_substance_id(ref):
            return True
    return False


def resolve_product_component_refs(
    *,
    product_path: Path,
    product: dict[str, Any],
    substances_dir: Path,
    substance_renames: dict[str, str],
    errors: list[str],
) -> bool:
    identities = _load_substance_identities(substances_dir, substance_renames, errors)
    if not identities:
        return False
    index = _identity_index(identities)

    changed = False
    for index_number, component_obj in enumerate(cast(list[Any], product.get("components") or [])):
        if not isinstance(component_obj, dict):
            continue
        component = cast(dict[str, Any], component_obj)
        ref = component.get("substance")
        if not isinstance(ref, str) or is_substance_id(ref):
            continue

        candidates = index.get(normalize_similarity_text(ref), {})
        if len(candidates) == 1:
            component["substance"] = next(iter(candidates))
            changed = True
            continue
        if not candidates:
            _append_resolution_error(
                errors,
                _unknown_ref_message(product_path, index_number, ref, identities),
            )
            continue
        _append_resolution_error(
            errors,
            _ambiguous_ref_message(product_path, index_number, ref, candidates),
        )
    return changed


def _load_substance_identities(
    substances_dir: Path,
    substance_renames: dict[str, str],
    errors: list[str],
) -> list[SubstanceIdentity]:
    identities: list[SubstanceIdentity] = []
    for path in sorted(substances_dir.glob("*.yaml")):
        try:
            card = load_card_mapping(path, "substance")
        except CardLoadError as e:
            _append_resolution_error(errors, f"auto-maintenance: could not read {strip_root_prefix(e.message)}")
            continue

        substance_id_raw = card.get("id")
        substance_id = substance_id_raw if isinstance(substance_id_raw, str) else substance_renames.get(path.stem)
        if substance_id is None:
            continue
        identities.append(_substance_identity(path, card, substance_id))
    return identities


def _substance_identity(
    path: Path,
    card: dict[str, Any],
    substance_id: str,
) -> SubstanceIdentity:
    name_raw = card.get("name")
    form_raw = card.get("form")
    name = name_raw if isinstance(name_raw, str) else substance_id
    form = form_raw if isinstance(form_raw, str) else None
    label = f"{name} ({form})" if form else name

    terms = [substance_id, name, _stem_without_id(path)]
    if form:
        terms.extend((f"{name} {form}", f"{name} ({form})"))
    aliases_obj = card.get("aliases")
    aliases: list[Any] = cast(list[Any], aliases_obj) if isinstance(aliases_obj, list) else []
    for alias in aliases:
        if not isinstance(alias, str):
            continue
        terms.append(alias)
        if form:
            terms.append(f"{alias} {form}")
    return SubstanceIdentity(
        substance_id=substance_id,
        label=label,
        path=path,
        terms=tuple(term for term in terms if term),
    )


def _stem_without_id(path: Path) -> str:
    stem = path.stem
    if "__sub_" in stem:
        return stem.split("__sub_", 1)[0]
    return stem


def _identity_index(
    identities: list[SubstanceIdentity],
) -> dict[str, dict[str, SubstanceIdentity]]:
    index: dict[str, dict[str, SubstanceIdentity]] = {}
    for identity in identities:
        for term in identity.terms:
            key = normalize_similarity_text(term)
            if not key:
                continue
            index.setdefault(key, {})[identity.substance_id] = identity
    return index


def _unknown_ref_message(
    path: Path,
    index_number: int,
    ref: str,
    identities: list[SubstanceIdentity],
) -> str:
    candidates = _candidate_labels(ref, identities)
    candidate_text = f" Candidates: {', '.join(candidates)}." if candidates else ""
    return (
        f"{path}: components[{index_number}].substance '{ref}' could not be resolved "
        f"to a unique substance. Use an exact substance name+form, alias, filename stem, "
        f"or explicit sub_* ID.{candidate_text}"
    )


def _ambiguous_ref_message(
    path: Path,
    index_number: int,
    ref: str,
    candidates: dict[str, SubstanceIdentity],
) -> str:
    labels = [
        f"{identity.substance_id} {identity.label}"
        for identity in sorted(candidates.values(), key=lambda item: item.label.casefold())
    ]
    return (
        f"{path}: components[{index_number}].substance '{ref}' is ambiguous: "
        f"{', '.join(labels)}. Use a more specific name+form or explicit sub_* ID."
    )


def _candidate_labels(ref: str, identities: list[SubstanceIdentity]) -> list[str]:
    scored: list[tuple[float, str]] = []
    for identity in identities:
        score = search_score(ref, list(identity.terms))
        if score > 0:
            scored.append((score, f"{identity.substance_id} {identity.label}"))
    return [label for _score, label in sorted(scored, key=lambda item: (-item[0], item[1].casefold()))[:5]]


def _append_resolution_error(errors: list[str], message: str) -> None:
    errors.append(message)
    print(f"ERROR: {strip_root_prefix(message)}", file=sys.stderr)
