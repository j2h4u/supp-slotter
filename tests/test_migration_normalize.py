from decimal import Decimal
from typing import cast

import pytest
from planner.ontology.migration_normalize import flatten_facts, normalize


@pytest.mark.parametrize(
    ("value", "value_type"),
    [
        (None, "null"),
        (True, "boolean"),
        (3, "integer"),
        (1.5, "float"),
        (Decimal("2.50"), "decimal"),
        ("c\r\nd", "string"),
        ({"b": 2, "a": 1}, "mapping"),
        (["x", 2], "sequence"),
        (bytearray(b"x"), "unsupported"),
    ],
)
def test_normalize_handles_scalar_and_container_shapes(value: object, value_type: str) -> None:
    if value_type == "unsupported":
        with pytest.raises(TypeError, match="Unsupported YAML value"):
            normalize(value)
        return
    result = normalize(value)
    assert result["type"] == value_type
    if value_type == "string":
        assert result["value"] == "c\nd"
    if value_type == "mapping":
        pairs = cast(list[list[object]], result["value"])
        assert [pair[0] for pair in pairs] == ["a", "b"]


def test_normalize_distinguishes_bool_integer_and_nested_values() -> None:
    assert normalize({"x": [False, 1]}) == {
        "type": "mapping",
        "value": [
            [
                "x",
                {
                    "type": "sequence",
                    "value": [
                        {"type": "boolean", "value": False},
                        {"type": "integer", "value": "1"},
                    ],
                },
            ]
        ],
    }


def test_flatten_facts_emits_mapping_and_sequence_paths_and_leaf_entity() -> None:
    facts = flatten_facts(normalize({"items": [{"name": "A"}, None]}), entity_id="e1")
    assert facts == [
        {"entity_id": "e1", "path": "$.items[0].name", "value": normalize("A")},
        {"entity_id": "e1", "path": "$.items[1]", "value": normalize(None)},
    ]


def test_flatten_facts_supports_custom_root_and_scalar() -> None:
    assert flatten_facts(normalize("x"), entity_id=None, path="$.field") == [
        {"entity_id": None, "path": "$.field", "value": normalize("x")}
    ]
