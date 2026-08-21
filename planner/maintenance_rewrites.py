"""Reference rewrite planning for auto-maintenance."""

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path
from typing import cast

import yaml

from planner.cards._common import load_card_mapping
from planner.cards.product import canonical_product_filename
from planner.cards.substance import canonical_substance_filename
from planner.contracts import CardLoadError
from planner.maintenance_atomic import EditPlan, EditPlanEntry
from planner.maintenance_mapping import product_from_mapping, substance_from_mapping
from planner.maintenance_substance_resolution import (
    MaintenanceContract,
    ReferenceResolution,
    has_draft_reference,
    resolve_references,
    rewrite_references,
)
from planner.paths import strip_root_prefix


@dataclass
class _ProductSubstanceRewriteContext:
    repository_root: Path
    substance_renames: dict[str, str]
    product_renames: dict[str, str]
    plan: EditPlan
    errors: list[str]
    contract: MaintenanceContract


def plan_substance_ref_rewrites(  # noqa: PLR0913
    data_dir: Path,
    substance_renames: dict[str, str],
    product_renames: dict[str, str],
    plan: EditPlan,
    *,
    collect_errors: list[str] | None = None,
    contract: MaintenanceContract,
) -> bool:
    errors = collect_errors if collect_errors is not None else []
    error_count = len(errors)
    context = _ProductSubstanceRewriteContext(
        repository_root=data_dir,
        substance_renames=substance_renames,
        product_renames=product_renames,
        plan=plan,
        errors=errors,
        contract=contract,
    )
    if not _plan_product_substance_ref_rewrites(
        context,
    ):
        return False
    if substance_renames:
        _plan_substance_prefer_with_rewrites(context)
    return len(errors) == error_count


def rewrite_stack_product_refs(
    stacks_data: dict[str, object], product_renames: dict[str, str], resolution: ReferenceResolution
) -> None:
    rewrite_references(stacks_data, resolution, product_renames)


def _plan_product_substance_ref_rewrites(
    context: _ProductSubstanceRewriteContext,
) -> bool:
    products_dir = context.repository_root / context.contract.product_path
    if not products_dir.exists():
        return True

    for path in sorted(products_dir.glob("*.yaml")):
        try:
            card = cast(
                dict[str, object],
                load_card_mapping(path, context.contract.product_substance.source_entity_class.casefold()),
            )
        except CardLoadError as e:
            print(f"warning: skipping {path}: {strip_root_prefix(e.message)}", file=sys.stderr)
            continue

        resolution = context.contract.product_substance
        renamed = rewrite_references(card, resolution, context.substance_renames)
        resolved = False
        if has_draft_reference(card, resolution):
            resolved = resolve_references(
                document_path=path,
                document=card,
                collection_dir=context.repository_root / resolution.source_path,
                resolution=resolution,
                identity_renames=context.substance_renames,
                errors=context.errors,
            )
        if not renamed and not resolved:
            continue

        final_path = _planned_product_path(path, card, context.product_renames)
        _upsert_card_edit(context.plan, final_path, card, path if final_path != path else None)
    return not context.errors


def _plan_substance_prefer_with_rewrites(context: _ProductSubstanceRewriteContext) -> None:
    for resolution in context.contract.substance_preferences:
        substances_dir = context.repository_root / resolution.document_path
        for path in sorted(substances_dir.glob("*.yaml")):
            _plan_substance_preference_file(context, path, resolution)


def _plan_substance_preference_file(
    context: _ProductSubstanceRewriteContext, path: Path, resolution: ReferenceResolution
) -> None:
    try:
        substance = cast(dict[str, object], load_card_mapping(path, resolution.target_entity_class.casefold()))
    except CardLoadError as e:
        print(f"warning: skipping {path}: {strip_root_prefix(e.message)}", file=sys.stderr)
        return

    changed = rewrite_references(substance, resolution, context.substance_renames)
    if not changed:
        return

    final_path = _planned_substance_path(path, substance, context.substance_renames)
    _upsert_card_edit(context.plan, final_path, substance, path if final_path != path else None)


def _planned_product_path(path: Path, card: dict[str, object], renames: dict[str, str]) -> Path:
    if path.stem in renames:
        card["id"] = renames[path.stem]
    return path.parent / canonical_product_filename(product_from_mapping(card))


def _planned_substance_path(path: Path, card: dict[str, object], renames: dict[str, str]) -> Path:
    if path.stem in renames:
        card["id"] = renames[path.stem]
    return path.parent / canonical_substance_filename(substance_from_mapping(card))


def _upsert_card_edit(
    plan: EditPlan,
    final_path: Path,
    data: dict[str, object],
    obsolete_path: Path | None,
) -> None:
    new_content = yaml.safe_dump(data, sort_keys=False, default_flow_style=False, allow_unicode=True)
    plan.upsert(
        EditPlanEntry(
            final_path=final_path,
            new_content=new_content,
            obsolete_path=obsolete_path,
        )
    )
