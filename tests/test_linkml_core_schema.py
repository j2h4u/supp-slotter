import json
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


def _read(name: str) -> YamlMapping:
    loaded = cast(object, yaml.safe_load((ROOT / "ontology" / name).read_text()))
    return _mapping(loaded)


def test_core_classes_and_structural_slots_are_authored() -> None:
    schema = _read("model.yaml")
    expected = {
        "IdentifiedNode",
        "Substance",
        "Product",
        "ProductComponent",
        "Pillbox",
        "Slot",
        "Stack",
        "StackEntry",
        "Dashboard",
        "EntitySelector",
        "CardConcern",
        "CardKnowledge",
        "CardSchedule",
        "SubstanceCard",
        "ProductCard",
    }
    assert expected <= set(_mapping(schema["classes"]))
    assert {"id", "label", "components", "slots", "entries", "selectors"} <= set(_mapping(schema["slots"]))


def test_vocabulary_terms_are_classes_not_linkml_enums() -> None:
    schema = _read("vocabulary-model.yaml")
    assert {"SemanticCategory", "OntologyTerm", "TermAssignment"} <= set(_mapping(schema["classes"]))
    assert "enums" not in schema


def test_global_slot_definitions_do_not_disagree() -> None:
    polymorphic_slots = {"axis", "source", "term"}
    modules = (
        "model.yaml",
        "vocabulary-model.yaml",
        "scheduling-model.yaml",
        "runtime-protocol.yaml",
        "relation-model.yaml",
        "supp_slotter.yaml",
    )
    seen: dict[str, tuple[str, YamlMapping]] = {}
    for name in modules:
        slots = _mapping(_read(name).get("slots", {}))
        for slot, definition in slots.items():
            slot_definition = {} if definition is None else _mapping(definition)
            semantic: YamlMapping = {
                k: slot_definition.get(k)
                for k in (
                    "range",
                    "multivalued",
                    "required",
                    "minimum_cardinality",
                    "maximum_cardinality",
                    "inlined",
                    "inlined_as_list",
                    "identifier",
                )
            }
            if semantic["range"] is None:
                semantic["range"] = "string"
            for key in ("multivalued", "required", "inlined", "inlined_as_list", "identifier"):
                semantic[key] = bool(semantic[key])
            if slot in polymorphic_slots:
                continue
            if slot in seen:
                assert seen[slot][1] == semantic, f"global slot disagreement: {slot}"
            else:
                seen[slot] = (name, semantic)


def test_composed_root_induced_embedding_and_reference_contracts() -> None:
    view = SchemaView(str(ROOT / "ontology" / "supp_slotter.yaml"))
    for cls, slot, rng in [
        ("Product", "components", "ProductComponent"),
        ("Pillbox", "slots", "Slot"),
        ("Stack", "entries", "StackEntry"),
        ("Dashboard", "selectors", "DashboardSelector"),
        ("Condition", "conditions", "Condition"),
        ("Condition", "left", "Condition"),
        ("Condition", "right", "Condition"),
        ("SchedulingConstraint", "condition", "Condition"),
        ("SchedulingConstraint", "action", "Action"),
    ]:
        s = view.induced_slot(slot, cls)
        assert s.range == rng and s.inlined
        if s.multivalued:
            assert s.inlined_as_list
    for cls, slot, rng in [
        ("Condition", "selector", "Selector"),
        ("TermAssignment", "subject", "Selector"),
        ("ProductComponent", "substance", "Substance"),
        ("StackEntry", "product", "Product"),
        ("EntitySelector", "entity_id", "IdentifiedNode"),
        ("TermAssignment", "term", "OntologyTerm"),
    ]:
        s = view.induced_slot(slot, cls)
        assert s.range == rng and not bool(s.inlined)
    for cls in (
        "SemanticCategory",
        "OntologyTerm",
    ):
        assert view.induced_slot("label", cls).required


def test_decorative_scheduling_classes_are_not_in_composed_schema() -> None:
    view = SchemaView(str(ROOT / "ontology" / "supp_slotter.yaml"))
    assert not {
        "SlotFeature",
        "SlotFeatureValue",
        "PolicyAxis",
        "PolicyEffect",
        "ScheduleAssignment",
        "ObjectiveTerm",
    } & set(view.all_classes())


def test_card_contracts_author_id_patterns_and_nested_cardinality() -> None:
    view = SchemaView(str(ROOT / "ontology" / "supp_slotter.yaml"))
    assert "name" in view.class_slots("SubstanceCard")
    assert "label" not in view.class_slots("SubstanceCard")
    assert "name" in view.class_slots("ProductCard")
    assert "label" not in view.class_slots("ProductCard")
    assert view.induced_slot("id", "SubstanceCard").pattern == r"^sub_[a-z0-9]{10}$"
    assert view.induced_slot("id", "ProductCard").pattern == r"^prd_[a-z0-9]{10}$"
    # The base schema owns the schedule envelope only.  Concrete axis and
    # knowledge properties are generated from authored catalogs.
    assert not {"intake", "timing", "activity"} & set(view.class_slots("CardSchedule"))
    assert not {"kind", "role", "quality", "effect", "risk", "context", "pathway"} & set(
        view.class_slots("CardKnowledge")
    )
    prefer_with = view.induced_slot("prefer_with", "CardSchedule")
    assert prefer_with.range == "string"
    assert prefer_with.pattern == r"^sub_[a-z0-9]{10}$"
    assert prefer_with.minimum_cardinality == 1
    assert view.induced_slot("components", "ProductCard").minimum_cardinality == 1


def test_generated_card_schema_projects_authored_axis_and_category_properties() -> None:
    generated = json.loads((ROOT / "ontology" / "generated" / "card.schema.json").read_text())
    definitions = generated["$defs"]
    assert set(definitions["CardSchedule"]["properties"]) >= {"intake", "timing", "activity", "prefer_with"}
    assert set(definitions["CardKnowledge"]["properties"]) >= {
        "kind",
        "role",
        "quality",
        "effect",
        "risk",
        "context",
        "pathway",
    }
