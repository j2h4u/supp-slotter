#!/usr/bin/env python3
"""Validate and apply the locked card-group slot-policy migration wire."""
# pyright: reportAny=false, reportExplicitAny=false, reportUnknownArgumentType=false, reportUnknownMemberType=false

from __future__ import annotations

import argparse
import copy
import json
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal, cast

import yaml

Owner = Literal["L6", "L7", "L8"]
State = Literal["PRE", "POST", "MIXED", "UNKNOWN"]
AXES = ("intake", "timing", "activity")
ACTIONS = {
    "KEEP_ASSIGNMENT_ADD_GOVERNANCE",
    "REPLACE_ASSIGNMENT_ADD_GOVERNANCE",
    "REMOVE_ASSIGNMENT_AND_GOVERNANCE",
}
POLICIES = {
    "intake": {"empty_preferred", "food_preferred"},
    "timing": {"energy_like", "sleep_support"},
    "activity": {"any_workout", "pre_workout"},
}
BEFORE_POLICIES = {
    **POLICIES,
    "intake": POLICIES["intake"] | {"fat_meal_required", "food_required", "food_neutral"},
}
EXPECTED_ACTIONS = {
    "KEEP_ASSIGNMENT_ADD_GOVERNANCE": 145,
    "REPLACE_ASSIGNMENT_ADD_GOVERNANCE": 26,
    "REMOVE_ASSIGNMENT_AND_GOVERNANCE": 79,
}
EXPECTED_OWNERS = {"L6": (26, 48), "L7": (97, 97), "L8": (105, 105)}
EXPECTED_BUCKETS = {"FORM": 88, "MINERAL": 35, "ENZYME": 4, "FAT": 3, "WATER_SPACING": 6, "EXCEPTION": 2}
EXPECTED_ROWS = 250
EXPECTED_ADJUDICATIONS = 138
EXPECTED_FILES = 228
EXPECTED_NEUTRAL_ROWS = 29
NEUTRAL_DECISION = {
    "disposition": "retired",
    "status": "retired",
    "enforcement_cap": "none",
    "reason_code": "REDUNDANT_ZERO_EFFECT_ASSIGNMENT",
    "retirement_reason": "Zero-effect food-neutral marker removed; absence is the canonical no-food-driver state.",
    "source_refs": [
        "baseline-main:data/traits/schedule.yaml#intake.food_neutral",
        "executable-plan-v3-amendment-5:2",
    ],
}


@dataclass(frozen=True)
class CardGroup:
    owner: Owner
    path: str
    card_id: str
    rows: tuple[dict[str, Any], ...]


def _load_yaml(path: Path) -> dict[str, Any]:
    value = yaml.safe_load(path.read_text())
    if not isinstance(value, dict):
        raise SystemExit(f"expected YAML mapping: {path}")
    return cast(dict[str, Any], value)


def _write_yaml(path: Path, value: dict[str, Any]) -> None:
    path.write_text(yaml.safe_dump(value, sort_keys=False, allow_unicode=True, width=120))


def _axis_view(card: dict[str, Any], axis: str) -> dict[str, Any]:
    schedule = card.get("schedule")
    values = schedule.get(axis, []) if isinstance(schedule, dict) else []
    governance = card.get("schedule_governance")
    entries = (
        {str(key): value for key, value in governance.items() if str(key).startswith(f"{axis}:")}
        if isinstance(governance, dict)
        else {}
    )
    return {"axis_values": values, "governance_entries": entries}


def classify_card(card: dict[str, Any], group: CardGroup) -> tuple[State, list[str]]:
    pieces: list[str] = []
    diagnostics: list[str] = []
    for row in group.rows:
        axis = str(row["axis"])
        observed = _axis_view(card, axis)
        before, after = row["before"], row["after"]
        if observed == before:
            pieces.append("PRE")
        elif observed == after:
            pieces.append("POST")
        else:
            values = observed["axis_values"]
            governance = observed["governance_entries"]
            assignment_known = values in (before["axis_values"], after["axis_values"])
            governance_known = governance in (before["governance_entries"], after["governance_entries"])
            pieces.append("MIXED" if assignment_known and governance_known else "UNKNOWN")
            diagnostics.append(f"{axis}: observed={observed!r}")
    unique = set(pieces)
    if unique == {"PRE"}:
        return "PRE", diagnostics
    if unique == {"POST"}:
        return "POST", diagnostics
    if "UNKNOWN" in unique:
        return "UNKNOWN", diagnostics
    return "MIXED", diagnostics


def _validate_governance(entries: dict[str, Any], axis: str, after_values: list[str]) -> None:  # noqa: C901, PLR0912
    if not after_values:
        if entries:
            raise SystemExit("retired row contains live governance")
        return
    expected_key = f"{axis}:{after_values[0]}"
    if set(entries) != {expected_key}:
        raise SystemExit(f"invalid governance keys for {expected_key}")
    governance = entries[expected_key]
    if not isinstance(governance, dict):
        raise SystemExit(f"governance is not a mapping: {expected_key}")
    required = {"status", "enforcement_cap", "scope", "evidence", "owner", "review_by"}
    allowed = required | {"evidence_gap"}
    if set(governance) - allowed or not required <= set(governance):
        raise SystemExit(f"incomplete governance: {expected_key}")
    status = governance["status"]
    if status not in {"approved", "review_pending"}:
        raise SystemExit(f"invalid governance status: {expected_key}")
    if status == "review_pending" and not governance.get("evidence_gap"):
        raise SystemExit(f"pending governance lacks evidence_gap: {expected_key}")
    if status == "approved" and "evidence_gap" in governance:
        raise SystemExit(f"approved governance has evidence_gap: {expected_key}")
    if governance["enforcement_cap"] not in {"preference", "advisory"}:
        raise SystemExit(f"invalid enforcement cap: {expected_key}")
    scope = governance["scope"]
    if not isinstance(scope, dict) or not scope or any(not isinstance(v, str) or not v for v in scope.values()):
        raise SystemExit(f"invalid scope: {expected_key}")
    evidence = governance["evidence"]
    if not isinstance(evidence, list):
        raise SystemExit(f"invalid evidence list: {expected_key}")
    for item in evidence:
        if not isinstance(item, dict) or set(item) != {"source", "supports", "limitations"}:
            raise SystemExit(f"invalid evidence object: {expected_key}")
        if any(not isinstance(item[key], str) or not item[key] for key in item):
            raise SystemExit(f"empty evidence literal: {expected_key}")


def _validate_neutral_retirement(row: dict[str, Any]) -> None:
    expected_keys = {"row_id", "card_id", "path", "owner", "axis", "action", "before", "after", "decision"}
    if set(row) != expected_keys:
        raise SystemExit(f"invalid neutral retirement row shape: {row.get('row_id')}")
    expected = {
        "row_id": f"{row.get('card_id')}|intake|food_neutral",
        "card_id": row.get("card_id"),
        "path": row.get("path"),
        "owner": row.get("owner"),
        "axis": "intake",
        "action": "REMOVE_ASSIGNMENT_AND_GOVERNANCE",
        "before": {"axis_values": ["food_neutral"], "governance_entries": {}},
        "after": {"axis_values": [], "governance_entries": {}},
        "decision": NEUTRAL_DECISION,
    }
    if row != expected:
        raise SystemExit(f"invalid neutral retirement wire: {row.get('row_id')}")


def validate_wire(  # noqa: C901, PLR0912, PLR0914, PLR0915
    ledger: dict[str, Any], manifest: dict[str, Any]
) -> tuple[list[dict[str, Any]], list[CardGroup]]:
    if ledger.get("format") != "supp-slotter.slot-policy-migration/v3" or ledger.get("schema_version") != "3":
        raise SystemExit("expected migration v3/schema 3")
    if manifest.get("format") != "supp-slotter.slot-policy-worker-manifest/v3" or manifest.get("schema_version") != "3":
        raise SystemExit("expected worker manifest v3/schema 3")
    rows = ledger.get("rows")
    cards = manifest.get("cards")
    if not isinstance(rows, list) or not isinstance(cards, list):
        raise SystemExit("rows/cards must be lists")
    typed_rows = cast(list[dict[str, Any]], rows)
    if len(typed_rows) != EXPECTED_ROWS or len({r.get("row_id") for r in typed_rows}) != EXPECTED_ROWS:
        raise SystemExit("expected 221 unique row_ids")
    if Counter(r.get("axis") for r in typed_rows) != {"intake": 224, "timing": 18, "activity": 8}:
        raise SystemExit("axis accounting mismatch")
    if Counter(r.get("action") for r in typed_rows) != EXPECTED_ACTIONS:
        raise SystemExit("action accounting mismatch")
    adjudications = [
        r["decision"]
        for r in typed_rows
        if isinstance(r.get("decision"), dict) and r["decision"].get("adjudication_key")
    ]
    if (
        len({d["adjudication_key"] for d in adjudications}) != EXPECTED_ADJUDICATIONS
        or Counter(d.get("bucket") for d in adjudications) != EXPECTED_BUCKETS
    ):
        raise SystemExit("adjudication bijection mismatch")
    required_sources = set(cast(list[str], ledger.get("required_evidence_sources", [])))
    used_sources: set[str] = set()
    grouped: dict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(list)
    neutral_rows = 0
    for row in typed_rows:
        axis, action = row.get("axis"), row.get("action")
        if axis not in AXES or action not in ACTIONS:
            raise SystemExit(f"invalid row axis/action: {row.get('row_id')}")
        before, after = row.get("before"), row.get("after")
        if not isinstance(before, dict) or not isinstance(after, dict):
            raise SystemExit(f"missing before/after: {row.get('row_id')}")
        before_values, after_values = before.get("axis_values"), after.get("axis_values")
        if (
            not isinstance(before_values, list)
            or len(before_values) != 1
            or not isinstance(after_values, list)
            or len(after_values) > 1
        ):
            raise SystemExit(f"invalid axis list shape: {row.get('row_id')}")
        if before_values == ["food_neutral"]:
            _validate_neutral_retirement(row)
            neutral_rows += 1
        if not set(before_values) <= BEFORE_POLICIES[str(axis)] or not set(after_values) <= POLICIES[str(axis)]:
            raise SystemExit(f"invalid policy token: {row.get('row_id')}")
        if before.get("governance_entries") != {} or not isinstance(after.get("governance_entries"), dict):
            raise SystemExit(f"invalid transition governance shape: {row.get('row_id')}")
        if action == "KEEP_ASSIGNMENT_ADD_GOVERNANCE" and after_values != before_values:
            raise SystemExit(f"invalid keep transition: {row.get('row_id')}")
        if action == "REPLACE_ASSIGNMENT_ADD_GOVERNANCE" and (not after_values or after_values == before_values):
            raise SystemExit(f"invalid replace transition: {row.get('row_id')}")
        if action == "REMOVE_ASSIGNMENT_AND_GOVERNANCE" and after_values:
            raise SystemExit(f"invalid removal transition: {row.get('row_id')}")
        _validate_governance(after["governance_entries"], str(axis), after_values)
        for value in after["governance_entries"].values():
            used_sources.update(item["source"] for item in value["evidence"])
        grouped[(str(row["owner"]), str(row["path"]), str(row["card_id"]))].append(row)
    if neutral_rows != EXPECTED_NEUTRAL_ROWS:
        raise SystemExit("expected exactly 29 neutral retirement rows")
    if used_sources != required_sources:
        raise SystemExit("required evidence source set mismatch")
    typed_cards = cast(list[dict[str, Any]], cards)
    if len(typed_cards) != EXPECTED_FILES:
        raise SystemExit("manifest card count mismatch")
    paths = [str(card.get("path")) for card in typed_cards]
    card_ids = [str(card.get("card_id")) for card in typed_cards]
    if len(set(paths)) != EXPECTED_FILES or len(set(card_ids)) != EXPECTED_FILES:
        raise SystemExit("duplicate manifest path or card_id")
    manifest_row_ids = [row_id for card in typed_cards for row_id in card.get("row_ids", [])]
    ledger_row_ids = [str(row["row_id"]) for row in typed_rows]
    if Counter(manifest_row_ids) != Counter(ledger_row_ids):
        raise SystemExit("manifest row_id union mismatch")
    manifest_by_path = {str(card["path"]): card for card in typed_cards}
    if set(manifest_by_path) != {key[1] for key in grouped} or len(manifest_by_path) != EXPECTED_FILES:
        raise SystemExit("manifest path set mismatch")
    groups: list[CardGroup] = []
    for (owner, path, card_id), group_rows in grouped.items():
        entry = manifest_by_path.get(path)
        if not entry or entry.get("owner") != owner or entry.get("card_id") != card_id:
            raise SystemExit(f"manifest owner/card mismatch: {path}")
        expected_axes = [axis for axis in AXES if any(row["axis"] == axis for row in group_rows)]
        expected_row_ids = {str(row["row_id"]) for row in group_rows}
        if entry.get("axes") != expected_axes or set(entry.get("row_ids", [])) != expected_row_ids:
            raise SystemExit(f"manifest axes/row_ids mismatch: {path}")
        groups.append(
            CardGroup(cast(Owner, owner), path, card_id, tuple(sorted(group_rows, key=lambda r: AXES.index(r["axis"]))))
        )
    for owner, (files, transitions) in EXPECTED_OWNERS.items():
        owner_rows = [row for row in typed_rows if row["owner"] == owner]
        action_counts = Counter(row["action"] for row in owner_rows)
        derived_accounting = {
            "unique_files": sum(group.owner == owner for group in groups),
            "keep_add_governance": action_counts["KEEP_ASSIGNMENT_ADD_GOVERNANCE"],
            "replace_add_governance": action_counts["REPLACE_ASSIGNMENT_ADD_GOVERNANCE"],
            "remove_assignment_and_governance": action_counts["REMOVE_ASSIGNMENT_AND_GOVERNANCE"],
            "transitions": len(owner_rows),
            "live_governance": sum(bool(row["after"]["governance_entries"]) for row in owner_rows),
        }
        if derived_accounting["unique_files"] != files or derived_accounting["transitions"] != transitions:
            raise SystemExit(f"owner accounting mismatch: {owner}")
        accounting = manifest.get("accounting")
        if not isinstance(accounting, dict) or accounting.get(owner) != derived_accounting:
            raise SystemExit(f"manifest accounting mismatch: {owner}")
    return typed_rows, sorted(groups, key=lambda group: group.path)


def _validate_catalog(root: Path, ledger: dict[str, Any]) -> None:
    required_sources = set(cast(list[str], ledger["required_evidence_sources"]))
    policies = _load_yaml(root / "ontology/policies.yaml")
    catalog = policies.get("slot_policy_evidence")
    if not isinstance(catalog, dict) or not required_sources <= set(catalog):
        missing = sorted(required_sources - set(catalog if isinstance(catalog, dict) else {}))
        raise SystemExit(f"prepared evidence catalog missing keys: {missing}")
    for key in required_sources:
        expected = catalog[key]
        if not isinstance(expected, dict):
            raise SystemExit(f"invalid catalog evidence: {key}")
    for row in cast(list[dict[str, Any]], ledger["rows"]):
        for governance in row["after"]["governance_entries"].values():
            for item in governance["evidence"]:
                source = item["source"]
                if item["supports"] != catalog[source].get("supports") or item["limitations"] != catalog[source].get(
                    "limitations"
                ):
                    raise SystemExit(f"ledger evidence literals differ from catalog: {source}")


def _fold(card: dict[str, Any], group: CardGroup) -> dict[str, Any]:
    result = copy.deepcopy(card)
    schedule = result.setdefault("schedule", {})
    governance = result.setdefault("schedule_governance", {})
    for row in group.rows:
        axis = row["axis"]
        values = row["after"]["axis_values"]
        for key in [key for key in governance if str(key).startswith(f"{axis}:")]:
            del governance[key]
        governance.update(copy.deepcopy(row["after"]["governance_entries"]))
        if values:
            schedule[axis] = copy.deepcopy(values)
        else:
            schedule.pop(axis, None)
    if not schedule:
        result.pop("schedule", None)
    if not governance:
        result.pop("schedule_governance", None)
    return result


def run(root: Path, ledger_path: Path, manifest_path: Path, owner: Owner | None, apply: bool) -> int:
    ledger = _load_yaml(ledger_path)
    manifest = cast(dict[str, Any], json.loads(manifest_path.read_text()))
    _, groups = validate_wire(ledger, manifest)
    selected = [group for group in groups if owner is None or group.owner == owner]
    observed: dict[State, list[tuple[CardGroup, list[str]]]] = defaultdict(list)
    cards: dict[str, dict[str, Any]] = {}
    for group in selected:
        card = _load_yaml(root / group.path)
        if card.get("id") != group.card_id:
            raise SystemExit(f"card id mismatch: {group.path}")
        cards[group.path] = card
        state, diagnostics = classify_card(card, group)
        observed[state].append((group, diagnostics))
    bad = observed["MIXED"] + observed["UNKNOWN"]
    if bad:
        details = "; ".join(f"{group.path} {diag}" for group, diag in bad)
        raise SystemExit(f"refusing mixed/unknown cards: {details}")
    if not apply:
        if observed["PRE"]:
            paths = [group.path for group, _ in observed["PRE"]]
            raise SystemExit(f"PRE cards are not applied: {paths}")
        print(f"{owner or 'ALL'}: POST {len(selected)} cards")
        return 0
    _validate_catalog(root, ledger)
    for group, _ in observed["PRE"]:
        path = root / group.path
        _write_yaml(path, _fold(cards[group.path], group))
    for group in selected:
        state, diagnostics = classify_card(_load_yaml(root / group.path), group)
        if state != "POST":
            raise SystemExit(f"post-write verification failed: {group.path} {state} {diagnostics}")
    print(f"{owner or 'ALL'}: POST {len(selected)} cards; wrote {len(observed['PRE'])}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--ledger", type=Path, default=Path("tests/fixtures/slot_policy/v2_migration_ledger.yaml"))
    parser.add_argument("--manifest", type=Path, default=Path("tests/fixtures/slot_policy/v2_worker_manifest.json"))
    parser.add_argument("--owner", choices=["L6", "L7", "L8"])
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--check", action="store_true")
    mode.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    root = cast(Path, args.root)
    ledger = cast(Path, args.ledger)
    manifest = cast(Path, args.manifest)
    if not ledger.is_absolute():
        ledger = root / ledger
    if not manifest.is_absolute():
        manifest = root / manifest
    return run(root, ledger, manifest, cast(Owner | None, args.owner), cast(bool, args.apply))


if __name__ == "__main__":
    sys.exit(main())
