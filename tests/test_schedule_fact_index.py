from __future__ import annotations

from pathlib import Path
from typing import cast

from planner.contracts import (
    EffectiveAssignmentProjection,
    EffectivePolicyGroup,
    GovernedScheduleProjection,
    ScheduleGovernance,
    SchedulingPolicy,
    ScopeEvaluation,
)
from planner.engine._plan_output import _append_trait_warnings
from planner.engine._plan_types import ActiveIndex
from planner.query_model.facts import active_fact_index
from planner.schedule_types import ScheduleData

from tests.planner_fixture import PlannerFixtureInput, plan_in_temp_dir, write_minimal_planner_fixture


def test_schedule_excludes_reviewer_only_facts_from_active_fact_index(tmp_path: Path) -> None:
    write_minimal_planner_fixture(
        tmp_path,
        PlannerFixtureInput(
            stack_items={
                "omega_product": {"stack": "daily"},
                "b6_product": {"stack": "daily"},
            },
            products={
                "omega_product": [
                    (
                        "epa_component",
                        [
                            "risk:bleeding_med_interaction",
                            "pathway:omega3_eicosanoid",
                            "effect:platelet_aggregation_modulation",
                        ],
                    )
                ],
                "b6_product": [
                    (
                        "b6_component",
                        [
                            "risk:b6_neuropathy_long_term",
                        ],
                    )
                ],
            },
            traits={
                "risk:bleeding_med_interaction": {
                    "label": "Bleeding medication interaction",
                    "description": "Fixture bleeding context",
                    "applies_when": "Fixture",
                    "warning": True,
                },
                "risk:b6_neuropathy_long_term": {
                    "label": "B6 neuropathy long-term",
                    "description": "Fixture B6 context",
                    "applies_when": "Fixture",
                    "warning": True,
                },
                "pathway:omega3_eicosanoid": {
                    "label": "Omega-3 / eicosanoid",
                    "description": "Fixture omega-3 pathway",
                    "applies_when": "Fixture",
                },
                "effect:platelet_aggregation_modulation": {
                    "label": "Platelet aggregation modulation",
                    "description": "Fixture platelet context",
                    "applies_when": "Fixture",
                },
            },
        ),
    )

    schedule = cast(ScheduleData, plan_in_temp_dir(tmp_path))
    fact_index = schedule["active_fact_index"]

    # Canonical effect facts remain visible; policy/risk and pathway entries
    # stay outside the scheduler's active fact index.
    assert [(entry["namespace"], entry["fact"]) for entry in fact_index] == [
        ("effect", "platelet_aggregation_modulation")
    ]
    assert fact_index[0]["label"] == "Platelet Aggregation Modulation"


def test_append_trait_warnings_uses_governed_assignment_sources() -> None:
    schedule = cast(ScheduleData, {"warnings": []})
    governance = ScheduleGovernance("approved", "preference", (), (), "owner", "2026-10-13")

    def assignment(
        assignment_id: str, policy_id: str, source: str, *, action: str = "active"
    ) -> EffectiveAssignmentProjection:
        return EffectiveAssignmentProjection(
            assignment_id=assignment_id,
            axis="intake",
            policy_id=policy_id,
            source_kind="substance",
            source_card_id=source,
            component_id=source,
            authority="component_primary",
            governance=governance,
            policy_scope=ScopeEvaluation("matched", (), (), "POLICY_SCOPE_MATCHED"),
            assignment_scope=ScopeEvaluation("matched", (), (), "ASSIGNMENT_SCOPE_MATCHED"),
            effective_cap="preference" if action == "active" else "none",
            action=action,  # type: ignore[arg-type]
            reason_code="ACTIVE" if action == "active" else "ASSIGNMENT_SCOPE_MISMATCH",
        )

    rows = (
        assignment("substance:sub_a:intake:known", "intake:known", "sub_a"),
        assignment("substance:sub_b:intake:known", "intake:known", "sub_b"),
        assignment("substance:sub_c:intake:known", "intake:known", "sub_c", action="suppressed"),
        assignment("substance:sub_d:intake:not_warning", "intake:not_warning", "sub_d"),
    )
    projection = GovernedScheduleProjection(
        rows,
        (
            EffectivePolicyGroup(
                "intake",
                "intake:known",
                tuple(r.assignment_id for r in rows[:2]),
                tuple(r.assignment_id for r in rows[:3]),
                "preference",
                1.0,
            ),
            EffectivePolicyGroup(
                "intake", "intake:not_warning", (rows[3].assignment_id,), (rows[3].assignment_id,), "preference", 1.0
            ),
        ),
        (),
    )
    active = ActiveIndex(
        item_products={"item_known": "prd_known"},
        active_components={},
        intra_product_relation_conflicts_by_item={},
        item_stacks={},
        governed_projection_by_item={"item_known": projection},
        active_policy_ids_by_item={"item_known": {"intake:known", "intake:not_warning"}},
    )
    policies = {
        "intake:known": SchedulingPolicy(
            id="intake:known",
            namespace="intake",
            short_name="known",
            label="Known risk",
            description="Known warning.",
            applies_when="Fixture",
            warning=True,
            action="Review known risk.",
        ),
        "intake:not_warning": SchedulingPolicy(
            id="intake:not_warning",
            namespace="intake",
            short_name="not_warning",
            label="Not warning",
            description="Ignored.",
            applies_when="Fixture",
        ),
    }

    _append_trait_warnings(schedule, active, policies)

    assert schedule["warnings"] == [
        {
            "item": "item_known",
            "product": "prd_known",
            "substance": "sub_a",
            "trait": "intake:known",
            "message": "Known warning.",
            "action": "Review known risk.",
        },
        {
            "item": "item_known",
            "product": "prd_known",
            "substance": "sub_b",
            "trait": "intake:known",
            "message": "Known warning.",
            "action": "Review known risk.",
        },
    ]


def test_active_fact_index_prefers_canonical_vocabulary_label() -> None:
    class _FakeDb:
        def query(self, statement: str, _params: dict[str, object] | None = None) -> list[dict[str, object]]:
            if statement.startswith("SELECT id, display_name, components FROM product"):
                return [{"id": "prd_fixture", "display_name": "Fixture Product", "components": ["sub_fixture"]}]
            if statement.startswith("SELECT id, risk, pathway, effect, context FROM substance"):
                return [{"id": "sub_fixture", "effect": ["pde5_inhibition"]}]
            if statement.startswith("SELECT slug, name FROM dashboard"):
                return []
            raise AssertionError(f"unexpected query: {statement}")

    result = active_fact_index(
        _FakeDb(),  # type: ignore[arg-type]
        item_id_sequence=["item_fixture"],
        item_products={"item_fixture": "prd_fixture"},
    )

    assert result == [
        {
            "namespace": "effect",
            "fact": "pde5_inhibition",
            "label": "PDE5 Inhibition",
            "product_count": 1,
            "products": ["Fixture Product"],
        }
    ]


def test_active_fact_index_production_path_keeps_authored_acronym_label(tmp_path: Path) -> None:
    write_minimal_planner_fixture(
        tmp_path,
        PlannerFixtureInput(
            stack_items={"tadalafil_product": {"stack": "daily"}},
            products={"tadalafil_product": [("tadalafil_component", ["effect:pde5_inhibition"])]},
            traits={},
        ),
    )

    schedule = cast(ScheduleData, plan_in_temp_dir(tmp_path))
    assert schedule["active_fact_index"] == [
        {
            "namespace": "effect",
            "fact": "pde5_inhibition",
            "label": "PDE5 Inhibition",
            "product_count": 1,
            "products": ["Tadalafil Product"],
        }
    ]


def test_active_fact_index_unknown_fact_uses_deterministic_fallback() -> None:
    class _FakeDb:
        def query(self, statement: str, _params: dict[str, object] | None = None) -> list[dict[str, object]]:
            if statement.startswith("SELECT id, display_name, components FROM product"):
                return [{"id": "prd_fixture", "display_name": "Fixture Product", "components": ["sub_fixture"]}]
            if statement.startswith("SELECT id, risk, pathway, effect, context FROM substance"):
                return [{"id": "sub_fixture", "effect": ["unknown_fact"]}]
            if statement.startswith("SELECT slug, name FROM dashboard"):
                return []
            raise AssertionError(f"unexpected query: {statement}")

    assert (
        active_fact_index(
            _FakeDb(),  # type: ignore[arg-type]
            item_id_sequence=["item_fixture"],
            item_products={"item_fixture": "prd_fixture"},
        )[0]["label"]
        == "Unknown Fact"
    )
