"""Fail-closed loading for checked-in generated ontology artifacts."""

from __future__ import annotations

from pathlib import Path
from typing import cast

import yaml

from planner.ontology.errors import OntologyInfrastructureError
from planner.ontology.generate import generate_ontology
from planner.ontology.runtime_contract import validate_runtime_assertions

RUNTIME_VOCABULARY_FORMAT = "supp-slotter.runtime-vocabulary/v2"


def load_runtime_vocabulary(ontology_root: Path) -> dict[str, object]:
    """Load a fresh generated vocabulary or raise an infrastructure failure."""
    generate_ontology(ontology_root, check=True)
    path = ontology_root / "generated" / "runtime-vocabulary.yaml"
    try:
        loaded = _safe_yaml_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as error:
        raise OntologyInfrastructureError(f"Cannot load generated runtime vocabulary {path}: {error}") from error
    if not isinstance(loaded, dict):
        raise OntologyInfrastructureError(f"Generated runtime vocabulary must be a mapping: {path}")
    vocabulary = cast(dict[str, object], loaded)
    if vocabulary.get("format") != RUNTIME_VOCABULARY_FORMAT:
        raise OntologyInfrastructureError(
            f"Unsupported generated runtime vocabulary format: {path}; expected {RUNTIME_VOCABULARY_FORMAT}. "
            "Run uv run python scripts/generate_ontology.py"
        )
    if vocabulary.get("schema_version") != "2" or not isinstance(vocabulary.get("slot_policy_evidence"), dict):
        raise OntologyInfrastructureError(f"Generated runtime vocabulary is missing v2 governance: {path}")
    validate_runtime_assertions(vocabulary.get("assertions"))
    return vocabulary


def _safe_yaml_load(text: str) -> object:
    return cast(object, yaml.safe_load(text))
