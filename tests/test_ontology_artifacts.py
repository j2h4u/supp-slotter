"""v2 ontology artifact and fail-closed generator contract."""

import shutil
from pathlib import Path
from typing import cast

import pytest
import yaml
from planner.ontology.artifacts import load_runtime_vocabulary
from planner.ontology.errors import OntologyInfrastructureError
from planner.ontology.generate import generate_ontology

ROOT = Path(__file__).resolve().parents[1]
ONTOLOGY = ROOT / "ontology"


def test_runtime_v2_shape_and_catalog() -> None:
    runtime = load_runtime_vocabulary(ONTOLOGY)
    assert runtime["format"] == "supp-slotter.runtime-vocabulary/v2"
    assert runtime["schema_version"] == "2"
    assert isinstance(runtime["slot_policy_evidence"], dict)
    assert isinstance(runtime["scheduling_policies"], dict)
    assert isinstance(runtime["audit_review_rules"], list)


def test_generation_is_deterministic_and_fresh(tmp_path: Path) -> None:
    copied = tmp_path / "ontology"
    shutil.copytree(ONTOLOGY, copied)
    shutil.copytree(ROOT / "data", tmp_path / "data")
    generate_ontology(copied)
    first = {p.name: p.read_bytes() for p in (copied / "generated").iterdir()}
    generate_ontology(copied)
    assert {p.name: p.read_bytes() for p in (copied / "generated").iterdir()} == first
    generate_ontology(copied, check=True)


def test_v1_runtime_is_rejected_with_regeneration_guidance(tmp_path: Path) -> None:
    copied = tmp_path / "ontology"
    shutil.copytree(ONTOLOGY, copied)
    runtime = copied / "generated/runtime-vocabulary.yaml"
    raw = cast(dict[str, object], yaml.safe_load(runtime.read_text(encoding="utf-8")))
    raw["format"] = "supp-slotter.runtime-vocabulary/v1"
    runtime.write_text(yaml.safe_dump(raw, sort_keys=False), encoding="utf-8")
    with pytest.raises(OntologyInfrastructureError):
        load_runtime_vocabulary(copied)


@pytest.mark.parametrize("field", ["status", "enforcement", "scope", "evidence", "owner", "review_by"])
def test_missing_policy_governance_fails_closed(tmp_path: Path, field: str) -> None:
    copied = tmp_path / "ontology"
    shutil.copytree(ONTOLOGY, copied)
    policy_path = copied / "policies.yaml"
    authored = cast(dict[str, object], yaml.safe_load(policy_path.read_text(encoding="utf-8")))
    policy = cast(dict[str, object], cast(dict[str, object], authored["scheduling_policies"])["intake:food_preferred"])
    policy.pop(field, None)
    policy_path.write_text(yaml.safe_dump(authored, sort_keys=False), encoding="utf-8")
    with pytest.raises(OntologyInfrastructureError):
        generate_ontology(copied)


def test_invalid_pending_block_and_retired_effects_fail(tmp_path: Path) -> None:
    copied = tmp_path / "ontology"
    shutil.copytree(ONTOLOGY, copied)
    path = copied / "policies.yaml"
    authored = cast(dict[str, object], yaml.safe_load(path.read_text(encoding="utf-8")))
    policies = cast(dict[str, object], authored["scheduling_policies"])
    pending = cast(dict[str, object], policies["activity:post_workout"])
    pending["enforcement"] = "block"
    path.write_text(yaml.safe_dump(authored, sort_keys=False), encoding="utf-8")
    with pytest.raises(OntologyInfrastructureError):
        generate_ontology(copied)


def test_evidence_catalog_rejects_empty_authoritative_text(tmp_path: Path) -> None:
    copied = tmp_path / "ontology"
    shutil.copytree(ONTOLOGY, copied)
    shutil.copytree(ROOT / "data", tmp_path / "data")
    path = copied / "policies.yaml"
    authored = cast(dict[str, object], yaml.safe_load(path.read_text(encoding="utf-8")))
    catalog = cast(dict[str, object], authored["slot_policy_evidence"])
    evidence = cast(dict[str, object], catalog["enzyme.E5"])
    evidence["supports"] = ""
    path.write_text(yaml.safe_dump(authored, sort_keys=False), encoding="utf-8")
    with pytest.raises(OntologyInfrastructureError, match="supports"):
        generate_ontology(copied)
