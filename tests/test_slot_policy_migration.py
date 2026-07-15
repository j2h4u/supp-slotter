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
NEUTRAL_IDS = {
    "sub_reiybxa1p9",
    "sub_2wbcgb78qg",
    "sub_j92h8kgjru",
    "sub_zhz9m31edv",
    "sub_fmuptat7pw",
    "sub_prx6ddszzi",
    "sub_7emxvn1qat",
    "sub_8noiw2mhhb",
    "sub_dznuinvc2n",
    "sub_2preozf0up",
    "sub_9c0908e7f7",
    "sub_5j1kg3bmgk",
    "sub_ud7grsqvtr",
    "sub_dopjesesge",
    "sub_giy6ioeiyv",
    "sub_vkp4f3tqf0",
    "sub_8wi86qpvwi",
    "sub_mzmh95u6ak",
    "sub_zqfp9n314s",
    "sub_ug92bkq5dh",
    "sub_7ozks6pos5",
    "sub_hpqw0esbgo",
    "sub_knwnyl1a9i",
    "sub_2se61pa12m",
    "sub_2gjf5yx7cz",
    "sub_4j9fttkil9",
    "sub_a3ec9f9c52",
    "sub_j9dhho47sz",
    "sub_7ehuhfcly5",
}
NEUTRAL_ROWS = {
    ("sub_reiybxa1p9", "data/substances/african_mango_whole_seed_powder__sub_reiybxa1p9.yaml", "L7"),
    ("sub_2wbcgb78qg", "data/substances/aloe_vera__sub_2wbcgb78qg.yaml", "L7"),
    ("sub_j92h8kgjru", "data/substances/beetroot_extract__sub_j92h8kgjru.yaml", "L6"),
    ("sub_zhz9m31edv", "data/substances/beta_hydroxy_beta_methylbutyrate__sub_zhz9m31edv.yaml", "L7"),
    ("sub_fmuptat7pw", "data/substances/betaine_nitrate_no3_t__sub_fmuptat7pw.yaml", "L6"),
    ("sub_prx6ddszzi", "data/substances/black_cohosh_root_rhizome_extract__sub_prx6ddszzi.yaml", "L7"),
    ("sub_7emxvn1qat", "data/substances/caffeine_anhydrous__sub_7emxvn1qat.yaml", "L6"),
    ("sub_8noiw2mhhb", "data/substances/chasteberry_fruit_extract__sub_8noiw2mhhb.yaml", "L7"),
    ("sub_dznuinvc2n", "data/substances/cimetidine__sub_dznuinvc2n.yaml", "L7"),
    ("sub_2preozf0up", "data/substances/collagen_peptides_hydrolyzed__sub_2preozf0up.yaml", "L7"),
    ("sub_9c0908e7f7", "data/substances/creatine_monohydrate__sub_9c0908e7f7.yaml", "L6"),
    ("sub_5j1kg3bmgk", "data/substances/dmae_bitartrate__sub_5j1kg3bmgk.yaml", "L6"),
    ("sub_ud7grsqvtr", "data/substances/echinacea_extract__sub_ud7grsqvtr.yaml", "L7"),
    ("sub_dopjesesge", "data/substances/elderberry_extract__sub_dopjesesge.yaml", "L7"),
    ("sub_giy6ioeiyv", "data/substances/fiber_seed_blend__sub_giy6ioeiyv.yaml", "L7"),
    ("sub_vkp4f3tqf0", "data/substances/l_theanine__sub_vkp4f3tqf0.yaml", "L6"),
    ("sub_8wi86qpvwi", "data/substances/lavender_flower__sub_8wi86qpvwi.yaml", "L6"),
    ("sub_mzmh95u6ak", "data/substances/mastic_gum__sub_mzmh95u6ak.yaml", "L8"),
    ("sub_zqfp9n314s", "data/substances/methotrexate__sub_zqfp9n314s.yaml", "L8"),
    ("sub_ug92bkq5dh", "data/substances/midazolam__sub_ug92bkq5dh.yaml", "L8"),
    ("sub_7ozks6pos5", "data/substances/nicotinamide_mononucleotide__sub_7ozks6pos5.yaml", "L8"),
    ("sub_hpqw0esbgo", "data/substances/peppermint_oil__sub_hpqw0esbgo.yaml", "L8"),
    ("sub_knwnyl1a9i", "data/substances/probiotic_blend__sub_knwnyl1a9i.yaml", "L8"),
    ("sub_2se61pa12m", "data/substances/ranitidine__sub_2se61pa12m.yaml", "L8"),
    ("sub_2gjf5yx7cz", "data/substances/saccharomyces_boulardii__sub_2gjf5yx7cz.yaml", "L8"),
    ("sub_4j9fttkil9", "data/substances/sodium__sub_4j9fttkil9.yaml", "L8"),
    ("sub_a3ec9f9c52", "data/substances/tadalafil__sub_a3ec9f9c52.yaml", "L8"),
    ("sub_j9dhho47sz", "data/substances/theobromine__sub_j9dhho47sz.yaml", "L6"),
    ("sub_7ehuhfcly5", "data/substances/whey_protein__sub_7ehuhfcly5.yaml", "L8"),
}


def _load_yaml(path: Path) -> dict[str, Any]:
    return cast(dict[str, Any], yaml.safe_load(path.read_text()))


def _wire() -> tuple[dict[str, Any], dict[str, Any]]:
    return _load_yaml(LEDGER_PATH), cast(dict[str, Any], json.loads(MANIFEST_PATH.read_text()))


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _fold_pre(card: dict[str, Any], group: CardGroup) -> dict[str, Any]:
    result = copy.deepcopy(card)
    schedule = result.setdefault("schedule", {})
    governance = result.setdefault("schedule_governance", {})
    for row in group.rows:
        axis = row["axis"]
        schedule[axis] = copy.deepcopy(row["before"]["axis_values"])
        for key in [key for key in governance if str(key).startswith(f"{axis}:")]:
            del governance[key]
        governance.update(copy.deepcopy(row["before"]["governance_entries"]))
    if not governance:
        result.pop("schedule_governance", None)
    return result


def _non_schedule_sha(card: dict[str, Any]) -> str:
    value = copy.deepcopy(card)
    schedule = dict(value.get("schedule") or {})
    for axis in ("intake", "timing", "activity"):
        schedule.pop(axis, None)
    if schedule:
        value["schedule"] = schedule
    else:
        value.pop("schedule", None)
    value.pop("schedule_governance", None)
    normalized = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    return hashlib.sha256(normalized).hexdigest()


def _temp_root(tmp_path: Path) -> Path:
    ledger, manifest = _wire()
    _, groups = validate_wire(ledger, manifest)
    groups_by_path = {group.path: group for group in groups}
    for source in (LEDGER_PATH, MANIFEST_PATH):
        target = tmp_path / source.relative_to(ROOT)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
    for entry in manifest["cards"]:
        source = ROOT / entry["path"]
        target = tmp_path / entry["path"]
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(yaml.safe_dump(_fold_pre(_load_yaml(source), groups_by_path[entry["path"]]), sort_keys=False))
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
        "REMOVE_ASSIGNMENT_AND_GOVERNANCE": 79,
    }
    live = [value for row in rows for value in row["after"]["governance_entries"].values()]
    assert len(live) == 171
    assert Counter(value["status"] for value in live) == {"review_pending": 143, "approved": 28}
    assert Counter(value["enforcement_cap"] for value in live) == {"preference": 167, "advisory": 4}
    assert len(groups) == 228
    assert Counter(len(group.rows) for group in groups) == {1: 206, 2: 22}


def test_exact_neutral_retirement_set_and_cascade_coverage() -> None:
    rows = _wire()[0]["rows"]
    neutral = [row for row in rows if row["before"]["axis_values"] == ["food_neutral"]]
    assert {row["card_id"] for row in neutral} == NEUTRAL_IDS
    assert {(row["card_id"], row["path"], row["owner"]) for row in neutral} == NEUTRAL_ROWS
    assert len(neutral) == 29
    for row in neutral:
        assert row["action"] == "REMOVE_ASSIGNMENT_AND_GOVERNANCE"
        assert row["row_id"] == f"{row['card_id']}|intake|food_neutral"
        assert row["axis"] == "intake"
        assert row["before"] == {"axis_values": ["food_neutral"], "governance_entries": {}}
        assert row["after"] == {"axis_values": [], "governance_entries": {}}
        assert row["decision"]["reason_code"] == "REDUNDANT_ZERO_EFFECT_ASSIGNMENT"
        assert row["decision"]["retirement_reason"] == (
            "Zero-effect food-neutral marker removed; absence is the canonical no-food-driver state."
        )
        assert row["decision"]["source_refs"] == [
            "baseline-main:data/traits/schedule.yaml#intake.food_neutral",
            "executable-plan-v3-amendment-5:2",
        ]
    relation_endpoints = {"sub_7ehuhfcly5", "sub_9c0908e7f7", "sub_zqfp9n314s", "sub_ug92bkq5dh"}
    product_components = {
        "sub_reiybxa1p9",
        "sub_fmuptat7pw",
        "sub_7emxvn1qat",
        "sub_9c0908e7f7",
        "sub_5j1kg3bmgk",
        "sub_giy6ioeiyv",
        "sub_vkp4f3tqf0",
        "sub_8wi86qpvwi",
        "sub_knwnyl1a9i",
        "sub_4j9fttkil9",
        "sub_a3ec9f9c52",
        "sub_j9dhho47sz",
    }
    assert relation_endpoints <= NEUTRAL_IDS
    assert product_components <= NEUTRAL_IDS
    assert all("prd_83dffd67bf" not in row["row_id"] for row in rows)


def test_complete_pre_distribution() -> None:
    intake = [row["before"]["axis_values"][0] for row in _wire()[0]["rows"] if row["axis"] == "intake"]
    assert Counter(intake) == {
        "empty_preferred": 30,
        "fat_meal_required": 19,
        "food_neutral": 29,
        "food_preferred": 134,
        "food_required": 12,
    }


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


def test_real_manifest_cards_are_one_coherent_global_phase() -> None:
    inventory = json.loads((FIX / "pre_migration_inventory.json").read_text())
    hashes = {row["path"]: row["sha256"] for row in inventory["data_snapshot"]}
    ledger, manifest = _wire()
    _, groups = validate_wire(ledger, manifest)
    states = {group.path: classify_card(_load_yaml(ROOT / group.path), group)[0] for group in groups}
    assert set(states.values()) in ({"PRE"}, {"POST"})
    if set(states.values()) == {"PRE"}:
        assert all(_sha(ROOT / group.path) == hashes[group.path] for group in groups)
    else:
        invariants = inventory["card_non_schedule_sha256"]
        assert all(_non_schedule_sha(_load_yaml(ROOT / group.path)) == invariants[group.path] for group in groups)


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


def test_unified_apply_reaches_all_228_post_and_is_byte_idempotent(tmp_path: Path) -> None:
    root = _temp_root(tmp_path)
    ledger = root / LEDGER_PATH.relative_to(ROOT)
    manifest = root / MANIFEST_PATH.relative_to(ROOT)
    assert run(root, ledger, manifest, None, apply=True) == 0
    cards = [root / entry["path"] for entry in json.loads(manifest.read_text())["cards"]]
    assert len(cards) == 228
    hashes = {path: _sha(path) for path in cards}
    assert run(root, ledger, manifest, None, apply=False) == 0
    assert run(root, ledger, manifest, None, apply=True) == 0
    assert hashes == {path: _sha(path) for path in cards}


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


def test_tampered_manifest_structure_fails_before_reads_or_writes(tmp_path: Path) -> None:
    root = _temp_root(tmp_path)
    ledger_path = root / LEDGER_PATH.relative_to(ROOT)
    manifest_path = root / MANIFEST_PATH.relative_to(ROOT)
    original = cast(dict[str, Any], json.loads(manifest_path.read_text()))
    first_path = root / original["cards"][0]["path"]
    before = _sha(first_path)

    variants: list[dict[str, Any]] = []
    bogus_axes = copy.deepcopy(original)
    bogus_axes["cards"][0]["axes"] = ["activity"]
    variants.append(bogus_axes)
    bogus_row = copy.deepcopy(original)
    bogus_row["cards"][0]["row_ids"][0] = "bogus|intake|food_neutral"
    variants.append(bogus_row)
    duplicate_card = copy.deepcopy(original)
    duplicate_card["cards"].append(copy.deepcopy(duplicate_card["cards"][0]))
    variants.append(duplicate_card)
    duplicate_path = copy.deepcopy(original)
    duplicate_path["cards"][-1]["path"] = duplicate_path["cards"][0]["path"]
    variants.append(duplicate_path)
    duplicate_card_id = copy.deepcopy(original)
    duplicate_card_id["cards"][-1]["card_id"] = duplicate_card_id["cards"][0]["card_id"]
    variants.append(duplicate_card_id)
    missing_row = copy.deepcopy(original)
    missing_row["cards"][0]["row_ids"].pop()
    variants.append(missing_row)
    duplicate_row = copy.deepcopy(original)
    duplicate_row["cards"][1]["row_ids"][0] = duplicate_row["cards"][0]["row_ids"][0]
    variants.append(duplicate_row)

    for manifest in variants:
        manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")
        with pytest.raises(SystemExit, match="manifest"):
            run(root, ledger_path, manifest_path, "L6", apply=True)
        assert _sha(first_path) == before


def test_tampered_neutral_decision_fails_before_writes(tmp_path: Path) -> None:
    root = _temp_root(tmp_path)
    ledger_path = root / LEDGER_PATH.relative_to(ROOT)
    manifest_path = root / MANIFEST_PATH.relative_to(ROOT)
    original = _load_yaml(ledger_path)
    first_path = root / json.loads(manifest_path.read_text())["cards"][0]["path"]
    before = _sha(first_path)
    neutral_index = next(
        index for index, row in enumerate(original["rows"]) if row["before"]["axis_values"] == ["food_neutral"]
    )

    variants: list[dict[str, Any]] = []
    for field in ("disposition", "status", "enforcement_cap"):
        missing = copy.deepcopy(original)
        missing["rows"][neutral_index]["decision"].pop(field)
        variants.append(missing)
        wrong = copy.deepcopy(original)
        wrong["rows"][neutral_index]["decision"][field] = "approved"
        variants.append(wrong)
    extra = copy.deepcopy(original)
    extra["rows"][neutral_index]["decision"]["unexpected"] = "forbidden"
    variants.append(extra)

    for ledger in variants:
        ledger_path.write_text(yaml.safe_dump(ledger, sort_keys=False))
        with pytest.raises(SystemExit, match="neutral retirement"):
            run(root, ledger_path, manifest_path, "L7", apply=True)
        assert _sha(first_path) == before


def test_inventory_snapshot_is_machine_classified() -> None:
    inventory = json.loads((FIX / "pre_migration_inventory.json").read_text())
    assert all({"record_kind", "type", "sha256", "bytes"} <= set(row) for row in inventory["data_snapshot"])
    assert inventory["snapshot_counts"] == {"dashboard": 27, "product": 59, "substance": 253, "other": 3}


def test_final_manifest_accounting_and_deep_preservation(tmp_path: Path) -> None:
    """The complete wire accounts for every transition without touching payload data."""
    ledger, manifest = _wire()
    rows, groups = validate_wire(ledger, manifest)
    assert len(manifest["cards"]) == 228
    assert len(rows) == 250
    assert Counter(row["action"] for row in rows) == {
        "KEEP_ASSIGNMENT_ADD_GOVERNANCE": 145,
        "REPLACE_ASSIGNMENT_ADD_GOVERNANCE": 26,
        "REMOVE_ASSIGNMENT_AND_GOVERNANCE": 79,
    }
    assert len([entry for row in rows for entry in row["after"]["governance_entries"].values()]) == 171
    assert {group.owner for group in groups} == {"L6", "L7", "L8"}
    assert Counter(group.owner for group in groups) == {"L6": 26, "L7": 97, "L8": 105}
    assert Counter(row["decision"]["disposition"] for row in rows) == {"active": 171, "retired": 79}

    # Apply the exact worker wire in isolation and prove card payloads and graph
    # records are preserved.  This also exercises product/substance cascade edges.
    root = _temp_root(tmp_path)
    # The worker fixture intentionally contains only manifest-owned cards;
    # populate immutable product/dashboard records for the deep snapshot gate.
    for row in json.loads((FIX / "pre_migration_inventory.json").read_text())["data_snapshot"]:
        source = ROOT / row["path"]
        target = root / row["path"]
        if source.exists() and not target.exists():
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, target)
    for name in ("relations.yaml", "stacks.yaml", "pillboxes.yaml"):
        shutil.copyfile(ROOT / "data" / name, root / "data" / name)
    ledger_path = root / LEDGER_PATH.relative_to(ROOT)
    manifest_path = root / MANIFEST_PATH.relative_to(ROOT)
    assert run(root, ledger_path, manifest_path, None, apply=True) == 0
    inventory = json.loads((FIX / "pre_migration_inventory.json").read_text())
    assert inventory["card_counts"] == {"substances": 253, "products": 59, "dashboards": 27}
    assert {p.relative_to(root).as_posix() for p in (root / "data/substances").glob("*.yaml")} == {
        row["path"] for row in inventory["data_snapshot"] if row["record_kind"] == "substance"
    }
    assert {p.relative_to(root).as_posix() for p in (root / "data/products").glob("*.yaml")} == {
        row["path"] for row in inventory["data_snapshot"] if row["record_kind"] == "product"
    }
    for row in inventory["data_snapshot"]:
        if row["record_kind"] in {"product", "dashboard"}:
            assert _sha(root / row["path"]) == row["sha256"]
    assert _sha(root / "data/relations.yaml") == _sha(ROOT / "data/relations.yaml")
    assert _sha(root / "data/stacks.yaml") == _sha(ROOT / "data/stacks.yaml")
    assert _sha(root / "data/pillboxes.yaml") == _sha(ROOT / "data/pillboxes.yaml")
    assert all(
        _non_schedule_sha(_load_yaml(root / entry["path"])) == inventory["card_non_schedule_sha256"][entry["path"]]
        for entry in manifest["cards"]
    )
