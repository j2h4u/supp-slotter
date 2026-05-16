"""Regression tests for maintenance, io error handling, and auto-maintenance sentinel changes.

Covers:
  - EH1/EH2: load_yaml / load_schema descriptive error wrapping
  - C1: guarded stacks.yaml write in maintenance pipeline
  - EH7: vocal CardLoadError skips in rewrite_substance_refs
  - EH9: vocal load_global_relations on non-mapping data
  - EH10: auto_maintenance_needed None vs False disambiguation
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
import yaml

from planner.contracts import CardLoadError
from planner.io import Paths, load_schema, load_yaml
from planner.maintenance import (
    auto_maintenance_needed,
    rewrite_substance_refs,
    run_auto_maintenance,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _write_yaml(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(data, sort_keys=False, allow_unicode=True))


def _minimal_substance(
    sub_id: str = "sub_abc1234567",
    name: str = "Magnesium Glycinate",
) -> dict[str, Any]:
    return {"id": sub_id, "name": name, "traits": []}


def _minimal_product(
    prd_id: str = "prd_abc1234567",
    name: str = "Mag Glycinate 400",
    components: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    return {
        "id": prd_id,
        "name": name,
        "components": components or [{"substance": "sub_abc1234567"}],
    }


# ---------------------------------------------------------------------------
# Task 1 — EH1/EH2: load_yaml and load_schema descriptive errors
# ---------------------------------------------------------------------------

def test_load_yaml_missing_file_raises_card_load_error(tmp_path: Path) -> None:
    absent = tmp_path / "absent.yaml"
    with pytest.raises(CardLoadError) as exc_info:
        load_yaml(absent)
    assert str(absent) in exc_info.value.message


def test_load_yaml_malformed_yaml_raises_card_load_error(tmp_path: Path) -> None:
    bad = tmp_path / "bad.yaml"
    bad.write_text(":\n  - bad: [")
    with pytest.raises(CardLoadError) as exc_info:
        load_yaml(bad)
    assert "invalid YAML" in exc_info.value.message


def test_load_schema_missing_raises_runtime_error_naming_schema(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("planner.io.SCHEMA_DIR", tmp_path)
    with pytest.raises(RuntimeError) as exc_info:
        load_schema("nope")
    assert "nope.schema.json" in str(exc_info.value)


def test_load_schema_malformed_json_raises_runtime_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    bad_schema = tmp_path / "bad.schema.json"
    bad_schema.write_text("{not json")
    monkeypatch.setattr("planner.io.SCHEMA_DIR", tmp_path)
    with pytest.raises(RuntimeError) as exc_info:
        load_schema("bad")
    assert "bad.schema.json" in str(exc_info.value)


# ---------------------------------------------------------------------------
# Task 2 — C1: guarded stacks.yaml write
# ---------------------------------------------------------------------------

def _build_rename_tree(tmp_path: Path) -> tuple[Path, Path, Path]:
    """Create data/substances/, data/products/, data/stacks.yaml under tmp_path.

    The product references substance sub_old which gets renamed to sub_new,
    so the stacks-write branch is exercised.
    Returns (substances_dir, products_dir, stacks_path).
    """
    data_dir = tmp_path / "data"
    substances_dir = data_dir / "substances"
    substances_dir.mkdir(parents=True)
    products_dir = data_dir / "products"
    products_dir.mkdir(parents=True)

    # Substance card — no id so it gets one assigned and the old stem is tracked as rename
    sub_path = substances_dir / "magnesium_glycinate.yaml"
    _write_yaml(sub_path, {"name": "Magnesium Glycinate", "traits": []})

    # Product card — also no id
    prd_path = products_dir / "mag_glycinate_400.yaml"
    _write_yaml(prd_path, {"name": "Mag Glycinate 400", "components": [{"substance": "magnesium_glycinate"}]})

    stacks_path = data_dir / "stacks.yaml"
    _write_yaml(stacks_path, {"daily": ["mag_glycinate_400"], "training": []})

    return substances_dir, products_dir, stacks_path


def test_run_auto_maintenance_returns_1_when_stacks_write_fails(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    from planner.maintenance import run_auto_maintenance

    _build_rename_tree(tmp_path)

    # Make stacks.yaml read-only so write_text raises OSError
    stacks_path = tmp_path / "data" / "stacks.yaml"
    stacks_path.chmod(0o444)

    try:
        result = run_auto_maintenance(Paths.from_root(tmp_path))
    finally:
        stacks_path.chmod(0o644)

    assert result == 1
    captured = capsys.readouterr()
    assert "stacks.yaml" in captured.err


# ---------------------------------------------------------------------------
# Task 3 — EH7: vocal CardLoadError skips in rewrite_substance_refs
# ---------------------------------------------------------------------------

def test_rewrite_substance_refs_warns_on_corrupted_product(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    substances_dir = tmp_path / "substances"
    substances_dir.mkdir()
    products_dir = tmp_path / "products"
    products_dir.mkdir()

    # Valid substance
    _write_yaml(
        substances_dir / "magnesium_glycinate.yaml",
        _minimal_substance("sub_abc1234567", "Magnesium Glycinate"),
    )

    # Corrupted product YAML
    bad_product = products_dir / "bad_product.yaml"
    bad_product.write_text("id: [bad nested\n")

    rewrite_substance_refs(tmp_path, {"old_sub": "new_sub"})

    captured = capsys.readouterr()
    assert "warning: skipping" in captured.err
    assert "bad_product.yaml" in captured.err


# ---------------------------------------------------------------------------
# Task 3 — EH9: load_global_relations warns on non-mapping top-level
# ---------------------------------------------------------------------------

def test_load_global_relations_warns_on_non_mapping(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    from planner.cards.relations import load_global_relations

    data_dir = tmp_path / "data"
    data_dir.mkdir()
    rel_path = data_dir / "relations.yaml"
    rel_path.write_text("- a list at top level\n")
    paths = Paths.from_root(tmp_path)

    result = load_global_relations(paths)

    assert result == []
    captured = capsys.readouterr()
    assert "expected mapping, got list" in captured.err


def test_load_global_relations_quiet_on_mapping(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    from planner.cards.relations import load_global_relations

    data_dir = tmp_path / "data"
    data_dir.mkdir()
    rel_path = data_dir / "relations.yaml"
    _write_yaml(rel_path, {"balance": []})
    paths = Paths.from_root(tmp_path)

    result = load_global_relations(paths)

    assert result == []
    captured = capsys.readouterr()
    assert captured.err == ""


# ---------------------------------------------------------------------------
# Task 4 — EH10: auto_maintenance_needed None vs False disambiguation
# ---------------------------------------------------------------------------

def test_auto_maintenance_needed_returns_none_on_card_load_error(
    tmp_path: Path,
) -> None:
    substances_dir = tmp_path / "data" / "substances"
    substances_dir.mkdir(parents=True)
    products_dir = tmp_path / "data" / "products"
    products_dir.mkdir(parents=True)

    # Malformed substance YAML so load_card_mapping raises CardLoadError
    broken = substances_dir / "broken.yaml"
    broken.write_text(":\n  - bad: [")

    result = auto_maintenance_needed(Paths.from_root(tmp_path))

    assert result is None


def test_run_auto_maintenance_returns_1_without_acquiring_lock_on_load_error(
    tmp_path: Path,
) -> None:
    substances_dir = tmp_path / "data" / "substances"
    substances_dir.mkdir(parents=True)
    products_dir = tmp_path / "data" / "products"
    products_dir.mkdir(parents=True)

    broken = substances_dir / "broken.yaml"
    broken.write_text(":\n  - bad: [")

    paths = Paths.from_root(tmp_path)
    result = run_auto_maintenance(paths, suppress_output=True)

    assert result == 1
    assert not paths.maintenance_lock.exists()


def test_auto_maintenance_needed_still_returns_false_when_clean(
    tmp_path: Path,
) -> None:
    from planner.cards.product import canonical_product_filename
    from planner.cards.substance import canonical_substance_filename
    from planner.contracts import Product as ProductContract
    from planner.contracts import Substance

    substances_dir = tmp_path / "data" / "substances"
    substances_dir.mkdir(parents=True)
    products_dir = tmp_path / "data" / "products"
    products_dir.mkdir(parents=True)

    sub_data = _minimal_substance("sub_abc1234567", "Magnesium Glycinate")
    sub_contract = Substance(id="sub_abc1234567", name="Magnesium Glycinate")
    sub_filename = canonical_substance_filename(sub_contract)
    _write_yaml(substances_dir / sub_filename, sub_data)

    prd_data = _minimal_product("prd_abc1234567", "Mag Glycinate 400")
    prd_contract = ProductContract(id="prd_abc1234567", name="Mag Glycinate 400", components=())
    prd_filename = canonical_product_filename(prd_contract)
    _write_yaml(products_dir / prd_filename, prd_data)

    result = auto_maintenance_needed(Paths.from_root(tmp_path))

    assert result is False
