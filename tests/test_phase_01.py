from __future__ import annotations

from pathlib import Path

from tests.helpers import ROOT, run_planner


def test_phase_01_check_passes() -> None:
    result = run_planner("check")

    assert result.returncode == 0, result.stdout + result.stderr
    assert "All checks passed." in result.stdout
    assert "ERROR:" not in result.stderr
    assert str(ROOT) not in result.stdout


def test_dashboard_ref_validator_rejects_unknown_from_traits_slug_and_restores_file() -> None:
    dashboard_path = ROOT / "data/dashboards/vascular_health.yaml"
    original = dashboard_path.read_bytes()

    try:
        corrupted = original.replace(
            b"  - vascular_health",
            b"  - vascular_health\n  - bogus_slug_xyz456",
            1,
        )
        assert corrupted != original
        dashboard_path.write_bytes(corrupted)

        result = run_planner("check")

        assert result.returncode != 0
        combined_output = result.stdout + result.stderr
        assert "bogus_slug_xyz456" in combined_output
        assert "create data/dashboards/" in combined_output
    finally:
        dashboard_path.write_bytes(original)

    restored = run_planner("check")
    assert restored.returncode == 0, restored.stdout + restored.stderr
