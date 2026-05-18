"""Stack file loading, alignment, and duplicate-item detection."""

from __future__ import annotations

from pathlib import Path
from typing import Any, cast

from planner.contracts import CardLoadError
from planner.paths import Paths
from planner.schema_validation import schema_errors
from planner.yaml_io import load_yaml


def check_stack_alignment(
    stacks_data: dict[str, Any], product_ids: dict[str, Path], stacks_file: Path
) -> tuple[list[str], list[str]]:
    """Verify every stack entry references an existing product card, and warn for product cards not yet added to any stack.

    Returns (errors, info).  Errors are fatal; info messages are non-fatal advisories.
    """
    errors: list[str] = []
    info: list[str] = []
    referenced_products: set[str] = set()

    for entry in normalize_stack_entries(stacks_data).values():
        product_ref = entry.get("product")
        if not isinstance(product_ref, str):
            continue
        referenced_products.add(product_ref)
        if product_ref not in product_ids:
            stack = entry.get("stack", "<unknown>")
            errors.append(
                f"{stacks_file}: {stack} contains product '{product_ref}' "
                "has no matching product card id under data/products/"
            )

    for pid, pf in product_ids.items():
        if pid not in referenced_products:
            msg = (
                f"{stacks_file}: product '{pid}' has no stack "
                f"entry (card at {pf}). Add it to a stack if it is on the shelf."
            )
            print(msg)
            info.append(msg)

    return errors, info


def check_stack_duplicate_items(stacks_data: dict[str, Any], stacks_file: Path) -> list[str]:
    errors: list[str] = []
    seen: dict[str, str] = {}

    for stack, items in stacks_data.items():
        if not isinstance(items, list):
            continue
        items_list = cast(list[Any], items)
        for item_id in items_list:
            if not isinstance(item_id, str):
                continue
            previous_stack = seen.get(item_id)
            if previous_stack is not None:
                errors.append(
                    f"{stacks_file}: stack item '{item_id}' appears in "
                    f"multiple stacks: {previous_stack}, {stack}"
                )
            else:
                seen[item_id] = stack
    return errors


def normalize_stack_entries(stacks_data: dict[str, Any]) -> dict[str, dict[str, str]]:
    """Return a flat dict mapping item_id → {product, stack} for all stack items regardless of active/inactive status."""
    normalized: dict[str, dict[str, str]] = {}

    for stack, items in stacks_data.items():
        if not isinstance(items, list):
            continue
        items_list = cast(list[Any], items)
        for entry in items_list:
            if not isinstance(entry, str):
                continue
            product_id = entry
            normalized[product_id] = {"product": product_id, "stack": stack}
    return normalized


def validate_stacks(
    paths: Paths,
    product_ids: dict[str, Path],
) -> tuple[list[str], list[str]]:
    """Validate the stacks file.  Returns (errors, info)."""
    stacks_path = paths.stacks_file
    if not stacks_path.exists():
        return [f"missing: {stacks_path}"], []
    try:
        stacks_data = load_yaml(stacks_path)
    except CardLoadError as e:
        return [e.message], []
    if not isinstance(stacks_data, dict):
        return [f"{stacks_path}: top-level must be a mapping"], []
    stacks_dict = cast(dict[str, Any], stacks_data)
    errors = schema_errors(stacks_dict, "stacks", stacks_path)
    errors.extend(check_stack_duplicate_items(stacks_dict, stacks_path))
    alignment_errors, alignment_info = check_stack_alignment(stacks_dict, product_ids, stacks_path)
    errors.extend(alignment_errors)
    return errors, alignment_info
