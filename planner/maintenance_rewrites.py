"""Reference rewrite planning for auto-maintenance."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, cast

import yaml

from planner.cards._common import load_card_mapping
from planner.cards.product import canonical_product_filename
from planner.cards.substance import canonical_substance_filename
from planner.contracts import CardLoadError
from planner.maintenance_atomic import EditPlan, EditPlanEntry
from planner.maintenance_mapping import product_from_mapping, substance_from_mapping
from planner.paths import strip_root_prefix


def plan_substance_ref_rewrites(
    data_dir: Path,
    substance_renames: dict[str, str],
    product_renames: dict[str, str],
    plan: EditPlan,
) -> None:
    if not substance_renames:
        return

    _plan_product_substance_ref_rewrites(
        data_dir / "products",
        substance_renames,
        product_renames,
        plan,
    )
    _plan_substance_prefer_with_rewrites(
        data_dir / "substances",
        substance_renames,
        plan,
    )


def rewrite_stack_product_refs(
    stacks_data: dict[str, Any], product_renames: dict[str, str]
) -> None:
    for stack_name, items in stacks_data.items():
        if not isinstance(items, list):
            continue
        new_items: list[Any] = []
        for item in cast(list[Any], items):
            if isinstance(item, str):
                new_items.append(product_renames.get(item, item))
            else:
                new_items.append(item)
        stacks_data[stack_name] = new_items


def _plan_product_substance_ref_rewrites(
    products_dir: Path,
    substance_renames: dict[str, str],
    product_renames: dict[str, str],
    plan: EditPlan,
) -> None:
    if not products_dir.exists():
        return

    for path in sorted(products_dir.glob("*.yaml")):
        try:
            card = load_card_mapping(path, "product")
        except CardLoadError as e:
            print(f"warning: skipping {path}: {strip_root_prefix(e.message)}", file=sys.stderr)
            continue

        if not _rewrite_product_components(card, substance_renames):
            continue

        final_path = _planned_product_path(path, card, product_renames)
        _upsert_card_edit(plan, final_path, card, path if final_path != path else None)


def _plan_substance_prefer_with_rewrites(
    substances_dir: Path,
    substance_renames: dict[str, str],
    plan: EditPlan,
) -> None:
    for path in sorted(substances_dir.glob("*.yaml")):
        try:
            substance = load_card_mapping(path, "substance")
        except CardLoadError as e:
            print(f"warning: skipping {path}: {strip_root_prefix(e.message)}", file=sys.stderr)
            continue

        schedule_raw = substance.get("schedule")
        if not isinstance(schedule_raw, dict):
            continue
        schedule = cast(dict[str, Any], schedule_raw)
        prefer_with = schedule.get("prefer_with")
        if not isinstance(prefer_with, list):
            continue

        rewritten = [
            substance_renames.get(item, item) if isinstance(item, str) else item
            for item in cast(list[Any], prefer_with)
        ]
        if rewritten == prefer_with:
            continue

        schedule["prefer_with"] = rewritten
        final_path = _planned_substance_path(path, substance, substance_renames)
        _upsert_card_edit(plan, final_path, substance, path if final_path != path else None)


def _rewrite_product_components(
    card: dict[str, Any],
    substance_renames: dict[str, str],
) -> bool:
    changed = False
    for member_obj in cast(list[Any], card.get("components") or []):
        if not isinstance(member_obj, dict):
            continue
        member = cast(dict[str, Any], member_obj)
        old_ref = member.get("substance")
        if isinstance(old_ref, str) and old_ref in substance_renames:
            member["substance"] = substance_renames[old_ref]
            changed = True
    return changed


def _planned_product_path(path: Path, card: dict[str, Any], renames: dict[str, str]) -> Path:
    if path.stem in renames:
        card["id"] = renames[path.stem]
    return path.parent / canonical_product_filename(product_from_mapping(card))


def _planned_substance_path(path: Path, card: dict[str, Any], renames: dict[str, str]) -> Path:
    if path.stem in renames:
        card["id"] = renames[path.stem]
    return path.parent / canonical_substance_filename(substance_from_mapping(card))


def _upsert_card_edit(
    plan: EditPlan,
    final_path: Path,
    data: dict[str, Any],
    obsolete_path: Path | None,
) -> None:
    new_content = yaml.safe_dump(
        data, sort_keys=False, default_flow_style=False, allow_unicode=True
    )
    plan.upsert(
        EditPlanEntry(
            final_path=final_path,
            new_content=new_content,
            obsolete_path=obsolete_path,
        )
    )
