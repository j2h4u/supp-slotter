"""Stack partition loading, alignment, and topology validation."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import cast

from planner.contracts import CardLoadError, StackEntry
from planner.ontology.artifacts import OntologyBundle
from planner.ontology.runtime_program import RuntimeProgram, RuntimeStackPartition
from planner.paths import Paths
from planner.yaml_io import load_yaml


def _partition_entries(
    stacks_data: Mapping[str, object], runtime: RuntimeProgram
) -> tuple[dict[str, StackEntry], set[str]]:
    """Validate the closed product partition and project schedulable entries.

    The runtime program declares the routable, excluded, and tracked-unassigned
    partition names. The tracked partition is an explicit registry, not a
    stack: its records establish product ownership but never reach scheduling,
    review, or a pillbox topology.
    """
    partition = runtime.glue_contract.stack_partition
    _validate_partition_names(stacks_data, partition)
    normalized: dict[str, StackEntry] = {}
    tracked_unassigned: set[str] = set()
    seen: dict[str, str] = {}

    for stack, items in stacks_data.items():
        if not isinstance(items, list):
            raise ValueError(f"stack {stack!r} must be a list")
        entries = cast(list[object], items)
        if stack == partition.tracked_unassigned_partition_name:
            for product_id in _tracked_unassigned_product_ids(entries, stack):
                _claim_product(seen, product_id, stack)
                tracked_unassigned.add(product_id)
            continue

        for index, product_id in enumerate(entries):
            if not isinstance(product_id, str) or not product_id.strip():
                raise ValueError(f"stack {stack!r}[{index}] must be a non-empty product id")
            _claim_product(seen, product_id, stack)
            normalized[product_id] = {"product": product_id, "stack": stack}

    return normalized, tracked_unassigned


def _validate_partition_names(stacks_data: Mapping[str, object], partition: RuntimeStackPartition) -> None:
    actual_names: set[str] = set()
    for stack in stacks_data:
        if not isinstance(stack, str) or not stack.strip():
            raise ValueError("stack names must be non-empty strings")
        actual_names.add(stack)
    expected_names = {
        *partition.routable_stack_names,
        *partition.excluded_stack_names,
        partition.tracked_unassigned_partition_name,
    }
    unexpected_names = actual_names - expected_names
    if unexpected_names:
        raise ValueError(f"unknown stack partitions: {', '.join(sorted(unexpected_names))}")
    missing_names = expected_names - actual_names
    if missing_names:
        raise ValueError(f"missing configured stack partitions: {', '.join(sorted(missing_names))}")


def _tracked_unassigned_product_ids(items: list[object], partition_name: str) -> list[str]:
    product_ids: list[str] = []
    for index, raw_entry in enumerate(items):
        if not isinstance(raw_entry, Mapping):
            raise ValueError(f"{partition_name}[{index}] must be a product/reason mapping")
        entry = cast(Mapping[object, object], raw_entry)
        if set(entry) != {"product", "reason"}:
            raise ValueError(f"{partition_name}[{index}] must contain exactly product and reason")
        product_id = entry["product"]
        reason = entry["reason"]
        if not isinstance(product_id, str) or not product_id.strip():
            raise ValueError(f"{partition_name}[{index}].product must be a non-empty product id")
        if not isinstance(reason, str) or not reason.strip():
            raise ValueError(f"{partition_name}[{index}].reason must be a non-empty string")
        product_ids.append(product_id)
    return product_ids


def _claim_product(seen: dict[str, str], product_id: str, partition: str) -> None:
    previous = seen.get(product_id)
    if previous is None:
        seen[product_id] = partition
        return
    if previous == partition:
        raise ValueError(f"product '{product_id}' appears more than once in {partition!r}")
    raise ValueError(f"product '{product_id}' appears in multiple partitions: {previous}, {partition}")


def check_stack_alignment(
    stacks_data: Mapping[str, object], product_ids: dict[str, Path], stacks_file: Path, runtime: RuntimeProgram
) -> tuple[list[str], list[str]]:
    """Verify the product partition is complete and references product cards."""
    errors: list[str] = []
    info: list[str] = []
    referenced_products: set[str] = set()
    partition = runtime.glue_contract.stack_partition

    try:
        normalized_entries, tracked_unassigned = _partition_entries(stacks_data, runtime)
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

    for product_ref in tracked_unassigned:
        referenced_products.add(product_ref)
        if product_ref not in product_ids:
            errors.append(
                f"{stacks_file}: {partition.tracked_unassigned_partition_name} contains product '{product_ref}' "
                "has no matching product card id under data/products/"
            )

    for pid, pf in product_ids.items():
        if pid not in referenced_products:
            errors.append(
                f"{stacks_file}: product '{pid}' has no stack "
                f"entry (card at {pf}). Add it to `{runtime.glue_contract.inactive_stack_name}` if it is still on the shelf, "
                f"or add an explicit `{partition.tracked_unassigned_partition_name}` record with a reason."
            )

    return errors, info


def normalize_stack_entries(stacks_data: Mapping[str, object], runtime: RuntimeProgram) -> dict[str, StackEntry]:
    """Return only routable/inactive product entries after partition validation."""
    normalized, _tracked_unassigned = _partition_entries(stacks_data, runtime)
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
    alignment_errors, alignment_info = check_stack_alignment(
        stacks_data,
        product_ids,
        stacks_path,
        bundle.runtime_program,
    )
    errors = list(alignment_errors)
    pillboxes_path = paths.data / "pillboxes.yaml"
    try:
        pillboxes = load_yaml(pillboxes_path)
        if not isinstance(pillboxes, dict):
            pillboxes = {}
        pillbox_mapping = cast(dict[str, object], pillboxes)
        errors.extend(
            check_routable_topologies(
                stacks_path,
                _pillbox_stack_counts(pillbox_mapping),
                bundle.runtime_program,
            )
        )
    except CardLoadError:
        pass
    return errors, alignment_info


def check_routable_topologies(
    stacks_path: Path,
    pillbox_stack_counts: Mapping[str, int],
    runtime: RuntimeProgram,
) -> list[str]:
    routable_stacks = set(runtime.glue_contract.stack_partition.routable_stack_names)
    errors = [
        f"{stacks_path}: routable stack '{stack_name}' requires exactly one pillbox, found {pillbox_stack_counts.get(stack_name, 0)}"
        for stack_name in sorted(routable_stacks)
        if pillbox_stack_counts.get(stack_name, 0) != 1
    ]
    errors.extend(
        f"{stacks_path}: pillbox references non-routable stack '{stack_name}'"
        for stack_name in sorted(pillbox_stack_counts)
        if stack_name not in routable_stacks
    )
    errors.extend(
        f"{stacks_path}: stack '{stack_name}' has {count} pillboxes; exactly one is required"
        for stack_name, count in sorted(pillbox_stack_counts.items())
        if stack_name in routable_stacks and count > 1
    )
    return errors


def _pillbox_stack_counts(pillboxes: dict[str, object]) -> dict[str, int]:
    stacks: dict[str, int] = {}
    for raw_value in pillboxes.values():
        if not isinstance(raw_value, dict):
            continue
        value = cast(dict[str, object], raw_value)
        stack = value.get("stack")
        if isinstance(stack, str):
            stacks[stack] = stacks.get(stack, 0) + 1
    return stacks
