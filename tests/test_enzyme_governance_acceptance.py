"""Behavioral acceptance tests for exact enzyme intake dispositions."""

# pyright: reportUnknownArgumentType=false, reportUnknownLambdaType=false

from __future__ import annotations

import shutil
from collections.abc import Mapping
from dataclasses import replace
from pathlib import Path
from typing import cast

import pytest
import yaml
from planner.cards.substance import load_substance
from planner.contracts import (
    GovernedScheduleProjection,
    PlannerCapability,
    Product,
    ProductComponent,
    ScheduleGovernance,
    SchedulingPolicy,
    Slot,
    SlotPolicyEvidence,
    Substance,
)
from planner.engine import cmd_audit
from planner.engine._plan_feasibility import build_feasibility_index
from planner.engine._plan_search import PlanSearchInput, run_plan_search
from planner.engine._plan_types import ActiveIndex
from planner.engine._scheduling import compute_slot_score, project_governed_assignments
from planner.ontology.artifacts import load_ontology
from planner.ontology.errors import OntologyInfrastructureError
from planner.ontology.glue_capabilities import AUDIT_GOVERNANCE_KEY_SEPARATOR
from planner.ontology.policies import load_scheduling_policies
from planner.query_model import audit_full
from planner.query_model.session import SurrealSession
from planner.schema_validation import schema_errors, validate_schedule_contract
from planner.yaml_io import YamlValue
from scripts.ontology_compiler import generate_ontology

from tests.helpers import ontology_bundle
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


def _copy_repository_fixture(repository: Path) -> Path:
    copied = repository / "ontology"
    shutil.copytree(ONTOLOGY, copied)
    shutil.copytree(ROOT / "data", repository / "data")
    scripts = repository / "scripts"
    scripts.mkdir()
    shutil.copy2(ROOT / "scripts/ontology_compiler.py", scripts / "ontology_compiler.py")
    return copied


def _runtime() -> Mapping[str, object]:
    return ontology_bundle().runtime_vocabulary


def _rules() -> list[dict[str, object]]:
    return cast(list[dict[str, object]], _runtime()["audit_review_rules"])


def _live_rule() -> dict[str, object]:
    return next(rule for rule in _rules() if rule["id"] == "audit_intake_enzyme_digestive")


def _real(card_id: str) -> Substance:
    return load_substance(next((ROOT / "data/substances").glob(f"*__{card_id}.yaml")), ontology_bundle())


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
    policies = load_scheduling_policies(ontology_bundle())
    return project_governed_assignments(
        ontology_bundle().runtime_program, product, {substance.id: substance}, policies, capability
    ), policies


def _slot(food: bool) -> Slot:
    return Slot(f"food_{food}", f"Food {food}", 1, "day_meal", food, "daily", "Daily", "daily")


def _card_tuple(card_id: str) -> tuple[object, ...]:
    card = _real(card_id)
    key = f"intake{AUDIT_GOVERNANCE_KEY_SEPARATOR}{card.intake[0]}"
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
    policies = load_scheduling_policies(ontology_bundle())
    candidate_product = Product("prd_candidate", "Candidate", (ProductComponent(card.id),))
    anchor = Substance("sub_anchor", "Anchor")
    anchor_product = Product("prd_anchor", "Anchor", (ProductComponent(anchor.id),))

    def capability(product: Product, source_forms: tuple[tuple[str, str], ...]) -> PlannerCapability:
        return PlannerCapability("slot_policy", "binary", frozenset({"binary"}), product.id, source_forms)

    candidate_forms = ((card.id, card.form),) if card.form else ()
    projections = {
        "candidate": project_governed_assignments(
            ontology_bundle().runtime_program,
            candidate_product,
            {card.id: card},
            policies,
            capability(candidate_product, candidate_forms),
        ),
        "anchor": project_governed_assignments(
            ontology_bundle().runtime_program,
            anchor_product,
            {anchor.id: anchor},
            policies,
            capability(anchor_product, ()),
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
    feasibility = build_feasibility_index(ontology_bundle().runtime_program, slots, active, policies, [])
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
            scheduling_constraint_plans=(),
            effect_scoring=ontology_bundle().runtime_program.effect_scoring,
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


def test_digestive_context_is_advisory_not_assignment(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    card = Substance("sub_digestive", "Digestive", kind=("enzyme",), effect=("digestive_enzyme_context",))
    projection, _ = _projection(card)
    assert projection.assignments == ()
    monkeypatch.setattr(
        audit_full, "load_audit_review_rules", lambda _ontology_bundle: _single_rule(card.id, "governed_assignment")
    )
    db = cast(SurrealSession, _Rows([{"id": card.id, "name": card.name}]))
    assert "explicit intake disposition missing" in audit_full._intake_review(db, {card.id: card}, ontology_bundle())[0]
    copied = _copy_repository_fixture(tmp_path)
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
        for item in cast(list[dict[str, object]], load_ontology(copied).runtime_vocabulary["audit_review_rules"])
        if item["id"] == "audit_intake_enzyme_digestive"
    )
    monkeypatch.setattr(audit_full, "load_audit_review_rules", lambda _ontology_bundle: [generated])
    assert audit_full._intake_review(db, {card.id: card}, load_ontology(copied)) == []
    assert card.intake == () and _projection(card)[0].assignments == ()


def test_intake_review_rejects_unknown_authored_disposition(monkeypatch: pytest.MonkeyPatch) -> None:
    card = Substance("sub_unknown", "Unknown", intake=("food_preferred",))
    rule = {
        **_live_rule(),
        "subjects": {card.id: {"disposition": "unrecognized"}},
    }
    monkeypatch.setattr(audit_full, "load_audit_review_rules", lambda _ontology_bundle: [rule])
    db = cast(SurrealSession, _Rows([{"id": card.id, "name": card.name}]))
    with pytest.raises(ValueError, match="unsupported disposition"):
        audit_full._intake_review(db, {card.id: card}, ontology_bundle())


def test_assignment_governance_rejects_unknown_lifecycle() -> None:
    card = Substance(
        "sub_unknown_lifecycle",
        "Unknown lifecycle",
        schedule_governance={
            "intake:food_preferred": ScheduleGovernance(
                "unknown",
                "preference",
                (),
                (),
                "owner",
                "2026-10-13",
            )
        },
    )
    with pytest.raises(ValueError, match="unknown runtime lifecycle state"):
        audit_full._assignment_governance({card.id: card}, ontology_bundle(), include_retired=False)


def test_review_pending_assignment_cannot_block_food_false() -> None:
    policy = load_scheduling_policies(ontology_bundle())["intake:food_required"]
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
    traces = [
        compute_slot_score(ontology_bundle().runtime_program, projection, _slot(food), policies)
        for food in (False, True)
    ]
    assert not any(trace.blocked for trace in traces)
    codes = {row.code for trace in traces for row in trace.diagnostics}
    assert {"review_pending_block", "enforcement_advisory_role", "block_suppressed", "level_suppressed"} <= codes
    assert {row.source_card_id for trace in traces for row in trace.diagnostics} == {card.id}
    assert traces[0].effects[0].assignment_ids == ("substance:sub_pending:intake:food_required",)
    assert traces[0].effects[0].source_card_ids == (card.id,)
    assert "block_suppressed" in traces[0].effects[0].action_codes
    assert "level_suppressed" in traces[1].effects[0].action_codes


def test_approved_food_required_can_block_when_scope_and_evidence_present() -> None:
    policies = load_scheduling_policies(ontology_bundle())
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
    projection = project_governed_assignments(
        ontology_bundle().runtime_program, product, {component.id: component}, policies, capability
    )
    assert compute_slot_score(ontology_bundle().runtime_program, projection, _slot(False), policies).blocked
    assert not compute_slot_score(ontology_bundle().runtime_program, projection, _slot(True), policies).blocked
    mismatch = PlannerCapability("slot_policy", "binary", frozenset({"binary"}), "prd_other", ())
    suppressed = project_governed_assignments(
        ontology_bundle().runtime_program, product, {component.id: component}, policies, mismatch
    )
    direct = next(row for row in suppressed.assignments if row.source_kind == "product")
    mismatch_trace = compute_slot_score(ontology_bundle().runtime_program, suppressed, _slot(False), policies)
    assert direct.assignment_scope.reason_code == "mismatch_scope;suppress_assignment"
    assert (direct.effective_cap, mismatch_trace.score, mismatch_trace.blocked) == ("none", 0, False)


def test_assignment_governance_keys_exactly_match_schedule_traits(tmp_path: Path) -> None:
    for card_id in MATRIX:
        card = _real(card_id)
        assert set(card.schedule_governance) == {f"intake{AUDIT_GOVERNANCE_KEY_SEPARATOR}{card.intake[0]}"}
        assert isinstance(next(iter(card.schedule_governance.values())), ScheduleGovernance)
    card = cast(YamlValue, {"id": "sub_test", "name": "Test", "schedule": {"intake": ["food_preferred"]}})
    assert any(
        "missing schedule_governance" in error
        for error in validate_schedule_contract(
            card, Path("test.yaml"), card_kind="substance", bundle=ontology_bundle()
        )
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
        for error in validate_schedule_contract(
            orphan, Path("test.yaml"), card_kind="substance", bundle=ontology_bundle()
        )
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
    loaded = load_substance(valid_path, ontology_bundle())
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
    errors = validate_schedule_contract(card, Path("test.yaml"), card_kind="substance", bundle=ontology_bundle())
    assert any("requires applicable evidence" in error for error in errors)
    unknown = cast(dict[str, object], cast(dict[str, object], card)["schedule_governance"])
    unknown_record = cast(dict[str, object], unknown["intake:food_preferred"])
    unknown_record["evidence"] = [{"source": "unknown", "supports": "Synthetic.", "limitations": "Synthetic."}]
    assert any(
        "not in slot_policy_evidence" in error
        for error in validate_schedule_contract(
            card, Path("test.yaml"), card_kind="substance", bundle=ontology_bundle()
        )
    )
    unknown_record["evidence"] = [{"source": "enzyme.E3", "supports": "Synthetic."}]
    assert schema_errors(card, "substance", Path("test.yaml"), ontology_bundle())
    unknown_record.update({
        "evidence": [{"source": "enzyme.E3", "supports": "Synthetic.", "limitations": "Synthetic."}],
        "enforcement_cap": "block",
        "scope": {"formulation": "unknown"},
    })
    assert any(
        "unobservable scope cannot declare enforcement_cap block" in error
        for error in validate_schedule_contract(
            card, Path("test.yaml"), card_kind="substance", bundle=ontology_bundle()
        )
    )
    copied = _copy_repository_fixture(tmp_path)
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
        for trace in (
            compute_slot_score(ontology_bundle().runtime_program, projection, _slot(food), policies)
            for food in (False, True)
        )
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
            compute_slot_score(ontology_bundle().runtime_program, value, _slot(food), policies).score,
            compute_slot_score(ontology_bundle().runtime_program, value, _slot(food), policies).blocked,
        )
        for value in (plain_projection, bio_projection)
        for food in (False, True)
    ] == [(0, False)] * 4
    plain_plan = _plan_scenario(plain)
    biochemical_plan = _plan_scenario(biochemical)
    for key in ("traces", "trace_slot_ids", "feasible_order", "assignment", "chosen", "metrics"):
        assert biochemical_plan[key] == plain_plan[key]


def test_pancreatin_evidence_does_not_leak_across_scope() -> None:
    card = _real("sub_winwtayogk")
    assert _card_tuple(card.id) == MATRIX[card.id]
    projection, policies = _projection(card)
    generic = projection.assignments[0]
    assert (generic.assignment_scope.outcome, generic.governance.status, generic.effective_cap) == (
        "limited",
        "review_pending",
        "advisory",
    )
    assert not any(
        compute_slot_score(ontology_bundle().runtime_program, projection, _slot(food), policies).blocked
        for food in (False, True)
    )
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
        ontology_bundle().runtime_program,
        product,
        {card.id: card},
        policies,
        PlannerCapability("slot_policy", "binary", frozenset({"binary"}), product.id, ()),
    )
    assert compute_slot_score(ontology_bundle().runtime_program, matching, _slot(False), policies).blocked
    mismatch = project_governed_assignments(
        ontology_bundle().runtime_program,
        product,
        {card.id: card},
        policies,
        PlannerCapability("slot_policy", "binary", frozenset({"binary"}), "prd_other", ()),
    )
    direct = next(row for row in mismatch.assignments if row.source_kind == "product")
    mismatch_trace = compute_slot_score(ontology_bundle().runtime_program, mismatch, _slot(False), policies)
    assert (direct.effective_cap, mismatch_trace.score, mismatch_trace.blocked) == ("none", 0, False)


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
        lambda _ontology_bundle, *, include_retired=False: [rule],
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
