"""Focused acceptance checks for the formal card-grooming contract."""

from planner.engine import cmd_groom
from planner.ontology.artifacts import load_ontology
from planner.paths import ROOT


def test_groom_selects_one_complete_deterministic_dossier() -> None:
    first = cmd_groom()
    second = cmd_groom()

    assert first.exit_code == 0, first.stderr
    assert second.exit_code == 0, second.stderr
    assert first.work_item is not None
    assert first.work_item == second.work_item
    assert first.eligible_count >= 1
    assert first.output.count("card ") == 1
    assert first.work_item.active_unique_product_count == len(first.work_item.active_products)
    assert "use_pattern:" in first.output and "notes:" in first.output
    assert all(relation.owner_id in relation.active_endpoint_ids for relation in first.work_item.open_relations)
    assert all(first.output.count(relation.id) == 1 for relation in first.work_item.open_relations)


def test_groom_policy_is_closed_and_formal() -> None:
    policy = load_ontology(ROOT / "ontology").runtime_program.grooming_policy

    assert policy.require_active_reachable is True
    assert policy.open_research_state == "unassessed"
    assert [(row.field, row.direction) for row in policy.rank_fields] == [
        ("active_unique_product_count", "descending"),
        ("open_owned_item_count", "descending"),
        ("substance_id", "ascending"),
    ]
    assert policy.selection_count == 1
    assert policy.relation_owner_field == "substance_id"
    assert policy.relation_owner_direction == "ascending"


def test_groom_policy_rank_fields_are_executable_structural_inputs() -> None:
    policy = load_ontology(ROOT / "ontology").runtime_program.grooming_policy
    metrics_a = {"active_unique_product_count": 1, "open_owned_item_count": 9, "substance_id": "sub_a"}
    metrics_b = {"active_unique_product_count": 2, "open_owned_item_count": 1, "substance_id": "sub_b"}
    from planner.engine.grooming import _rank_key

    normal = sorted((metrics_a, metrics_b), key=lambda row: _rank_key(row, policy.rank_fields))
    toggled = tuple(reversed(policy.rank_fields))
    changed = sorted((metrics_a, metrics_b), key=lambda row: _rank_key(row, toggled))
    assert normal != changed
