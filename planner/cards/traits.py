"""Trait definitions: flattening, validation, and rendering helpers."""

from __future__ import annotations

from pathlib import Path
from typing import Any, cast

from planner.cards._common import load_card_mapping
from planner.contracts import (
    CardLoadError,
    SlotNear,
    TraitDef,
    TraitEffect,
    TraitEffectMatch,
)
from planner.io import REGISTERED_NAMESPACES


def _build_trait_effect(effect: dict[str, Any]) -> TraitEffect:
    match_raw = effect.get("match") if isinstance(effect.get("match"), dict) else {}
    if not isinstance(match_raw, dict):
        match_raw = {}
    near_raw = match_raw.get("near")
    food_raw = match_raw.get("food")
    return TraitEffect(
        match=TraitEffectMatch(
            near=cast(SlotNear, near_raw) if isinstance(near_raw, str) else None,
            food=food_raw if isinstance(food_raw, bool) else None,
        ),
        level=effect.get("level"),
        block=effect.get("block"),
    )


def load_traits(path: Path) -> dict[str, TraitDef]:
    """Load traits.yaml into a flat namespace:short -> TraitDef map.

    Raises CardLoadError on missing file, parse error, or non-mapping top-level.
    """
    data = load_card_mapping(path, "traits")
    out: dict[str, TraitDef] = {}
    for namespace, entries in data.items():
        if not isinstance(namespace, str) or not isinstance(entries, dict):
            continue
        for short_name, trait in entries.items():
            if not isinstance(short_name, str):
                continue
            if not isinstance(trait, dict):
                trait = {}
            tid = f"{namespace}:{short_name}"
            try:
                out[tid] = TraitDef(
                    id=tid,
                    namespace=namespace,
                    short_name=short_name,
                    label=trait.get("label") or "",
                    description=trait.get("description") or "",
                    applies_when=trait.get("applies_when") or "",
                    effects=tuple(
                        _build_trait_effect(e)
                        for e in trait.get("effects") or ()
                        if isinstance(e, dict)
                    ),
                    separate_from=tuple(trait.get("separate_from") or ()),
                    warning=bool(trait.get("warning")),
                    action=trait.get("action"),
                )
            except KeyError as e:
                raise CardLoadError(path, f"{path}: missing required field {e}") from e
    return out


def check_traits(
    trait_defs: dict[str, TraitDef], traits_path: Path
) -> list[str]:
    """Validate trait namespaces and separate_from references.

    Match-key validation is handled by JSON schema + TraitEffectMatch dataclass:
    the schema constrains match to {near, food} with additionalProperties: false,
    and TraitEffectMatch enforces those at load time.
    """
    errors: list[str] = []
    trait_ids = set(trait_defs)

    for trait_id, trait in trait_defs.items():
        if trait.namespace not in REGISTERED_NAMESPACES:
            errors.append(
                f"{traits_path}: trait '{trait_id}' uses unregistered namespace "
                f"'{trait.namespace}' (registered: {sorted(REGISTERED_NAMESPACES)})"
            )

        for sep in trait.separate_from:
            if sep not in trait_ids:
                errors.append(
                    f"{traits_path}: trait '{trait_id}' separate_from references "
                    f"unknown trait '{sep}'"
                )

    return errors


def grouped_trait_defs(
    trait_defs: dict[str, TraitDef],
) -> dict[str, list[TraitDef]]:
    groups: dict[str, list[TraitDef]] = {}
    for trait in sorted(trait_defs.values(), key=lambda t: t.id):
        groups.setdefault(trait.namespace, []).append(trait)
    return {ns: groups[ns] for ns in sorted(groups, key=str.casefold)}


def format_trait_effect(effect: TraitEffect) -> str:
    parts: list[str] = []
    if effect.match.near is not None:
        parts.append(f"near={effect.match.near}")
    if effect.match.food is not None:
        parts.append(f"food={effect.match.food}")
    match_text = " when " + ", ".join(sorted(parts)) if parts else ""
    if effect.block is True:
        return f"blocks slot{match_text}"
    if effect.level is not None:
        return f"{effect.level}{match_text}"
    return ""


def print_trait_details(trait: TraitDef) -> None:
    if trait.description:
        print(f"      {trait.description}")
    if trait.applies_when:
        print(f"      Applies when: {trait.applies_when}")
    if trait.warning:
        print("      Output: schedule warning")
    rendered = [format_trait_effect(effect) for effect in trait.effects]
    rendered = [text for text in rendered if text]
    if rendered:
        print("      Slot effects: " + "; ".join(rendered))


def readable_traits(trait_ids: set[str], trait_defs: dict[str, TraitDef]) -> list[str]:
    labels: list[str] = []
    for trait_id in sorted(trait_ids):
        if trait_id == "risk:manual_review":
            continue
        if trait_id.startswith("class:"):
            continue
        trait = trait_defs.get(trait_id)
        labels.append(trait.label if trait and trait.label else trait_id)
    return sorted(labels, key=str.casefold)
