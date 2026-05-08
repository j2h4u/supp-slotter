"""Stack file loading, alignment, and duplicate-item detection."""

from __future__ import annotations

from pathlib import Path

import yaml

from planner.io import STACKS_PATH, load_yaml, schema_errors


def check_stack_alignment(
    stacks_data: dict, product_ids: dict[str, Path]
) -> list[str]:
    """Verify stack entries reference product cards and flag shelf candidates."""
    errors: list[str] = []
    referenced_products: set[str] = set()

    for _item_id, entry in normalize_stack_entries(stacks_data).items():
        if not isinstance(entry, dict):
            continue
        product_ref = entry.get("product")
        if not product_ref:
            continue
        referenced_products.add(product_ref)
        if product_ref not in product_ids:
            stack = entry.get("stack", "<unknown>")
            errors.append(
                f"{STACKS_PATH}: {stack} contains product '{product_ref}' "
                "has no matching product card id under data/products/"
            )

    for pid, pf in product_ids.items():
        if pid not in referenced_products:
            print(
                f"WARN: {STACKS_PATH}: product '{pid}' has no stack "
                f"entry (card at {pf}). Add it to a stack if it is on the shelf."
            )

    return errors

def check_stack_duplicate_items(stacks_data: dict) -> list[str]:
    errors: list[str] = []
    seen: dict[str, str] = {}

    for stack, items in stacks_data.items():
        if not isinstance(items, list):
            continue
        for item_id in items:
            if not isinstance(item_id, str):
                continue
            previous_stack = seen.get(item_id)
            if previous_stack is not None:
                errors.append(
                    f"{STACKS_PATH}: stack item '{item_id}' appears in "
                    f"multiple stacks: {previous_stack}, {stack}"
                )
            else:
                seen[item_id] = stack
    return errors

def normalize_stack_entries(stacks_data: dict) -> dict[str, dict]:
    """Return product ids keyed by item id with stack attached in memory."""
    normalized: dict[str, dict] = {}

    for stack, items in stacks_data.items():
        if not isinstance(items, list):
            continue
        for product_id in items:
            if not isinstance(product_id, str):
                continue
            normalized[product_id] = {"product": product_id, "stack": stack}
    return normalized

def validate_stacks(
    stacks_path: Path,
    product_ids: dict[str, Path],
    trait_ids: set[str],
) -> list[str]:
    if not stacks_path.exists():
        return [f"missing: {stacks_path}"]
    try:
        stacks_data = load_yaml(stacks_path)
    except yaml.YAMLError as e:
        return [f"{stacks_path}: yaml parse error: {e}"]
    if not isinstance(stacks_data, dict):
        return [f"{stacks_path}: top-level must be a mapping"]
    errors = schema_errors(stacks_data, "stacks", stacks_path)
    errors.extend(check_stack_duplicate_items(stacks_data))
    errors.extend(check_stack_alignment(stacks_data, product_ids))
    return errors

