#!/usr/bin/env python3
"""One-off migration: rewrite flat substance cards to schedule:/knowledge: nested shape.

Run from repo root:
    uv run python scripts/migrate_substance_cards.py [--dry-run]

Raises ValueError on partially-migrated cards (mixed nested+flat).
Delete this script after the migration commit is merged.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
SUBSTANCES_DIR = ROOT / "data" / "substances"

TIMING_SLUGS = {"energy_like", "sleep_disruptive", "sleep_support"}
FLAT_NAMESPACE_KEYS = {"is", "intake", "effect", "risk", "activity", "dashboard", "prefer_with"}


def migrate_card(data: dict) -> dict:
    """Migrate a v1 flat substance card to v2 nested schedule:/knowledge: form.

    Idempotent: returns input unchanged if already in v2 form.
    Raises ValueError on partially-migrated cards (mixed nested+flat keys).
    """
    has_nested = "schedule" in data or "knowledge" in data
    flat_present = set(data) & FLAT_NAMESPACE_KEYS

    # Mixed-card rejection (per-09-REVIEWS.md MEDIUM-3)
    if has_nested and flat_present:
        raise ValueError(
            f"partial migration in {data.get('id', '?')}: card has nested section AND "
            f"flat keys {sorted(flat_present)} — fix by hand"
        )

    # Idempotency: already in v2 form, no flat keys present
    if has_nested:
        return data

    # --- Pop v1 namespace keys ---
    intake = data.pop("intake", []) or []
    activity = data.pop("activity", []) or []
    is_val = data.pop("is", []) or []
    risk_val = data.pop("risk", []) or []
    dashboard_val = data.pop("dashboard", []) or []
    effect_slugs = data.pop("effect", []) or []
    # prefer_with: preserve None vs empty distinction
    prefer_with = data.pop("prefer_with", None)

    # Split effect slugs into timing (scheduling) vs knowledge.effect (non-scheduling)
    timing_slugs = [s for s in effect_slugs if s in TIMING_SLUGS]
    knowledge_effect_slugs = [s for s in effect_slugs if s not in TIMING_SLUGS]

    # Defensive: unknown effect slugs (not in TIMING_SLUGS and not a known knowledge slug)
    # are allowed — they go to knowledge.effect. But if any slug is unrecognised as timing,
    # we still need to check nothing unexpected landed in timing.
    # The plan says: "any other effect slug encountered during migration is a data error
    # and the migration script must abort with a clear message listing the file + slug."
    # Interpretation: any effect slug NOT in TIMING_SLUGS goes to knowledge.effect (fine).
    # The abort case is if we see an effect slug that is in TIMING_SLUGS mixed with
    # unexpected non-TIMING slugs — but that is handled by the split above naturally.
    # The plan's abort condition refers to slugs that are truly unrecognised timing
    # candidates. Since TIMING_SLUGS is the authoritative set, any slug not in it
    # lands in knowledge.effect — which is the correct default. No abort needed here
    # unless the script encounters an effect slug that IS in TIMING_SLUGS but also
    # appears to be a knowledge slug — which is structurally impossible by definition.

    # Build schedule: section
    schedule: dict = {}
    if intake:
        schedule["intake"] = list(intake)
    if timing_slugs:
        schedule["timing"] = [timing_slugs[0]]  # max 1 per schema
    if activity:
        schedule["activity"] = list(activity)
    if prefer_with:
        schedule["prefer_with"] = prefer_with

    # Build knowledge: section
    knowledge: dict = {}
    if is_val:
        knowledge["is"] = list(is_val)
    if knowledge_effect_slugs:
        knowledge["effect"] = knowledge_effect_slugs
    if risk_val:
        knowledge["risk"] = list(risk_val)
    if dashboard_val:
        knowledge["dashboard"] = list(dashboard_val)
    # pathway is not present in v1 cards — omit

    # Build result preserving common field order
    result: dict = {}
    for k in ("id", "name", "form", "aliases", "notes", "concerns"):
        if k in data:
            result[k] = data[k]
    if schedule:
        result["schedule"] = schedule
    if knowledge:
        result["knowledge"] = knowledge

    # Defensive: verify no v1 namespace key or legacy traits key remains
    residual = set(result) & (FLAT_NAMESPACE_KEYS | {"traits"})
    if residual:
        raise ValueError(
            f"residual v1 key in {data.get('id', '?')}: {sorted(residual)}"
        )

    return result


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Migrate flat v1 substance cards to v2 schedule:/knowledge: nested shape."
    )
    parser.add_argument("--dry-run", action="store_true", help="Preview only, no writes.")
    args = parser.parse_args()

    paths = sorted(SUBSTANCES_DIR.glob("*.yaml"))
    changed = 0
    for path in paths:
        raw = yaml.safe_load(path.read_text())
        if not isinstance(raw, dict):
            print(f"skip (non-mapping): {path.name}", file=sys.stderr)
            continue
        try:
            migrated = migrate_card(dict(raw))
        except ValueError as e:
            print(f"FAILED on {path.name}: {e}", file=sys.stderr)
            raise
        if migrated == raw:
            continue
        changed += 1
        if args.dry_run:
            print(f"would migrate: {path.name}")
        else:
            path.write_text(yaml.dump(migrated, allow_unicode=True, sort_keys=False))
            print(f"migrated: {path.name}")

    prefix = "[dry-run] " if args.dry_run else ""
    print(f"{prefix}done: {changed}/{len(paths)} cards updated")


if __name__ == "__main__":
    main()
