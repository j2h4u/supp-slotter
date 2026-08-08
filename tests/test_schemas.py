"""Substance schema checks."""

from __future__ import annotations

from pathlib import Path
from typing import cast

from planner.ontology.schema_enums import schema_enum_values
from planner.schema_validation import load_schema, schema_errors
from planner.yaml_io import YamlValue

from tests.helpers import ontology_bundle

ROOT = Path(__file__).resolve().parents[1]


def _make_substance_card(**extra: YamlValue) -> dict[str, YamlValue]:
    base: dict[str, YamlValue] = {"id": "sub_zz0000zzzz", "name": "Test Substance"}
    base.update(extra)
    return base


def test_substance_schema_accepts_nested_form() -> None:
    card = _make_substance_card(
        schedule={"intake": ["food_preferred"], "timing": ["sleep_support"]},
        knowledge={"kind": ["amino"], "risk": ["manual_review"]},
    )
    errors = schema_errors(card, "substance", Path("test"), ontology_bundle())
    assert errors == [], f"Expected no errors, got: {errors}"


def test_relation_schema_error_describes_canonical_selector_shape() -> None:
    errors = schema_errors(
        {
            "relations": [
                {
                    "id": "rel_invalid_selector",
                    "type": "supports",
                    "reason": "invalid selector fixture",
                    "source_selector": {"source_name": "fixture"},
                    "target_selector": {"target_trait": "fixture"},
                    "assertion_kind": "ontology_assertion",
                    "semantic_family": "biochemical_mechanism_assertion",
                }
            ]
        },
        "relations",
        Path("relations.yaml"),
        ontology_bundle(),
    )

    endpoint_errors = [error for error in errors if "relation endpoints must choose" in error]
    assert len(endpoint_errors) == 2
    assert all("{entity: {id|name}}" in error for error in endpoint_errors)
    assert all("source_name" not in error and "source_trait" not in error for error in endpoint_errors)


def test_relation_schema_enforces_ontology_relation_type_and_severity_enums() -> None:
    bundle = ontology_bundle()
    schema = load_schema("relations", bundle)
    defs = cast(dict[str, object], schema["$defs"])
    relation_list = cast(dict[str, object], defs["relationList"])
    relation_items = cast(dict[str, object], relation_list["items"])
    relation_properties = cast(dict[str, dict[str, object]], relation_items["properties"])

    relation_types = bundle.runtime_vocabulary["relation_types"]
    assert relation_properties["type"]["enum"] == list(cast(dict[str, object], relation_types))
    assert relation_properties["severity"]["enum"] == list(schema_enum_values(bundle, "Severity"))

    errors = schema_errors(
        {
            "relations": [
                {
                    "id": "rel_invalid_type_and_severity",
                    "type": "not_authored",
                    "reason": "invalid enum fixture",
                    "source_selector": {"entity": {"id": "sub_aaaaaaaaaa"}},
                    "target_selector": {"entity": {"id": "sub_bbbbbbbbbb"}},
                    "assertion_kind": "ontology_assertion",
                    "semantic_family": "biochemical_mechanism_assertion",
                    "severity": "not_authored",
                }
            ]
        },
        "relations",
        Path("relations.yaml"),
        bundle,
    )

    assert any("relations/0/type" in error and "not_authored" in error for error in errors)
    assert any("relations/0/severity" in error and "not_authored" in error for error in errors)
