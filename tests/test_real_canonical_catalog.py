"""Repository acceptance for the verified generic scheduling projection."""

from __future__ import annotations

from pathlib import Path

from planner.cards.product import load_product_registry
from planner.cards.substance import load_substance_registry
from planner.ontology.canonical_facts import validate_canonical_scheduling
from planner.paths import Paths

from tests.helpers import ontology_bundle


def test_current_repository_facts_are_validated_through_one_generic_catalog() -> None:
    bundle = ontology_bundle()
    paths = Paths.from_root(Path(__file__).resolve().parents[1])
    scheduling = bundle.runtime_program.canonical_scheduling

    validate_canonical_scheduling(
        scheduling,
        load_substance_registry(paths, bundle),
        load_product_registry(paths, bundle),
    )
    assert len(scheduling.facts) == 6
    assert len(scheduling.laws) == 9
    assert len(scheduling.evidence_sources) == 12
    assert {fact.family for fact in scheduling.facts} == {"FoodEffect", "PreExercisePerformanceEffect"}
