"""Focused acceptance checks for categorical research-state grooming."""

from planner.engine.grooming import cmd_grooming_research


def test_research_state_grooming_filters_active_reachable_legacy_assertions() -> None:
    result = cmd_grooming_research("unassessed", limit=5)

    assert result.exit_code == 0, result.stderr
    assert result.shown <= 5
    assert result.total_matching >= result.shown
    assert result.assertion_count >= len(result.candidates)
    assert all(card.assertions for card in result.cards)
    assert all(
        assertion.research_state == "unassessed"
        for card in result.cards
        for assertion in (*card.assertions, *card.related_relations)
    )
    assert "Research-state card queue (unassessed)" in result.output


def test_research_state_grooming_limit_counts_cards_and_groups_assertions() -> None:
    result = cmd_grooming_research("unassessed", limit=1)

    assert result.exit_code == 0, result.stderr
    assert result.shown == 1
    assert len(result.cards[0].assertions) > 1
    assert f"{result.total_matching} cards" in result.output
    assert f"{result.assertion_count} assertions" in result.output


def test_research_state_grooming_default_is_one_complete_card() -> None:
    result = cmd_grooming_research("unassessed")

    assert result.exit_code == 0, result.stderr
    assert result.limit == result.shown == 1
    assert len(result.cards[0].assertions) > 1
    assert f"{result.total_matching} cards, showing 1" in result.output


def test_research_state_grooming_current_card_summary_and_relation_attachment() -> None:
    result = cmd_grooming_research("unassessed", limit=50)

    assert result.exit_code == 0, result.stderr
    assert result.shown == result.total_matching
    status_counts = {
        status: sum(card.assessment_status == status for card in result.cards)
        for status in {card.assessment_status for card in result.cards}
    }
    assert sum(status_counts.values()) == result.total_matching
    assert status_counts.get("wholly_unassessed", 0) + status_counts.get("partially_assessed", 0) > 0
    knowledge_count = sum(len(card.assertions) for card in result.cards)
    relation_ids = [relation.id for card in result.cards for relation in card.related_relations]
    assert knowledge_count + len(set(relation_ids)) == result.assertion_count
    assert len({card.id for card in result.cards}) == result.total_matching


def test_research_state_grooming_priority_is_transparent_and_deterministic() -> None:
    result = cmd_grooming_research("unassessed", limit=50)

    keys = [
        (-card.active_product_count, -card.unresolved_item_count, card.name.casefold(), card.id)
        for card in result.cards
    ]
    assert keys == sorted(keys)
    assert "active_products=" in result.output
    assert "unresolved=" in result.output


def test_research_state_grooming_rejects_unknown_state() -> None:
    result = cmd_grooming_research("not-a-research-state")

    assert result.exit_code == 1
    assert "invalid --state" in result.stderr
