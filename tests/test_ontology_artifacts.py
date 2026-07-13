"""Contract tests for the canonical executable ontology package."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import cast

import pytest
import yaml
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
    shutil.copytree(ROOT / "data", tmp_path / "data")

    generate_ontology(copied_ontology)
    first = _artifact_bytes(copied_ontology)
    generate_ontology(copied_ontology)

    assert _artifact_bytes(copied_ontology) == first
    generate_ontology(copied_ontology, check=True)
    generate_ontology(ONTOLOGY_ROOT, check=True)


def test_freshness_check_fails_closed_when_generated_artifact_changes(tmp_path: Path) -> None:
    copied_ontology = tmp_path / "ontology"
    shutil.copytree(ONTOLOGY_ROOT, copied_ontology)
    shutil.copytree(ROOT / "data", tmp_path / "data")
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


def test_shacl_rejects_clinical_exposure_emitted_as_biological_effect() -> None:
    invalid = _term_graph(
        category=SS.effect,
        profile=SS.dependent_assertion,
        assertion_kind=SS.clinical_exposure_context,
    )
    conforms, _, report = validate_graph(invalid, ONTOLOGY_ROOT)

    assert not conforms
    assert "clinical_exposure_context must be a context" in report


def test_generator_rejects_planner_policy_on_biological_or_context_term(tmp_path: Path) -> None:
    copied_ontology = tmp_path / "ontology"
    shutil.copytree(ONTOLOGY_ROOT, copied_ontology)
    shutil.copytree(ROOT / "data", tmp_path / "data")
    policies = copied_ontology / "policies.yaml"
    policies.write_text(
        policies.read_text(encoding="utf-8")
        + "\n  effect:insulin_signaling_context:\n    applies_when: invalid semantic boundary probe\n",
        encoding="utf-8",
    )

    with pytest.raises(OntologyInfrastructureError, match="not a biological or context assertion"):
        generate_ontology(copied_ontology)


def test_generated_ontology_assertions_are_nonblocking_and_semantically_partitioned() -> None:
    generated = cast(
        object, yaml.safe_load((ONTOLOGY_ROOT / "generated" / "runtime-vocabulary.yaml").read_text(encoding="utf-8"))
    )
    assert isinstance(generated, dict)
    generated_mapping = cast(dict[str, object], generated)
    assertions_raw = generated_mapping.get("ontology_assertions")
    assert isinstance(assertions_raw, dict)
    assertions = {
        key: cast(dict[str, object], value)
        for key, value in cast(dict[object, object], assertions_raw).items()
        if isinstance(key, str) and isinstance(value, dict)
    }

    assert len(assertions) == 28
    assert {record["relation_type"] for record in assertions.values()} == {"balance", "supports", "review_with"}
    assert all("enforcement" not in record and "effect" not in record for record in assertions.values())
    assert assertions["rel_supports_009"]["semantic_family"] == "absorption_interaction_claim"
    assert assertions["rel_supports_010"]["semantic_family"] == "nutritional_adequacy_advisory"
    assert assertions["rel_review_with_013"]["assertion_kind"] == "clinical_review_signal"


def test_generator_rejects_invalid_assertion_family_and_endpoints(tmp_path: Path) -> None:
    copied_ontology = tmp_path / "ontology"
    copied_data = tmp_path / "data"
    shutil.copytree(ONTOLOGY_ROOT, copied_ontology)
    shutil.copytree(ROOT / "data", copied_data)
    assertions_path = copied_data / "relations.yaml"
    assertions = cast(object, yaml.safe_load(assertions_path.read_text(encoding="utf-8")))
    assert isinstance(assertions, dict)
    assertions_mapping = cast(dict[str, object], assertions)
    relations = assertions_mapping.get("relations")
    assert isinstance(relations, list)
    relation_records = cast(list[object], relations)
    assert len(relation_records) > 2 and isinstance(relation_records[2], dict)
    cast(dict[str, object], relation_records[2])["semantic_family"] = "nutrient_balance_review_signal"
    assertions_path.write_text(yaml.safe_dump(assertions, sort_keys=False), encoding="utf-8")

    with pytest.raises(OntologyInfrastructureError, match="semantic_family incompatible with supports"):
        generate_ontology(copied_ontology)


def _artifact_bytes(ontology_root: Path) -> dict[str, bytes]:
    generated = ontology_root / "generated"
    return {path.name: path.read_bytes() for path in sorted(generated.iterdir()) if path.is_file()}


def _term_graph(*, category: URIRef, profile: URIRef, assertion_kind: URIRef | None = None) -> Graph:
    graph = Graph()
    term = SS["test-term"]
    graph.add((term, RDF.type, SS.OntologyTerm))
    graph.add((term, SS.semanticCategory, category))
    graph.add((term, SS.ontocleanProfile, profile))
    graph.add((term, SS.label, Literal("Test term")))
    if assertion_kind is not None:
        graph.add((term, SS.assertionKind, assertion_kind))
    return graph
