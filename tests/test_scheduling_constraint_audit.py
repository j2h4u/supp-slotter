"""User-facing audit coverage for canonical scheduling constraints."""

from __future__ import annotations

import contextlib
import io
from pathlib import Path

from planner.engine.audit import cmd_audit

from tests.test_audit_command import _write_audit_fixture


def test_full_audit_prints_all_constraint_structure_and_unresolved_coverage(tmp_path: Path) -> None:
    _write_audit_fixture(tmp_path)
    stdout = io.StringIO()

    with contextlib.redirect_stdout(stdout):
        result = cmd_audit(data_root=tmp_path, full=True)

    lines = result.full["full.scheduling_constraints"]
    assert len(lines) == 8
    assert [line.split(":", maxsplit=1)[0] for line in lines] == sorted(
        line.split(":", maxsplit=1)[0] for line in lines
    )
    assert all("source=" in line and "target=" in line for line in lines)
    assert all("effect=separate_slots; enforcement=block" in line for line in lines)
    assert all("status=review_pending" in line and "owner=supp-slotter-maintainers" in line for line in lines)
    assert all(
        "review_by=2026-10-13" in line and "assertion_type=clinical_scheduling_constraint" in line for line in lines
    )
    assert any("coverage=UNRESOLVED" in line for line in lines)
    assert "Scheduling constraints — structure and selector coverage (8)" in stdout.getvalue()
    assert "sc_mineral_fat_soluble_separate_slots" in stdout.getvalue()


def test_regular_audit_does_not_print_constraint_coverage(tmp_path: Path) -> None:
    _write_audit_fixture(tmp_path)
    stdout = io.StringIO()

    with contextlib.redirect_stdout(stdout):
        result = cmd_audit(data_root=tmp_path)

    assert result.full == {}
    assert "Scheduling constraints — structure and selector coverage" not in stdout.getvalue()
