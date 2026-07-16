from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]


def _schema(name: str) -> dict:
    return yaml.safe_load((ROOT / "ontology" / name).read_text())


def test_authored_assertion_and_governance_modules_load() -> None:
    for name in ("assertion-model.yaml", "governance-model.yaml"):
        doc = _schema(name)
        assert doc["id"].startswith("https://")
        assert "linkml:types" in doc["imports"]
        assert doc["classes"]


def test_assertion_contract_carries_directionality_endpoints_and_explanations() -> None:
    doc = _schema("assertion-model.yaml")
    relation = doc["classes"]["RelationType"]["slots"]
    assertion = doc["classes"]["OntologyAssertion"]["slots"]
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
    claim = doc["classes"]["EvidenceClaim"]["slots"]
    record = doc["classes"]["GovernanceRecord"]["slots"]
    assert {"source", "applicability", "applicable_to", "limitations", "lifecycle_state"} <= set(claim)
    assert {"lifecycle_state", "enforcement_mode", "warning_behavior", "evidence_claim", "explanation_id"} <= set(
        record
    )


def test_modules_do_not_define_domain_enums() -> None:
    for name in ("assertion-model.yaml", "governance-model.yaml"):
        assert "enums" not in _schema(name)
