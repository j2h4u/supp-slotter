# pyright: reportAny=false
import json
from pathlib import Path

import yaml

ROOT = Path(__file__).parents[1]
FIX = ROOT / "tests/fixtures/slot_policy"


def test_wave0_ledger_counts_and_bijection():
    ledger = yaml.safe_load((FIX / "v2_migration_ledger.yaml").read_text())
    rows = ledger["rows"]
    assert sum(r["axis"] == "intake" for r in rows) == 195
    assert sum(r["axis"] in {"timing", "activity"} for r in rows) == 26
    intake = [r for r in rows if r["axis"] == "intake"]
    assert len({(r["card_id"], r["axis"], r["current_policy"]) for r in intake}) == 195


def test_worker_manifest_disjoint_and_accounted():
    manifest = json.loads((FIX / "v2_worker_manifest.json").read_text())["cards"]
    owners = {o: {r["path"] for r in manifest if r["owner"] == o} for o in ("L6", "L7", "L8")}
    assert not (owners["L6"] & owners["L7"])
    assert not (owners["L6"] & owners["L8"])
    assert not (owners["L7"] & owners["L8"])
    assert {k: len(v) for k, v in owners.items()} == {"L6": 26, "L7": 87, "L8": 94}


def test_every_row_has_locked_governance_and_adjudication_buckets():
    rows = yaml.safe_load((FIX / "v2_migration_ledger.yaml").read_text())["rows"]
    required = {"final_status", "enforcement_cap", "scope", "evidence_keys", "owner", "review_by"}
    assert all(required <= set(row) and row["evidence_keys"] for row in rows)
    intake = [r for r in rows if r["axis"] == "intake" and r.get("bucket")]
    ambiguous = [r for r in intake if r.get("adjudication_key")]
    assert len(ambiguous) == 138
    from collections import Counter

    assert Counter(r["bucket"] for r in ambiguous) == {
        "FORM": 88,
        "MINERAL": 35,
        "ENZYME": 4,
        "FAT": 3,
        "WATER_SPACING": 6,
        "EXCEPTION": 2,
    }
    assert sum("adjudication_key" in r for r in rows if r["axis"] == "intake") == 138


def test_inventory_snapshot_is_machine_classified():
    inventory = json.loads((FIX / "pre_migration_inventory.json").read_text())
    assert all({"record_kind", "type", "sha256", "bytes"} <= set(r) for r in inventory["data_snapshot"])
    assert inventory["snapshot_counts"]["substance"] == 253
    assert inventory["snapshot_counts"]["product"] == 59
    assert inventory["snapshot_counts"]["dashboard"] == 27
