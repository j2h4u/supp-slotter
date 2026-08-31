"""YAML loaders feeding the read model."""

from __future__ import annotations

from planner.cards.stacks import normalize_stack_entries
from planner.contracts import CardLoadError
from planner.ontology.runtime_program import RuntimeProgram
from planner.paths import Paths
from planner.yaml_io import load_yaml_mapping


def stacks_for_read_model(paths: Paths, runtime: RuntimeProgram) -> dict[str, list[str]]:
    """Read validated routable stack membership, excluding tracked-unassigned records."""
    raw = load_yaml_mapping(paths.stacks_file)
    try:
        entries = normalize_stack_entries(raw, runtime)
    except ValueError as error:
        raise CardLoadError(paths.stacks_file, f"{paths.stacks_file}: {error}") from error

    out: dict[str, list[str]] = {}
    for product_id, entry in entries.items():
        out.setdefault(entry["stack"], []).append(product_id)
    return {stack: sorted(product_ids) for stack, product_ids in sorted(out.items())}
