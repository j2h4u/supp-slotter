"""Wave C2 closed repository projection contract."""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import cast

import pytest
import yaml
from planner.ontology.errors import OntologyInfrastructureError
from scripts.ontology_compiler import compile_ontology, generate_ontology

ROOT = Path(__file__).resolve().parents[1]
ONTOLOGY = ROOT / "ontology"


def _fixture(tmp_path: Path) -> Path:
    repository = tmp_path / "repo"
    shutil.copytree(ONTOLOGY, repository / "ontology")
    shutil.copytree(ROOT / "data", repository / "data")
    return repository / "ontology"


def _manifest(path: Path) -> dict[str, object]:
    return cast(dict[str, object], yaml.safe_load(path.read_text(encoding="utf-8")))


def _write_manifest(path: Path, manifest: dict[str, object]) -> None:
    path.write_text(yaml.safe_dump(manifest, sort_keys=False), encoding="utf-8")


def test_projection_sources_are_closed_and_catalog_ref_is_not_a_live_path() -> None:
    manifest = _manifest(ONTOLOGY / "manifest.yaml")
    projection = cast(dict[str, object], manifest["repository_projection"])
    assert projection["format_version"] == "repository-projection-v1"
    sources = cast(list[dict[str, object]], projection["sources"])
    assert [item["id"] for item in sources] == [
        "substances",
        "products",
        "dashboards",
        "stacks",
        "pillboxes",
        "assertions",
    ]
    assertions = sources[-1]
    assert assertions["locator"] == {"kind": "catalog_ref", "catalog_id": "assertions"}
    assert all("path" not in cast(dict[str, object], assertions["locator"]) for _ in [0])


def test_card_content_and_same_shape_addition_do_not_change_compilation(tmp_path: Path) -> None:
    ontology = _fixture(tmp_path)
    baseline = compile_ontology(ontology)
    card = next((ontology.parent / "data/substances").glob("*.yaml"))
    authored = cast(dict[str, object], cast(object, yaml.safe_load(card.read_text(encoding="utf-8"))))
    assert isinstance(authored, dict)
    authored["name"] = str(authored["name"]) + " changed"
    card.write_text(yaml.safe_dump(authored, sort_keys=False), encoding="utf-8")
    assert compile_ontology(ontology) == baseline
    extra = ontology.parent / "data/substances/fixture_unique__sub_fixtureunique.yaml"
    authored["id"] = "sub_fixtureunique"
    extra.write_text(yaml.safe_dump(authored, sort_keys=False), encoding="utf-8")
    assert compile_ontology(ontology) == baseline
    renamed = card.with_name(card.stem + "__renamed.yaml")
    card.rename(renamed)
    assert compile_ontology(ontology) == baseline
    renamed.unlink()
    assert compile_ontology(ontology) == baseline


@pytest.mark.parametrize("container", ["mapping", "list"])
def test_unknown_empty_container_fails_coverage(tmp_path: Path, container: str) -> None:
    ontology = _fixture(tmp_path)
    card = next((ontology.parent / "data/substances").glob("*.yaml"))
    authored = cast(dict[str, object], cast(object, yaml.safe_load(card.read_text(encoding="utf-8"))))
    assert isinstance(authored, dict)
    authored["unknown_field"] = {} if container == "mapping" else []
    card.write_text(yaml.safe_dump(authored, sort_keys=False), encoding="utf-8")
    with pytest.raises(OntologyInfrastructureError, match="unknown_field"):
        compile_ontology(ontology)


def test_projection_manifest_change_changes_compiler_outputs(tmp_path: Path) -> None:
    ontology = _fixture(tmp_path)
    baseline = compile_ontology(ontology)
    manifest_path = ontology / "manifest.yaml"
    manifest = _manifest(manifest_path)
    projection = cast(dict[str, object], manifest["repository_projection"])
    sources = cast(list[dict[str, object]], projection["sources"])
    cast(dict[str, object], sources[0]["locator"])["path"] = "data/products"
    _write_manifest(manifest_path, manifest)
    with pytest.raises(OntologyInfrastructureError):
        compile_ontology(ontology)
    cast(dict[str, object], sources[0]["locator"])["path"] = "data/substances"
    cast(dict[str, object], sources[0])["root_class"] = "Product"
    _write_manifest(manifest_path, manifest)
    with pytest.raises(OntologyInfrastructureError):
        compile_ontology(ontology)
    cast(dict[str, object], sources[0])["root_class"] = "Substance"
    cast(dict[str, object], sources[0]["locator"])["kind"] = "explicit_paths"
    cast(dict[str, object], sources[0]["locator"]).pop("path")
    cast(dict[str, object], sources[0]["locator"])["paths"] = [
        "data/substances/" + path.name for path in sorted((ontology.parent / "data/substances").glob("*.yaml"))
    ]
    _write_manifest(manifest_path, manifest)
    assert compile_ontology(ontology) != baseline


@pytest.mark.parametrize("mutation", ["wildcard", "dotdot", "absolute", "unknown_locator", "unknown_root"])
def test_locator_attack_matrix_fails_closed(tmp_path: Path, mutation: str) -> None:
    ontology = _fixture(tmp_path)
    manifest_path = ontology / "manifest.yaml"
    manifest = _manifest(manifest_path)
    source = cast(list[dict[str, object]], cast(dict[str, object], manifest["repository_projection"])["sources"])[0]
    locator = cast(dict[str, object], source["locator"])
    if mutation == "wildcard":
        locator["path"] = "data/*"
    elif mutation == "dotdot":
        locator["path"] = "data/../data/substances"
    elif mutation == "absolute":
        locator["path"] = str((ontology.parent / "data/substances").resolve())
    elif mutation == "unknown_locator":
        locator["kind"] = "glob"
    else:
        source["root_class"] = "Unknown"
    _write_manifest(manifest_path, manifest)
    with pytest.raises(OntologyInfrastructureError):
        compile_ontology(ontology)


def test_assertion_catalog_ref_cannot_switch_catalog_role(tmp_path: Path) -> None:
    ontology = _fixture(tmp_path)
    manifest_path = ontology / "manifest.yaml"
    manifest = _manifest(manifest_path)
    projection = cast(dict[str, object], manifest["repository_projection"])
    sources = cast(list[dict[str, object]], projection["sources"])
    assertion = next(item for item in sources if item["id"] == "assertions")
    cast(dict[str, object], assertion["locator"])["catalog_id"] = "policies"
    _write_manifest(manifest_path, manifest)
    with pytest.raises(OntologyInfrastructureError):
        compile_ontology(ontology)


def test_symlink_and_unexpected_flat_root_entry_fail_closed(tmp_path: Path) -> None:
    ontology = _fixture(tmp_path)
    root = ontology.parent / "data/substances"
    unexpected = root / "unexpected.txt"
    unexpected.write_text("x", encoding="utf-8")
    with pytest.raises(OntologyInfrastructureError):
        compile_ontology(ontology)
    unexpected.unlink()
    link = root / "linked.yaml"
    try:
        link.symlink_to(next(root.glob("*.yaml")))
    except OSError, NotImplementedError:
        pytest.skip("symlinks unavailable")
    with pytest.raises(OntologyInfrastructureError):
        compile_ontology(ontology)


def test_generated_projection_is_deterministic_and_checkable() -> None:
    first = compile_ontology(ONTOLOGY)
    second = compile_ontology(ONTOLOGY)
    assert first == second
    projection = cast(dict[str, object], json.loads(first[Path("projection-map.json")]))
    repository_projection = cast(dict[str, object], projection["repository_projection"])
    assert repository_projection["format_version"] == "repository-projection-v1"
    generate_ontology(ONTOLOGY, check=True)
