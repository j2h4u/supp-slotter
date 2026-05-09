"""Trait definitions: flattening, validation, and rendering helpers."""

from __future__ import annotations

from pathlib import Path
from typing import cast

from planner.cards._common import load_card_mapping
from planner.contracts import (
    CardLoadError,
    SlotNear,
    TraitDef,
    TraitEffect,
    TraitEffectMatch,
)
from planner.io import REGISTERED_NAMESPACES


def _build_trait_effect(effect: dict) -> TraitEffect:
    match_raw = effect.get("match") if isinstance(effect.get("match"), dict) else {}
    near_raw = match_raw.get("near") if isinstance(match_raw, dict) else None
    return TraitEffect(
        match=TraitEffectMatch(
            near=cast(SlotNear, near_raw) if isinstance(near_raw, str) else None,
            food=match_raw.get("food") if isinstance(match_raw, dict) else None,
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


def flatten_trait_defs(traits_data: dict) -> dict[str, dict]:
    traits: dict[str, dict] = {}
    for namespace, entries in traits_data.items():
        if not isinstance(namespace, str) or not isinstance(entries, dict):
            continue
        for short_name, trait in entries.items():
            if isinstance(short_name, str):
                traits[f"{namespace}:{short_name}"] = trait if isinstance(trait, dict) else {}
    return traits

def check_traits(
    traits_data: dict, traits_path: Path, slot_fields: set[str]
) -> list[str]:
    errors: list[str] = []
    trait_defs = flatten_trait_defs(traits_data)
    trait_ids = set(trait_defs)

    for trait_id, trait in trait_defs.items():
        ns = trait_id.split(":", 1)[0]
        if ns not in REGISTERED_NAMESPACES:
            errors.append(
                f"{traits_path}: trait '{trait_id}' uses unregistered namespace '{ns}' "
                f"(registered: {sorted(REGISTERED_NAMESPACES)})"
            )

        for sep in trait.get("separate_from") or []:
            if sep not in trait_ids:
                errors.append(
                    f"{traits_path}: trait '{trait_id}' separate_from references "
                    f"unknown trait '{sep}'"
                )

        for i, eff in enumerate(trait.get("effects") or []):
            for key in eff.get("match", {}):
                if key not in slot_fields:
                    errors.append(
                        f"{traits_path}: trait '{trait_id}' effect[{i}] match key "
                        f"'{key}' is not a slot field (known: {sorted(slot_fields)})"
                    )

    return errors

def grouped_trait_defs(trait_defs: dict) -> dict[str, list[tuple[str, str, dict]]]:
    groups: dict[str, list[tuple[str, str, dict]]] = {}
    for trait_id, trait in sorted(trait_defs.items(), key=lambda item: str(item[0])):
        namespace, _, short_name = str(trait_id).partition(":")
        if not isinstance(trait, dict):
            trait = {}
        groups.setdefault(namespace, []).append(
            (short_name or str(trait_id), str(trait_id), trait)
        )
    return {
        namespace: groups[namespace]
        for namespace in sorted(groups, key=str.casefold)
    }

def format_trait_effect(effect: dict) -> str:
    match = effect.get("match")
    match_text = ""
    if isinstance(match, dict) and match:
        match_text = " when " + ", ".join(
            f"{key}={value}" for key, value in sorted(match.items())
        )
    if effect.get("block") is True:
        return f"blocks slot{match_text}"
    level = effect.get("level")
    if isinstance(level, str):
        return f"{level}{match_text}"
    return ""

def print_trait_details(trait: dict) -> None:
    description = trait.get("description")
    if description:
        print(f"      {description}")
    applies_when = trait.get("applies_when")
    if applies_when:
        print(f"      Applies when: {applies_when}")
    if trait.get("warning") is True:
        print("      Output: schedule warning")
    effects = [
        format_trait_effect(effect)
        for effect in trait.get("effects") or []
        if isinstance(effect, dict)
    ]
    effects = [effect for effect in effects if effect]
    if effects:
        print("      Slot effects: " + "; ".join(effects))

def readable_traits(trait_ids: set[str], traits_data: dict) -> list[str]:
    labels: list[str] = []
    trait_defs = flatten_trait_defs(traits_data) if isinstance(traits_data, dict) else {}
    for trait_id in sorted(trait_ids):
        if trait_id == "risk:manual_review":
            continue
        if trait_id.startswith("class:"):
            continue
        trait = trait_defs.get(trait_id) or {}
        label = trait.get("label") if isinstance(trait, dict) else None
        labels.append(str(label or trait_id))
    return sorted(labels, key=str.casefold)
