"""Executable OntoClean and keyed-catalog identity contracts."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import cast

import pytest
import yaml
from planner.ontology.errors import OntologyInfrastructureError
from scripts.ontology_compiler import compile_ontology

from tests.test_ontology_artifacts import _copy_repository_shape


@pytest.mark.parametrize(
    ("catalog", "mutate", "message"),
    [
        (
            "vocabulary.yaml",
            lambda source: cast(dict[str, dict[str, object]], source["semantic_categories"])["kind"].update(
                ontoclean_profile="unknown"
            ),
            "unknown OntoClean profile",
        ),
        (
            "ontoclean.yaml",
            lambda source: cast(dict[str, dict[str, object]], source["ontoclean_profiles"])["rigid_identity"].update(
                rigidity="not_a_rigidity"
            ),
            "Invalid OntoCleanCatalog instance",
        ),
        (
            "ontoclean.yaml",
            lambda source: cast(dict[str, dict[str, object]], source["ontoclean_profiles"])["rigid_identity"].update(
                id="other"
            ),
            "mismatched embedded id",
        ),
        (
            "ontoclean.yaml",
            lambda source: cast(dict[str, dict[str, object]], source["ontoclean_profiles"])[
                "anti_rigid_dependent"
            ].update(supplies_identity=True),
            "anti-rigid but supplies identity",
        ),
    ],
)
def test_ontoclean_mutations_fail_closed(
    tmp_path: Path, catalog: str, mutate: Callable[[dict[str, object]], None], message: str
) -> None:
    root = _copy_repository_shape(tmp_path)
    path = root / catalog
    source = cast(dict[str, object], yaml.safe_load(path.read_text(encoding="utf-8")))
    mutate(source)
    path.write_text(yaml.safe_dump(source, sort_keys=False), encoding="utf-8")

    with pytest.raises(OntologyInfrastructureError, match=message):
        compile_ontology(root)


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


def test_duplicate_keyed_profile_id_is_rejected(tmp_path: Path) -> None:
    root = _copy_repository_shape(tmp_path)
    path = root / "ontoclean.yaml"
    path.write_text(
        path.read_text(encoding="utf-8")
        + "\n  rigid_identity:\n    rigidity: rigid\n    supplies_identity: true\n    dependence: independent\n",
        encoding="utf-8",
    )

    with pytest.raises(OntologyInfrastructureError, match="duplicate key"):
        compile_ontology(root)
