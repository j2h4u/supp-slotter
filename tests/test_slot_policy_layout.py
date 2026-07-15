# pyright: reportAny=false, reportExplicitAny=false, reportUnknownArgumentType=false, reportUnknownLambdaType=false, reportUnknownMemberType=false
"""Reproducible, non-causal provenance for the slot-policy layout delta."""

from __future__ import annotations

import copy
import gc
import hashlib
import io
import json
import os
import shutil
import subprocess
import sys
import tarfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

import pytest
import yaml
from planner.engine import cmd_plan
from planner.engine._plan_active_index import ActiveIndexInput, build_active_index
from planner.engine._plan_inputs import load_plan_inputs
from planner.engine._scheduling import compute_slot_score
from planner.paths import Paths
from planner.query_model import build_stack_read_model, dashboards_for_read_model
from planner.query_model.surreal import SurrealLoadContext

ROOT = Path(__file__).parents[1]
FIX = ROOT / "tests/fixtures/slot_policy"
PROVENANCE = FIX / "v2_layout_provenance.yaml"
LEDGER = FIX / "v2_migration_ledger.yaml"
MANIFEST = FIX / "v2_worker_manifest.json"
RUNTIME_PATHS = (
    "planner/contracts.py",
    "planner/cards/substance.py",
    "planner/cards/product.py",
    "planner/engine/_scheduling.py",
    "planner/engine/_plan_types.py",
    "planner/engine/_plan_active_index.py",
    "planner/engine/_plan_feasibility.py",
    "planner/engine/_plan_output.py",
    "planner/engine/_plan_search.py",
    "planner/engine/plan.py",
    "planner/schedule_types.py",
)
PRE_SOURCE = {
    "requested_ref": "2580032^1",
    "commit": "da877e4e49e2fe66245f0242a272e962b5895c20",
    "tree": "6ac8e5127902730e970b4937d991538dc1b029f9",
    "inventory_blob": "3d64903290d7b1669dd0edc211c4cd9762b462af",
    "historical_source_blobs": {
        "planner/engine/_scheduling.py": "0b26653da66941d9df2674cdaefb865df5538d3b",
        "planner/engine/_plan_feasibility.py": "4dd7202e26b952c26fa5b1fbd5e153443f5d3ccb",
        "planner/engine/_plan_search.py": "06fa9904a8a7226d18b069a0602438fbcd04e0ca",
    },
    "legacy_policy_commit": "a3202f381933ccbc728ec20bfb3cfdc8b716a9f2",
    "legacy_policy_path": "data/traits/schedule.yaml",
    "legacy_policy_blob": "3c1dce6786286ce2edbdfff0a11d583f58d9b1cd",
    "legacy_policy_sha256": "051480ee7b0e37395dc7d69876a6f1ada75bb9750e2f88dbf534dbb7e7af999f",
    "archived_card_blobs_sha256": "01b38a38d34ccc3453bd482ccba6c9e561d676d5c6c5cd559b1d4f64b9b287ad",
    "pre_axis_snapshot_sha256": "50bb1dc7b7662c95b11f1bf881cf7a007fe8779c0fbd82b2bc40a00d26a96d0c",
    "daily_loads": [2, 4, 4, 2],
}
LEGACY_LEVEL_SCORES = {"prefer_strong": 4, "prefer": 2, "avoid": -2, "avoid_strong": -4}
LEGACY_SECONDARY_TRAIT_WEIGHT = 0.5


def _map(value: object) -> dict[str, object]:
    assert isinstance(value, dict)
    assert all(isinstance(key, str) for key in value)
    return cast(dict[str, object], value)


def _yaml(path: Path) -> dict[str, object]:
    return _map(cast(object, yaml.safe_load(path.read_text())))


def _canonical_sha(value: object) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(payload).hexdigest()


def _file_sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _assignment_id(source_kind: str, card_id: str, axis: str, policy: str) -> str:
    slug = policy.split(":", 1)[1] if ":" in policy else policy
    return f"{source_kind}:{card_id}:{axis}:{slug}"


def _name_index(root: Path) -> dict[str, str]:
    result: dict[str, str] = {}
    for path in sorted((root / "data/products").glob("*.yaml")):
        card = _yaml(path)
        brand, name = card.get("brand"), str(card["name"])
        result[f"{brand} - {name}" if brand and brand != "unknown" else name] = str(card["id"])
    return result


def _placement(root: Path) -> list[dict[str, str]]:
    names, schedule = _name_index(root), _yaml(root / "schedule.yaml")
    rows: list[dict[str, str]] = []
    for pillbox, raw_pillbox in _map(schedule["pillboxes"]).items():
        for slot, raw_slot in _map(_map(raw_pillbox)["slots"]).items():
            for product in cast(list[object], _map(raw_slot).get("products", [])):
                rows.append({"product_id": names[str(product)], "pillbox": pillbox, "slot": slot})
    return sorted(rows, key=lambda row: row["product_id"])


def _load_runtime(root: Path) -> tuple[Any, Any]:
    paths, errors = Paths.from_root(root), []
    inputs = load_plan_inputs(paths)
    assert inputs is not None
    read_model = build_stack_read_model(
        inputs.substances,
        inputs.global_relations,
        inputs.products,
        context=SurrealLoadContext(
            policies=inputs.policies,
            stacks_data=None,
            pillbox_stack_names=None,
            dashboards=dashboards_for_read_model(paths),
            scheduling_constraints=inputs.scheduling_constraints,
        ),
    )
    active = build_active_index(
        inputs.stack_entries,
        ActiveIndexInput(
            inputs.products, inputs.substances, inputs.policies, read_model, inputs.scheduling_constraints
        ),
        inputs.slots,
        errors,
    )
    assert active is not None, errors
    return inputs, active


def _ledger_rows() -> list[dict[str, object]]:
    raw = _yaml(LEDGER)["rows"]
    assert isinstance(raw, list)
    return [_map(row) for row in raw]


def _ledger_record(row: dict[str, object]) -> dict[str, object]:
    axis, card = str(row["axis"]), str(row["card_id"])
    before, after, decision = _map(row["before"]), _map(row["after"]), _map(row["decision"])
    return {
        "row_id": str(row["row_id"]),
        "card_id": card,
        "axis": axis,
        "action": str(row["action"]),
        "reason_code": str(decision["reason_code"]),
        "before_assignment_ids": sorted(
            _assignment_id("substance", card, axis, str(v)) for v in cast(list[object], before["axis_values"])
        ),
        "after_assignment_ids": sorted(
            _assignment_id("substance", card, axis, str(v)) for v in cast(list[object], after["axis_values"])
        ),
    }


def _archived_score(
    traits: set[str],
    sources: dict[str, list[str]],
    slot: dict[str, object],
    policies: dict[str, dict[str, object]],
    weight: float = 1.0,
) -> tuple[int, bool, list[str]]:
    score, blocked, assignment_ids = 0, False, []
    for policy_id in sorted(traits):
        for raw_effect in cast(list[object], policies[policy_id].get("effects", [])):
            effect, match = _map(raw_effect), _map(_map(raw_effect).get("match", {}))
            if ("near" in match and match["near"] != slot.get("near")) or (
                "food" in match and match["food"] != slot.get("food")
            ):
                continue
            score += round(LEGACY_LEVEL_SCORES.get(str(effect.get("level")), 0) * weight)
            blocked = blocked or effect.get("block") is True
            assignment_ids.extend(
                _assignment_id("substance", source, *policy_id.split(":", 1)) for source in sources[policy_id]
            )
    return score, blocked, sorted(set(assignment_ids))


def _archived_products(  # noqa: PLR0914
    archive_root: Path,
    placement: list[dict[str, str]],
    rows: list[dict[str, object]],
    legacy_policy_bytes: bytes,
) -> dict[str, object]:
    raw_policies = _map(cast(object, yaml.safe_load(legacy_policy_bytes)))
    policies = {
        f"{axis}:{slug}": _map(policy)
        for axis, axis_policies in raw_policies.items()
        for slug, policy in _map(axis_policies).items()
    }
    by_card: dict[str, list[dict[str, object]]] = {}
    for row in rows:
        by_card.setdefault(str(row["card_id"]), []).append(row)
    product_cards = {
        str(card["id"]): card
        for path in sorted((archive_root / "data/products").glob("*.yaml"))
        if (card := _yaml(path))
    }
    stacks = _yaml(archive_root / "data/stacks.yaml")
    item_stacks = {
        str(product_id): stack
        for stack, product_ids in stacks.items()
        if stack != "inactive"
        for product_id in cast(list[object], product_ids)
    }
    slots = [
        (pillbox, slot_id, _map(slot))
        for pillbox, raw_pillbox in _yaml(archive_root / "data/pillboxes.yaml").items()
        for slot_id, slot in _map(_map(raw_pillbox)["slots"]).items()
    ]
    products: dict[str, object] = {}
    for product_id in (row["product_id"] for row in placement):
        product = product_cards[product_id]
        raw_components = [_map(value) for value in cast(list[object], product["components"])]
        components = [str(component["substance"]) for component in raw_components]
        effective: set[str] = set()
        primary: set[str] = set()
        sources: dict[str, list[str]] = {}
        has_primary = any(component.get("primary") is True for component in raw_components)
        for component in raw_components:
            substance = str(component["substance"])
            for row in by_card.get(substance, []):
                axis = str(row["axis"])
                for slug in cast(list[object], _map(row["before"])["axis_values"]):
                    policy = f"{axis}:{slug}"
                    effective.add(policy)
                    sources.setdefault(policy, []).append(substance)
                    if not has_primary or component.get("primary") is True:
                        primary.add(policy)
        secondary = effective - primary
        score_traits = primary or effective
        assignments = [
            {
                "assignment_id": _assignment_id(
                    "substance", str(row["card_id"]), str(row["axis"]), f"{row['axis']}:{slug}"
                ),
                "source_kind": "substance",
                "source_card_id": str(row["card_id"]),
                "axis": str(row["axis"]),
                "policy_id": f"{row['axis']}:{slug}",
                "lifecycle": "legacy",
                "declared_cap": "block",
                "effective_cap": "block",
                "action": "active",
                "scope": [],
            }
            for component in components
            for row in by_card.get(component, [])
            for slug in cast(list[object], _map(row["before"])["axis_values"])
        ]
        slot_scores = []
        for pillbox, slot_id, slot in slots:
            if pillbox != item_stacks[product_id]:
                score, blocked, ids, diagnostics = 0, True, [], ["STACK_MISMATCH"]
            else:
                score, blocked, ids = _archived_score(score_traits, sources, slot, policies)
                if secondary:
                    extra, _, extra_ids = _archived_score(
                        secondary, sources, slot, policies, LEGACY_SECONDARY_TRAIT_WEIGHT
                    )
                    score += extra
                    ids = sorted(set(ids + extra_ids))
                diagnostics = []
            slot_scores.append({
                "pillbox": pillbox,
                "slot": slot_id,
                "score": score,
                "blocked": blocked,
                "assignment_ids": ids,
                "diagnostics": diagnostics,
            })
        local = sorted(
            (row for component in components for row in by_card.get(component, [])),
            key=lambda row: (str(row["card_id"]), str(row["axis"]), str(row["row_id"])),
        )
        products[product_id] = {
            "components": components,
            "ledger_rows": [_ledger_record(row) for row in local],
            "assignments": sorted(assignments, key=lambda row: row["assignment_id"]),
            "slot_scores": slot_scores,
        }
    assert set(products) == {row["product_id"] for row in placement}
    return products


def _post_products(inputs: Any, active: Any) -> dict[str, object]:
    by_card: dict[str, list[dict[str, object]]] = {}
    for row in _ledger_rows():
        by_card.setdefault(str(row["card_id"]), []).append(row)
    result = {}
    for product_id in active.item_products:
        product, projection = inputs.products[product_id], active.governed_projection_by_item[product_id]
        components = [component.substance for component in product.components]
        assignments = [
            {
                "assignment_id": row.assignment_id,
                "source_kind": row.source_kind,
                "source_card_id": row.source_card_id,
                "axis": row.axis,
                "policy_id": row.policy_id,
                "lifecycle": row.governance.status,
                "declared_cap": row.governance.enforcement_cap,
                "effective_cap": row.effective_cap,
                "action": row.action,
                "scope": [list(pair) for pair in row.governance.scope],
            }
            for row in sorted(projection.assignments, key=lambda value: value.assignment_id)
        ]
        scores = []
        for slot in inputs.slots.values():
            if slot.stack != active.item_stacks[product_id]:
                score, blocked, ids, diagnostics = 0, True, [], ["STACK_MISMATCH"]
            else:
                trace = compute_slot_score(projection, slot, inputs.policies)
                score, blocked = trace.score, trace.blocked
                ids = sorted({assignment for effect in trace.effects for assignment in effect.assignment_ids})
                diagnostics = sorted({diagnostic.code for diagnostic in trace.diagnostics})
            scores.append({
                "pillbox": slot.pillbox,
                "slot": slot.slot_id,
                "score": score,
                "blocked": blocked,
                "assignment_ids": ids,
                "diagnostics": diagnostics,
            })
        local = sorted(
            (row for component in components for row in by_card.get(component, [])),
            key=lambda row: (str(row["card_id"]), str(row["axis"]), str(row["row_id"])),
        )
        result[product_id] = {
            "components": components,
            "ledger_rows": [_ledger_record(row) for row in local],
            "assignments": assignments,
            "slot_scores": scores,
        }
    return result


@dataclass(frozen=True, slots=True)
class RecomputedPostState:
    placement: list[dict[str, str]]
    products: dict[str, object]
    source: dict[str, str]


@dataclass(frozen=True, slots=True)
class RecomputedPreState:
    placement: list[dict[str, str]]
    products: dict[str, object]
    source: dict[str, object]
    loads: list[int]
    row_states: dict[str, int]
    card_states: dict[str, int]


@dataclass(frozen=True, slots=True)
class ProtectedHashes:
    invariants: dict[str, object]
    root_schedule_before: tuple[int, int, str] | None
    root_schedule_after: tuple[int, int, str] | None


@dataclass(frozen=True, slots=True)
class RecomputedTruth:
    pre: RecomputedPreState
    run_1: RecomputedPostState
    run_2: RecomputedPostState
    protected: ProtectedHashes


def _tree_sha(root: Path) -> str:
    paths = sorted(
        (path for path in root.rglob("*") if path.is_file()),
        key=lambda path: path.relative_to(root).as_posix().encode("utf-8"),
    )
    pairs = [[path.relative_to(root).as_posix(), _file_sha(path)] for path in paths]
    return _canonical_sha(pairs)


def _runtime_source(data_root: Path, placement: list[dict[str, str]]) -> dict[str, str]:
    runtime = [[path, _file_sha(ROOT / path)] for path in sorted(RUNTIME_PATHS, key=lambda value: value.encode())]
    return {
        "runtime_inputs_sha256": _canonical_sha(runtime),
        "ontology_inputs_sha256": _tree_sha(ROOT / "ontology"),
        "data_inputs_sha256": _tree_sha(data_root / "data"),
        "ledger_sha256": _file_sha(LEDGER),
        "placement_sha256": _canonical_sha(placement),
    }


def _run_current(isolated_root: Path) -> RecomputedPostState:
    shutil.copytree(ROOT / "data", isolated_root / "data")
    result = cmd_plan(data_root=isolated_root)
    assert result.exit_code == 0, result.errors
    assert result.schedule_written
    placement = _placement(isolated_root)
    inputs, active = _load_runtime(isolated_root)
    products = _post_products(inputs, active)
    source = _runtime_source(isolated_root, placement)
    del active, inputs
    gc.collect()
    return RecomputedPostState(placement=placement, products=products, source=source)


@dataclass(frozen=True, slots=True)
class ArchivedVerification:
    rows: list[dict[str, object]]
    legacy_policy_bytes: bytes
    row_states: dict[str, int]
    card_states: dict[str, int]


def _git_output(*args: str, text: bool = True) -> str | bytes:
    result = subprocess.run(
        ["git", *args],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=text,
    )
    return result.stdout


def _git_oid(spec: str) -> str:
    return cast(str, _git_output("rev-parse", spec)).strip()


def _verify_and_export_pre(archive_root: Path) -> bytes:
    assert not archive_root.exists()
    assert _git_oid(str(PRE_SOURCE["requested_ref"])) == PRE_SOURCE["commit"]
    assert _git_oid(f"{PRE_SOURCE['requested_ref']}^{{tree}}") == PRE_SOURCE["tree"]
    assert (
        _git_oid(f"{PRE_SOURCE['commit']}:tests/fixtures/slot_policy/pre_migration_inventory.json")
        == PRE_SOURCE["inventory_blob"]
    )
    for path, blob in cast(dict[str, str], PRE_SOURCE["historical_source_blobs"]).items():
        assert _git_oid(f"{PRE_SOURCE['commit']}:{path}") == blob
    legacy_spec = f"{PRE_SOURCE['legacy_policy_commit']}:{PRE_SOURCE['legacy_policy_path']}"
    assert _git_oid(legacy_spec) == PRE_SOURCE["legacy_policy_blob"]
    legacy_policy_bytes = cast(bytes, _git_output("show", legacy_spec, text=False))
    assert hashlib.sha256(legacy_policy_bytes).hexdigest() == PRE_SOURCE["legacy_policy_sha256"]
    archive_bytes = cast(bytes, _git_output("archive", str(PRE_SOURCE["commit"]), text=False))
    archive_root.mkdir()
    with tarfile.open(fileobj=io.BytesIO(archive_bytes)) as archive:
        archive.extractall(archive_root, filter="data")
    return legacy_policy_bytes


def _axis_state(
    axis_values: object,
    governance_entries: object,
    before: dict[str, object],
    after: dict[str, object],
) -> str:
    is_pre = axis_values == before["axis_values"] and governance_entries == before["governance_entries"]
    is_post = axis_values == after["axis_values"] and governance_entries == after["governance_entries"]
    if is_pre and is_post:
        return "MIXED"
    if is_pre:
        return "PRE"
    if is_post:
        return "POST"
    return "UNKNOWN"


def _verify_archived_cards(archive_root: Path, legacy_policy_bytes: bytes) -> ArchivedVerification:  # noqa: PLR0914
    inventory = json.loads((archive_root / "tests/fixtures/slot_policy/pre_migration_inventory.json").read_text())
    ledger = _yaml(archive_root / "tests/fixtures/slot_policy/v2_migration_ledger.yaml")
    for entry in cast(list[dict[str, object]], inventory["data_snapshot"]):
        payload = (archive_root / str(entry["path"])).read_bytes()
        assert len(payload) == entry["bytes"]
        assert hashlib.sha256(payload).hexdigest() == entry["sha256"]
    assignments = cast(list[dict[str, object]], inventory["assignments"])
    ledger_rows = cast(list[dict[str, object]], ledger["rows"])
    assert len(assignments) == len(ledger_rows) == 250
    ledger_by_id = {str(row["row_id"]): row for row in ledger_rows}
    assert len(ledger_by_id) == 250
    row_states: dict[str, int] = dict.fromkeys(("PRE", "POST", "MIXED", "UNKNOWN"), 0)
    states_by_path: dict[str, list[str]] = {}
    snapshot: list[list[object]] = []
    for assignment in assignments:
        row_id, card_id, path, axis = (
            str(assignment["row_id"]),
            str(assignment["card_id"]),
            str(assignment["path"]),
            str(assignment["axis"]),
        )
        ledger_row = ledger_by_id[row_id]
        assert {key: assignment[key] for key in ("row_id", "card_id", "path", "axis", "before")} == {
            key: ledger_row[key] for key in ("row_id", "card_id", "path", "axis", "before")
        }
        card = _yaml(archive_root / path)
        assert card["id"] == card_id
        schedule = _map(card.get("schedule", {}))
        axis_values = list(cast(list[object], schedule.get(axis, [])))
        governance_entries = card.get("schedule_governance", {})
        before, after = _map(ledger_row["before"]), _map(ledger_row["after"])
        state = _axis_state(axis_values, governance_entries, before, after)
        row_states[state] += 1
        states_by_path.setdefault(path, []).append(state)
        snapshot.append([row_id, card_id, path, axis, axis_values, governance_entries])
    snapshot.sort(key=lambda row: tuple(str(value) for value in row[:4]))
    assert _canonical_sha(snapshot) == PRE_SOURCE["pre_axis_snapshot_sha256"]
    assert row_states == {"PRE": 250, "POST": 0, "MIXED": 0, "UNKNOWN": 0}
    assert len(states_by_path) == 228
    card_states: dict[str, int] = dict.fromkeys(("PRE", "POST", "MIXED", "UNKNOWN"), 0)
    for states in states_by_path.values():
        unique_states = set(states)
        state = (
            "PRE"
            if unique_states == {"PRE"}
            else "POST"
            if unique_states == {"POST"}
            else "UNKNOWN"
            if "UNKNOWN" in unique_states
            else "MIXED"
        )
        card_states[state] += 1
    assert card_states == {"PRE": 228, "POST": 0, "MIXED": 0, "UNKNOWN": 0}
    blob_pairs = [
        [path, _git_oid(f"{PRE_SOURCE['commit']}:{path}")]
        for path in sorted(states_by_path, key=lambda value: value.encode("utf-8"))
    ]
    assert _canonical_sha(blob_pairs) == PRE_SOURCE["archived_card_blobs_sha256"]
    return ArchivedVerification(ledger_rows, legacy_policy_bytes, row_states, card_states)


def _run_archived_planner(archive_root: Path) -> tuple[list[dict[str, str]], list[int]]:
    runner = """
import json
import planner
from pathlib import Path
from planner.engine import cmd_plan
root = Path.cwd().resolve()
assert Path(planner.__file__).resolve().is_relative_to(root)
result = cmd_plan(data_root=root)
assert result.exit_code == 0, result.errors
assert result.schedule_written
print('ARCHIVED_RESULT=' + json.dumps(result.slot_loads, sort_keys=True))
"""
    environment = dict(os.environ)
    environment["PYTHONPATH"] = str(archive_root)
    result = subprocess.run(
        [sys.executable, "-c", runner],
        cwd=archive_root,
        env=environment,
        check=True,
        capture_output=True,
        text=True,
    )
    assert any(line.startswith("ARCHIVED_RESULT=") for line in result.stdout.splitlines())
    placement = _placement(archive_root)
    loads = [
        sum(1 for row in placement if row["slot"] == slot)
        for slot in ("morning_empty", "morning_food", "day_food", "evening_empty")
    ]
    assert loads == [2, 4, 4, 2]
    return placement, loads


def _recompute_pre(archive_root: Path) -> RecomputedPreState:
    legacy_policy_bytes = _verify_and_export_pre(archive_root)
    verified = _verify_archived_cards(archive_root, legacy_policy_bytes)
    placement, loads = _run_archived_planner(archive_root)
    products = _archived_products(archive_root, placement, verified.rows, legacy_policy_bytes)
    source = {**PRE_SOURCE, "historical_placement_sha256": _canonical_sha(placement)}
    return RecomputedPreState(placement, products, source, loads, verified.row_states, verified.card_states)


def _protected_hashes(
    root: Path,
    active: Any,
    inputs: Any,
    before: tuple[int, int, str] | None,
) -> ProtectedHashes:
    manifest = json.loads(MANIFEST.read_text())
    assert manifest["format"] == "supp-slotter.slot-policy-worker-manifest/v3"
    paths = [str(row["path"]) for row in manifest["cards"]]
    assert len(paths) == len(set(paths)) == 228
    assert all(_file_sha(ROOT / path) for path in paths)
    components = {component for values in active.active_components.values() for component in values}
    invariants = {
        "active_products": len(active.item_products),
        "unique_substances": len(components),
        "pillboxes": len(inputs.pillboxes),
        "slots": len(inputs.slots),
        "ledger_rows": len(_ledger_rows()),
        "live_assignments": sum(len(card.schedule_governance) for card in inputs.substances.values())
        + sum(len(card.schedule_governance) for card in inputs.products.values()),
        "migrated_paths": len(paths),
        "substance_cards": len(list((root / "data/substances").glob("*.yaml"))),
        "product_cards": len(list((root / "data/products").glob("*.yaml"))),
        "dashboard_cards": len(list((root / "data/dashboards").glob("*.yaml"))),
        "cross_pillbox_movements": 0,
        "root_schedule_untouched": True,
    }
    return ProtectedHashes(invariants, before, _root_schedule_identity())


def _root_schedule_identity() -> tuple[int, int, str] | None:
    path = ROOT / "schedule.yaml"
    return (path.stat().st_ino, path.stat().st_mtime_ns, _file_sha(path)) if path.exists() else None


def _state_rows(value: object) -> list[dict[str, str]]:
    rows = cast(list[dict[str, str]], value)
    assert all(set(row) == {"product_id", "pillbox", "slot"} for row in rows)
    assert rows == sorted(rows, key=lambda row: row["product_id"])
    assert len({row["product_id"] for row in rows}) == len(rows)
    return rows


def _assert_product_schema(products: dict[str, object], *, post: bool) -> None:
    assignment_keys = {
        "assignment_id",
        "source_kind",
        "source_card_id",
        "axis",
        "policy_id",
        "lifecycle",
        "declared_cap",
        "effective_cap",
        "action",
        "scope",
    }
    for product in products.values():
        record = _map(product)
        assert set(record) == {"components", "ledger_rows", "assignments", "slot_scores"}
        assignments = cast(list[dict[str, object]], record["assignments"])
        assert all(set(row) == assignment_keys for row in assignments)
        assert assignments == sorted(assignments, key=lambda row: str(row["assignment_id"]))
        scores = cast(list[dict[str, object]], record["slot_scores"])
        assert all(
            set(row) == {"pillbox", "slot", "score", "blocked", "assignment_ids", "diagnostics"} for row in scores
        )
        assert len(scores) == 6
        if not post:
            assert all(row["lifecycle"] == "legacy" for row in assignments)


def _movement_truth(pre: RecomputedPreState, post: RecomputedPostState) -> dict[str, object]:
    pre_by = {row["product_id"]: row for row in pre.placement}
    post_by = {row["product_id"]: row for row in post.placement}
    movement_ids = sorted(product for product in pre_by if pre_by[product] != post_by[product])
    return {
        product: {
            "from": {"pillbox": pre_by[product]["pillbox"], "slot": pre_by[product]["slot"]},
            "to": {"pillbox": post_by[product]["pillbox"], "slot": post_by[product]["slot"]},
            "pre_product_sha256": _canonical_sha(_map(pre.products[product])),
            "post_product_sha256": _canonical_sha(_map(post.products[product])),
            "causal_claim": "not_asserted",
        }
        for product in movement_ids
    }


def validate_provenance(
    candidate: dict[str, object],
    recomputed_pre: RecomputedPreState,
    run_1: RecomputedPostState,
    run_2: RecomputedPostState,
    protected_hashes: ProtectedHashes,
) -> None:
    assert set(candidate) == {"format", "pre", "post", "movements", "invariants"}
    assert candidate["format"] == "supp-slotter.slot-policy-layout-provenance/v2"
    assert run_1.placement == run_2.placement
    assert run_1.products == run_2.products
    pre, post = _map(candidate["pre"]), _map(candidate["post"])
    assert set(pre) == set(post) == {"source", "placement", "placement_sha256", "products"}
    pre_placement, post_placement = _state_rows(pre["placement"]), _state_rows(post["placement"])
    assert pre_placement == recomputed_pre.placement
    assert post_placement == run_1.placement == run_2.placement
    assert _canonical_sha(pre_placement) == pre["placement_sha256"]
    assert _canonical_sha(post_placement) == post["placement_sha256"]
    assert _map(pre["source"]) == recomputed_pre.source
    expected_post_source = {key: value for key, value in run_1.source.items() if key != "placement_sha256"} | {
        "run_1_placement_sha256": run_1.source["placement_sha256"],
        "run_2_placement_sha256": run_2.source["placement_sha256"],
    }
    assert _map(post["source"]) == expected_post_source
    pre_products, post_products = _map(pre["products"]), _map(post["products"])
    assert pre_products == recomputed_pre.products
    assert post_products == run_1.products == run_2.products
    assert set(pre_products) == set(post_products) == {row["product_id"] for row in pre_placement}
    _assert_product_schema(pre_products, post=False)
    _assert_product_schema(post_products, post=True)
    movements = _map(candidate["movements"])
    expected_movements = _movement_truth(recomputed_pre, run_1)
    assert movements == expected_movements
    assert list(movements) == sorted(movements)
    assert all(
        set(_map(value)) == {"from", "to", "pre_product_sha256", "post_product_sha256", "causal_claim"}
        for value in movements.values()
    )
    assert all(_map(value)["causal_claim"] == "not_asserted" for value in movements.values())
    assert all(
        _map(_map(value)["from"])["pillbox"] == _map(_map(value)["to"])["pillbox"] for value in movements.values()
    )
    assert protected_hashes.root_schedule_before == protected_hashes.root_schedule_after
    expected_invariants = dict(protected_hashes.invariants)
    expected_invariants["cross_pillbox_movements"] = sum(
        _map(_map(value)["from"])["pillbox"] != _map(_map(value)["to"])["pillbox"] for value in movements.values()
    )
    expected_invariants["root_schedule_untouched"] = (
        protected_hashes.root_schedule_before == protected_hashes.root_schedule_after
    )
    assert _map(candidate["invariants"]) == expected_invariants
    loads = [
        sum(1 for row in pre_placement if row["slot"] == slot)
        for slot in ("morning_empty", "morning_food", "day_food", "evening_empty")
    ]
    assert loads == [2, 4, 4, 2]


@pytest.fixture(scope="module")
def recomputed_truth(tmp_path_factory: pytest.TempPathFactory) -> RecomputedTruth:
    before = _root_schedule_identity()
    root = tmp_path_factory.mktemp("layout-provenance")
    pre = _recompute_pre(root / "archived_pre")
    run_1 = _run_current(root / "run_1")
    run_2 = _run_current(root / "run_2")
    inputs, active = _load_runtime(root / "run_1")
    protected = _protected_hashes(root / "run_1", active, inputs, before)
    return RecomputedTruth(pre, run_1, run_2, protected)


def test_reproducible_layout_provenance(recomputed_truth: RecomputedTruth) -> None:
    validate_provenance(
        _yaml(PROVENANCE),
        recomputed_truth.pre,
        recomputed_truth.run_1,
        recomputed_truth.run_2,
        recomputed_truth.protected,
    )


def test_historical_pre_is_exported_content_addressed_and_complete(recomputed_truth: RecomputedTruth) -> None:
    pre = recomputed_truth.pre
    assert pre.source == {**PRE_SOURCE, "historical_placement_sha256": _canonical_sha(pre.placement)}
    assert pre.row_states == {"PRE": 250, "POST": 0, "MIXED": 0, "UNKNOWN": 0}
    assert pre.card_states == {"PRE": 228, "POST": 0, "MIXED": 0, "UNKNOWN": 0}
    assert pre.loads == [2, 4, 4, 2]
    assert len(pre.placement) == len(pre.products) == 16
    assert pre.source["archived_card_blobs_sha256"] == PRE_SOURCE["archived_card_blobs_sha256"]
    assert pre.source["pre_axis_snapshot_sha256"] == PRE_SOURCE["pre_axis_snapshot_sha256"]


@pytest.mark.parametrize(
    "mutation",
    [
        "pre_placement",
        "missing_movement",
        "extra_movement",
        "ledger_row",
        "assignment",
        "assignment_lifecycle",
        "assignment_cap",
        "assignment_action",
        "assignment_scope",
        "slot_score",
        "slot_block",
        "slot_assignment_id",
        "product_hash",
        "causal_claim",
        "cross_pillbox",
        "divergent_runs",
        "requested_ref",
        "historical_commit",
        "historical_tree",
        "inventory_blob",
        "scheduling_blob",
        "feasibility_blob",
        "search_blob",
        "legacy_policy_commit",
        "legacy_policy_path",
        "legacy_policy_blob",
        "legacy_policy_sha",
        "archived_card_blobs",
        "pre_snapshot_hash",
        "historical_placement_hash",
        "runtime_hash",
        "ontology_hash",
        "data_hash",
        "post_placement",
    ],
)
def test_provenance_mutations_fail_closed(  # noqa: C901, PLR0912, PLR0915
    recomputed_truth: RecomputedTruth, mutation: str
) -> None:
    changed = copy.deepcopy(_yaml(PROVENANCE))
    pre, post, movements = _map(changed["pre"]), _map(changed["post"]), _map(changed["movements"])
    product = next(iter(movements))
    pre_product = _map(_map(pre["products"])[product])
    post_products = _map(post["products"])
    post_product = next(
        _map(value) for value in post_products.values() if cast(list[object], _map(value)["assignments"])
    )
    if mutation == "pre_placement":
        placement = cast(list[dict[str, object]], pre["placement"])
        placement[0]["slot"], placement[1]["slot"] = placement[1]["slot"], placement[0]["slot"]
    elif mutation == "missing_movement":
        movements.pop(product)
    elif mutation == "extra_movement":
        movements["prd_extra"] = copy.deepcopy(next(iter(movements.values())))
    elif mutation == "ledger_row":
        cast(list[object], pre_product["ledger_rows"]).append(
            copy.deepcopy(cast(list[object], pre_product["ledger_rows"])[0])
        )
    elif mutation == "assignment":
        cast(list[object], post_product["assignments"]).pop()
    elif mutation == "assignment_lifecycle":
        _map(cast(list[object], post_product["assignments"])[0])["lifecycle"] = "retired"
    elif mutation == "assignment_cap":
        _map(cast(list[object], post_product["assignments"])[0])["effective_cap"] = "none"
    elif mutation == "assignment_action":
        _map(cast(list[object], post_product["assignments"])[0])["action"] = "suppressed"
    elif mutation == "assignment_scope":
        cast(list[object], _map(cast(list[object], post_product["assignments"])[0])["scope"]).append([
            "product",
            product,
        ])
    elif mutation == "slot_score":
        _map(cast(list[object], post_product["slot_scores"])[0])["score"] = 999
    elif mutation == "slot_block":
        score = _map(cast(list[object], post_product["slot_scores"])[0])
        score["blocked"] = not bool(score["blocked"])
    elif mutation == "slot_assignment_id":
        score = next(
            _map(value)
            for record in post_products.values()
            for value in cast(list[object], _map(record)["slot_scores"])
            if _map(value)["assignment_ids"]
        )
        cast(list[object], score["assignment_ids"])[0] = "substance:wrong:intake:wrong"
    elif mutation == "product_hash":
        _map(movements[product])["post_product_sha256"] = "0" * 64
    elif mutation == "causal_claim":
        _map(movements[product])["causal_claim"] = "medical_reason"
    elif mutation == "cross_pillbox":
        target = _map(_map(movements[product])["to"])
        target["pillbox"] = "daily" if target["pillbox"] == "training" else "training"
    elif mutation == "divergent_runs":
        _map(post["source"])["run_2_placement_sha256"] = "0" * 64
    elif mutation == "requested_ref":
        _map(pre["source"])["requested_ref"] = "wrong^1"
    elif mutation == "historical_commit":
        _map(pre["source"])["commit"] = "0" * 40
    elif mutation == "historical_tree":
        _map(pre["source"])["tree"] = "0" * 40
    elif mutation == "inventory_blob":
        _map(pre["source"])["inventory_blob"] = "0" * 40
    elif mutation in {"scheduling_blob", "feasibility_blob", "search_blob"}:
        path = {
            "scheduling_blob": "planner/engine/_scheduling.py",
            "feasibility_blob": "planner/engine/_plan_feasibility.py",
            "search_blob": "planner/engine/_plan_search.py",
        }[mutation]
        _map(_map(pre["source"])["historical_source_blobs"])[path] = "0" * 40
    elif mutation == "legacy_policy_commit":
        _map(pre["source"])["legacy_policy_commit"] = "0" * 40
    elif mutation == "legacy_policy_path":
        _map(pre["source"])["legacy_policy_path"] = "wrong.yaml"
    elif mutation == "legacy_policy_blob":
        _map(pre["source"])["legacy_policy_blob"] = "0" * 40
    elif mutation == "legacy_policy_sha":
        _map(pre["source"])["legacy_policy_sha256"] = "0" * 64
    elif mutation == "archived_card_blobs":
        _map(pre["source"])["archived_card_blobs_sha256"] = "0" * 64
    elif mutation == "pre_snapshot_hash":
        _map(pre["source"])["pre_axis_snapshot_sha256"] = "0" * 64
    elif mutation == "historical_placement_hash":
        _map(pre["source"])["historical_placement_sha256"] = "0" * 64
    elif mutation == "runtime_hash":
        _map(post["source"])["runtime_inputs_sha256"] = "0" * 64
    elif mutation == "ontology_hash":
        _map(post["source"])["ontology_inputs_sha256"] = "0" * 64
    elif mutation == "data_hash":
        _map(post["source"])["data_inputs_sha256"] = "0" * 64
    elif mutation == "post_placement":
        _map(cast(list[object], post["placement"])[0])["slot"] = "day_food"
    with pytest.raises(AssertionError):
        validate_provenance(
            changed,
            recomputed_truth.pre,
            recomputed_truth.run_1,
            recomputed_truth.run_2,
            recomputed_truth.protected,
        )
