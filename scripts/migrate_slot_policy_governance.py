#!/usr/bin/env python3
"""Apply the locked slot-policy migration ledger (never invent actions)."""
# pyright: basic, reportUnknownParameterType=false, reportUnknownMemberType=false, reportUnknownArgumentType=false, reportAny=false
# ruff: noqa: C901, PLR2004, PLR0912, PLR0915, PLR0914

from __future__ import annotations

import argparse
import hashlib
import sys
from pathlib import Path

import yaml


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load(path: Path):
    return yaml.safe_load(path.read_text()) or {}


def _save(path: Path, obj) -> None:
    path.write_text(yaml.safe_dump(obj, sort_keys=False, allow_unicode=True))


def migrate(root: Path, ledger_path: Path, owner: str | None, apply: bool) -> int:
    ledger = _load(ledger_path)
    rows = ledger.get("rows", [])
    if not isinstance(rows, list):
        raise SystemExit("ledger rows must be a list")
    seen: set[tuple[str, str, str]] = set()
    if len(rows) != 221 or sum(r.get("axis") == "intake" for r in rows) != 195:
        raise SystemExit("ledger count mismatch: expected 195 intake + 26 timing/activity rows")
    adjudications = [r for r in rows if r.get("axis") == "intake" and r.get("adjudication_key")]
    buckets = {"FORM": 88, "MINERAL": 35, "ENZYME": 4, "FAT": 3, "WATER_SPACING": 6, "EXCEPTION": 2}
    if len(adjudications) != 138 or {b: sum(r.get("bucket") == b for r in adjudications) for b in buckets} != buckets:
        raise SystemExit("adjudication bijection or bucket counts mismatch")
    required = {
        "final_status",
        "enforcement_cap",
        "scope",
        "evidence_keys",
        "owner",
        "review_by",
        "action",
        "old_value",
    }
    for row in rows:
        missing = required - row.keys()
        if missing or (row["action"] != "remove" and not row.get("new_value")):
            raise SystemExit(f"incomplete locked ledger row {row.get('card_id')}: {sorted(missing)}")
        if not row.get("evidence_keys"):
            raise SystemExit(f"missing evidence bundle: {row.get('card_id')}")
        key = (row["card_id"], row["axis"], row["current_policy"])
        if key in seen:
            raise SystemExit(f"duplicate ledger key: {key}")
        seen.add(key)
        if owner and row.get("owner") != owner:
            continue
        path = root / row["path"]
        if not path.is_file():
            raise SystemExit(f"missing card path: {path}")
        card = _load(path)
        current = (card.get("schedule") or {}).get(row["axis"], [])
        expected = row["old_value"]
        if expected not in current:
            raise SystemExit(f"old-value mismatch for {path}: expected {expected!r}")
        if row.get("action") not in {"keep", "replace", "remove"}:
            raise SystemExit(f"unsupported ledger action: {row.get('action')!r}")
        target = row.get("new_value")
        if row["action"] == "remove":
            new_values = [v for v in current if v != expected]
        else:
            new_values = [target if v == expected else v for v in current]
        if apply:
            card.setdefault("schedule", {})[row["axis"]] = new_values
            gov = card.setdefault("schedule_governance", {})
            gov_key = f"{row['axis']}:{target}" if target else f"{row['axis']}:{expected}"
            if row["action"] == "remove":
                gov.pop(gov_key, None)
            else:
                gov[gov_key] = row.get("governance", {})
            _save(path, card)
        print(f"{path}: {row['action']} {expected} -> {target or '-'}")
    return 0


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--ledger", type=Path, default=Path("tests/fixtures/slot_policy/v2_migration_ledger.yaml"))
    p.add_argument("--owner", choices=["L6", "L7", "L8"])
    mode = p.add_mutually_exclusive_group(required=True)
    mode.add_argument("--check", action="store_true")
    mode.add_argument("--apply", action="store_true")
    args = p.parse_args()
    return migrate(Path.cwd(), args.ledger, args.owner, args.apply)


if __name__ == "__main__":
    sys.exit(main())
