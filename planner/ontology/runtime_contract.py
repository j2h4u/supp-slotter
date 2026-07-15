"""Frozen runtime assertions for generated ontology v2 artifacts."""

from __future__ import annotations

from planner.ontology.errors import OntologyInfrastructureError


def runtime_assertions() -> dict[str, object]:
    return {
        "assignment_governance_required": True,
        "scope_allowlist": [
            "planner",
            "food_model",
            "slot_model",
            "intended_use",
            "substrate",
            "product",
            "formulation",
        ],
    }


def validate_runtime_assertions(raw: object) -> None:
    if raw != runtime_assertions():
        raise OntologyInfrastructureError(
            "Generated runtime vocabulary assertions are non-canonical; run uv run python scripts/generate_ontology.py"
        )
