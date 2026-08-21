"""Focused acceptance checks for categorical research-state grooming."""

from planner.engine.grooming import cmd_grooming_research


def test_research_state_grooming_filters_active_reachable_legacy_assertions() -> None:
    result = cmd_grooming_research("unassessed", limit=5)

    assert result.exit_code == 0, result.stderr
    assert result.shown <= 5
    assert result.total_matching >= result.shown
    assert all(candidate.research_state == "unassessed" for candidate in result.candidates)
    assert "Research-state queue (unassessed)" in result.output


def test_research_state_grooming_rejects_unknown_state() -> None:
    result = cmd_grooming_research("not-a-research-state")

    assert result.exit_code == 1
    assert "invalid --state" in result.stderr
