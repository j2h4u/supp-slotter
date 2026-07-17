from planner.contracts import Product, ScheduleGovernance, SlotPolicyEvidence, Substance
from planner.query_model.surreal_records import product_record, substance_record


def test_substance_record_projects_typed_governance_losslessly() -> None:
    governance = ScheduleGovernance(
        status="review_pending",
        enforcement_cap="preference",
        scope=(("slot_model", "binary"), ("food_model", "binary")),
        evidence=(
            SlotPolicyEvidence("source.second", "Second support.", "Second limitation."),
            SlotPolicyEvidence("source.first", "First support.", "First limitation."),
        ),
        owner="neutral-owner",
        review_by="2026-10-13",
        evidence_gap="Neutral synthetic gap.",
    )
    substance = Substance(
        id="sub_neutral",
        name="Neutral Substance",
        intake=("neutral_policy",),
        schedule_governance={"intake:neutral_policy": governance},
    )

    record = substance_record(substance.id, substance)

    assert record["schedule_governance"] == {
        "intake:neutral_policy": {
            "status": "review_pending",
            "enforcement_cap": "preference",
            "scope": {"food_model": "binary", "slot_model": "binary"},
            "evidence": [
                {
                    "source": "source.second",
                    "supports": "Second support.",
                    "limitations": "Second limitation.",
                },
                {
                    "source": "source.first",
                    "supports": "First support.",
                    "limitations": "First limitation.",
                },
            ],
            "owner": "neutral-owner",
            "review_by": "2026-10-13",
            "evidence_gap": "Neutral synthetic gap.",
        }
    }


def test_product_record_projects_optional_governance_fields_losslessly() -> None:
    governance = ScheduleGovernance(
        status="retired",
        enforcement_cap="none",
        scope=(("product", "prd_neutral"),),
        evidence=(SlotPolicyEvidence("source.neutral", "Neutral support.", "Neutral limitation."),),
        owner="neutral-owner",
        review_by="2026-10-13",
        retirement_reason="Neutral synthetic retirement.",
    )
    product = Product(
        id="prd_neutral",
        name="Neutral Product",
        components=(),
        timing=("neutral_policy",),
        schedule_governance={"timing:neutral_policy": governance},
    )

    record = product_record(product.id, product)

    assert record["schedule_governance"] == {
        "timing:neutral_policy": {
            "status": "retired",
            "enforcement_cap": "none",
            "scope": {"product": "prd_neutral"},
            "evidence": [
                {
                    "source": "source.neutral",
                    "supports": "Neutral support.",
                    "limitations": "Neutral limitation.",
                }
            ],
            "owner": "neutral-owner",
            "review_by": "2026-10-13",
            "retirement_reason": "Neutral synthetic retirement.",
        }
    }
