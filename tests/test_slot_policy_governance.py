from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import cast

import pytest
import yaml
from planner.cards.product import load_product
from planner.cards.substance import load_substance
from planner.contracts import CardLoadError, SchedulingPolicy
from planner.paths import ROOT
from planner.schema_validation import schema_errors
from planner.yaml_io import YamlValue, load_yaml


def _evidence(source: str = "intake.E16") -> list[dict[str, str]]:
    return [
        {
            "source": source,
            "supports": "Focused governance contract test.",
            "limitations": "Synthetic card; no medical claim.",
        }
    ]


def _governance(
    *,
    status: str = "approved",
    cap: str = "preference",
    scope: dict[str, str] | None = None,
    evidence: list[dict[str, str]] | None = None,
) -> dict[str, object]:
    return {
        "status": status,
        "enforcement_cap": cap,
        "scope": scope or {"planner": "slot_policy"},
        "evidence": _evidence() if evidence is None else evidence,
        "owner": "supp-slotter-maintainers",
        "review_by": "2026-10-13",
    }


def _substance_card() -> dict[str, object]:
    return {
        "id": "sub_aaa0000001",
        "name": "Governed test substance",
        "schedule": {"intake": ["food_preferred"]},
        "schedule_governance": {"intake:food_preferred": _governance()},
    }


def _product_card() -> dict[str, object]:
    product_id = "prd_aaa0000001"
    return {
        "id": product_id,
        "name": "Governed test product",
        "components": [{"substance": "sub_aaa0000001", "primary": True}],
        "schedule": {"intake": ["food_preferred"]},
        "schedule_governance": {"intake:food_preferred": _governance(scope={"product": product_id})},
    }


def _errors(card: dict[str, object], kind: str) -> str:
    return "\n".join(schema_errors(cast(YamlValue, card), kind, Path(f"test-{kind}.yaml")))


def _write_card(tmp_path: Path, name: str, card: dict[str, object]) -> Path:
    path = tmp_path / name
    path.write_text(yaml.safe_dump(card, sort_keys=False), encoding="utf-8")
    return path


def test_scheduling_policy_typed_governance_defaults() -> None:
    policy = SchedulingPolicy(
        id="intake:test_policy",
        namespace="intake",
        short_name="test_policy",
        label="Test policy",
        description="Typed contract test.",
        applies_when="Synthetic fixture only.",
    )

    assert policy.status == "approved"
    assert policy.enforcement == "none"
    assert policy.scope == ()


def test_valid_substance_assignment_governance_loads(tmp_path: Path) -> None:
    substance = load_substance(_write_card(tmp_path, "substance.yaml", _substance_card()))

    assert substance.intake == ("food_preferred",)
    assert set(substance.schedule_governance) == {"intake:food_preferred"}


def test_valid_direct_product_assignment_has_explicit_precedence_shape(tmp_path: Path) -> None:
    product = load_product(_write_card(tmp_path, "product.yaml", _product_card()))

    assert product.intake == ("food_preferred",)
    governance = product.schedule_governance["intake:food_preferred"]
    assert governance.enforcement_cap == "preference"
    assert dict(governance.scope) == {"product": product.id}


def test_assignment_without_governance_fails() -> None:
    card = _substance_card()
    card.pop("schedule_governance")

    assert "missing schedule_governance" in _errors(card, "substance")


def test_governance_without_assignment_fails() -> None:
    card = _substance_card()
    card["schedule"] = {}

    assert "has no schedule assignment" in _errors(card, "substance")


def test_unknown_policy_key_fails_closed() -> None:
    card = _substance_card()
    card["schedule"] = {"intake": ["not_a_policy"]}
    card["schedule_governance"] = {"intake:not_a_policy": _governance()}

    assert "references unknown scheduling policy" in _errors(card, "substance")


def test_unknown_governance_field_fails_closed() -> None:
    card = _substance_card()
    governance = cast(dict[str, object], cast(dict[str, object], card["schedule_governance"])["intake:food_preferred"])
    governance["effects"] = []

    assert "Additional properties are not allowed" in _errors(card, "substance")


@pytest.mark.parametrize("missing", ["status", "enforcement_cap", "scope", "evidence", "owner", "review_by"])
def test_governance_required_fields_fail_closed(missing: str) -> None:
    card = _substance_card()
    governance = cast(dict[str, object], cast(dict[str, object], card["schedule_governance"])["intake:food_preferred"])
    governance.pop(missing)

    assert "is a required property" in _errors(card, "substance")


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("status", "draft", "is not one of"),
        ("enforcement_cap", "strong", "is not one of"),
        ("scope", {"diagnosis": "anything"}, "Additional properties are not allowed"),
        (
            "evidence",
            [{"source": "intake.E16", "supports": "ok", "limitations": "ok", "url": "http://x"}],
            "Additional properties are not allowed",
        ),
        ("owner", "", "should be non-empty"),
        ("review_by", "2026-02-30", "is not a 'date'"),
    ],
)
def test_invalid_governance_values_fail(field: str, value: object, message: str) -> None:
    card = _substance_card()
    governance = cast(dict[str, object], cast(dict[str, object], card["schedule_governance"])["intake:food_preferred"])
    governance[field] = value

    assert message in _errors(card, "substance")


def test_unknown_evidence_key_fails_closed() -> None:
    card = _substance_card()
    governance = cast(dict[str, object], cast(dict[str, object], card["schedule_governance"])["intake:food_preferred"])
    governance["evidence"] = _evidence("unknown.report_key")

    assert "is not in slot_policy_evidence" in _errors(card, "substance")


def test_assignment_evidence_cannot_use_url_as_source_key() -> None:
    card = _substance_card()
    governance = cast(dict[str, object], cast(dict[str, object], card["schedule_governance"])["intake:food_preferred"])
    governance["evidence"] = _evidence("http://example.com/not-a-catalog-key")

    assert "is not in slot_policy_evidence" in _errors(card, "substance")


def test_review_pending_empty_evidence_requires_gap() -> None:
    card = _substance_card()
    governance = cast(dict[str, object], cast(dict[str, object], card["schedule_governance"])["intake:food_preferred"])
    governance.update(status="review_pending", evidence=[])

    assert "requires evidence or evidence_gap" in _errors(card, "substance")

    governance["evidence_gap"] = "Confirm exact formulation and label direction."
    assert _errors(card, "substance") == ""


def test_approved_assignment_requires_evidence() -> None:
    card = _substance_card()
    governance = cast(dict[str, object], cast(dict[str, object], card["schedule_governance"])["intake:food_preferred"])
    governance["evidence"] = []

    assert "approved assignment requires applicable evidence" in _errors(card, "substance")


def test_retired_assignment_must_be_removed() -> None:
    live = _substance_card()
    governance = cast(dict[str, object], cast(dict[str, object], live["schedule_governance"])["intake:food_preferred"])
    governance.update(status="retired", enforcement_cap="none", retirement_reason="Policy retired.")
    assert "cannot remain beside an active assignment" in _errors(live, "substance")

    removed = {"id": live["id"], "name": live["name"]}
    assert _errors(removed, "substance") == ""


def test_assignment_enforcement_cap_cannot_exceed_policy() -> None:
    card = _substance_card()
    governance = cast(dict[str, object], cast(dict[str, object], card["schedule_governance"])["intake:food_preferred"])
    governance["enforcement_cap"] = "block"

    assert "exceeds policy enforcement 'preference'" in _errors(card, "substance")


def test_product_scope_is_required_and_must_match_product_id() -> None:
    card = _product_card()
    governance = cast(dict[str, object], cast(dict[str, object], card["schedule_governance"])["intake:food_preferred"])
    governance["scope"] = {"planner": "slot_policy"}
    assert "direct product assignment requires scope.product" in _errors(card, "product")

    governance["scope"] = {"product": "prd_bbb0000002"}
    assert "scope.product must equal product id" in _errors(card, "product")


def test_substance_cannot_use_product_scope() -> None:
    card = _substance_card()
    governance = cast(dict[str, object], cast(dict[str, object], card["schedule_governance"])["intake:food_preferred"])
    governance["scope"] = {"product": "prd_aaa0000001"}

    assert "scope.product is valid only on a product card" in _errors(card, "substance")


def test_production_products_have_no_direct_schedule_assignments() -> None:
    assigned: list[Path] = []
    for path in sorted((ROOT / "data" / "products").glob("*.yaml")):
        raw = load_yaml(path)
        if isinstance(raw, dict) and raw.get("schedule"):
            assigned.append(path)

    assert assigned == []


def test_loader_rejects_governance_mismatch(tmp_path: Path) -> None:
    card = deepcopy(_product_card())
    card.pop("schedule_governance")

    with pytest.raises(CardLoadError, match="missing schedule_governance"):
        load_product(_write_card(tmp_path, "product.yaml", card))
