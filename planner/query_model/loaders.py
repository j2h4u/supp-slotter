"""YAML loaders feeding the read model."""

from __future__ import annotations

from typing import cast

from planner.cards.dashboards import load_dashboard
from planner.cards.stacks import normalize_stack_entries
from planner.contracts import CardLoadError, Dashboard
from planner.ontology.artifacts import OntologyBundle
from planner.paths import Paths
from planner.yaml_io import load_yaml_mapping


def stacks_for_read_model(paths: Paths) -> dict[str, list[str]]:
    """Read data/stacks.yaml and return {stack_name: [product_id, ...]}."""
    raw = cast(dict[str, object], load_yaml_mapping(paths.stacks_file))
    out: dict[str, list[str]] = {}
    for name, items in raw.items():
        if not isinstance(name, str) or not name.strip():
            raise CardLoadError(paths.stacks_file, f"{paths.stacks_file}: stack names must be non-empty strings")
        if not isinstance(items, list):
            raise CardLoadError(paths.stacks_file, f"{paths.stacks_file}: stack {name!r} must be a list")
        product_ids: list[str] = []
        for index, item in enumerate(items):
            if not isinstance(item, str) or not item.strip():
                raise CardLoadError(
                    paths.stacks_file,
                    f"{paths.stacks_file}: stack {name!r}[{index}] must be a non-empty product id",
                )
            product_ids.append(item)
        out[name] = product_ids
    # Reuse the canonical normalization guard so read-model consumers cannot
    # silently choose a stack based on YAML order.
    try:
        normalize_stack_entries(out)
    except ValueError as e:
        raise CardLoadError(paths.stacks_file, f"{paths.stacks_file}: {e}") from e
    return out


def pillbox_stack_names(paths: Paths) -> set[str]:
    """Authored stack references declared by data/pillboxes.yaml."""
    raw = cast(dict[str, object], load_yaml_mapping(paths.data / "pillboxes.yaml"))
    stack_names: set[str] = set()
    for name, pillbox in raw.items():
        if not isinstance(name, str) or not name.strip():
            raise CardLoadError(
                paths.data / "pillboxes.yaml",
                f"{paths.data / 'pillboxes.yaml'}: pillbox names must be non-empty strings",
            )
        if not isinstance(pillbox, dict):
            raise CardLoadError(
                paths.data / "pillboxes.yaml",
                f"{paths.data / 'pillboxes.yaml'}: pillbox {name!r} must be a mapping",
            )
        stack = pillbox.get("stack")
        if not isinstance(stack, str) or not stack.strip():
            raise CardLoadError(
                paths.data / "pillboxes.yaml",
                f"{paths.data / 'pillboxes.yaml'}: pillbox {name!r}.stack must be a non-empty string",
            )
        stack_names.add(stack)
    return stack_names


def dashboards_for_read_model(paths: Paths, bundle: OntologyBundle) -> dict[str, Dashboard]:
    """Load dashboards into a map keyed only by authored canonical ID."""
    dashboards: dict[str, Dashboard] = {}
    for path in sorted(paths.dashboards.glob("*.yaml")):
        dashboard = load_dashboard(path, bundle)
        if dashboard.id in dashboards:
            previous_path = dashboards[dashboard.id].source_path
            raise CardLoadError(
                path,
                f"{path}: duplicate dashboard id {dashboard.id!r}; "
                f"already defined in {previous_path or '<unknown source>'}",
            )
        dashboards[dashboard.id] = dashboard
    return dashboards
