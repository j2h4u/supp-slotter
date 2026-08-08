"""Small runtime helpers for structural scheduling capabilities.

Scheduling preferences and constraints are interpreted directly by the planner
from the generated ontology program. This module only adapts the authored
capability table to the slot-model loader.
"""

from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Mapping

from planner.ontology.errors import MALFORMED, OntologyInfrastructureError
from planner.ontology.runtime_program import RuntimeProgram


@dataclass(frozen=True, slots=True)
class RuntimeCapabilityDecision:
    capability_id: str
    base_slot_models: tuple[str, ...]
    slot_models: tuple[str, ...]
    product_scope: tuple[str, ...]
    formulations: tuple[str, ...]
    near_to_model: Mapping[str, str]


def _error(message: str) -> OntologyInfrastructureError:
    return OntologyInfrastructureError(f"scheduling capability {message}", code=MALFORMED)


def resolve_capability(program: RuntimeProgram, planner: str, food_model: str) -> RuntimeCapabilityDecision:
    """Resolve the sole capability row for an exact planner/food-model pair."""
    if not isinstance(planner, str) or not planner or not isinstance(food_model, str) or not food_model:
        raise _error("planner and food model must be non-empty strings")
    rows = tuple(row for row in program.capability_rules if row.planner == planner and row.food_model == food_model)
    if len(rows) != 1:
        raise _error("planner/food-model pair is missing or ambiguous")
    row = rows[0]
    near = {item.near: item.model for item in row.near_to_model}
    if len(near) != len(row.near_to_model):
        raise _error("near-model keys are ambiguous")
    return RuntimeCapabilityDecision(
        row.id,
        row.base_slot_models,
        row.slot_models,
        row.product_scope,
        row.formulations,
        MappingProxyType(near),
    )


__all__ = ["RuntimeCapabilityDecision", "resolve_capability"]
