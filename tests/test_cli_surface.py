from __future__ import annotations

from tests.helpers import run_planner


def test_cli_help_exposes_simple_agent_commands() -> None:
    result = run_planner("--help")

    assert result.returncode == 0, result.stdout + result.stderr
    assert "{check,audit,find,review,review-substance}" in result.stdout
