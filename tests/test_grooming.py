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


def test_groom_policy_is_closed_and_formal() -> None:
    policy = load_ontology(ROOT / "ontology").runtime_program.grooming_policy

    assert policy.work_unit == "substance_card"
    assert policy.eligibility == ("active_reachable", "unassessed_owned_item")
    assert [(row.field, row.direction) for row in policy.rank_fields] == [
        ("active_unique_product_count", "descending"),
        ("open_owned_item_count", "descending"),
        ("substance_id", "ascending"),
    ]
    assert policy.selection_count == 1
    assert policy.relation_owner == "lowest_stable_substance_id"
