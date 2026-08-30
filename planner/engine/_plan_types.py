"""Shared plan-command data containers."""

from __future__ import annotations

from typing import NamedTuple

from planner.contracts import (
    Pillbox,
    Product,
    Slot,
    StackEntry,
    Substance,
)
from planner.ontology.canonical_inference import InferenceResult as CanonicalInferenceResult
from planner.ontology.runtime_program import RuntimeCanonicalFactCatalog, RuntimeProgram


class PlanInputs(NamedTuple):
    runtime_program: RuntimeProgram
    canonical_fact_catalog: RuntimeCanonicalFactCatalog
    slots: dict[str, Slot]
    substances: dict[str, Substance]
    products: dict[str, Product]
    stack_entries: dict[str, StackEntry]
    pillboxes: dict[str, Pillbox]


class ActiveIndex(NamedTuple):
    item_products: dict[str, str]
    item_stacks: dict[str, str]
    canonical_inference: CanonicalInferenceResult
