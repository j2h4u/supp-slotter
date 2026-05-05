from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]


def copy_data_tree(tmp_path: Path) -> Path:
    temp_data = tmp_path / "data"
    shutil.copytree(ROOT / "data", temp_data)
    return temp_data


def test_refresh_adds_missing_product_formula_to_temp_inventory(tmp_path: Path) -> None:
    temp_data = copy_data_tree(tmp_path)
    shutil.copy2(ROOT / "planner.py", tmp_path / "planner.py")
    shutil.copytree(ROOT / "schema", tmp_path / "schema")
    probe_path = temp_data / "products" / "__refresh_probe__.yaml"
    probe_path.write_text(
        yaml.safe_dump(
            {
                "id": "__refresh_probe__",
                "name": "Refresh Probe",
                "components": [{"substance": "nattokinase"}],
            },
            sort_keys=False,
        )
    )

    result = subprocess.run(
        ["uv", "run", "planner.py", "refresh"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    inventory = yaml.safe_load((temp_data / "inventory.yaml").read_text())
    assert inventory["supplements"]["__refresh_probe__"] == {
        "product": "__refresh_probe__",
        "stack": "inactive",
    }
    assert not (ROOT / "data/products/__refresh_probe__.yaml").exists()
    assert "__refresh_probe__" not in (ROOT / "data/inventory.yaml").read_text()
