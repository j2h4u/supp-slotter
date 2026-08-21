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
    assert result.total_matching == 36
    assert result.shown == 1
    assert result.assertion_count == 170
    assert len(result.cards[0].assertions) > 1
    assert "36 cards" in result.output
    assert "170 assertions" in result.output


def test_research_state_grooming_default_is_one_complete_card() -> None:
    result = cmd_grooming_research("unassessed")

    assert result.exit_code == 0, result.stderr
    assert result.limit == result.shown == 1
    assert len(result.cards[0].assertions) > 1
    assert "36 cards, showing 1" in result.output


def test_research_state_grooming_current_card_summary_and_relation_attachment() -> None:
    result = cmd_grooming_research("unassessed", limit=50)

    assert result.exit_code == 0, result.stderr
    assert (result.total_matching, result.shown, result.assertion_count) == (36, 36, 170)
    assert sum(card.assessment_status == "wholly_unassessed" for card in result.cards) == 25
    assert sum(card.assessment_status == "partially_assessed" for card in result.cards) == 11
    relation_ids = [relation.id for card in result.cards for relation in card.related_relations]
    assert relation_ids
    assert len({card.id for card in result.cards}) == 36
    assert len(set(relation_ids)) < len(relation_ids)  # multi-endpoint leads attach to each relevant card


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
