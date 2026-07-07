from __future__ import annotations

import pytest

from tests.helpers import run_planner


def test_cli_help_exposes_simple_agent_commands() -> None:
    result = run_planner("--help")

    assert result.returncode == 0, result.stdout + result.stderr
    assert "{check,audit,find,review,review-substance}" in result.stdout


def test_cli_helper_requires_explicit_root_for_behavior_commands() -> None:
    with pytest.raises(ValueError, match="requires root=tmp_path"):
        run_planner("check")
