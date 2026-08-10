"""Substance schema checks."""

from __future__ import annotations

from pathlib import Path
from typing import cast

import pytest
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


def test_product_schema_rejects_unsupported_schedule_field() -> None:
    card: dict[str, YamlValue] = {
        "id": "prd_zz0000zzzz",
        "name": "Test Product",
        "components": [{"substance": "sub_zz0000zzzz"}],
        "schedule": {"timing": ["sleep_support"]},
    }
    errors = schema_errors(card, "product", Path("test"), ontology_bundle())
    assert any("schedule" in error for error in errors)


def test_generated_card_schema_owns_identity_schedule_and_reference_constraints() -> None:
    cases: tuple[dict[str, YamlValue], ...] = (
        _make_substance_card(id="sub_INVALID"),
        _make_substance_card(schedule={"intake": ["a", "b"]}),
        _make_substance_card(schedule={"prefer_with": ["prd_aaaaaaaaaa"]}),
        _make_substance_card(schedule={"unknown_axis": ["a"]}),
    )
    for card in cases:
        assert schema_errors(card, "substance", Path("test"), ontology_bundle())


def test_generated_relation_schema_rejects_noncanonical_selector_shape() -> None:
    errors = schema_errors(
        {
            "relations": [
                {
                    "id": "rel_invalid_selector",
                    "relation_type": "supports",
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

    assert any("source_selector" in error for error in errors)
    assert any("target_selector" in error for error in errors)


def test_generated_relation_schema_enforces_formal_selector_exclusivity() -> None:
    invalid_sources: tuple[dict[str, YamlValue], ...] = (
        {},
        {"entity": {"entity_id": "sub_aaaaaaaaaa"}, "category": "kind"},
        {"entity": {"entity_id": "sub_aaaaaaaaaa", "name": "Duplicate identity"}},
    )
    for source_selector in invalid_sources:
        errors = schema_errors(
            {
                "relations": [
                    {
                        "id": "rel_invalid_selector",
                        "relation_type": "supports",
                        "reason": "formal selector exclusivity fixture",
                        "source_selector": source_selector,
                        "target_selector": {"entity": {"entity_id": "sub_bbbbbbbbbb"}},
                        "assertion_kind": "ontology_assertion",
                        "semantic_family": "biochemical_mechanism_assertion",
                    }
                ]
            },
            "relations",
            Path("relations.yaml"),
            ontology_bundle(),
        )
        assert errors, f"Expected formal schema rejection for {source_selector!r}"


@pytest.mark.parametrize(
    "selector",
    [
        {"entity": {"entity_id": None}},
        {"entity": {"entity_id": "   "}},
        {"entity": {"name": None}},
        {"entity": {"name": "   "}},
        {"category": None, "term": "mineral"},
        {"category": "kind", "term": "   "},
    ],
)
def test_generated_relation_schema_rejects_nullable_or_blank_selector_scalars(
    selector: dict[str, YamlValue],
) -> None:
    errors = schema_errors(
        {
            "relations": [
                {
                    "id": "rel_invalid_selector_scalar",
                    "relation_type": "supports",
                    "reason": "non-null selector fixture",
                    "source_selector": selector,
                    "target_selector": {"entity": {"entity_id": "sub_bbbbbbbbbb"}},
                    "assertion_kind": "ontology_assertion",
                    "semantic_family": "biochemical_mechanism_assertion",
                }
            ]
        },
        "relations",
        Path("relations.yaml"),
        ontology_bundle(),
    )
    assert errors


def test_relation_schema_enforces_ontology_relation_type_and_severity_enums() -> None:
    bundle = ontology_bundle()
    schema = load_schema("relations", bundle)
    defs = cast(dict[str, object], schema["$defs"])
    relation_record = cast(dict[str, object], defs["RelationAssertionRecord"])
    relation_properties = cast(dict[str, dict[str, object]], relation_record["properties"])

    relation_types = bundle.runtime_vocabulary["relation_types"]
    assert relation_properties["relation_type"] == {"$ref": "#/$defs/RelationType"}
    assert relation_properties["severity"] == {"$ref": "#/$defs/Severity"}
    assert set(schema_enum_values(bundle, "RelationType")) == set(cast(dict[str, object], relation_types))

    errors = schema_errors(
        {
            "relations": [
                {
                    "id": "rel_invalid_type_and_severity",
                    "relation_type": "not_authored",
                    "reason": "invalid enum fixture",
                    "source_selector": {"entity": {"entity_id": "sub_aaaaaaaaaa"}},
                    "target_selector": {"entity": {"entity_id": "sub_bbbbbbbbbb"}},
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

    assert any("relations/0/relation_type" in error and "not_authored" in error for error in errors)
    assert any("relations/0/severity" in error and "not_authored" in error for error in errors)
