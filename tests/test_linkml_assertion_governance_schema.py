from pathlib import Path
from typing import TypeGuard, cast

import yaml

ROOT = Path(__file__).resolve().parents[1]


YamlMapping = dict[str, object]


def _is_mapping(value: object) -> TypeGuard[YamlMapping]:
    return isinstance(value, dict) and all(isinstance(key, str) for key in value)


def _mapping(value: object) -> YamlMapping:
    assert _is_mapping(value), "expected a YAML mapping"
    return value


def _string(value: object) -> str:
    assert isinstance(value, str), "expected a YAML string"
    return value


def _string_list(value: object) -> list[str]:
    assert isinstance(value, list) and all(isinstance(item, str) for item in value), "expected a YAML string list"
    return value


def _schema(name: str) -> YamlMapping:
    loaded = cast(object, yaml.safe_load((ROOT / "ontology" / name).read_text()))
    return _mapping(loaded)


def test_authored_assertion_and_governance_modules_load() -> None:
    for name in ("assertion-model.yaml", "governance-model.yaml"):
        doc = _schema(name)
        assert _string(doc["id"]).startswith("https://")
        assert "linkml:types" in _string_list(doc["imports"])
        assert _mapping(doc["classes"])


def test_assertion_contract_carries_directionality_endpoints_and_explanations() -> None:
    doc = _schema("assertion-model.yaml")
    classes = _mapping(doc["classes"])
    relation_type = _mapping(classes["RelationType"])
    relation = _string_list(relation_type["slots"])
    ontology_assertion = _mapping(classes["OntologyAssertion"])
    assertion = _string_list(ontology_assertion["slots"])
    assert {
        "directionality",
        "symmetric",
        "source_endpoint_type",
        "target_endpoint_type",
        "trigger",
        "warning_behavior",
    } <= set(relation)
    assert {
        "relation_type",
        "assertion_family",
        "assertion_source",
        "assertion_target",
        "severity",
        "lifecycle_state",
        "evidence_claim",
        "explanation_id",
    } <= set(assertion)


def test_governance_contract_carries_evidence_applicability_and_explanation_ids() -> None:
    doc = _schema("governance-model.yaml")
    classes = _mapping(doc["classes"])
    evidence_claim = _mapping(classes["EvidenceClaim"])
    claim = _string_list(evidence_claim["slots"])
    governance_record = _mapping(classes["GovernanceRecord"])
    record = _string_list(governance_record["slots"])
    assert {"source", "applicability", "applicable_to", "limitations", "lifecycle_state"} <= set(claim)
    assert {"lifecycle_state", "enforcement_mode", "warning_behavior", "evidence_claim", "explanation_id"} <= set(
        record
    )


def test_modules_do_not_define_domain_enums() -> None:
    for name in ("assertion-model.yaml", "governance-model.yaml"):
        assert "enums" not in _schema(name)
