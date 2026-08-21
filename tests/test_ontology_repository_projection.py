"""Focused tests for compiled repository discovery and RDF projection."""

from __future__ import annotations

from pathlib import Path

import pytest
from planner.ontology.artifacts import load_ontology
from planner.ontology.errors import OntologyInfrastructureError
from planner.ontology.projection import _project_repository_with_projection, project_repository
from rdflib import URIRef
from rdflib.namespace import RDF

BASE = "https://example.test/ontology/"


def _map() -> dict[str, object]:
    sources: list[dict[str, object]] = [
        {
            "id": "substances",
            "locator": {"kind": "flat_root", "path": "data/substances"},
            "root_class": "Substance",
            "documents": {
                "document_shape": "mapping",
                "identity": {"source": "id", "predicate": BASE + "slot/id"},
                "instructions": [
                    {"kind": "slot", "source": "id", "predicate": BASE + "slot/id"},
                    {"kind": "alias", "source": "name", "predicate": BASE + "slot/label"},
                    {"kind": "sequence", "source": "aliases[]", "predicate": BASE + "slot/aliases"},
                ],
            },
        },
        {
            "id": "products",
            "locator": {"kind": "flat_root", "path": "data/products"},
            "root_class": "Product",
            "documents": {
                "document_shape": "mapping",
                "identity": {"source": "id", "predicate": BASE + "slot/id"},
                "instructions": [
                    {"kind": "slot", "source": "id", "predicate": BASE + "slot/id"},
                    {
                        "kind": "reference",
                        "source": "substance",
                        "predicate": BASE + "slot/substance",
                        "target": "Substance",
                    },
                ],
            },
        },
        {
            "id": "dashboards",
            "locator": {"kind": "flat_root", "path": "data/dashboards"},
            "root_class": "Dashboard",
            "documents": {
                "document_shape": "mapping",
                "identity": {"source": "id", "predicate": BASE + "slot/id"},
                "instructions": [{"kind": "slot", "source": "id", "predicate": BASE + "slot/id"}],
            },
        },
        {
            "id": "stacks",
            "locator": {"kind": "explicit_path", "path": "data/stacks.yaml"},
            "root_class": "Stack",
            "documents": {
                "document_shape": "keyed-map",
                "identity": {"source": "<key>", "predicate": BASE + "slot/id"},
                "instructions": [
                    {"kind": "sequence", "source": "<key>[]", "predicate": BASE + "slot/product", "target": "Product"}
                ],
            },
        },
        {
            "id": "pillboxes",
            "locator": {"kind": "explicit_path", "path": "data/pillboxes.yaml"},
            "root_class": "Pillbox",
            "documents": {
                "document_shape": "keyed-map",
                "identity": {"source": "<key>", "predicate": BASE + "slot/id"},
                "instructions": [{"kind": "slot", "source": "<key>.label", "predicate": BASE + "slot/label"}],
            },
        },
        {
            "id": "assertions",
            "locator": {"kind": "catalog_ref", "catalog_id": "assertions"},
            "root_class": "AssertionCatalog",
            "documents": {
                "document_shape": "mapping",
                "instructions": [{"kind": "slot", "source": "relations[].id", "predicate": BASE + "slot/assertion_id"}],
            },
        },
    ]
    return {
        "catalogs": [{"id": "assertions", "path": "data/relations.yaml"}],
        "repository_projection": {"format_version": "repository-projection-v1", "base_iri": BASE, "sources": sources},
    }


def _repo(tmp_path: Path) -> Path:
    (tmp_path / "data/substances").mkdir(parents=True)
    (tmp_path / "data/products").mkdir()
    (tmp_path / "data/dashboards").mkdir()
    (tmp_path / "data/substances/a.yaml").write_text("id: sub_a\nname: A\naliases: [aa]\n", encoding="utf-8")
    (tmp_path / "data/products/p.yaml").write_text("id: prd_p\nsubstance: sub_a\n", encoding="utf-8")
    (tmp_path / "data/dashboards/d.yaml").write_text("id: dash_d\n", encoding="utf-8")
    (tmp_path / "data/stacks.yaml").write_text("daily: [prd_p]\n", encoding="utf-8")
    (tmp_path / "data/pillboxes.yaml").write_text("daily:\n  label: Daily\n", encoding="utf-8")
    (tmp_path / "data/relations.yaml").write_text("relations:\n- id: rel_1\n", encoding="utf-8")
    return tmp_path


def test_catalog_ref_selects_declared_catalog_and_does_not_ingest_schedule(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    (repo / "schedule.yaml").write_text("id: should_not_be_read\n", encoding="utf-8")
    result = _project_repository_with_projection(repo, _map())
    assert any(
        record.source_id == "assertions" and record.field_path == "relations[0].id" for record in result.provenance
    )
    assert not any("should_not_be_read" in triple for triple in result.triples)


def test_unknown_empty_container_fails_closed(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    (repo / "data/substances/a.yaml").write_text("id: sub_a\nname: A\nunknown: {}\n", encoding="utf-8")
    with pytest.raises(OntologyInfrastructureError, match="unknown"):
        _project_repository_with_projection(repo, _map())


def test_scheduling_assessment_projects_one_typed_envelope_and_three_axes() -> None:
    graph = project_repository(Path(__file__).resolve().parents[1], load_ontology(Path("ontology"))).graph
    base = "https://j2h4u.github.io/supp-slotter/ontology/v1/"
    substance = URIRef(base + "substance/sub_4j9fttkil9")
    envelope_predicate = URIRef(base + "scheduling_assessment")
    envelope = list(graph.objects(substance, envelope_predicate))
    assert len(envelope) == 1
    envelope_node = envelope[0]
    assert (envelope_node, RDF.type, URIRef(base + "SchedulingAssessment")) in graph
    for axis in ("intake", "timing", "activity"):
        records = list(graph.objects(envelope_node, URIRef(base + axis)))
        assert len(records) == 1
        assert (records[0], RDF.type, URIRef(base + "SchedulingAssessmentRecord")) in graph
