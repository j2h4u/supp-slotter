from __future__ import annotations

from pathlib import Path

import pytest

from tests.helpers import run_planner


def test_cli_help_exposes_simple_agent_commands() -> None:
    result = run_planner("--help")

    assert result.returncode == 0, result.stdout + result.stderr
    assert "{check,normalize,find,review,groom}" in result.stdout
    assert "next canonical-coverage grooming role" in result.stdout


def test_cli_helper_requires_explicit_root_for_behavior_commands() -> None:
    with pytest.raises(ValueError, match="requires root=tmp_path"):
        run_planner("check")


def test_cli_normalize_is_an_explicit_command(tmp_path: Path) -> None:
    result = run_planner("normalize", root=tmp_path)

    assert result.returncode == 0, result.stdout + result.stderr
    assert not (tmp_path / ".planner-maintenance.lock").exists()
