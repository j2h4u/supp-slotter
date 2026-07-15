"""Behavioral acceptance tests for exact enzyme intake dispositions."""

from __future__ import annotations

import shutil
from dataclasses import replace
from pathlib import Path
from typing import cast

import pytest
import yaml
from planner.cards.substance import load_substance, load_substance_registry
from planner.contracts import (
    GovernedScheduleProjection,
    PlannerCapability,
    Product,
    ProductComponent,
    ScheduleGovernance,
    SchedulingPolicy,
    Slot,
    SlotCandidateTrace,
    SlotPolicyEvidence,
    Substance,
)
from planner.engine import cmd_audit
from planner.engine._plan_feasibility import build_feasibility_index
from planner.engine._plan_search import PlanSearchInput, run_plan_search
from planner.engine._plan_types import ActiveIndex
from planner.engine._scheduling import compute_slot_score, project_governed_assignments
from planner.ontology.artifacts import load_runtime_vocabulary
from planner.ontology.errors import OntologyInfrastructureError
from planner.ontology.generate import generate_ontology
from planner.ontology.policies import load_scheduling_policies
from planner.paths import Paths
from planner.query_model import audit_full
from planner.query_model.session import SurrealSession
from planner.schema_validation import schema_errors, validate_schedule_contract
from planner.yaml_io import YamlValue

from tests.test_audit_command import _write_audit_fixture

ROOT = Path(__file__).resolve().parents[1]
ONTOLOGY = ROOT / "ontology"
MatrixTuple = tuple[str, str, str, tuple[tuple[str, str], ...], tuple[str, ...]]
MATRIX: dict[str, MatrixTuple] = {
    "sub_6zegokcu7e": (
        "intake:food_preferred",
        "review_pending",
        "preference",
        (("formulation", "unknown"), ("intended_use", "digestive")),
        ("enzyme.E4",),
    ),
    "sub_bwatu3taud": ("intake:food_preferred", "approved", "preference", (("substrate", "lactose"),), ("enzyme.E1",)),
    "sub_51p30t3o4j": (
        "intake:food_preferred",
        "approved",
        "preference",
        (("intended_use", "digestive"),),
        ("enzyme.E3", "enzyme.E4"),
    ),
    "sub_877c24aad4": (
        "intake:empty_preferred",
        "review_pending",
        "preference",
        (("formulation", "unknown"),),
        ("enzyme.E5", "enzyme.E6"),
    ),
    "sub_winwtayogk": (
        "intake:food_preferred",
        "review_pending",
        "preference",
        (("formulation", "unknown"), ("intended_use", "digestive")),
        ("enzyme.E2",),
    ),
    "sub_6tk5moz0wh": (
        "intake:food_preferred",
        "review_pending",
        "preference",
        (("formulation", "unknown"), ("intended_use", "digestive")),
        ("enzyme.E8",),
    ),
    "sub_mw9uw4se1u": (
        "intake:food_preferred",
        "review_pending",
        "preference",
        (("formulation", "unknown"), ("intended_use", "digestive")),
        ("enzyme.E9",),
    ),
}


def _runtime() -> dict[str, object]:
    return load_runtime_vocabulary(ONTOLOGY)


def _rules() -> list[dict[str, object]]:
    return cast(list[dict[str, object]], _runtime()["audit_review_rules"])


def _live_rule() -> dict[str, object]:
    return next(rule for rule in _rules() if rule["id"] == "audit_intake_enzyme_digestive")


def _real(card_id: str) -> Substance:
    return load_substance(next((ROOT / "data/substances").glob(f"*__{card_id}.yaml")))


def _projection(
    substance: Substance,
) -> tuple[GovernedScheduleProjection, dict[str, SchedulingPolicy]]:
    product = Product("prd_fixture", "Fixture", (ProductComponent(substance.id),))
    capability = PlannerCapability(
        "slot_policy",
        "binary",
        frozenset({"binary"}),
        product.id,
        ((substance.id, substance.form),) if substance.form else (),
    )
    policies = load_scheduling_policies()
    return project_governed_assignments(product, {substance.id: substance}, policies, capability), policies


def _slot(food: bool) -> Slot:
    return Slot(f"food_{food}", f"Food {food}", 1, "day_meal", food, "daily", "Daily", "daily")


def _card_tuple(card_id: str) -> tuple[object, ...]:
    card = _real(card_id)
    key = f"intake:{card.intake[0]}"
    governance = card.schedule_governance[key]
    return (
        key,
        governance.status,
        governance.enforcement_cap,
        governance.scope,
        tuple(row.source for row in governance.evidence),
    )


class _Rows:
    rows: list[dict[str, object]]

    def __init__(self, rows: list[dict[str, object]]) -> None:
        self.rows = rows

    def query(self, _query: str) -> list[dict[str, object]]:
        return self.rows


def _single_rule(card_id: str, disposition: str) -> list[dict[str, object]]:
    return [{**_live_rule(), "subjects": {card_id: {"disposition": disposition}}}]


def _plan_scenario(card: Substance) -> dict[str, object]:
    policies = load_scheduling_policies()
    candidate_product = Product("prd_candidate", "Candidate", (ProductComponent(card.id),))
    anchor = Substance("sub_anchor", "Anchor")
    anchor_product = Product("prd_anchor", "Anchor", (ProductComponent(anchor.id),))

    def capability(product: Product, source_forms: tuple[tuple[str, str], ...]) -> PlannerCapability:
        return PlannerCapability("slot_policy", "binary", frozenset({"binary"}), product.id, source_forms)

    candidate_forms = ((card.id, card.form),) if card.form else ()
    projections = {
        "candidate": project_governed_assignments(
            candidate_product, {card.id: card}, policies, capability(candidate_product, candidate_forms)
        ),
        "anchor": project_governed_assignments(
            anchor_product, {anchor.id: anchor}, policies, capability(anchor_product, ())
        ),
    }
    slots = {"food_false": _slot(False), "food_true": _slot(True)}
    slots["food_false"] = replace(slots["food_false"], slot_id="food_false", order=1)
    slots["food_true"] = replace(slots["food_true"], slot_id="food_true", order=2)
    active = ActiveIndex(
        item_products={"candidate": candidate_product.id, "anchor": anchor_product.id},
        active_components={"candidate": [card.id], "anchor": [anchor.id]},
        intra_product_relation_conflicts_by_item={},
        item_stacks={"candidate": "daily", "anchor": "daily"},
        governed_projection_by_item=projections,
        active_policy_ids_by_item={
            item: {group.policy_id for group in projection.groups} for item, projection in projections.items()
        },
    )
    feasibility = build_feasibility_index(slots, active, policies, [])
    assert feasibility is not None
    assignment, metrics = run_plan_search(
        PlanSearchInput(
            slots=slots,
            items_by_scheduling_priority=feasibility.items_by_scheduling_priority,
            item_id_sequence=feasibility.item_id_sequence,
            item_stacks=active.item_stacks,
            feasible_slots_by_item=feasibility.feasible_slots_by_item,
            remaining_score_upper_bound=feasibility.remaining_score_upper_bound,
            prefer_pairs=set(),
            active_components=active.active_components,
            substances={card.id: card, anchor.id: anchor},
            scheduling_constraints=(),
        )
    )
    assert assignment is not None and metrics is not None
    traces = feasibility.candidate_traces_by_item["candidate"]
    return {
        "projection": projections["candidate"],
        "traces": traces,
        "trace_slot_ids": tuple(trace.slot_id for trace in traces),
        "feasible_order": tuple(row[0] for row in feasibility.feasible_slots_by_item["candidate"]),
        "assignment": assignment,
        "chosen": assignment["candidate"],
        "metrics": metrics,
    }


def test_enzyme_inventory_has_governed_intake_disposition(tmp_path: Path) -> None:
    shutil.copytree(ROOT / "data", tmp_path / "data")
    copied = tmp_path / "ontology"
    shutil.copytree(ONTOLOGY, copied)
    substances = load_substance_registry(Paths.from_root(tmp_path))
    enzyme_ids = {card.id for card in substances.values() if "enzyme" in card.kind}
    assert enzyme_ids == set(MATRIX) == set(cast(dict[str, object], _live_rule()["subjects"]))
    eighth_path = tmp_path / "data/substances/eighth__sub_eighth.yaml"
    eighth_path.write_text(
        yaml.safe_dump({"id": "sub_eighth", "name": "Eighth", "knowledge": {"kind": ["enzyme"]}}),
        encoding="utf-8",
    )
    substances = load_substance_registry(Paths.from_root(tmp_path))
    eight_ids = {card.id for card in substances.values() if "enzyme" in card.kind}
    assert eight_ids != set(cast(dict[str, object], _live_rule()["subjects"]))
    authored = cast(dict[str, object], yaml.safe_load((copied / "policies.yaml").read_text()))
    subjects = cast(
        dict[str, object], cast(dict[str, object], authored["audit_review_rules"])["audit_intake_enzyme_digestive"]
    )["subjects"]
    assert "sub_eighth" not in cast(dict[str, object], subjects)
    cast(dict[str, object], subjects)["sub_eighth"] = {
        "disposition": "reviewed_no_assignment",
        "status": "review_pending",
        "scope": {"planner": "audit"},
        "evidence": [],
        "owner": "supp-slotter-maintainers",
        "review_by": "2026-10-13",
        "evidence_gap": "Explicit no-assignment review pending.",
    }
    (copied / "policies.yaml").write_text(yaml.safe_dump(authored, sort_keys=False))
    generate_ontology(copied)
    generated_subjects = cast(
        dict[str, object],
        next(
            r
            for r in cast(list[dict[str, object]], load_runtime_vocabulary(copied)["audit_review_rules"])
            if r["id"] == "audit_intake_enzyme_digestive"
        )["subjects"],
    )
    assert set(generated_subjects) == eight_ids


def test_non_digestive_absence_does_not_imply_empty_preferred(monkeypatch: pytest.MonkeyPatch) -> None:
    card = Substance("sub_synthetic", "Synthetic", kind=("enzyme",))
    projection, policies = _projection(card)
    assert projection.assignments == projection.groups == ()
    monkeypatch.setattr(
        audit_full,
        "load_audit_review_rules",
        lambda: _single_rule(card.id, "governed_assignment"),
    )
    lines = audit_full._intake_review(
        cast(SurrealSession, _Rows([{"id": card.id, "name": card.name}])), {card.id: card}
    )
    assert lines == [
        "Synthetic (sub_synthetic): explicit intake disposition missing [audit_intake_enzyme_digestive]; add a governed assignment or reviewed no-assignment disposition; no intake value inferred"
    ]
    assert not any(policy_id in lines[0] for policy_id in policies)


def test_digestive_context_is_advisory_not_assignment(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    card = Substance("sub_digestive", "Digestive", kind=("enzyme",), effect=("digestive_enzyme_context",))
    projection, _ = _projection(card)
    assert projection.assignments == ()
    monkeypatch.setattr(audit_full, "load_audit_review_rules", lambda: _single_rule(card.id, "governed_assignment"))
    db = cast(SurrealSession, _Rows([{"id": card.id, "name": card.name}]))
    assert "explicit intake disposition missing" in audit_full._intake_review(db, {card.id: card})[0]
    copied = tmp_path / "ontology"
    shutil.copytree(ONTOLOGY, copied)
    shutil.copytree(ROOT / "data", tmp_path / "data")
    authored = cast(dict[str, object], yaml.safe_load((copied / "policies.yaml").read_text()))
    rule = cast(
        dict[str, object], cast(dict[str, object], authored["audit_review_rules"])["audit_intake_enzyme_digestive"]
    )
    rule["subjects"] = {
        card.id: {
            "disposition": "reviewed_no_assignment",
            "status": "review_pending",
            "scope": {"planner": "audit"},
            "evidence": [],
            "owner": "supp-slotter-maintainers",
            "review_by": "2026-10-13",
            "evidence_gap": "Explicit review pending.",
        }
    }
    (copied / "policies.yaml").write_text(yaml.safe_dump(authored, sort_keys=False), encoding="utf-8")
    generate_ontology(copied)
    generated = next(
        item
        for item in cast(list[dict[str, object]], load_runtime_vocabulary(copied)["audit_review_rules"])
        if item["id"] == "audit_intake_enzyme_digestive"
    )
    monkeypatch.setattr(audit_full, "load_audit_review_rules", lambda: [generated])
    assert audit_full._intake_review(db, {card.id: card}) == []
    assert card.intake == () and _projection(card)[0].assignments == ()


def test_review_pending_assignment_cannot_block_food_false() -> None:
    policy = load_scheduling_policies()["intake:food_required"]
    governance = ScheduleGovernance(
        "review_pending",
        "block",
        (("planner", "slot_policy"),),
        (SlotPolicyEvidence("enzyme.E3", "s", "l"),),
        "owner",
        "2026-10-13",
    )
    card = Substance("sub_pending", "Pending", intake=("food_required",), schedule_governance={policy.id: governance})
    projection, policies = _projection(card)
    traces = [compute_slot_score(projection, _slot(food), policies) for food in (False, True)]
    assert not any(trace.blocked for trace in traces)
    codes = {row.code for trace in traces for row in trace.diagnostics}
    assert {"PENDING_BLOCK_SUPPRESSED", "STRONG_EFFECT_DOWNGRADED"} <= codes
    assert {row.source_card_id for trace in traces for row in trace.diagnostics} == {card.id}
    assert traces[0].effects[0].assignment_ids == ("substance:sub_pending:intake:food_required",)
    assert traces[0].effects[0].source_card_ids == (card.id,)
    assert "PENDING_BLOCK_SUPPRESSED" in traces[0].effects[0].action_codes
    assert "STRONG_EFFECT_DOWNGRADED" in traces[1].effects[0].action_codes


def test_approved_food_required_can_block_when_scope_and_evidence_present() -> None:
    policies = load_scheduling_policies()
    component = _real("sub_bwatu3taud")
    governance = ScheduleGovernance(
        "approved",
        "block",
        (("product", "prd_pert"),),
        (SlotPolicyEvidence("enzyme.E2", "s", "l"),),
        "owner",
        "2026-10-13",
    )
    product = Product(
        "prd_pert",
        "PERT",
        (ProductComponent(component.id),),
        intake=("food_required",),
        schedule_governance={"intake:food_required": governance},
    )
    capability = PlannerCapability("slot_policy", "binary", frozenset({"binary"}), product.id, ())
    projection = project_governed_assignments(product, {component.id: component}, policies, capability)
    assert compute_slot_score(projection, _slot(False), policies).blocked
    assert not compute_slot_score(projection, _slot(True), policies).blocked
    mismatch = PlannerCapability("slot_policy", "binary", frozenset({"binary"}), "prd_other", ())
    suppressed = project_governed_assignments(product, {component.id: component}, policies, mismatch)
    direct = next(row for row in suppressed.assignments if row.source_kind == "product")
    mismatch_trace = compute_slot_score(suppressed, _slot(False), policies)
    assert direct.assignment_scope.reason_code == "ASSIGNMENT_SCOPE_MISMATCH:product"
    assert (direct.effective_cap, mismatch_trace.score, mismatch_trace.blocked) == ("none", 0, False)


def test_retired_enzyme_empty_rule_is_non_enforcing(monkeypatch: pytest.MonkeyPatch) -> None:
    rule = next(rule for rule in _rules() if rule["id"] == "audit_intake_enzyme_empty")
    assert (rule["status"], rule["enforcement"], rule["subjects"], rule["effects"]) == ("retired", "none", {}, [])
    monkeypatch.setattr(
        audit_full,
        "load_audit_review_rules",
        lambda *, include_retired=False: [rule],
    )
    card = Substance("sub_any", "Any")
    assert (
        audit_full._intake_review(cast(SurrealSession, _Rows([{"id": card.id, "name": card.name}])), {card.id: card})
        == []
    )


def test_policy_enforcement_matches_effect_projection(tmp_path: Path) -> None:
    mutations = (
        ("intake:food_required", {"status": "review_pending", "enforcement": "block"}),
        ("intake:food_preferred", {"status": "retired", "enforcement": "none"}),
        ("risk:manual_review", {"status": "retired", "enforcement": "advisory"}),
        ("intake:food_preferred", {"status": "approved", "enforcement": "none"}),
    )
    for index, (policy_id, updates) in enumerate(mutations):
        root = tmp_path / str(index)
        copied = root / "ontology"
        shutil.copytree(ONTOLOGY, copied)
        shutil.copytree(ROOT / "data", root / "data")
        authored = cast(dict[str, object], yaml.safe_load((copied / "policies.yaml").read_text()))
        policy = cast(dict[str, object], cast(dict[str, object], authored["scheduling_policies"])[policy_id])
        policy.update(updates)
        (copied / "policies.yaml").write_text(yaml.safe_dump(authored, sort_keys=False), encoding="utf-8")
        with pytest.raises(OntologyInfrastructureError):
            generate_ontology(copied)
    governance = ScheduleGovernance(
        "review_pending",
        "block",
        (("planner", "slot_policy"),),
        (SlotPolicyEvidence("enzyme.E3", "s", "l"),),
        "owner",
        "2026-10-13",
    )
    card = Substance(
        "sub_defensive",
        "Defensive",
        intake=("food_required",),
        schedule_governance={"intake:food_required": governance},
    )
    projection, policies = _projection(card)
    assert not compute_slot_score(projection, _slot(False), policies).blocked


def test_assignment_governance_keys_exactly_match_schedule_traits(tmp_path: Path) -> None:
    for card_id in MATRIX:
        card = _real(card_id)
        assert set(card.schedule_governance) == {f"intake:{card.intake[0]}"}
        assert isinstance(next(iter(card.schedule_governance.values())), ScheduleGovernance)
    card = cast(YamlValue, {"id": "sub_test", "name": "Test", "schedule": {"intake": ["food_preferred"]}})
    assert any(
        "missing schedule_governance" in error
        for error in validate_schedule_contract(card, Path("test.yaml"), card_kind="substance")
    )
    orphan = cast(
        YamlValue,
        {
            "id": "sub_test",
            "name": "Test",
            "schedule_governance": {"intake:food_preferred": {}},
        },
    )
    assert any(
        "has no schedule assignment" in error
        for error in validate_schedule_contract(orphan, Path("test.yaml"), card_kind="substance")
    )
    valid_path = tmp_path / "valid__sub_valid.yaml"
    valid_path.write_text(
        yaml.safe_dump(
            {
                "id": "sub_valid",
                "name": "Valid",
                "schedule": {"intake": ["food_preferred"]},
                "schedule_governance": {
                    "intake:food_preferred": {
                        "status": "approved",
                        "enforcement_cap": "preference",
                        "scope": {"food_model": "binary"},
                        "evidence": [
                            {
                                "source": "enzyme.E3",
                                "supports": "Synthetic validation.",
                                "limitations": "Synthetic only.",
                            }
                        ],
                        "owner": "supp-slotter-maintainers",
                        "review_by": "2026-10-13",
                    }
                },
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    loaded = load_substance(valid_path)
    assert loaded.id == "sub_valid"
    assert set(loaded.schedule_governance) == {"intake:food_preferred"}
    assert isinstance(loaded.schedule_governance["intake:food_preferred"], ScheduleGovernance)


def test_approved_clinical_assignment_requires_applicable_evidence(tmp_path: Path) -> None:
    card = cast(
        YamlValue,
        {
            "id": "sub_test",
            "name": "Test",
            "schedule": {"intake": ["food_preferred"]},
            "schedule_governance": {
                "intake:food_preferred": {
                    "status": "approved",
                    "enforcement_cap": "preference",
                    "scope": {"food_model": "binary"},
                    "evidence": [],
                    "owner": "owner",
                    "review_by": "2026-10-13",
                }
            },
        },
    )
    errors = validate_schedule_contract(card, Path("test.yaml"), card_kind="substance")
    assert any("requires applicable evidence" in error for error in errors)
    unknown = cast(dict[str, object], cast(dict[str, object], card)["schedule_governance"])
    unknown_record = cast(dict[str, object], unknown["intake:food_preferred"])
    unknown_record["evidence"] = [{"source": "unknown", "supports": "Synthetic.", "limitations": "Synthetic."}]
    assert any(
        "not in slot_policy_evidence" in error
        for error in validate_schedule_contract(card, Path("test.yaml"), card_kind="substance")
    )
    unknown_record["evidence"] = [{"source": "enzyme.E3", "supports": "Synthetic."}]
    assert schema_errors(card, "substance", Path("test.yaml"))
    unknown_record.update({
        "evidence": [{"source": "enzyme.E3", "supports": "Synthetic.", "limitations": "Synthetic."}],
        "enforcement_cap": "block",
        "scope": {"formulation": "unknown"},
    })
    assert any(
        "unobservable scope cannot declare enforcement_cap block" in error
        for error in validate_schedule_contract(card, Path("test.yaml"), card_kind="substance")
    )
    copied = tmp_path / "ontology"
    shutil.copytree(ONTOLOGY, copied)
    shutil.copytree(ROOT / "data", tmp_path / "data")
    authored = cast(dict[str, object], yaml.safe_load((copied / "policies.yaml").read_text()))
    catalog = cast(dict[str, dict[str, object]], authored["slot_policy_evidence"])
    source = catalog["enzyme.E3"]
    source.pop("ref", None)
    source["url"] = "http://example.test/not-https"
    (copied / "policies.yaml").write_text(yaml.safe_dump(authored, sort_keys=False), encoding="utf-8")
    with pytest.raises(OntologyInfrastructureError):
        generate_ontology(copied)
    governance = ScheduleGovernance(
        "approved",
        "preference",
        (("formulation", "different"),),
        (SlotPolicyEvidence("enzyme.E3", "s", "l"),),
        "owner",
        "2026-10-13",
    )
    mismatch = Substance(
        "sub_form",
        "Form",
        form="actual",
        intake=("food_preferred",),
        schedule_governance={"intake:food_preferred": governance},
    )
    projection, policies = _projection(mismatch)
    assert projection.assignments[0].effective_cap == "none"
    assert all(
        (trace.score, trace.blocked) == (0, False)
        for trace in (compute_slot_score(projection, _slot(food), policies) for food in (False, True))
    )


def test_biochemical_traits_do_not_project_to_schedule() -> None:
    plain = Substance("sub_plain", "Plain")
    biochemical = replace(
        plain,
        kind=("enzyme",),
        effect=("digestive_enzyme_context", "fibrinolytic"),
        risk=("bleeding_med_interaction",),
    )
    plain_projection, policies = _projection(plain)
    bio_projection, _ = _projection(biochemical)
    assert plain_projection.assignments == bio_projection.assignments == ()
    assert [
        (
            compute_slot_score(value, _slot(food), policies).score,
            compute_slot_score(value, _slot(food), policies).blocked,
        )
        for value in (plain_projection, bio_projection)
        for food in (False, True)
    ] == [(0, False)] * 4
    plain_plan = _plan_scenario(plain)
    biochemical_plan = _plan_scenario(biochemical)
    for key in ("traces", "trace_slot_ids", "feasible_order", "assignment", "chosen", "metrics"):
        assert biochemical_plan[key] == plain_plan[key]


def test_lactase_uses_soft_scoped_food_context() -> None:
    card = _real("sub_bwatu3taud")
    assert _card_tuple(card.id) == MATRIX[card.id]
    projection, policies = _projection(card)
    assignment = projection.assignments[0]
    assert assignment.assignment_scope.reason_code == "ASSIGNMENT_SCOPE_LIMITED:substrate"
    assert (assignment.assignment_scope.outcome, assignment.effective_cap) == ("limited", "preference")
    traces = [compute_slot_score(projection, _slot(food), policies) for food in (False, True)]
    assert [(trace.score, trace.blocked) for trace in traces] == [(0, False), (2, False)]
    assert assignment.governance.scope == (("substrate", "lactose"),)


def test_pancreatin_evidence_does_not_leak_across_scope() -> None:
    card = _real("sub_winwtayogk")
    assert _card_tuple(card.id) == MATRIX[card.id]
    projection, policies = _projection(card)
    generic = projection.assignments[0]
    assert (generic.assignment_scope.outcome, generic.governance.status, generic.effective_cap) == (
        "limited",
        "review_pending",
        "preference",
    )
    assert not any(compute_slot_score(projection, _slot(food), policies).blocked for food in (False, True))
    direct_governance = ScheduleGovernance(
        "approved",
        "block",
        (("product", "prd_pert"),),
        (SlotPolicyEvidence("enzyme.E2", "s", "l"),),
        "owner",
        "2026-10-13",
    )
    product = Product(
        "prd_pert",
        "PERT",
        (ProductComponent(card.id),),
        intake=("food_required",),
        schedule_governance={"intake:food_required": direct_governance},
    )
    matching = project_governed_assignments(
        product,
        {card.id: card},
        policies,
        PlannerCapability("slot_policy", "binary", frozenset({"binary"}), product.id, ()),
    )
    assert compute_slot_score(matching, _slot(False), policies).blocked
    mismatch = project_governed_assignments(
        product,
        {card.id: card},
        policies,
        PlannerCapability("slot_policy", "binary", frozenset({"binary"}), "prd_other", ()),
    )
    direct = next(row for row in mismatch.assignments if row.source_kind == "product")
    mismatch_trace = compute_slot_score(mismatch, _slot(False), policies)
    assert (direct.effective_cap, mismatch_trace.score, mismatch_trace.blocked) == ("none", 0, False)


def test_generated_ontology_preserves_lifecycle_projection(tmp_path: Path) -> None:
    copied = tmp_path / "ontology"
    shutil.copytree(ONTOLOGY, copied)
    shutil.copytree(ROOT / "data", tmp_path / "data")
    generate_ontology(copied)
    authored = cast(dict[str, object], yaml.safe_load((copied / "policies.yaml").read_text()))
    runtime = load_runtime_vocabulary(copied)
    generated_policies = cast(dict[str, dict[str, object]], runtime["scheduling_policies"])
    fields = (
        "status",
        "enforcement",
        "scope",
        "effects",
        "evidence",
        "owner",
        "review_by",
        "evidence_gap",
        "retirement_reason",
    )
    for policy_id, raw in cast(dict[str, dict[str, object]], authored["scheduling_policies"]).items():
        expected = {key: raw.get(key) for key in fields}
        expected["effects"] = raw.get("effects", [])
        assert {key: generated_policies[policy_id].get(key) for key in fields} == expected
    generated_rules = {rule["id"]: rule for rule in cast(list[dict[str, object]], runtime["audit_review_rules"])}
    rule_fields = (
        "axis",
        "predicate",
        "subjects",
        "status",
        "enforcement",
        "scope",
        "effects",
        "evidence",
        "owner",
        "review_by",
        "evidence_gap",
        "retirement_reason",
    )
    for rule_id, raw in cast(dict[str, dict[str, object]], authored["audit_review_rules"]).items():
        assert {key: generated_rules[rule_id].get(key) for key in rule_fields} == {
            key: raw.get(key) for key in rule_fields
        }
    generate_ontology(copied, check=True)


def test_full_audit_reports_policy_governance_deterministically(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    rule: dict[str, object] = {
        **_live_rule(),
        "subjects": {"sub_absent": {"disposition": "governed_assignment"}},
    }
    monkeypatch.setattr(
        audit_full,
        "load_audit_review_rules",
        lambda *, include_retired=False: [rule],
    )
    results: list[dict[str, list[str]]] = []
    for name in ("run_1", "run_2"):
        root = tmp_path / name
        _write_audit_fixture(root)
        result = cmd_audit(data_root=root, full=True)
        assert result.exit_code == 0
        results.append(result.full)
    assert results[0] == results[1]
    for section in ("full.intake_review", "full.policy_governance", "full.assignment_governance"):
        assert results[0][section] == results[1][section]
    assert results[0]["full.intake_review"] == [
        "sub_absent (sub_absent): explicit intake disposition missing [audit_intake_enzyme_digestive]; add a governed assignment or reviewed no-assignment disposition; no intake value inferred"
    ]


@pytest.mark.parametrize(
    "db_present,typed_present,expected_name",
    [
        (False, True, "Typed (form)"),
        (True, False, "Database"),
        (False, False, "sub_declared"),
    ],
)
def test_declared_subject_source_loss_fails_closed(
    monkeypatch: pytest.MonkeyPatch,
    db_present: bool,
    typed_present: bool,
    expected_name: str,
) -> None:
    subject_id = "sub_declared"
    rule: dict[str, object] = {
        **_live_rule(),
        "subjects": {subject_id: {"disposition": "governed_assignment"}},
    }
    monkeypatch.setattr(audit_full, "load_audit_review_rules", lambda: [rule])
    rows: list[dict[str, object]] = [{"id": subject_id, "name": "Database"}] if db_present else []
    typed = {subject_id: Substance(subject_id, "Typed", form="form")} if typed_present else {}
    db = cast(SurrealSession, _Rows(rows))
    expected = [
        f"{expected_name} ({subject_id}): explicit intake disposition missing [audit_intake_enzyme_digestive]; add a governed assignment or reviewed no-assignment disposition; no intake value inferred"
    ]
    assert audit_full._intake_review(db, typed) == expected
    assert audit_full._intake_review(db, typed) == expected


@pytest.mark.parametrize("card_id,expected", sorted(MATRIX.items()))
def test_per_record_governance_matrix_replaces_blanket_assertion(card_id: str, expected: MatrixTuple) -> None:
    assert _card_tuple(card_id) == expected
    projection, policies = _projection(_real(card_id))
    traces = [compute_slot_score(projection, _slot(food), policies) for food in (False, True)]
    expected_scores = (2, -2) if expected[0] == "intake:empty_preferred" else (0, 2)
    assert tuple(trace.score for trace in traces) == expected_scores
    assert not any(trace.blocked for trace in traces)
    assignment = projection.assignments[0]
    assert assignment.source_card_id == card_id
    expected_assignment_id = f"substance:{card_id}:{expected[0]}"
    for trace in traces:
        for effect in trace.effects:
            assert effect.assignment_ids == (expected_assignment_id,)
            assert effect.source_card_ids == (card_id,)


@pytest.mark.parametrize(
    "card_id,policy_id",
    [
        ("sub_iu7b8h87g2", "intake:empty_preferred"),
        ("sub_e6vq6f2s3n", "intake:food_preferred"),
        ("sub_gjaf5119cu", "intake:empty_preferred"),
        ("sub_605u9zvqt2", "intake:food_preferred"),
    ],
)
def test_real_advisory_assignments_are_behaviorally_inert(card_id: str, policy_id: str) -> None:
    card = _real(card_id)
    assert card.schedule_governance[policy_id].enforcement_cap == "advisory"
    control = replace(card, intake=(), timing=(), activity=(), schedule_governance={})
    real_plan = _plan_scenario(card)
    control_plan = _plan_scenario(control)
    for key in ("trace_slot_ids", "feasible_order", "assignment", "chosen", "metrics"):
        assert real_plan[key] == control_plan[key]
    real_traces = cast(tuple[SlotCandidateTrace, ...], real_plan["traces"])
    assert all((trace.score, trace.blocked) == (0, False) for trace in real_traces)
    projection = cast(GovernedScheduleProjection, real_plan["projection"])
    assert len(projection.assignments) == 1
    assert (projection.assignments[0].source_card_id, projection.assignments[0].policy_id) == (
        card_id,
        policy_id,
    )
    codes = {
        row.code for trace in cast(tuple[SlotCandidateTrace, ...], real_plan["traces"]) for row in trace.diagnostics
    }
    assert "ADVISORY_NO_SCORE" in codes
    assert cast(GovernedScheduleProjection, control_plan["projection"]).assignments == ()
