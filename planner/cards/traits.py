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
from planner.domain_constants import REGISTERED_NAMESPACES


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


def trait_source_files(path: Path) -> list[Path]:
    """Return trait YAML sources from the split trait directory."""
    if path.is_dir():
        files = sorted(path.glob("*.yaml"))
        if files:
            return files
        raise CardLoadError(path, f"{path}: no traits found")
    if path.exists():
        raise CardLoadError(path, f"{path}: expected trait directory")
    raise CardLoadError(path, f"{path}: directory does not exist")


def load_trait_mapping(path: Path) -> dict[str, Any]:
    """Load split trait YAML files and merge them by namespace.

    Each namespace has one owner file. This keeps the split registry readable
    and prevents accidental duplicate axis definitions.
    """
    merged: dict[str, Any] = {}
    namespace_sources: dict[str, Path] = {}
    for source in trait_source_files(path):
        data = load_card_mapping(source, "traits")
        for namespace, entries in data.items():
            if namespace in namespace_sources:
                raise CardLoadError(
                    source,
                    f"{source}: namespace '{namespace}' is already defined in {namespace_sources[namespace]}",
                )
            namespace_sources[namespace] = source
            merged[namespace] = entries
    if not merged:
        raise CardLoadError(path, f"{path}: no traits found")
    return merged


def load_traits(path: Path) -> dict[str, TraitDef]:
    """Load trait definitions into a flat namespace:short -> TraitDef map.

    Raises CardLoadError on missing file, parse error, or non-mapping top-level.
    """
    data = load_trait_mapping(path)
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
                    warning=bool(trait.get("warning")),
                    action=cast(str | None, trait.get("action")),
                )
            except KeyError as e:
                raise CardLoadError(path, f"{path}: missing required field {e}") from e
    return out


def check_traits(trait_defs: dict[str, TraitDef], traits_path: Path) -> list[str]:
    """Validate trait namespaces.

    Match-key validation is handled by JSON schema + TraitEffectMatch dataclass:
    the schema constrains match to {near, food} with additionalProperties: false,
    and TraitEffectMatch enforces those at load time.

    Class-level competes (relations.yaml source_class/target_class) is the
    block-pair mechanism; traits do not define separation pairs.
    """
    errors: list[str] = []

    for trait_id, trait in trait_defs.items():
        if trait.namespace not in REGISTERED_NAMESPACES:
            errors.append(
                f"{traits_path}: trait '{trait_id}' uses unregistered namespace "
                f"'{trait.namespace}' (registered: {sorted(REGISTERED_NAMESPACES)})"
            )

    return errors


NAMESPACE_ORDER = (
    "is",
    "effect",
    "intake",
    "timing",
    "risk",
    "activity",
    "context",
    "pathway",
)


def grouped_trait_defs(
    trait_defs: dict[str, TraitDef],
) -> dict[str, list[TraitDef]]:
    """Group TraitDefs by namespace in stable display order.

    Order is fixed: is, effect, intake, timing, risk, activity, context, pathway.
    Only namespaces that have at least one registered trait are included;
    the review-substance command is responsible for showing empty-namespace
    headings for namespaces the substance references but that have no traits.
    """
    groups: dict[str, list[TraitDef]] = {}
    for trait in sorted(trait_defs.values(), key=lambda t: t.id):
        groups.setdefault(trait.namespace, []).append(trait)
    # Emit in canonical order; fall back to sorted for any unrecognised namespaces.
    known = [ns for ns in NAMESPACE_ORDER if ns in groups]
    extra = sorted(ns for ns in groups if ns not in NAMESPACE_ORDER)
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
    - context:* (operator-curated review-context membership — review-classification axis,
      not a scheduling driver)
    - timing:* (scheduling-driver only — drives near/sleep slot rules internally;
      not a human-readable narrative label)
    - pathway:* (Reviewer-only metabolic pathway membership — not used by Planner
      scheduling and not meaningful as a schedule narrative label)

    For full grouped display (all namespaces, used by review-substance), use
    grouped_trait_defs() + print_trait_details() instead. The two paths are
    intentionally distinct:
      readable_traits()       = schedule narrative (scheduling drivers only)
      review-substance output = full audit (all namespaces visible)
    """
    labels: list[str] = []
    for trait_id in sorted(trait_ids):
        if trait_id == "risk:manual_review":
            continue
        if trait_id.startswith("is:"):
            continue
        if trait_id.startswith("context:"):
            continue
        if trait_id.startswith("timing:"):
            continue
        if trait_id.startswith("pathway:"):
            continue
        trait = trait_defs.get(trait_id)
        labels.append(trait.label if trait and trait.label else trait_id)
    return sorted(labels, key=str.casefold)
