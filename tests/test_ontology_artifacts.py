"""Generated ontology artifact checks without retired governance contracts."""

from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path
from typing import cast

import yaml
from planner.ontology.artifacts import load_runtime_program
from scripts.ontology_compiler import compile_ontology

ROOT = Path(__file__).resolve().parents[1]
ONTOLOGY = ROOT / "ontology"


def _copy_repository_shape(tmp_path: Path) -> Path:
    repository = tmp_path / "repo"
    copied = repository / "ontology"
    shutil.copytree(ONTOLOGY, copied)
    manifest = cast(dict[str, object], yaml.safe_load((ONTOLOGY / "manifest.yaml").read_text(encoding="utf-8")))
    paths: set[str] = set()
    for field in ("linkml_root", "linkml_modules", "policy_sources", "constraint_sources", "assertion_sources", "custom_shapes"):
        value = manifest.get(field)
        if isinstance(value, str):
            paths.add(value)
        elif isinstance(value, list):
            paths.update(item for item in value if isinstance(item, str))
    for catalog in cast(list[dict[str, object]], manifest.get("catalogs", [])):
        path = catalog.get("path")
        if isinstance(path, str):
            paths.add(path)
    projection = manifest.get("repository_projection")
    if isinstance(projection, dict):
        for source in cast(list[object], projection.get("sources", [])):
            if not isinstance(source, dict):
                continue
            locator = source.get("locator")
            if not isinstance(locator, dict):
                continue
            kind = locator.get("kind")
            if kind == "flat_root":
                value = locator.get("path")
                if isinstance(value, str):
                    source_dir = ROOT / value
                    paths.update(
                        (Path(value) / child.name).as_posix()
                        for child in source_dir.iterdir()
                        if child.is_file() and child.suffix == ".yaml"
                    )
            elif kind == "explicit_path":
                value = locator.get("path")
                if isinstance(value, str):
                    paths.add(value)
            elif kind == "explicit_paths":
                values = locator.get("paths")
                if isinstance(values, list):
                    paths.update(item for item in values if isinstance(item, str))
    for relative in paths:
        source = ROOT / relative
        destination = repository / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
    return copied


def test_generation_is_deterministic_and_direct_projection_is_fresh() -> None:
    first = compile_ontology(ONTOLOGY)
    assert compile_ontology(ONTOLOGY) == first
    program = json.loads(first[Path("runtime-program.json")])
    projection = cast(dict[str, object], program["projection"])
    assert "effect_scoring" in projection
    assert "prefer_with_policy" in projection
    assert "constraint_execution_policies" in projection


def test_committed_runtime_program_decodes() -> None:
    runtime = load_runtime_program(ONTOLOGY)
    assert runtime.effect_scoring.prefer_with_bonus > 0
    assert runtime.constraint_execution_policy_for("separate_products_same_slot") is not None


def test_runtime_source_digest_is_current() -> None:
    program = json.loads((ONTOLOGY / "generated/runtime-program.json").read_text(encoding="utf-8"))
    provenance = cast(dict[str, object], program["provenance"])
    assert provenance["source_sha256"] == hashlib.sha256((ONTOLOGY / "runtime-policy.yaml").read_bytes()).hexdigest()
