from __future__ import annotations

from pathlib import Path

import pytest
from planner.engine.results import ShowResult

from tests.helpers import run_planner


def test_cli_help_exposes_simple_agent_commands() -> None:
    result = run_planner("--help")

    assert result.returncode == 0, result.stdout + result.stderr
    assert "{show,check,normalize,find,review}" in result.stdout
    assert "(bare invocation) or show" in result.stdout
    assert "groom" not in result.stdout


def test_cli_show_is_an_explicit_alias_for_bare_invocation(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr("planner.__main__.cmd_show", lambda *, data_root: ShowResult(0, f"schedule:{data_root}\n"))

    result = run_planner("show", root=tmp_path)

    assert result.returncode == 0
    assert result.stdout == f"schedule:{tmp_path}\n"


def test_cli_helper_requires_explicit_root_for_behavior_commands() -> None:
    with pytest.raises(ValueError, match="requires root=tmp_path"):
        run_planner("check")


def test_cli_normalize_is_an_explicit_command(tmp_path: Path) -> None:
    result = run_planner("normalize", root=tmp_path)

    assert result.returncode == 0, result.stdout + result.stderr
    assert not (tmp_path / ".planner-maintenance.lock").exists()
