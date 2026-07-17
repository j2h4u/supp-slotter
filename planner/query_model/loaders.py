"""YAML loaders feeding the read model."""

from __future__ import annotations

from typing import cast

from planner.cards.dashboards import load_dashboard
from planner.contracts import Dashboard
from planner.paths import Paths
from planner.ontology.artifacts import OntologyBundle
from planner.yaml_io import load_yaml_mapping


def stacks_for_read_model(paths: Paths) -> dict[str, list[str]]:
    """Read data/stacks.yaml and return {stack_name: [product_id, ...]}."""
    raw = cast(dict[str, object], load_yaml_mapping(paths.stacks_file))
    out: dict[str, list[str]] = {}
    for name, items in raw.items():
        if isinstance(items, list):
            out[name] = [item for item in items if isinstance(item, str)]
    return out


def pillbox_stack_names(paths: Paths) -> set[str]:
    """Top-level stack names declared in data/pillboxes.yaml."""
    raw = cast(dict[str, object], load_yaml_mapping(paths.data / "pillboxes.yaml"))
    return set(raw.keys())


def dashboards_for_read_model(paths: Paths, bundle: OntologyBundle) -> dict[str, Dashboard]:
    """Load all data/dashboards/*.yaml into a {slug: Dashboard} map."""
    return {p.stem: load_dashboard(p, bundle) for p in sorted(paths.dashboards.glob("*.yaml"))}
