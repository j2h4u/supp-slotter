from pathlib import Path

import yaml
from linkml_runtime.utils.schemaview import SchemaView

ROOT = Path(__file__).resolve().parents[1]


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
    doc = yaml.safe_load((ROOT / "ontology/runtime-protocol.yaml").read_text())
    assert "enums" not in doc
    assert doc["classes"]["Condition"]["slots"]
