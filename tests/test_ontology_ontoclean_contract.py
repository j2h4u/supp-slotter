"""Executable OntoClean and keyed-catalog identity contracts."""

from __future__ import annotations

from pathlib import Path
from typing import cast

import pytest
import yaml
from linkml_runtime.utils.schemaview import SchemaView
from planner.ontology.errors import OntologyInfrastructureError
from scripts.ontology_compiler import (
    _keyed_record_map,
    _linkml_catalog_instance,
    _load_ontoclean_profiles,
    _validate_linkml_instance,
    _validate_semantic_categories,
    compile_ontology,
)

from tests.test_ontology_artifacts import _copy_repository_shape

ROOT = Path(__file__).resolve().parents[1]
ONTOLOGY = ROOT / "ontology"


def _load_catalog(name: str) -> dict[str, object]:
    value = yaml.safe_load((ONTOLOGY / name).read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return cast(dict[str, object], value)


def test_semantic_categories_reject_unknown_ontoclean_profile() -> None:
    vocabulary = _load_catalog("vocabulary.yaml")
    categories = cast(dict[str, dict[str, object]], vocabulary["semantic_categories"])
    categories["kind"]["ontoclean_profile"] = "unknown"
    profiles = _keyed_record_map(cast(dict[str, object], _load_catalog("ontoclean.yaml")["ontoclean_profiles"]))

    with pytest.raises(OntologyInfrastructureError, match="unknown OntoClean profile"):
        _validate_semantic_categories(categories, profiles)


def test_linkml_instance_validator_rejects_invalid_ontoclean_rigidity(tmp_path: Path) -> None:
    root = _copy_repository_shape(tmp_path)
    source = cast(dict[str, object], yaml.safe_load((root / "ontoclean.yaml").read_text(encoding="utf-8")))
    profiles = cast(dict[str, dict[str, object]], source["ontoclean_profiles"])
    profiles["rigid_identity"]["rigidity"] = "not_a_rigidity"
    schema_view = SchemaView(str(root / "supp_slotter.yaml"))

    with pytest.raises(OntologyInfrastructureError, match="Invalid OntoCleanCatalog instance"):
        _validate_linkml_instance(schema_view, "OntoCleanCatalog", _linkml_catalog_instance("OntoCleanCatalog", source))


def test_keyed_record_map_rejects_mismatched_embedded_profile_id() -> None:
    source = _load_catalog("ontoclean.yaml")
    profiles = cast(dict[str, dict[str, object]], source["ontoclean_profiles"])
    profiles["rigid_identity"]["id"] = "other"

    with pytest.raises(OntologyInfrastructureError, match="mismatched embedded id"):
        _keyed_record_map(cast(dict[str, object], source["ontoclean_profiles"]))


def test_ontoclean_profiles_reject_anti_rigid_identity_supply(tmp_path: Path) -> None:
    root = _copy_repository_shape(tmp_path)
    path = root / "ontoclean.yaml"
    source = cast(dict[str, object], yaml.safe_load(path.read_text(encoding="utf-8")))
    profiles = cast(dict[str, dict[str, object]], source["ontoclean_profiles"])
    profiles["anti_rigid_dependent"]["supplies_identity"] = True
    path.write_text(yaml.safe_dump(source, sort_keys=False), encoding="utf-8")
    manifest = cast(dict[str, object], yaml.safe_load((root / "manifest.yaml").read_text(encoding="utf-8")))
    schema_view = SchemaView(str(root / "supp_slotter.yaml"))

    with pytest.raises(OntologyInfrastructureError, match="anti-rigid but supplies identity"):
        _load_ontoclean_profiles(root, manifest, schema_view)


def test_current_ontoclean_catalog_is_executable_and_projected(tmp_path: Path) -> None:
    root = _copy_repository_shape(tmp_path)
    artifacts = compile_ontology(root)
    runtime = cast(dict[str, object], yaml.safe_load(artifacts[Path("runtime-vocabulary.yaml")]))
    profiles = cast(dict[str, dict[str, object]], runtime["ontoclean_profiles"])
    assert set(profiles) == {"rigid_identity", "anti_rigid_dependent", "dependent_assertion"}
    assert profiles["rigid_identity"] == {
        "id": "rigid_identity",
        "rigidity": "rigid",
        "supplies_identity": True,
        "dependence": "independent",
    }
