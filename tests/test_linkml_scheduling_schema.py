from pathlib import Path
from typing import TypeGuard, cast

import yaml
from linkml_runtime.utils.schemaview import SchemaView

ROOT = Path(__file__).resolve().parents[1]


YamlMapping = dict[str, object]


def _is_mapping(value: object) -> TypeGuard[YamlMapping]:
    return isinstance(value, dict) and all(isinstance(key, str) for key in value)


def _mapping(value: object) -> YamlMapping:
    assert _is_mapping(value), "expected a YAML mapping"
    return value


def _string_list(value: object) -> list[str]:
    assert isinstance(value, list) and all(isinstance(item, str) for item in value), "expected a YAML string list"
    return value


def test_scheduling_schema_loads_and_exposes_required_classes() -> None:
    view = SchemaView(str(ROOT / "ontology/scheduling-model.yaml"))
    assert {
        "SlotFeature",
        "SlotFeatureValue",
        "PolicyAxis",
        "ScheduleAssignment",
        "SchedulingPolicy",
        "PolicyEffect",
        "SchedulingConstraint",
        "ObjectiveTerm",
        "AuthorityRule",
        "ScopeDimension",
    } <= set(view.all_classes())


def test_runtime_protocol_is_generic_and_loadable() -> None:
    view = SchemaView(str(ROOT / "ontology/runtime-protocol.yaml"))
    assert {"Condition", "Action", "LifecycleGate", "PrecedenceRule", "TableLookup"} <= set(view.all_classes())
    text = (ROOT / "ontology/runtime-protocol.yaml").read_text()
    assert "permissible_values" not in text
    for domain in ("intake", "timing", "activity", "food_preferred", "sleep_support"):
        assert domain not in text


def test_protocol_operators_are_open_values() -> None:
    loaded = cast(object, yaml.safe_load((ROOT / "ontology/runtime-protocol.yaml").read_text()))
    doc = _mapping(loaded)
    assert "enums" not in doc
    classes = _mapping(doc["classes"])
    condition = _mapping(classes["Condition"])
    assert _string_list(condition["slots"])
