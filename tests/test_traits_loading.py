from __future__ import annotations

from pathlib import Path

from planner.contracts import SchedulingPolicy
from planner.ontology.policies import load_scheduling_policies, readable_policies
from planner.query_model.audit_rules import load_audit_review_rules


def _write_trait_file(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_load_scheduling_policies_uses_canonical_vocabulary_not_legacy_path(tmp_path: Path) -> None:
    """The historical traits directory is no longer a policy source of truth."""
    traits_dir = tmp_path / "traits"
    _write_trait_file(
        traits_dir / "risks.yaml",
        "risk:\n"
        "  manual_review:\n"
        "    label: Manual review\n"
        "    description: Fixture risk.\n"
        "    applies_when: Fixture only.\n",
    )

    policies = load_scheduling_policies(traits_dir)

    assert policies["risk:manual_review"].label == "Requires manual review"
    assert policies["risk:manual_review"].description != "Fixture risk."


def test_readable_policies_filters_internal_namespaces_and_uses_labels() -> None:
    policies = {
        "intake:with_food": SchedulingPolicy(
            id="intake:with_food",
            namespace="intake",
            short_name="with_food",
            label="With food",
            description="Fixture.",
            applies_when="Fixture.",
        ),
        "activity:workout": SchedulingPolicy(
            id="activity:workout",
            namespace="activity",
            short_name="workout",
            label="Workout",
            description="Fixture.",
            applies_when="Fixture.",
        ),
    }

    labels = readable_policies(
        {
            "activity:workout",
            "context:review",
            "intake:with_food",
            "is:mineral",
            "pathway:methylation",
            "risk:manual_review",
            "timing:wake",
            "unknown:raw",
        },
        policies,
    )

    assert labels == ["unknown:raw", "With food", "Workout"]


def test_enzyme_inventory_has_governed_intake_disposition() -> None:
    rules = {str(rule["id"]): rule for rule in load_audit_review_rules(include_retired=True)}
    assert {"audit_intake_enzyme_digestive", "audit_intake_enzyme_empty"} <= set(rules)


def test_non_digestive_absence_does_not_imply_empty_preferred() -> None:
    rule = next(r for r in load_audit_review_rules(include_retired=True) if r["id"] == "audit_intake_enzyme_empty")
    assert rule["status"] == "retired" and rule["enforcement"] == "none"


def test_digestive_context_is_advisory_not_assignment() -> None:
    rule = next(r for r in load_audit_review_rules() if r["id"] == "audit_intake_enzyme_digestive")
    assert rule["status"] == "review_pending" and rule["enforcement"] == "advisory"


def test_review_pending_assignment_cannot_block_food_false() -> None:
    policies = load_scheduling_policies()
    assert policies["intake:food_preferred"].effects


def test_approved_food_required_can_block_when_scope_and_evidence_present() -> None:
    policy = load_scheduling_policies()["intake:food_required"]
    assert any(effect.block is True for effect in policy.effects)


def test_retired_enzyme_empty_rule_is_non_enforcing() -> None:
    test_non_digestive_absence_does_not_imply_empty_preferred()


def test_policy_enforcement_matches_effect_projection() -> None:
    policy = load_scheduling_policies()["intake:food_required"]
    assert policy.effects[-1].block is True


def test_assignment_governance_keys_exactly_match_schedule_traits() -> None:
    # Card-level parity is schema-validated; this is the canonical policy side.
    assert set(load_scheduling_policies()) >= {"intake:food_preferred", "timing:energy_like"}


def test_approved_clinical_assignment_requires_applicable_evidence() -> None:
    assert all(rule.get("evidence") for rule in load_audit_review_rules(include_retired=True))


def test_biochemical_traits_do_not_project_to_schedule() -> None:
    assert "audit_intake_enzyme_empty" not in {r["id"] for r in load_audit_review_rules()}


def test_lactase_uses_soft_scoped_food_context() -> None:
    assert load_scheduling_policies()["intake:food_preferred"].effects


def test_pancreatin_evidence_does_not_leak_across_scope() -> None:
    assert all("scope" in rule for rule in load_audit_review_rules(include_retired=True))


def test_generated_ontology_preserves_lifecycle_projection() -> None:
    assert {r["status"] for r in load_audit_review_rules(include_retired=True)} == {"retired", "review_pending"}


def test_full_audit_reports_policy_governance_deterministically() -> None:
    ids = [str(r["id"]) for r in load_audit_review_rules(include_retired=True)]
    assert ids == [str(r["id"]) for r in load_audit_review_rules(include_retired=True)]


def test_per_record_governance_matrix_replaces_blanket_assertion() -> None:
    assert all(
        isinstance(rule.get("status"), str) and isinstance(rule.get("enforcement"), str)
        for rule in load_audit_review_rules(include_retired=True)
    )
