"""Focused tests for the pure locked-artifact runtime loader."""

from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path
from typing import cast

import pytest
import yaml
from planner.ontology.artifacts import OntologyBundle, load_ontology, load_runtime_vocabulary
from planner.ontology.errors import (
    MALFORMED,
    MISSING,
    STALE,
    UNSUPPORTED,
    OntologyInfrastructureError,
)

ROOT = Path(__file__).resolve().parents[1]
ONTOLOGY = ROOT / "ontology"


def _fixture(tmp_path: Path) -> Path:
    repository = tmp_path / "repo"
    shutil.copytree(ONTOLOGY, repository / "ontology")
    scripts = repository / "scripts"
    scripts.mkdir()
    shutil.copy2(ROOT / "scripts/ontology_compiler.py", scripts / "ontology_compiler.py")
    data = repository / "data"
    data.mkdir()
    shutil.copy2(ROOT / "data/relations.yaml", data / "relations.yaml")
    return repository / "ontology"


def _raises(root: Path, code: str) -> None:
    with pytest.raises(OntologyInfrastructureError) as raised:
        load_ontology(root)
    assert raised.value.code == code


def test_success_and_runtime_vocabulary_delegate_to_one_bundle(tmp_path: Path) -> None:
    root = _fixture(tmp_path)
    bundle = load_ontology(root)
    assert isinstance(bundle, OntologyBundle)
    assert bundle.runtime_vocabulary["format"] == "supp-slotter.runtime-vocabulary/v2"
    assert load_runtime_vocabulary(root) == bundle.runtime_vocabulary
    profiles = bundle.ontoclean_profiles
    assert set(profiles) == {"rigid_identity", "anti_rigid_dependent", "dependent_assertion"}
    categories = cast(dict[str, dict[str, object]], bundle.runtime_vocabulary["categories"])
    for term in cast(list[dict[str, object]], bundle.runtime_vocabulary["terms"]):
        category = cast(str, term["semantic_category"])
        assert term["ontoclean_profile"] == categories[category]["ontoclean_profile"]


def test_missing_output_fails_closed(tmp_path: Path) -> None:
    root = _fixture(tmp_path)
    (root / "generated/runtime-program.json").unlink()
    _raises(root, MISSING)


def test_source_and_output_hash_mismatch_are_stale(tmp_path: Path) -> None:
    root = _fixture(tmp_path)
    (root / "model.yaml").write_text((root / "model.yaml").read_text() + "\n# mutation\n")
    _raises(root, STALE)

    root = _fixture(tmp_path / "second")
    output = root / "generated/runtime-vocabulary.yaml"
    output.write_bytes(output.read_bytes() + b"\n")
    _raises(root, STALE)


def test_malformed_and_unsupported_contracts_fail_closed(tmp_path: Path) -> None:
    root = _fixture(tmp_path)
    output = root / "generated/runtime-program.json"
    output.write_bytes(b"{")
    lock_path = root / "generated/artifact-lock.json"
    lock = cast(dict[str, object], json.loads(lock_path.read_text()))
    for record in cast(list[dict[str, object]], lock["outputs"]):
        if record["path"] == "runtime-program.json":
            record["sha256"] = hashlib.sha256(b"{").hexdigest()
    lock_path.write_text(json.dumps(lock, indent=2) + "\n")
    _raises(root, MALFORMED)

    root = _fixture(tmp_path / "second")
    lock_path = root / "generated/artifact-lock.json"
    lock = cast(dict[str, object], json.loads(lock_path.read_text()))
    lock["format_version"] = "unknown-lock"
    lock_path.write_text(json.dumps(lock, indent=2) + "\n")
    _raises(root, UNSUPPORTED)


@pytest.mark.parametrize(
    "mutation",
    ["empty_terms", "category_identity", "unknown_profile", "term_profile_mismatch", "changed_profile"],
)
def test_bundle_registration_rejects_malformed_catalog_before_card_load(tmp_path: Path, mutation: str) -> None:
    root = _fixture(tmp_path)
    vocabulary_path = root / "generated/runtime-vocabulary.yaml"
    vocabulary = cast(dict[str, object], yaml.safe_load(vocabulary_path.read_text(encoding="utf-8")))
    if mutation == "empty_terms":
        vocabulary["terms"] = []
    elif mutation == "category_identity":
        categories = cast(dict[str, dict[str, object]], vocabulary["categories"])
        categories["kind"]["allowed_predicates"] = ["knowledge.role"]
    elif mutation == "unknown_profile":
        terms = cast(list[dict[str, object]], vocabulary["terms"])
        terms[0]["ontoclean_profile"] = "unknown_profile"
    elif mutation == "term_profile_mismatch":
        terms = cast(list[dict[str, object]], vocabulary["terms"])
        categories = cast(dict[str, dict[str, object]], vocabulary["categories"])
        terms[0]["ontoclean_profile"] = categories["kind"]["ontoclean_profile"]
        categories[cast(str, terms[0]["semantic_category"])]["ontoclean_profile"] = "anti_rigid_dependent"
    else:
        profiles = cast(dict[str, dict[str, object]], vocabulary["ontoclean_profiles"])
        profiles["rigid_identity"]["rigidity"] = "anti_rigid"
    content = yaml.safe_dump(vocabulary, sort_keys=False).encode("utf-8")
    vocabulary_path.write_bytes(content)
    lock_path = root / "generated/artifact-lock.json"
    lock = cast(dict[str, object], json.loads(lock_path.read_text(encoding="utf-8")))
    for record in cast(list[dict[str, object]], lock["outputs"]):
        if record["path"] == "runtime-vocabulary.yaml":
            record["sha256"] = hashlib.sha256(content).hexdigest()
    lock_path.write_text(json.dumps(lock, indent=2) + "\n")

    _raises(root, MALFORMED)
