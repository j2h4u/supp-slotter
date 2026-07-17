"""Active-stack indexing for the plan command."""

from __future__ import annotations

import sys
from collections.abc import Iterable
from typing import NamedTuple

from planner.cards.product import product_component_substances
from planner.contracts import (
    GovernedScheduleProjection,
    PlannerCapability,
    Product,
    SchedulingConstraint,
    SchedulingPolicy,
    Slot,
    StackEntry,
    Substance,
)
from planner.engine._plan_types import ActiveIndex
from planner.engine._scheduling import project_governed_assignments, slot_matches
from planner.ontology.errors import MALFORMED, OntologyInfrastructureError
from planner.ontology.runtime_program import RuntimeProgram
from planner.ontology.scheduling_runtime import resolve_capability
from planner.query_model import StackReadModel
from planner.query_model.relation_conflicts import RelationConflictWarningRow
from planner.schedule_types import ScheduleWarning


class _ActiveItemIndex(NamedTuple):
    product_id: str
    stack: str
    active_components: list[str]
    relation_conflicts: list[RelationConflictWarningRow]
    projection: GovernedScheduleProjection


class ActiveIndexInput(NamedTuple):
    runtime_program: RuntimeProgram
    products: dict[str, Product]
    substances: dict[str, Substance]
    policies: dict[str, SchedulingPolicy]
    read_model: StackReadModel
    scheduling_constraints: tuple[SchedulingConstraint, ...]


class _ActiveItemInput(NamedTuple):
    item_id: str
    entry: StackEntry
    context: ActiveIndexInput
    slots: dict[str, Slot]


class _PreferTargetContext(NamedTuple):
    prefer_pairs: set[frozenset[str]]
    ambiguous_prefer_with_warnings: list[ScheduleWarning]
    item_products: dict[str, str]
    substance_to_active_items: dict[str, list[str]]


def build_active_index(
    stack_entries: dict[str, StackEntry],
    index_input: ActiveIndexInput,
    slots: dict[str, Slot],
    errors: list[str],
) -> ActiveIndex | None:
    """Build per-item trait/conflict/stack indexes from the active stack entries."""
    item_products: dict[str, str] = {}
    active_components: dict[str, list[str]] = {}
    intra_product_relation_conflicts_by_item: dict[str, list[RelationConflictWarningRow]] = {}
    item_stacks: dict[str, str] = {}
    governed_projection_by_item: dict[str, GovernedScheduleProjection] = {}
    active_policy_ids_by_item: dict[str, set[str]] = {}

    for item_id, entry in stack_entries.items():
        item_index = _active_item_index(
            _ActiveItemInput(item_id=item_id, entry=entry, context=index_input, slots=slots)
        )
        if item_index is None:
            continue
        item_products[item_id] = item_index.product_id
        active_components[item_id] = item_index.active_components
        intra_product_relation_conflicts_by_item[item_id] = item_index.relation_conflicts
        item_stacks[item_id] = item_index.stack
        governed_projection_by_item[item_id] = item_index.projection
        active_policy_ids_by_item[item_id] = {g.policy_id for g in item_index.projection.groups}

    if not item_products:
        msg = "plan: no non-inactive stack items."
        print(msg, file=sys.stderr)
        errors.append(msg)
        return None

    for item_id, projection in governed_projection_by_item.items():
        inert_policies = sorted(
            group.policy_id
            for group in projection.groups
            if _policy_reachable(index_input.policies[group.policy_id], slots.values())
            and not _policy_reachable(
                index_input.policies[group.policy_id],
                (slot for slot in slots.values() if slot.stack == item_stacks[item_id]),
            )
        )
        if inert_policies:
            # Capability diagnostic only: these policies cannot affect the
            # item's stack. They do not block planning or fall back to another axis.
            print(
                f"plan: stack item '{item_id}' policies {','.join(inert_policies)} "
                f"inactive_by_capability (stack '{item_stacks[item_id]}' has no matching slots).",
                file=sys.stderr,
            )

    return ActiveIndex(
        item_products=item_products,
        active_components=active_components,
        intra_product_relation_conflicts_by_item=intra_product_relation_conflicts_by_item,
        item_stacks=item_stacks,
        governed_projection_by_item=governed_projection_by_item,
        active_policy_ids_by_item=active_policy_ids_by_item,
    )


def _active_item_index(
    index_input: _ActiveItemInput,
) -> _ActiveItemIndex | None:
    item_id = index_input.item_id
    entry = index_input.entry
    stack = index_input.entry.get("stack")
    if stack == "inactive":
        return None
    product_id = entry.get("product")
    product = index_input.context.products.get(product_id)
    if product is None:
        print(
            f"plan: skipping '{item_id}' - product '{product_id}' missing or invalid",
            file=sys.stderr,
        )
        return None
    capability_rows = index_input.context.runtime_program.capability_rules
    if len(capability_rows) != 1:
        raise OntologyInfrastructureError(
            "plan scheduling capability table must contain exactly one row",
            code=MALFORMED,
        )
    capability_row = capability_rows[0]
    resolved = resolve_capability(
        index_input.context.runtime_program,
        capability_row.planner,
        capability_row.food_model,
    )
    slot_models = set(resolved.base_slot_models)
    for slot in index_input.slots.values():
        model = resolved.near_to_model.get(slot.near)
        if model is None or model not in resolved.slot_models:
            raise OntologyInfrastructureError(
                f"plan scheduling capability has no valid model for slot near {slot.near!r}",
                code=MALFORMED,
            )
        slot_models.add(model)
    component_forms_list: list[tuple[str, str]] = []
    for component in product.components:
        substance = index_input.context.substances.get(component.substance)
        if substance is not None and substance.form is not None:
            component_forms_list.append((component.substance, substance.form))
    component_forms = tuple(sorted(component_forms_list))
    capability = PlannerCapability(
        capability_row.planner,
        capability_row.food_model,
        frozenset(slot_models),
        product.id,
        component_forms,
    )
    projection = project_governed_assignments(
        index_input.context.runtime_program,
        product,
        index_input.context.substances,
        index_input.context.policies,
        capability,
    )
    active_components = product_component_substances(product)
    relation_conflicts = index_input.context.read_model.collect_intra_product_scheduling_constraint_conflicts(
        item_id=item_id,
        product_id=product_id,
        component_ids=active_components,
    )
    return _ActiveItemIndex(
        product_id=product_id,
        stack=stack,
        active_components=active_components,
        relation_conflicts=relation_conflicts,
        projection=projection,
    )


def _policy_reachable(policy: SchedulingPolicy, slots: Iterable[Slot]) -> bool:
    return any(slot_matches(slot, effect.match) for slot in slots for effect in policy.effects)


def resolve_prefer_pairs(
    active_components: dict[str, list[str]],
    item_products: dict[str, str],
    substances: dict[str, Substance],
) -> tuple[set[frozenset[str]], list[ScheduleWarning], dict[str, list[str]]]:
    """Build prefer pairs, ambiguity warnings, and substance-to-active-items index."""
    prefer_pairs: set[frozenset[str]] = set()
    ambiguous_prefer_with_warnings: list[ScheduleWarning] = []
    substance_to_active_items = _substance_to_active_items(active_components)

    for item_id, component_ids in active_components.items():
        for component_id in component_ids:
            substance = substances.get(component_id)
            if substance is None:
                continue
            for target_substance in substance.prefer_with:
                _add_prefer_target(
                    item_id=item_id,
                    component_id=component_id,
                    target_substance=target_substance,
                    context=_PreferTargetContext(
                        prefer_pairs=prefer_pairs,
                        ambiguous_prefer_with_warnings=ambiguous_prefer_with_warnings,
                        item_products=item_products,
                        substance_to_active_items=substance_to_active_items,
                    ),
                )

    return prefer_pairs, ambiguous_prefer_with_warnings, substance_to_active_items


def _substance_to_active_items(active_components: dict[str, list[str]]) -> dict[str, list[str]]:
    substance_to_active_items: dict[str, list[str]] = {}
    for item_id, component_ids in active_components.items():
        for component_id in component_ids:
            substance_to_active_items.setdefault(component_id, []).append(item_id)
    for component_id in substance_to_active_items:
        substance_to_active_items[component_id].sort()
    return substance_to_active_items


def _add_prefer_target(
    item_id: str,
    component_id: str,
    target_substance: str,
    context: _PreferTargetContext,
) -> None:
    target_items = context.substance_to_active_items.get(target_substance, [])
    if len(target_items) == 1:
        other_item = target_items[0]
        if other_item != item_id:
            context.prefer_pairs.add(frozenset([item_id, other_item]))
        return
    if len(target_items) > 1:
        context.ambiguous_prefer_with_warnings.append({
            "type": "ambiguous_prefer_with",
            "item": item_id,
            "product": context.item_products[item_id],
            "source_substance": component_id,
            "target_substance": target_substance,
            "candidate_items": target_items,
            "message": "prefer_with target maps to multiple active stack items; no bonus awarded",
        })
