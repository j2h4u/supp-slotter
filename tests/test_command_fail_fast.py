"""Command-boundary regressions for fail-fast validation and publication."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import planner.engine.check as check_module
import planner.engine.plan as plan_module
import planner.engine.show as show_module
import pytest
from planner.contracts import CardLoadError
from planner.engine.results import CheckResult
from planner.paths import Paths

from tests.planner_fixture import PlannerFixtureInput, write_minimal_planner_fixture


def test_malformed_substance_stops_before_registry_and_relations(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    paths = Paths.from_root(tmp_path)
    paths.data.mkdir()
    paths.data.joinpath("pillboxes.yaml").write_text("{}\n", encoding="utf-8")
    paths.relations_file.write_text("relations: []\n", encoding="utf-8")
    bundle = SimpleNamespace()
    called: list[str] = []

    monkeypatch.setattr(
        check_module,
        "check_substances",
        lambda *_args: (["malformed substance"], [], {"sub": paths.data / "sub.yaml"}),
    )
    monkeypatch.setattr(check_module, "load_substance_registry", lambda *_args: called.append("registry"))
    monkeypatch.setattr(check_module, "check_global_relations", lambda *_args: called.append("relations"))

    result = check_module._extend_card_validation_errors(paths, [], [], bundle)  # type: ignore[arg-type]

    assert result == CheckResult(1, ["malformed substance"], [])
    assert called == []
    assert "malformed substance" in capsys.readouterr().err


def test_malformed_stacks_are_reported_before_substance_validation(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    paths = Paths.from_root(tmp_path)
    paths.data.mkdir()
    paths.data.joinpath("pillboxes.yaml").write_text("{}\n", encoding="utf-8")
    paths.stacks_file.write_text("stacks: [\n", encoding="utf-8")
    paths.relations_file.write_text("relations: []\n", encoding="utf-8")
    bundle = SimpleNamespace()
    called: list[str] = []

    original_load_yaml = check_module.load_yaml

    def load_yaml(path: Path) -> object:
        if path == paths.stacks_file:
            raise CardLoadError(path, f"{path}: yaml parse error")
        return original_load_yaml(path)

    monkeypatch.setattr(check_module, "load_yaml", load_yaml)
    monkeypatch.setattr(check_module, "check_substances", lambda *_args: called.append("substances"))

    result = check_module._cmd_check_inner(paths, bundle)  # type: ignore[arg-type]

    assert result.exit_code == 1
    assert result.errors == [f"{paths.stacks_file}: yaml parse error"]
    assert called == []
    assert f"{paths.stacks_file}: yaml parse error" in capsys.readouterr().err


def test_show_invalidates_stale_schedule_and_does_not_render_or_write(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    write_minimal_planner_fixture(
        tmp_path,
        PlannerFixtureInput(
            stack_items={"product": {"stack": "daily"}},
            products={"product": [("component", [])]},
            traits={},
        ),
    )
    schedule = tmp_path / "schedule.yaml"
    schedule.write_text("stale layout\n", encoding="utf-8")
    (tmp_path / "data" / "stacks.yaml").write_text("stacks: [\n", encoding="utf-8")
    calls: list[str] = []

    monkeypatch.setattr(plan_module, "write_schedule_file", lambda *_args: calls.append("writer"))
    monkeypatch.setattr(show_module, "_show_inner", lambda *_args: calls.append("render"))

    result = show_module.cmd_show(data_root=tmp_path)

    assert result.exit_code == 1
    assert result.output == ""
    assert not schedule.exists()
    assert calls == []
    assert "invalid YAML" in capsys.readouterr().err
