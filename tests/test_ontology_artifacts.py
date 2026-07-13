"""Contract tests for the canonical executable ontology package."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
from planner.ontology.errors import OntologyInfrastructureError
from planner.ontology.generate import generate_ontology
from planner.ontology.validation import validate_graph
from rdflib import RDF, Graph, Literal, Namespace, URIRef

ROOT = Path(__file__).resolve().parents[1]
ONTOLOGY_ROOT = ROOT / "ontology"
SS = Namespace("https://j2h4u.github.io/supp-slotter/ontology/v1/")


@pytest.mark.parametrize(
    "command",
    [
        ["scripts/generate_ontology.py", "--check"],
        ["-m", "scripts.generate_ontology", "--check"],
    ],
)
def test_generator_cli_is_importable_without_pythonpath(command: list[str]) -> None:
    environment = os.environ.copy()
    environment.pop("PYTHONPATH", None)

    subprocess.run(
        [sys.executable, *command],
        check=True,
        cwd=ROOT,
        env=environment,
        capture_output=True,
        text=True,
    )


def test_generation_is_byte_deterministic_and_checked_in_artifacts_are_fresh(tmp_path: Path) -> None:
    copied_ontology = tmp_path / "ontology"
    shutil.copytree(ONTOLOGY_ROOT, copied_ontology, ignore=shutil.ignore_patterns("generated"))

    generate_ontology(copied_ontology)
    first = _artifact_bytes(copied_ontology)
    generate_ontology(copied_ontology)

    assert _artifact_bytes(copied_ontology) == first
    generate_ontology(copied_ontology, check=True)
    generate_ontology(ONTOLOGY_ROOT, check=True)


def test_freshness_check_fails_closed_when_generated_artifact_changes(tmp_path: Path) -> None:
    copied_ontology = tmp_path / "ontology"
    shutil.copytree(ONTOLOGY_ROOT, copied_ontology)
    generated = copied_ontology / "generated" / "runtime-vocabulary.yaml"
    generated.write_text("format: forged\n", encoding="utf-8")

    with pytest.raises(OntologyInfrastructureError, match="Stale or missing"):
        generate_ontology(copied_ontology, check=True)


def test_shacl_accepts_complete_term_and_rejects_kind_with_nonrigid_profile() -> None:
    valid = _term_graph(category=SS.kind, profile=SS.rigid_identity)
    conforms, _, report = validate_graph(valid, ONTOLOGY_ROOT)
    assert conforms, report

    invalid = _term_graph(category=SS.kind, profile=SS.anti_rigid_dependent)
    conforms, _, report = validate_graph(invalid, ONTOLOGY_ROOT)
    assert not conforms
    assert "Kinds must use the rigid_identity OntoClean profile" in report


def _artifact_bytes(ontology_root: Path) -> dict[str, bytes]:
    generated = ontology_root / "generated"
    return {path.name: path.read_bytes() for path in sorted(generated.iterdir()) if path.is_file()}


def _term_graph(*, category: URIRef, profile: URIRef) -> Graph:
    graph = Graph()
    term = SS["test-term"]
    graph.add((term, RDF.type, SS.OntologyTerm))
    graph.add((term, SS.semanticCategory, category))
    graph.add((term, SS.ontocleanProfile, profile))
    graph.add((term, SS.label, Literal("Test term")))
    return graph
