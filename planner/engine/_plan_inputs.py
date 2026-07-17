"""Plan-command input loaders.

Extracted from `planner.engine.plan` to keep the scheduler module focused
on search + orchestration. This module owns:

- `load_plan_inputs` — read pillboxes/traits/stacks/substances/products/relations
"""

from __future__ import annotations

import sys
from typing import cast

from planner.cards.pillboxes import flatten_pillbox_slots, load_pillboxes
from planner.cards.product import load_product_registry
from planner.cards.relations import load_global_relations
from planner.cards.stacks import normalize_stack_entries
from planner.cards.substance import load_substance_registry
from planner.contracts import CardLoadError, Slot
from planner.engine._plan_types import PlanInputs
from planner.ontology.artifacts import OntologyBundle
from planner.ontology.policies import load_scheduling_constraints, load_scheduling_policies
from planner.paths import Paths
from planner.scheduling_constraint_execution import compile_scheduling_constraint_execution_plans
from planner.yaml_io import load_yaml


def load_plan_inputs(
    paths: Paths,
    bundle: OntologyBundle,
) -> PlanInputs | None:
    """Load all static inputs needed before the active-index build.

    Returns a PlanInputs or None on failure.
    """
    try:
        pillboxes = load_pillboxes(paths.data / "pillboxes.yaml")
    except CardLoadError as e:
        print(f"plan: {e.message}", file=sys.stderr)
        return None
    try:
        policies = load_scheduling_policies(bundle)
    except CardLoadError as e:
        print(f"plan: {e.message}", file=sys.stderr)
        return None
    stacks_data = load_yaml(paths.stacks_file)

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
    global_relations = load_global_relations(paths)
    dashboard_files = sorted(paths.dashboards.glob("*.yaml")) if paths.dashboards.exists() else []
    stack_entries = normalize_stack_entries(stacks_dict)

    scheduling_constraints = load_scheduling_constraints(bundle, include_retired=True)
    scheduling_constraint_plans = compile_scheduling_constraint_execution_plans(
        scheduling_constraints,
        substances,
        bundle.runtime_program,
    )

    return PlanInputs(
        ontology_bundle=bundle,
        runtime_program=bundle.runtime_program,
        effect_scoring=bundle.runtime_program.effect_scoring,
        slots=slots,
        policies=policies,
        scheduling_constraints=scheduling_constraints,
        substances=substances,
        products=products,
        global_relations=global_relations,
        dashboard_files=dashboard_files,
        stack_entries=stack_entries,
        pillboxes=pillboxes,
        scheduling_constraint_plans=scheduling_constraint_plans,
    )
