"""User-facing audit coverage for canonical scheduling constraints."""

from __future__ import annotations

import contextlib
import io
from pathlib import Path

from planner.engine.audit import cmd_audit

from tests.test_audit_command import _write_audit_fixture


def test_full_audit_prints_constraint_structure_and_selector_coverage(tmp_path: Path) -> None:
    _write_audit_fixture(tmp_path)
    stdout = io.StringIO()

    with contextlib.redirect_stdout(stdout):
        result = cmd_audit(data_root=tmp_path, full=True)

    lines = result.full["diagnostics"]
    assert len(lines) == 4
    assert [line.split(":", maxsplit=1)[0] for line in lines] == sorted(
        line.split(":", maxsplit=1)[0] for line in lines
    )
    assert all("selectors=" in line and "source=" in line and "target=" in line for line in lines)
    assert all("operation=separate_products_same_slot" in line for line in lines)
    assert all("action=" in line for line in lines)
    assert all("coverage=resolved" in line for line in lines)
    assert "Full audit (4)" in stdout.getvalue()


def test_regular_audit_does_not_print_constraint_coverage(tmp_path: Path) -> None:
    _write_audit_fixture(tmp_path)
    stdout = io.StringIO()

    with contextlib.redirect_stdout(stdout):
        result = cmd_audit(data_root=tmp_path)

    assert result.full == {}
    assert "Scheduling constraints — structure and selector coverage" not in stdout.getvalue()
