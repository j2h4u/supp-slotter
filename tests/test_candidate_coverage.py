"""Focused acceptance checks for the closed candidate/coverage boundary."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from planner.cards.product import load_product_registry
from planner.cards.relations import load_global_relations
from planner.cards.stacks import normalize_stack_entries
from planner.cards.substance import load_substance_registry
from planner.ontology.artifacts import load_ontology
from planner.ontology.candidate_catalog import load_candidate_catalog
from planner.ontology.canonical_facts import composition_roles_for_products
from planner.ontology.coverage import (
    derive_coverage,
    load_coverage_closure,
    validate_coverage_closure,
    validate_coverage_manifest,
)
from planner.paths import Paths
from planner.yaml_io import load_yaml

ROOT = Path(__file__).resolve().parents[1]


def test_real_candidate_catalog_is_closed_and_deterministic() -> None:
    catalog = load_candidate_catalog(ROOT / "data" / "scheduling-candidates.yaml")

    assert len(catalog.candidates) == 64
    assert catalog.candidate_ids == tuple(candidate.id for candidate in catalog.candidates)
    assert catalog.disposition_counts == {
        "neutral": 5,
        "outside_model": 37,
        "pressure": 8,
        "unresolved_without_direction": 14,
    }


def test_unresolved_candidate_is_research_open_but_coverage_closed() -> None:
    catalog = load_candidate_catalog(ROOT / "data" / "scheduling-candidates.yaml")
    candidate = next(
        row
        for row in catalog.candidates
        if row.disposition == "unresolved_without_direction" and row.scope.active_shelf_reachable
    )

    manifest = derive_coverage(catalog, [{"id": candidate.scope.applicability_id}], dimensions=["meal_context"])
    certificate = manifest.certificates[0]
    assert manifest.complete
    assert certificate.research_open_candidate_ids == (candidate.id,)
    assert certificate.pressure_candidate_ids == ()


def test_empty_candidate_set_is_coverage_complete_without_fake_candidate() -> None:
    catalog = load_candidate_catalog(ROOT / "data" / "scheduling-candidates.yaml")
    manifest = derive_coverage(catalog, ["cmp_unassessed"], dimensions=["meal_context"])

    assert manifest.complete
    assert manifest.certificates[0].evaluated_candidate_ids == ()
    assert validate_coverage_manifest(manifest, catalog) == ()


def test_real_global_closure_matches_current_runtime_inputs() -> None:
    paths = Paths.default()
    bundle = load_ontology(ROOT / "ontology")
    substances = load_substance_registry(paths, bundle)
    products = load_product_registry(paths, bundle)
    entries = normalize_stack_entries(load_yaml(paths.stacks_file), bundle.runtime_program)
    routable = set(bundle.runtime_program.glue_contract.stack_partition.routable_stack_names)
    active_products = {entry["product"] for entry in entries.values() if entry["stack"] in routable}
    roles = tuple(role for role in composition_roles_for_products(products) if role.product in active_products)
    relations = load_global_relations(paths, bundle, substances)
    catalog = load_candidate_catalog(paths.data / "scheduling-candidates.yaml")
    closure = load_coverage_closure(paths.data / "coverage-closure.yaml")

    assert validate_coverage_closure(
        closure, catalog, roles, substances=substances, relations=relations
    ) == ()

    stale = replace(closure, role_universe_sha256="0" * 64)
    assert validate_coverage_closure(
        stale, catalog, roles, substances=substances, relations=relations
    ) == ("coverage closure stale role universe",)
