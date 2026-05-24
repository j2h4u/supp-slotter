"""Auto-maintenance orchestration for card ids, filenames, and refs."""

from __future__ import annotations

import sys
from typing import Any, cast

import yaml

from planner.cards.product import canonical_product_filename
from planner.cards.substance import canonical_substance_filename
from planner.maintenance_atomic import EditPlan, EditPlanEntry
from planner.maintenance_card_plan import plan_card_dir
from planner.maintenance_lock import (
    acquire_maintenance_lock,
    clear_stale_lock,
    process_is_running,
    read_lock_pid,
    release_maintenance_lock,
)
from planner.maintenance_mapping import product_from_mapping, substance_from_mapping
from planner.maintenance_probe import auto_maintenance_needed
from planner.maintenance_rewrites import (
    plan_substance_ref_rewrites,
    rewrite_stack_product_refs,
)
from planner.paths import Paths
from planner.yaml_io import load_yaml

__all__ = [
    "acquire_maintenance_lock",
    "auto_maintenance_needed",
    "clear_stale_lock",
    "process_is_running",
    "read_lock_pid",
    "release_maintenance_lock",
    "rewrite_stack_product_refs",
    "run_auto_maintenance",
]


def run_auto_maintenance(
    paths: Paths,
    *,
    suppress_output: bool = False,
    collect_errors: list[str] | None = None,
) -> int:
    """Acquire the maintenance lock only when mutations are needed."""
    lock_acquired = False
    needs = auto_maintenance_needed(paths)
    if needs is None:
        return 1
    if needs:
        if not acquire_maintenance_lock(
            paths.maintenance_lock,
            collect_errors=collect_errors,
        ):
            return 1
        lock_acquired = True

    try:
        return _run_auto_maintenance_unlocked(
            paths,
            suppress_output=suppress_output,
            collect_errors=collect_errors,
        )
    finally:
        if lock_acquired:
            release_maintenance_lock(paths.maintenance_lock)


def _run_auto_maintenance_unlocked(
    paths: Paths,
    *,
    suppress_output: bool = False,
    collect_errors: list[str] | None = None,
) -> int:
    """Normalize substances and products through a staged edit plan."""
    data_dir = paths.data
    stacks_path = paths.stacks_file
    edit_plan = EditPlan()

    sub_result = plan_card_dir(
        data_dir / "substances",
        lambda data: canonical_substance_filename(substance_from_mapping(data)),
        "sub",
        edit_plan,
    )
    if sub_result is None:
        return 1
    substance_renames, substance_file_moves = sub_result

    prd_result = plan_card_dir(
        data_dir / "products",
        lambda data: canonical_product_filename(product_from_mapping(data)),
        "prd",
        edit_plan,
    )
    if prd_result is None:
        return 1
    product_renames, product_file_moves = prd_result

    if not plan_substance_ref_rewrites(
        data_dir,
        substance_renames,
        product_renames,
        edit_plan,
        collect_errors=collect_errors,
    ):
        return 1
    _plan_stack_ref_rewrites(stacks_path, product_renames, edit_plan)

    if not edit_plan.stage():
        return 1

    try:
        edit_plan.commit()
    except OSError:
        return 1

    _print_summary(
        suppress_output=suppress_output,
        substance_renames=substance_renames,
        substance_file_moves=substance_file_moves,
        product_renames=product_renames,
        product_file_moves=product_file_moves,
    )
    return 0


def _plan_stack_ref_rewrites(
    stacks_path: Any,
    product_renames: dict[str, str],
    edit_plan: EditPlan,
) -> None:
    if not stacks_path.exists() or not product_renames:
        return

    stacks_data = load_yaml(stacks_path)
    if not isinstance(stacks_data, dict):
        return

    rewrite_stack_product_refs(cast(dict[str, Any], stacks_data), product_renames)
    stacks_content = yaml.safe_dump(
        stacks_data,
        sort_keys=False,
        default_flow_style=False,
        allow_unicode=True,
    )
    edit_plan.entries.append(
        EditPlanEntry(
            final_path=stacks_path,
            new_content=stacks_content,
            obsolete_path=None,
        )
    )


def _print_summary(
    *,
    suppress_output: bool,
    substance_renames: dict[str, str],
    substance_file_moves: int,
    product_renames: dict[str, str],
    product_file_moves: int,
) -> None:
    changed = (
        len(substance_renames)
        + substance_file_moves
        + len(product_renames)
        + product_file_moves
    )
    if not changed:
        return

    if suppress_output:
        print(f"auto-maintenance: renamed {changed} file(s)", file=sys.stderr)
        return

    print(
        "normalized substances: "
        f"{len(substance_renames)} ids, {substance_file_moves} filenames"
    )
    for old_id, new_id in sorted(substance_renames.items()):
        print(f"  {old_id} -> {new_id}")
    print(
        "normalized products: "
        f"{len(product_renames)} ids, {product_file_moves} filenames"
    )
    for old_id, new_id in sorted(product_renames.items()):
        print(f"  {old_id} -> {new_id}")
