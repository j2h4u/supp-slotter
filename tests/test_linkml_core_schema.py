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
    }
    assert expected <= set(_mapping(schema["classes"]))
    assert {"id", "label", "components", "slots", "entries", "selectors"} <= set(_mapping(schema["slots"]))


def test_vocabulary_terms_are_classes_not_linkml_enums() -> None:
    schema = _read("vocabulary-model.yaml")
    assert {"SemanticCategory", "OntologyTerm", "TermAssignment"} <= set(_mapping(schema["classes"]))
    assert "enums" not in schema


def test_linkml_schema_views_load_core_modules() -> None:
    schemaview = SchemaView
    for filename in ("model.yaml", "vocabulary-model.yaml"):
        view = schemaview(str(ROOT / "ontology" / filename))
        assert view.all_classes()


def test_root_imports_modular_graph_with_repo_relative_names() -> None:
    root = _read("supp_slotter.yaml")
    assert _string_list(root["imports"]) == [
        "linkml:types",
        "model",
        "vocabulary-model",
        "assertion-model",
        "scheduling-model",
        "governance-model",
        "runtime-protocol",
    ]
    imports = _string_list(root["imports"])
    assert all("/" not in item and ".." not in item for item in imports if not item.startswith("linkml:"))


def test_global_slot_definitions_do_not_disagree() -> None:
    modules = (
        "model.yaml",
        "vocabulary-model.yaml",
        "scheduling-model.yaml",
        "runtime-protocol.yaml",
        "assertion-model.yaml",
        "governance-model.yaml",
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
        ("Dashboard", "selectors", "Selector"),
        ("PolicyAxis", "value_bindings", "AxisValueBinding"),
        ("Condition", "conditions", "Condition"),
        ("Condition", "left", "Condition"),
        ("Condition", "right", "Condition"),
        ("LifecycleGate", "condition", "Condition"),
        ("LifecycleGate", "action", "Action"),
        ("PolicyEffect", "condition", "Condition"),
        ("PolicyEffect", "action", "Action"),
        ("SchedulingConstraint", "condition", "Condition"),
        ("SchedulingConstraint", "action", "Action"),
        ("OntologyAssertion", "trigger", "Condition"),
        ("EvidenceClaim", "applicability", "ApplicabilityBinding"),
    ]:
        s = view.induced_slot(slot, cls)
        assert s.range == rng and s.inlined
        if s.multivalued:
            assert s.inlined_as_list
    for cls, slot, rng in [
        ("Condition", "selector", "Selector"),
        ("PolicyAxis", "schedule_rule", "OntologyTerm"),
        ("GovernanceRecord", "governance_scope", "ScopeDimension"),
        ("ApplicabilityBinding", "binding_target", "Selector"),
        ("TermAssignment", "vocabulary_authority", "AuthorityRule"),
        ("ProductComponent", "substance", "Substance"),
        ("StackEntry", "product", "Product"),
        ("EntitySelector", "entity_id", "IdentifiedNode"),
        ("TermAssignment", "term", "OntologyTerm"),
        ("TermAssignment", "vocabulary_source", "EvidenceSource"),
        ("SlotFeatureValue", "feature", "SlotFeature"),
        ("PolicyAxis", "features", "SlotFeature"),
        ("AxisValueBinding", "axis", "PolicyAxis"),
        ("AxisValueBinding", "value", "SlotFeatureValue"),
        ("ScheduleAssignment", "subject", "Selector"),
        ("ScheduleAssignment", "policy", "SchedulingPolicy"),
        ("SchedulingPolicy", "axes", "PolicyAxis"),
        ("SchedulingPolicy", "effects", "PolicyEffect"),
        ("SchedulingPolicy", "constraints", "SchedulingConstraint"),
        ("SchedulingPolicy", "objectives", "ObjectiveTerm"),
        ("SchedulingPolicy", "scope", "ScopeDimension"),
        ("SchedulingPolicy", "authority_rule", "AuthorityRule"),
        ("SchedulingPolicy", "evidence", "EvidenceClaim"),
        ("EvidenceClaim", "source", "EvidenceSource"),
        ("EvidenceClaim", "applicable_to", "Selector"),
        ("GovernanceRecord", "lifecycle_state", "LifecycleState"),
        ("GovernanceRecord", "evidence_claim", "EvidenceClaim"),
        ("GovernanceRecord", "explanation_id", "ExplanationTemplate"),
        ("OntologyAssertion", "assertion_source", "Selector"),
        ("OntologyAssertion", "assertion_target", "Selector"),
    ]:
        s = view.induced_slot(slot, cls)
        assert s.range == rng and s.inlined is False
    for cls in (
        "SemanticCategory",
        "OntologyTerm",
        "RelationType",
        "AssertionFamily",
        "LifecycleState",
        "EnforcementMode",
        "EvidenceSource",
        "ExplanationTemplate",
        "AuthorityRule",
    ):
        assert view.induced_slot("label", cls).required
    assert view.induced_slot("schedule_rule", "PolicyAxis").required
    assert view.induced_slot("vocabulary_authority", "TermAssignment").inlined is False
