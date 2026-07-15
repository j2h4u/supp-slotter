# pyright: reportAny=false, reportExplicitAny=false
from __future__ import annotations

import copy
import hashlib
import json
import shutil
from collections import Counter
from pathlib import Path
from typing import Any, cast

import pytest
import yaml
from scripts.migrate_slot_policy_governance import CardGroup, _fold, classify_card, run, validate_wire

ROOT = Path(__file__).parents[1]
FIX = ROOT / "tests/fixtures/slot_policy"
LEDGER_PATH = FIX / "v2_migration_ledger.yaml"
MANIFEST_PATH = FIX / "v2_worker_manifest.json"


def _load_yaml(path: Path) -> dict[str, Any]:
    return cast(dict[str, Any], yaml.safe_load(path.read_text()))


def _wire() -> tuple[dict[str, Any], dict[str, Any]]:
    return _load_yaml(LEDGER_PATH), cast(dict[str, Any], json.loads(MANIFEST_PATH.read_text()))


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _temp_root(tmp_path: Path) -> Path:
    ledger, manifest = _wire()
    for source in (LEDGER_PATH, MANIFEST_PATH):
        target = tmp_path / source.relative_to(ROOT)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
    for entry in manifest["cards"]:
        source = ROOT / entry["path"]
        target = tmp_path / entry["path"]
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
    catalog: dict[str, dict[str, str]] = {}
    for row in ledger["rows"]:
        for governance in row["after"]["governance_entries"].values():
            for item in governance["evidence"]:
                catalog[item["source"]] = {
                    "supports": item["supports"],
                    "limitations": item["limitations"],
                }
    ontology = tmp_path / "ontology/policies.yaml"
    ontology.parent.mkdir(parents=True, exist_ok=True)
    ontology.write_text(yaml.safe_dump({"slot_policy_evidence": catalog}, sort_keys=False))
    return tmp_path


def test_v3_wire_exact_accounting_and_governance() -> None:
    ledger, manifest = _wire()
    rows, groups = validate_wire(ledger, manifest)
    assert Counter(row["action"] for row in rows) == {
        "KEEP_ASSIGNMENT_ADD_GOVERNANCE": 145,
        "REPLACE_ASSIGNMENT_ADD_GOVERNANCE": 26,
        "REMOVE_ASSIGNMENT_AND_GOVERNANCE": 50,
    }
    live = [value for row in rows for value in row["after"]["governance_entries"].values()]
    assert len(live) == 171
    assert Counter(value["status"] for value in live) == {"review_pending": 143, "approved": 28}
    assert Counter(value["enforcement_cap"] for value in live) == {"preference": 167, "advisory": 4}
    assert len(groups) == 207
    assert Counter(len(group.rows) for group in groups) == {1: 193, 2: 14}


def test_exact_adjudication_and_final_policy_counts() -> None:
    rows = _wire()[0]["rows"]
    decisions = [row["decision"] for row in rows if row["decision"].get("adjudication_key")]
    assert len({decision["adjudication_key"] for decision in decisions}) == 138
    assert Counter(decision["bucket"] for decision in decisions) == {
        "FORM": 88,
        "MINERAL": 35,
        "ENZYME": 4,
        "FAT": 3,
        "WATER_SPACING": 6,
        "EXCEPTION": 2,
    }
    final = Counter()
    for row in rows:
        for policy in row["after"]["axis_values"]:
            final[f"{row['axis']}:{policy}"] += 1
    assert final == {
        "intake:empty_preferred": 22,
        "intake:food_preferred": 141,
        "timing:energy_like": 1,
        "timing:sleep_support": 3,
        "activity:any_workout": 2,
        "activity:pre_workout": 2,
    }


def test_real_manifest_cards_remain_exact_frozen_pre() -> None:
    inventory = json.loads((FIX / "pre_migration_inventory.json").read_text())
    hashes = {row["path"]: row["sha256"] for row in inventory["data_snapshot"]}
    ledger, manifest = _wire()
    _, groups = validate_wire(ledger, manifest)
    assert all(_sha(ROOT / group.path) == hashes[group.path] for group in groups)
    assert all(classify_card(_load_yaml(ROOT / group.path), group)[0] == "PRE" for group in groups)


def test_check_fails_pre_apply_is_resumable_and_double_apply_is_noop(tmp_path: Path) -> None:
    root = _temp_root(tmp_path)
    ledger = root / LEDGER_PATH.relative_to(ROOT)
    manifest = root / MANIFEST_PATH.relative_to(ROOT)
    with pytest.raises(SystemExit, match="PRE cards"):
        run(root, ledger, manifest, "L6", apply=False)
    assert run(root, ledger, manifest, "L6", apply=True) == 0
    assert run(root, ledger, manifest, "L6", apply=False) == 0
    paths = [root / entry["path"] for entry in json.loads(manifest.read_text())["cards"] if entry["owner"] == "L6"]
    hashes = {path: _sha(path) for path in paths}
    assert run(root, ledger, manifest, "L6", apply=True) == 0
    assert hashes == {path: _sha(path) for path in paths}


def test_owner_resume_allows_whole_card_pre_and_post(tmp_path: Path) -> None:
    root = _temp_root(tmp_path)
    ledger_path = root / LEDGER_PATH.relative_to(ROOT)
    manifest_path = root / MANIFEST_PATH.relative_to(ROOT)
    ledger, manifest = _wire()
    _, groups = validate_wire(ledger, manifest)
    group = next(group for group in groups if group.owner == "L7")
    path = root / group.path
    path.write_text(yaml.safe_dump(_fold(_load_yaml(path), group), sort_keys=False))
    assert run(root, ledger_path, manifest_path, "L7", apply=True) == 0
    assert run(root, ledger_path, manifest_path, "L7", apply=False) == 0


def test_mixed_unknown_and_assignment_governance_split_are_refused(tmp_path: Path) -> None:
    root = _temp_root(tmp_path)
    ledger_path = root / LEDGER_PATH.relative_to(ROOT)
    manifest_path = root / MANIFEST_PATH.relative_to(ROOT)
    ledger, manifest = _wire()
    _, groups = validate_wire(ledger, manifest)
    group = next(group for group in groups if len(group.rows) == 2)
    path = root / group.path
    card = _load_yaml(path)
    first_only = CardGroup(group.owner, group.path, group.card_id, (group.rows[0],))
    path.write_text(yaml.safe_dump(_fold(card, first_only), sort_keys=False))
    with pytest.raises(SystemExit, match="mixed/unknown"):
        run(root, ledger_path, manifest_path, group.owner, apply=True)
    path.write_text(yaml.safe_dump(card, sort_keys=False))
    row = group.rows[0]
    split = copy.deepcopy(card)
    split.setdefault("schedule", {})[row["axis"]] = row["after"]["axis_values"]
    path.write_text(yaml.safe_dump(split, sort_keys=False))
    with pytest.raises(SystemExit, match="mixed/unknown"):
        run(root, ledger_path, manifest_path, group.owner, apply=True)
    split.setdefault("schedule", {})[row["axis"]] = ["unknown_policy"]
    path.write_text(yaml.safe_dump(split, sort_keys=False))
    with pytest.raises(SystemExit, match="mixed/unknown"):
        run(root, ledger_path, manifest_path, group.owner, apply=True)


def test_tampered_manifest_accounting_fails_before_writes(tmp_path: Path) -> None:
    root = _temp_root(tmp_path)
    ledger_path = root / LEDGER_PATH.relative_to(ROOT)
    manifest_path = root / MANIFEST_PATH.relative_to(ROOT)
    manifest = json.loads(manifest_path.read_text())
    first_path = root / manifest["cards"][0]["path"]
    before = _sha(first_path)
    manifest["accounting"]["L6"]["live_governance"] += 1
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")
    with pytest.raises(SystemExit, match="manifest accounting mismatch: L6"):
        run(root, ledger_path, manifest_path, "L6", apply=True)
    assert _sha(first_path) == before


def test_inventory_snapshot_is_machine_classified() -> None:
    inventory = json.loads((FIX / "pre_migration_inventory.json").read_text())
    assert all({"record_kind", "type", "sha256", "bytes"} <= set(row) for row in inventory["data_snapshot"])
    assert inventory["snapshot_counts"] == {"dashboard": 27, "product": 59, "substance": 253, "other": 3}
