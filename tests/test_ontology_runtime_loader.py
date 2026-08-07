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
    UNSAFE_PATH,
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


def _lock(root: Path) -> dict[str, object]:
    return cast(dict[str, object], json.loads((root / "generated/artifact-lock.json").read_text()))


def _write_lock(root: Path, lock: dict[str, object]) -> None:
    (root / "generated/artifact-lock.json").write_text(json.dumps(lock, indent=2) + "\n")


def _refresh_manifest_hash(root: Path, lock: dict[str, object]) -> None:
    digest = hashlib.sha256((root / "manifest.yaml").read_bytes()).hexdigest()
    for record in cast(list[dict[str, object]], lock["sources"]):
        if record["path"] == "ontology/manifest.yaml":
            record["sha256"] = digest
            return
    raise AssertionError("fixture lock has no manifest source record")


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


def test_unsafe_output_path_fails_closed(tmp_path: Path) -> None:
    root = _fixture(tmp_path)
    lock = _lock(root)
    outputs = cast(list[dict[str, object]], lock["outputs"])
    outputs[0]["path"] = "../escape.json"
    _write_lock(root, lock)
    _raises(root, UNSAFE_PATH)


def test_symlink_output_fails_closed(tmp_path: Path) -> None:
    root = _fixture(tmp_path)
    output = root / "generated/runtime-program.json"
    payload = output.read_bytes()
    output.unlink()
    output.symlink_to(root / "generated/runtime-vocabulary.yaml")
    _raises(root, UNSAFE_PATH)
    output.unlink()
    output.write_bytes(payload)


def test_minimal_artifact_inventory_fails_closed(tmp_path: Path) -> None:
    root = _fixture(tmp_path)
    manifest = cast(dict[str, object], yaml.safe_load((root / "manifest.yaml").read_bytes()))
    assert isinstance(manifest, dict)
    manifest["artifacts"] = ["runtime-vocabulary.yaml", "artifact-lock.json"]
    (root / "manifest.yaml").write_text(yaml.safe_dump(manifest, sort_keys=False))
    lock = _lock(root)
    _refresh_manifest_hash(root, lock)
    _write_lock(root, lock)
    _raises(root, UNSUPPORTED)


def test_malformed_and_unsupported_contracts_fail_closed(tmp_path: Path) -> None:
    root = _fixture(tmp_path)
    output = root / "generated/runtime-program.json"
    output.write_bytes(b"{")
    lock = _lock(root)
    for record in cast(list[dict[str, object]], lock["outputs"]):
        if record["path"] == "runtime-program.json":
            record["sha256"] = hashlib.sha256(b"{").hexdigest()
    _write_lock(root, lock)
    _raises(root, MALFORMED)

    root = _fixture(tmp_path / "second")
    lock = _lock(root)
    lock["format_version"] = "unknown-lock"
    _write_lock(root, lock)
    _raises(root, UNSUPPORTED)
