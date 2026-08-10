"""Stack file loading, alignment, and duplicate-item detection."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

from planner.contracts import CardLoadError, StackEntry
from planner.ontology.artifacts import OntologyBundle
from planner.paths import Paths
from planner.schema_validation import schema_errors
from planner.yaml_io import load_yaml


def check_stack_alignment(
    stacks_data: Mapping[str, object], product_ids: dict[str, Path], stacks_file: Path, inactive_stack_name: str
) -> tuple[list[str], list[str]]:
    """Verify every stack entry references an existing product card, and warn for product cards not yet added to any stack.

    Returns (errors, info).  Errors are fatal; info messages are non-fatal advisories.
    """
    errors: list[str] = []
    info: list[str] = []
    referenced_products: set[str] = set()

    try:
        normalized_entries = normalize_stack_entries(stacks_data)
    except ValueError as e:
        return [f"{stacks_file}: {e}"], info

    for entry in normalized_entries.values():
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
                f"entry (card at {pf}). Add it to `{inactive_stack_name}` if it is still on "
                "the shelf; if it is depleted/not owned/reference-only, keep it "
                "outside stacks intentionally."
            )
            print(msg)
            info.append(msg)

    return errors, info


def normalize_stack_entries(stacks_data: Mapping[str, object]) -> dict[str, StackEntry]:
    """Return stack entries, rejecting product IDs assigned to multiple stacks.

    The previous mapping projection let later YAML keys overwrite earlier
    assignments.  That made downstream dashboard and scheduling state depend
    on source order, so normalization is deliberately fail-closed.
    """
    normalized: dict[str, StackEntry] = {}

    for stack, items in stacks_data.items():
        if not isinstance(items, list):
            continue
        items_list = items
        for entry in items_list:
            if not isinstance(entry, str):
                continue
            product_id = entry
            previous = normalized.get(product_id)
            if previous is not None:
                previous_stack = previous["stack"]
                if previous_stack != stack:
                    raise ValueError(f"stack item '{product_id}' appears in multiple stacks: {previous_stack}, {stack}")
                raise ValueError(f"stack item '{product_id}' appears more than once in stack '{stack}'")
            normalized[product_id] = {"product": product_id, "stack": stack}
    return normalized


def validate_stacks(
    paths: Paths,
    product_ids: dict[str, Path],
    bundle: OntologyBundle,
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
    errors = schema_errors(stacks_data, "stacks", stacks_path, bundle)
    alignment_errors, alignment_info = check_stack_alignment(
        stacks_data,
        product_ids,
        stacks_path,
        bundle.runtime_program.glue_contract.inactive_stack_name,
    )
    errors.extend(alignment_errors)
    return errors, alignment_info
