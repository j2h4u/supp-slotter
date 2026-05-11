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
    match_raw_obj = effect.get("match")
    if not isinstance(match_raw_obj, dict):
        match_raw: dict[str, Any] = {}
    else:
        match_raw = cast(dict[str, Any], match_raw_obj)
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
    for namespace, entries_obj in data.items():
        if not isinstance(entries_obj, dict):
            continue
        entries = cast(dict[str, Any], entries_obj)
        for short_name, trait_obj in entries.items():
            if not isinstance(trait_obj, dict):
                trait: dict[str, Any] = {}
            else:
                trait = cast(dict[str, Any], trait_obj)
            tid = f"{namespace}:{short_name}"
            try:
                out[tid] = TraitDef(
                    id=tid,
                    namespace=namespace,
                    short_name=short_name,
                    label=cast(str, trait.get("label") or ""),
                    description=cast(str, trait.get("description") or ""),
                    applies_when=cast(str, trait.get("applies_when") or ""),
                    effects=tuple(
                        _build_trait_effect(cast(dict[str, Any], e))
                        for e in trait.get("effects") or ()
                        if isinstance(e, dict)
                    ),
                    separate_from=tuple(trait.get("separate_from") or ()),
                    warning=bool(trait.get("warning")),
                    action=cast(str | None, trait.get("action")),
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


_NAMESPACE_ORDER = ("is", "intake", "effect", "risk", "activity", "dashboard")


def grouped_trait_defs(
    trait_defs: dict[str, TraitDef],
) -> dict[str, list[TraitDef]]:
    """Group TraitDefs by namespace in stable display order.

    Order is fixed: is, intake, effect, risk, activity, dashboard.
    Only namespaces that have at least one registered trait are included;
    the review-substance command is responsible for showing empty-namespace
    headings for namespaces the substance references but that have no traits.
    """
    groups: dict[str, list[TraitDef]] = {}
    for trait in sorted(trait_defs.values(), key=lambda t: t.id):
        groups.setdefault(trait.namespace, []).append(trait)
    # Emit in canonical order; fall back to sorted for any unrecognised namespaces.
    known = [ns for ns in _NAMESPACE_ORDER if ns in groups]
    extra = sorted(ns for ns in groups if ns not in _NAMESPACE_ORDER)
    return {ns: groups[ns] for ns in known + extra}


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
    """Return display labels for scheduling-narrative use (schedule.yaml review_tags field).

    Excludes:
    - risk:manual_review (operator-only flag, not narrative content)
    - is:* (intrinsic category — review-classification axis, not a scheduling driver)
    - dashboard:* (operator-curated cluster membership — review-classification axis,
      not a scheduling driver)

    For full grouped display (all 6 namespaces, used by review-substance), use
    grouped_trait_defs() + print_trait_details() instead. The two paths are
    intentionally distinct:
      readable_traits()       = schedule narrative (scheduling drivers only)
      review-substance output = full audit (all 6 namespaces visible)
    """
    labels: list[str] = []
    for trait_id in sorted(trait_ids):
        if trait_id == "risk:manual_review":
            continue
        if trait_id.startswith("is:"):
            continue
        if trait_id.startswith("dashboard:"):
            continue
        trait = trait_defs.get(trait_id)
        labels.append(trait.label if trait and trait.label else trait_id)
    return sorted(labels, key=str.casefold)
