"""Plan-command input loaders.

Extracted from `planner.engine.plan` to keep the scheduler module focused
on search + orchestration. This module owns:

- `load_plan_inputs` — read pillboxes/traits/stacks/substances/products/relations
"""

from __future__ import annotations

import sys
from typing import cast

from planner.cards.pillboxes import check_pillbox_slot_anchors, flatten_pillbox_slots, load_pillboxes
from planner.cards.product import load_product_registry
from planner.cards.stacks import check_routable_topologies, check_stack_alignment, normalize_stack_entries
from planner.cards.substance import load_substance_registry
from planner.contracts import CardLoadError, Slot
from planner.engine._plan_types import PlanInputs
from planner.ontology.artifacts import OntologyBundle
from planner.ontology.canonical_facts import validate_canonical_fact_catalog
from planner.paths import Paths
from planner.yaml_io import load_yaml


def load_plan_inputs(
    paths: Paths,
    bundle: OntologyBundle,
) -> PlanInputs | None:
    """Load all static inputs needed before the active-index build.

    Returns a PlanInputs or None on failure.
    """
    try:
        pillboxes = load_pillboxes(paths.data / "pillboxes.yaml", bundle)
        anchor_errors = check_pillbox_slot_anchors(
            pillboxes,
            paths.data / "pillboxes.yaml",
            bundle,
        )
        if anchor_errors:
            raise CardLoadError(paths.data / "pillboxes.yaml", "\n".join(anchor_errors))
    except CardLoadError as e:
        print(f"plan: {e.message}", file=sys.stderr)
        return None
    try:
        stacks_data = load_yaml(paths.stacks_file)
    except CardLoadError as e:
        print(f"plan: {e.message}", file=sys.stderr)
        return None
    if not isinstance(stacks_data, dict):
        print("plan: stacks.yaml: top-level must be a mapping", file=sys.stderr)
        return None

    stacks_dict = cast(dict[str, object], stacks_data)
    slots: dict[str, Slot] = dict(
        sorted(
            flatten_pillbox_slots(pillboxes).items(),
            key=lambda kv: (kv[1].pillbox, kv[1].order),
        )
    )

    substances = load_substance_registry(paths, bundle)
    products = load_product_registry(paths, bundle)
    try:
        partition_errors, _partition_info = check_stack_alignment(
            stacks_dict,
            {product_id: paths.products / product_id for product_id in products},
            paths.stacks_file,
            bundle.runtime_program.glue_contract.inactive_stack_name,
        )
        topology_errors = check_routable_topologies(
            paths.stacks_file,
            stacks_dict,
            {pillbox.stack: 1 for pillbox in pillboxes.values()},
            bundle.runtime_program.glue_contract.inactive_stack_name,
        )
        if partition_errors or topology_errors:
            raise CardLoadError(paths.stacks_file, "\n".join((*partition_errors, *topology_errors)))
        validate_canonical_fact_catalog(bundle.runtime_program.canonical_fact_catalog, substances, products)
    except CardLoadError as e:
        print(f"plan: {e.message}", file=sys.stderr)
        return None
    try:
        stack_entries = normalize_stack_entries(stacks_dict)
    except ValueError as e:
        print(f"plan: {paths.stacks_file}: {e}", file=sys.stderr)
        return None

    return PlanInputs(
        runtime_program=bundle.runtime_program,
        canonical_fact_catalog=bundle.runtime_program.canonical_fact_catalog,
        slots=slots,
        substances=substances,
        products=products,
        stack_entries=stack_entries,
        pillboxes=pillboxes,
    )
