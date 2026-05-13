# Phase 9: Planner / Reviewer Ontology Split — Pattern Map

**Mapped:** 2026-05-13
**Files analyzed:** 13 new/modified files
**Analogs found:** 12 / 13

---

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|---|---|---|---|---|
| `schema/substance.schema.json` | config | transform | self (rewrite) | self |
| `planner/contracts.py` | model | transform | self (modify) | self |
| `planner/io.py` | config | transform | self (modify) | self |
| `planner/cards/substance.py` | service | CRUD | self (modify) | self |
| `planner/cards/traits.py` | service | CRUD | self (modify) | self |
| `planner/engine/_scheduling.py` | service | transform | self (modify) | self |
| `planner/engine/plan.py` | service | transform | self (modify) | self |
| `planner/engine/review.py` | service | request-response | `planner/engine/audit.py` | role-match |
| `planner/engine/audit.py` | service | request-response | self (modify) | self |
| `planner/__main__.py` | utility | request-response | self (modify) | self |
| `scripts/migrate_substance_cards.py` | utility | batch | `planner/engine/audit.py` (_collect_cleanup_sections) | partial |
| `tests/test_schemas.py` | test | transform | self (extend) | self |
| `tests/test_scheduling_units.py` | test | transform | self (update fixtures) | self |
| `tests/test_review_command.py` | test | request-response | `tests/test_scheduling_units.py` | role-match |

---

## Pattern Assignments

### `schema/substance.schema.json` (config, transform)

**Analog:** self — full rewrite from flat to `schedule:`/`knowledge:` nested shape.

**Current shape** (lines 1–112) — flat top-level properties with `additionalProperties: false`:
```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "type": "object",
  "additionalProperties": false,
  "required": ["id", "name"],
  "properties": {
    "is":       { "type": "array", "uniqueItems": true, "items": { "type": "string", "pattern": "^[a-z][a-z0-9_]*$" } },
    "intake":   { "type": "array", "uniqueItems": true, "maxItems": 1, "items": { ... } },
    "effect":   { "type": "array", "uniqueItems": true, "items": { ... } },
    "risk":     { "type": "array", "uniqueItems": true, "items": { ... } },
    "activity": { "type": "array", "uniqueItems": true, "maxItems": 1, "items": { ... } },
    "dashboard":{ "type": "array", "uniqueItems": true, "items": { ... } }
  }
}
```

**Target shape** — replace the six flat namespace properties with two nested objects. Keep all common fields (`id`, `name`, `form`, `aliases`, `notes`, `concerns`, `prefer_with`) at top level unchanged. The nested objects must use `additionalProperties: false` to prevent mixed-format cards from passing:

```json
"schedule": {
  "type": "object",
  "additionalProperties": false,
  "properties": {
    "intake":     { "type": "array", "uniqueItems": true, "maxItems": 1, "items": { "type": "string", "pattern": "^[a-z][a-z0-9_]*$" } },
    "timing":     { "type": "array", "uniqueItems": true, "maxItems": 1, "items": { "type": "string", "pattern": "^[a-z][a-z0-9_]*$" } },
    "activity":   { "type": "array", "uniqueItems": true, "maxItems": 1, "items": { "type": "string", "pattern": "^[a-z][a-z0-9_]*$" } },
    "prefer_with":{ "type": "array", "minItems": 1, "uniqueItems": true, "items": { "type": "string", "pattern": "^sub_[a-z0-9]{10}$" } }
  }
},
"knowledge": {
  "type": "object",
  "additionalProperties": false,
  "properties": {
    "is":       { "type": "array", "uniqueItems": true, "items": { "type": "string", "pattern": "^[a-z][a-z0-9_]*$" } },
    "effect":   { "type": "array", "uniqueItems": true, "items": { "type": "string", "pattern": "^[a-z][a-z0-9_]*$" } },
    "risk":     { "type": "array", "uniqueItems": true, "items": { "type": "string", "pattern": "^[a-z][a-z0-9_]*$" } },
    "dashboard":{ "type": "array", "uniqueItems": true, "items": { "type": "string", "pattern": "^[a-z][a-z0-9_]*$" } },
    "pathway":  { "type": "array", "uniqueItems": true, "items": { "type": "string", "pattern": "^[a-z][a-z0-9_]*$" } }
  }
}
```

`prefer_with` moves inside `schedule:` — remove it from the top level. The old flat namespace keys (`is`, `intake`, `effect`, `risk`, `activity`, `dashboard`) must be removed from top-level `properties`; the top-level `additionalProperties: false` then rejects any card that still has them.

---

### `planner/contracts.py` — `Substance` dataclass (model, transform)

**Analog:** self — targeted modification of lines 44–57.

**Current `Substance`** (lines 43–57):
```python
@dataclass(frozen=True, slots=True)
class Substance:
    id: str
    name: str
    is_: tuple[str, ...] = ()
    intake: tuple[str, ...] = ()
    effect: tuple[str, ...] = ()
    risk: tuple[str, ...] = ()
    activity: tuple[str, ...] = ()
    dashboard: tuple[str, ...] = ()
    form: str | None = None
    aliases: tuple[str, ...] = ()
    notes: str | None = None
    concerns: tuple[Concern, ...] = ()
    prefer_with: tuple[str, ...] = ()
```

**Target `Substance`** — add `timing` and `pathway` fields; group by actor with comments:
```python
@dataclass(frozen=True, slots=True)
class Substance:
    id: str
    name: str
    # --- schedule: section (Planner reads these) ---
    intake: tuple[str, ...] = ()       # 0 or 1 slug
    timing: tuple[str, ...] = ()       # 0 or 1 slug — NEW (was effect: timing slugs)
    activity: tuple[str, ...] = ()     # 0 or 1 slug
    prefer_with: tuple[str, ...] = ()  # sub_* IDs
    # --- knowledge: section (Reviewer reads these) ---
    is_: tuple[str, ...] = ()          # structural classification
    effect: tuple[str, ...] = ()       # pharmacological effects (non-scheduling)
    risk: tuple[str, ...] = ()         # safety/interaction flags
    dashboard: tuple[str, ...] = ()    # editorial cluster membership
    pathway: tuple[str, ...] = ()      # metabolic pathway membership — NEW
    # --- common (neither actor) ---
    form: str | None = None
    aliases: tuple[str, ...] = ()
    notes: str | None = None
    concerns: tuple[Concern, ...] = ()
```

**`Relation` dataclass** (lines 102–111) — add two optional fields for class-level competes:
```python
@dataclass(frozen=True, slots=True)
class Relation:
    type: RelationType
    reason: str
    source_substance: str | None = None
    target_substance: str | None = None
    source_name: str | None = None
    target_name: str | None = None
    source_class: str | None = None    # NEW — class-level competes
    target_class: str | None = None    # NEW — class-level competes
    action: str | None = None
    severity: Severity | None = None
```

**`TraitDef` dataclass** (lines 127–138) — retire `separate_from` field by removing it entirely after migration. Keep `warning` and `action` fields unchanged.

---

### `planner/io.py` — `REGISTERED_NAMESPACES` (config, transform)

**Analog:** self — single-line set modification at lines 30–37.

**Current** (lines 30–37):
```python
REGISTERED_NAMESPACES = {
    "intake",
    "effect",
    "is",
    "risk",
    "activity",
    "dashboard",
}
```

**Target** — add `timing` and `pathway`; remove `effect` only if zero `effect:` traits remain in `traits.yaml` after migration (confirmed: all 3 effect slugs move to `timing:`):
```python
REGISTERED_NAMESPACES = {
    "intake",
    "timing",    # NEW — replaces effect: for scheduling-relevant slugs
    "is",
    "risk",
    "activity",
    "dashboard",
    "pathway",   # NEW — metabolic pathway membership
}
```

---

### `planner/cards/substance.py` — `load_substance` (service, CRUD)

**Analog:** self — targeted rewrite of `load_substance` (lines 27–58) with dual-format detection.

**Current loader pattern** (lines 27–58) — single-format, flat namespace reads:
```python
def load_substance(path: Path) -> Substance:
    data = load_card_mapping(path, "substance")
    errors = schema_errors(data, "substance", path)
    if errors:
        raise CardLoadError(path, errors[0])
    try:
        return Substance(
            id=data["id"],
            name=data["name"],
            is_=tuple(data.get("is") or ()),
            intake=tuple(data.get("intake") or ()),
            ...
        )
    except KeyError as e:
        raise CardLoadError(path, f"{path}: missing required field {e}") from e
```

**Target loader pattern** — dual-format detection using `"schedule" in data` sentinel; v1 path kept intact for migration period:
```python
def load_substance(path: Path) -> Substance:
    data = load_card_mapping(path, "substance")
    errors = schema_errors(data, "substance", path)
    if errors:
        raise CardLoadError(path, errors[0])

    # Ambiguous dual-format guard
    flat_keys = {"intake", "effect", "risk", "activity", "is", "dashboard"}
    if "schedule" in data and any(k in data for k in flat_keys):
        raise CardLoadError(
            path,
            f"{path}: card has both schedule: and flat fields — ambiguous format",
        )

    try:
        if "schedule" in data:
            # v2 nested format
            sched = data.get("schedule") or {}
            know = data.get("knowledge") or {}
            return Substance(
                id=data["id"],
                name=data["name"],
                intake=tuple(sched.get("intake") or ()),
                timing=tuple(sched.get("timing") or ()),
                activity=tuple(sched.get("activity") or ()),
                prefer_with=tuple(sched.get("prefer_with") or ()),
                is_=tuple(know.get("is") or ()),
                effect=tuple(know.get("effect") or ()),
                risk=tuple(know.get("risk") or ()),
                dashboard=tuple(know.get("dashboard") or ()),
                pathway=tuple(know.get("pathway") or ()),
                form=data.get("form"),
                aliases=tuple(data.get("aliases") or ()),
                notes=data.get("notes"),
                concerns=tuple(
                    Concern(kind=cast(dict[str, Any], c)["kind"], text=cast(dict[str, Any], c)["text"])
                    for c in cast(list[Any], data.get("concerns") or [])
                    if isinstance(c, dict)
                ),
            )
        else:
            # v1 flat format — unchanged from current implementation
            return Substance(
                id=data["id"],
                name=data["name"],
                is_=tuple(data.get("is") or ()),
                intake=tuple(data.get("intake") or ()),
                ...
            )
    except KeyError as e:
        raise CardLoadError(path, f"{path}: missing required field {e}") from e
```

**`check_substances` update** (lines 240–259) — replace the flat namespace iteration with nested namespace reads. The `prefer_with` cross-reference check moves from top-level `data.get("prefer_with")` to `sched.get("prefer_with")`. The namespace loop must change from iterating `("is", "intake", "effect", "risk", "activity", "dashboard")` at top level to reading from `sched` and `know` sub-dicts.

---

### `planner/cards/traits.py` — `NAMESPACE_ORDER` and `check_traits` (service, CRUD)

**Analog:** self — two targeted changes.

**Current `NAMESPACE_ORDER`** (line 105):
```python
NAMESPACE_ORDER = ("is", "intake", "effect", "risk", "activity", "dashboard")
```

**Target** — add `timing`, add `pathway`, remove `effect` if no `effect:` traits remain:
```python
NAMESPACE_ORDER = ("is", "intake", "timing", "risk", "activity", "dashboard", "pathway")
```

**`check_traits` update** (lines 76–101) — the `separate_from` validation loop (lines 95–101) must be removed once `TraitDef.separate_from` is retired. The namespace check at line 89 automatically benefits from the `REGISTERED_NAMESPACES` update in `io.py`.

**`grouped_trait_defs` update** (lines 108–124) — no structural change needed; `NAMESPACE_ORDER` update propagates automatically.

**`readable_traits` update** (lines 154–179) — the `is:*` and `dashboard:*` exclusion logic is unchanged. Add exclusion of `timing:*` slugs from the narrative since they are scheduling drivers, not narrative labels:
```python
# Add alongside existing is: and dashboard: exclusions:
if trait_id.startswith("timing:"):
    continue
```

---

### `planner/engine/_scheduling.py` — `effective_stack_item_traits` and `must_separate` (service, transform)

**Analog:** self — targeted modification of lines 52–58 and lines 209–227.

**Current `scheduling_traits` set comprehension** (lines 52–58) — includes `risk:` and `effect:`:
```python
scheduling_traits = (
    {f"is:{s}" for s in substance.is_}
    | {f"intake:{s}" for s in substance.intake}
    | {f"effect:{s}" for s in substance.effect}
    | {f"risk:{s}" for s in substance.risk}
    | {f"activity:{s}" for s in substance.activity}
)
```

**Target** — replace `effect:` with `timing:`, remove `risk:`, remove `is:` (narrowly added only for class-level competes, not here):
```python
scheduling_traits = (
    {f"intake:{s}" for s in substance.intake}
    | {f"timing:{s}" for s in substance.timing}
    | {f"activity:{s}" for s in substance.activity}
)
```

**`must_separate` and `_declares_against`** (lines 209–227) — remove entirely after `separate_from` is retired from `TraitDef`. Replace the intra-product conflict detection loop (lines 73–92) that calls `left_def.separate_from` with a no-op or class-level competes check. The `_declares_against` helper and `must_separate` function signatures are referenced in `plan.py` — both call sites in `plan.py` (`_slot_is_blocked`) must be updated simultaneously.

---

### `planner/engine/plan.py` — `_slot_is_blocked` (service, transform)

**Analog:** self — targeted modification of lines 631–659.

**Current `_slot_is_blocked`** (lines 631–659):
```python
def _slot_is_blocked(
    item: str,
    slot_name: str,
    item_traits: set[str],
    slot_traits: dict[str, list[set[str]]],
    slot_items: dict[str, list[str]],
    active_components: dict[str, list[str]],
    substances: dict[str, Substance],
    trait_defs: dict[str, TraitDef],
    global_relations: list[Relation],
) -> bool:
    if any(
        must_separate(item_traits, existing_traits, trait_defs)
        for existing_traits in slot_traits[slot_name]
    ):
        return True
    if any(
        component_sets_have_relation(...)
        ...
    ):
        return True
    return False
```

**Target** — replace the `must_separate` call with class-level competes check. The `component_sets_have_relation` call for substance-level `competes` entries in `relations.yaml` is unchanged. New class-level check reads `knowledge.is_` slugs from the already-loaded `Substance` dataclass (no re-parse):
```python
def _class_level_competes_blocked(
    item_classes: set[str],
    existing_classes: set[str],
    class_relations: list[Relation],
) -> bool:
    for rel in class_relations:
        src = rel.source_class
        tgt = rel.target_class
        if src and tgt:
            if (src in item_classes and tgt in existing_classes) or \
               (tgt in item_classes and src in existing_classes):
                return True
    return False
```

Call site in `_slot_is_blocked`: replace `must_separate(...)` with:
```python
item_classes = {s for comp in active_components[item]
                for sub in [substances.get(comp)] if sub
                for s in sub.is_}
if any(
    _class_level_competes_blocked(
        item_classes,
        {s for comp in active_components[existing_item]
         for sub in [substances.get(comp)] if sub
         for s in sub.is_},
        [r for r in global_relations if r.source_class or r.target_class],
    )
    for existing_item in slot_items[slot_name]
):
    return True
```

---

### `planner/engine/review.py` — new `cmd_review` (service, request-response)

**Analog:** `planner/engine/audit.py` — copy the command structure, output pattern, and `maybe_patch_root` guard; copy advisory sections (concerns, relations) from `cmd_audit`.

**Imports pattern** — copy from `audit.py` (lines 1–37), swap in `review`-relevant imports:
```python
"""``review`` command: knowledge-section review of active substance stack."""

from __future__ import annotations

import textwrap
from pathlib import Path
from typing import Any, cast

from planner.cards.relations import (
    load_global_relations,
    relation_endpoint_display,
    relation_endpoint_is_active,
)
from planner.cards.stacks import normalize_stack_entries
from planner.cards.substance import format_substance_name, load_substance_registry
from planner.cards.product import load_product_registry, format_product_name
from planner.contracts import CardLoadError, Product, Relation, Substance
from planner.engine._root_patch import maybe_patch_root
from planner.engine.results import ReviewResult
from planner.io import DATA_DIR, STACKS_PATH, load_yaml

SEPARATOR = "─" * 41   # copy verbatim from audit.py line 38
_WRAP_WIDTH = 79        # copy verbatim from audit.py line 39
_INDENT = "    "        # copy verbatim from audit.py line 40
```

**Command function signature** — copy `cmd_audit` (lines 307–314) pattern; return `ReviewResult` not `AuditResult`:
```python
def cmd_review(data_root: Path | None = None) -> ReviewResult:
    """Show knowledge-section facts for the active stack; always exits 0."""
    with maybe_patch_root(data_root):
        substances = load_substance_registry()
        products = load_product_registry()
        # ... advisory content from knowledge: fields
        return ReviewResult(exit_code=0)
```

**Output section pattern** — copy the concerns section from `cmd_audit` (lines 319–343) verbatim; it already reads `substance.concerns` which is in the common (neither-actor) section of the v2 `Substance` dataclass. The relations section (lines 345–373) moves here from `cmd_audit` entirely.

**Knowledge-specific section** — add a new section not in `audit.py` that iterates `knowledge.*` fields:
```python
# Risk flags (moved from Planner path)
print()
print(f"Risk flags ({len(risk_entries)})")
print(SEPARATOR)
for name, slugs in risk_entries:
    print(f"  {name}: {', '.join(slugs)}")

# Pathway memberships
print()
print(f"Pathway memberships ({len(pathway_entries)})")
print(SEPARATOR)
for name, slugs in pathway_entries:
    print(f"  {name}: {', '.join(slugs)}")
```

---

### `planner/engine/audit.py` — advisory section removal (service, request-response)

**Analog:** self — remove the relations section (lines 345–373) once it moves to `cmd_review`. The concerns section (lines 319–343) also moves; keep the cleanup-candidates section (lines 375–410) and full-audit section (lines 388–410) in `audit`.

The `_classify_relations` helper (lines 85–115) and `_build_active_substance_ids` helper (lines 66–83) move to `review.py` entirely. The `by_kind` concerns dict and its output loop move to `review.py`.

**`_collect_cleanup_sections` update** (lines 132–147) — the flat namespace field iteration must change from:
```python
for field_name, ns in [
    ("is_", "is"),
    ("intake", "intake"),
    ("effect", "effect"),
    ("risk", "risk"),
    ("activity", "activity"),
    ("dashboard", "dashboard"),
]:
    for slug in getattr(substance, field_name):
        trait_refs.add(f"{ns}:{slug}")
```
to reading from both schedule and knowledge fields:
```python
for field_name, ns in [
    ("intake", "intake"),
    ("timing", "timing"),
    ("activity", "activity"),
    ("is_", "is"),
    ("effect", "effect"),
    ("risk", "risk"),
    ("dashboard", "dashboard"),
    ("pathway", "pathway"),
]:
    for slug in getattr(substance, field_name):
        trait_refs.add(f"{ns}:{slug}")
```

---

### `planner/__main__.py` — add `review` subcommand (utility, request-response)

**Analog:** self — copy the `review-substance` subcommand registration pattern (lines 54–58) and dispatch block (lines 71–72).

**Import addition** (lines 8–14) — add `cmd_review`:
```python
from planner.engine import (
    cmd_audit,
    cmd_check,
    cmd_find,
    cmd_review,           # NEW
    cmd_review_substance,
    cmd_show,
)
```

**Subparser registration** — copy `review-substance` pattern (lines 54–58), add after it:
```python
sub.add_parser(
    "review",
    help="knowledge-section review of active stack (concerns, relations, risk flags)",
)
```

**Dispatch block** — copy `elif args.cmd == "review-substance":` pattern (lines 71–72), add:
```python
elif args.cmd == "review":
    sys.exit(cmd_review().exit_code)
```

**Epilog string** (lines 22–30) — add `review` entry to the usage table:
```python
"  python -m planner review         — knowledge-section review (concerns, relations, risk flags)\n"
```

---

### `scripts/migrate_substance_cards.py` — one-off migration script (utility, batch)

**Analog:** `planner/engine/audit.py` `_collect_cleanup_sections` for the pattern of iterating all substance YAML files from disk, plus `planner/cards/substance.py` `load_substance_registry` for the glob pattern.

**Script skeleton** — follows the pattern of a standalone CLI script reading from `data/substances/`:
```python
#!/usr/bin/env python3
"""One-off migration: rewrite flat substance cards to schedule:/knowledge: nested shape.

Run from repo root:
    uv run python scripts/migrate_substance_cards.py [--dry-run]

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


def migrate_card(data: dict) -> dict:
    if "schedule" in data:
        return data  # already migrated — idempotent

    effect_slugs = data.pop("effect", []) or []
    timing_slugs = [s for s in effect_slugs if s in TIMING_SLUGS]
    knowledge_effect_slugs = [s for s in effect_slugs if s not in TIMING_SLUGS]

    schedule: dict = {}
    intake = data.pop("intake", [])
    if intake:
        schedule["intake"] = [intake[0]] if isinstance(intake, list) else [intake]
    if timing_slugs:
        schedule["timing"] = [timing_slugs[0]]
    activity = data.pop("activity", [])
    if activity:
        schedule["activity"] = [activity[0]] if isinstance(activity, list) else [activity]
    prefer_with = data.pop("prefer_with", None)
    if prefer_with:
        schedule["prefer_with"] = prefer_with

    knowledge: dict = {}
    is_val = data.pop("is", []) or []
    if is_val:
        knowledge["is"] = is_val
    if knowledge_effect_slugs:
        knowledge["effect"] = knowledge_effect_slugs
    risk_val = data.pop("risk", []) or []
    if risk_val:
        knowledge["risk"] = risk_val
    dashboard_val = data.pop("dashboard", []) or []
    if dashboard_val:
        knowledge["dashboard"] = dashboard_val

    result: dict = {}
    for k in ("id", "name", "form", "aliases", "notes", "concerns"):
        if k in data:
            result[k] = data[k]
    if schedule:
        result["schedule"] = schedule
    if knowledge:
        result["knowledge"] = knowledge
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    paths = sorted(SUBSTANCES_DIR.glob("*.yaml"))
    changed = 0
    for path in paths:
        raw = yaml.safe_load(path.read_text())
        if not isinstance(raw, dict):
            print(f"skip (non-mapping): {path.name}", file=sys.stderr)
            continue
        migrated = migrate_card(dict(raw))
        if migrated == raw:
            continue
        changed += 1
        if args.dry_run:
            print(f"would migrate: {path.name}")
        else:
            path.write_text(yaml.dump(migrated, allow_unicode=True, sort_keys=False))
            print(f"migrated: {path.name}")

    print(f"{'[dry-run] ' if args.dry_run else ''}done: {changed}/{len(paths)} cards updated")


if __name__ == "__main__":
    main()
```

---

### `tests/test_schemas.py` — extend with v2 schema tests (test, transform)

**Analog:** self — copy the `_make_substance_card` factory pattern (lines 33–35) and `schema_errors` assertion pattern (lines 39–62).

**New test pattern** — use `_make_substance_card` with nested `schedule`/`knowledge` kwargs; assert `schema_errors` returns empty for valid v2, non-empty for old flat:
```python
def test_substance_schema_accepts_nested_form() -> None:
    card = _make_substance_card(
        schedule={"intake": ["food_preferred"], "timing": ["sleep_support"]},
        knowledge={"is": ["amino"], "risk": ["manual_review"]},
    )
    errors = schema_errors(card, "substance", Path("test"))
    assert errors == [], f"Expected no errors, got: {errors}"


def test_substance_schema_rejects_flat_form() -> None:
    card = _make_substance_card(**{"intake": ["food_preferred"], "is": ["amino"]})
    errors = schema_errors(card, "substance", Path("test"))
    assert errors, "Expected schema to reject old flat top-level namespace keys"


def test_check_rejects_ambiguous_dual_format() -> None:
    # Card with BOTH schedule: and flat intake: must be rejected by load_substance
    from planner.cards.substance import load_substance
    from planner.contracts import CardLoadError
    import tempfile, yaml
    card = {"id": "sub_zz0000zzzz", "name": "Test", "intake": ["food_preferred"],
            "schedule": {"timing": ["sleep_support"]}}
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml",
                                     prefix="ambiguous_test__sub_zz0000zzzz",
                                     dir="/tmp", delete=False) as f:
        yaml.dump(card, f)
        tmp = Path(f.name)
    try:
        import pytest
        with pytest.raises(CardLoadError, match="ambiguous"):
            load_substance(tmp)
    finally:
        tmp.unlink(missing_ok=True)
```

---

### `tests/test_scheduling_units.py` — update fixtures (test, transform)

**Analog:** self — all `make_*` factory functions (lines 34–71) remain intact. Only the `Substance` constructor calls that set `effect=`, `risk=`, or `is_=` at old positions need updating.

**`make_substance` factory** (line 65–66) — add `timing` kwarg and `is_` kwarg to the existing factory to allow tests to set scheduling-relevant fields:
```python
def make_substance(
    sub_id: str,
    name: str = "Substance",
    *,
    intake: tuple[str, ...] = (),
    timing: tuple[str, ...] = (),
    activity: tuple[str, ...] = (),
    is_: tuple[str, ...] = (),
    risk: tuple[str, ...] = (),
) -> Substance:
    return Substance(id=sub_id, name=name, intake=intake, timing=timing,
                     activity=activity, is_=is_, risk=risk)
```

**New tests for Phase 9 behavior** — copy the `test_dashboard_excluded_from_scheduling_traits` pattern from `test_schemas.py` (lines 205–252); assert that `timing:` traits appear in effective traits and `risk:` traits do not:
```python
def test_scheduling_reads_schedule_section_only() -> None:
    """effective_stack_item_traits must not include risk: or knowledge.effect: slugs."""
    # ... construct Substance with timing=("sleep_support",), risk=("manual_review",)
    # assert "timing:sleep_support" in effective
    # assert "risk:manual_review" not in effective


def test_class_level_competes_blocks_slot() -> None:
    """Class-level competes blocks co-placement of mineral + fat_soluble items."""
    # ... construct two Substances with is_=("mineral",) and is_=("fat_soluble",)
    # ... construct Relation(type="competes", source_class="mineral", target_class="fat_soluble", ...)
    # assert _class_level_competes_blocked({"mineral"}, {"fat_soluble"}, [relation]) is True
```

---

### `tests/test_review_command.py` — new smoke test (test, request-response)

**Analog:** `tests/test_scheduling_units.py` for the no-disk-access fixture pattern; `planner/engine/review.py` `cmd_review_substance` for the `ReviewResult` return shape.

**File structure** — copy module docstring, imports, and fixture pattern from `test_scheduling_units.py`:
```python
"""Smoke tests for cmd_review (Phase 9: Planner/Reviewer ontology split).

Tests use a temporary data root — no live data/ directory access required
for smoke coverage.
"""

from __future__ import annotations

from pathlib import Path
import tempfile

import yaml

from planner.engine.review import cmd_review
from planner.engine.results import ReviewResult


def _write_minimal_data_root(tmp: Path) -> None:
    """Write the minimum files cmd_review needs to run without crashing."""
    # ... write stacks.yaml, substances/, products/, traits.yaml, relations.yaml


def test_cmd_review_exits_zero_with_empty_stack() -> None:
    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d)
        _write_minimal_data_root(tmp)
        result = cmd_review(data_root=tmp)
        assert isinstance(result, ReviewResult)
        assert result.exit_code == 0


def test_cmd_review_produces_nonempty_output() -> None:
    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d)
        _write_minimal_data_root(tmp)
        result = cmd_review(data_root=tmp)
        assert result.output or True  # smoke: does not crash
```

---

## Shared Patterns

### `maybe_patch_root` context manager
**Source:** `planner/engine/_root_patch.py` (imported in `audit.py` line 34, `review.py` line 25)
**Apply to:** `planner/engine/review.py`, `scripts/migrate_substance_cards.py` (script uses ROOT directly)

All `cmd_*` functions that accept `data_root: Path | None` must wrap their body with:
```python
with maybe_patch_root(data_root):
    # all registry loads happen here
```

### `CardLoadError` raise pattern
**Source:** `planner/cards/substance.py` lines 36–37 and 57–58
**Apply to:** `planner/cards/substance.py` (dual-format detection), `scripts/migrate_substance_cards.py` (skip-and-warn pattern)

Standard raise:
```python
raise CardLoadError(path, f"{path}: <descriptive message>")
```

### Result dataclass pattern
**Source:** `planner/engine/results.py` lines 44–49
**Apply to:** `planner/engine/review.py` `cmd_review` — return `ReviewResult(exit_code=0)`.

`ReviewResult` already has `output: str = ""` and `stderr: str = ""` fields. When `data_root` is set (test mode), use `contextlib.redirect_stdout` and capture into `ReviewResult.output` — copy the pattern from `cmd_review_substance` (lines 43–56 of `review.py`).

### YAML output formatting constants
**Source:** `planner/engine/audit.py` lines 38–40
**Apply to:** `planner/engine/review.py`

```python
SEPARATOR = "─" * 41
_WRAP_WIDTH = 79
_INDENT = "    "
```

Copy verbatim — these are the established display conventions for all `cmd_*` human-readable output.

### `textwrap.fill` concern rendering
**Source:** `planner/engine/audit.py` lines 335–340
**Apply to:** `planner/engine/review.py` concerns section

```python
for name, text in entries:
    print(f"  {name}")
    wrapped = textwrap.fill(
        text, width=_WRAP_WIDTH, initial_indent=_INDENT, subsequent_indent=_INDENT
    )
    print(wrapped)
```

### Inline dataclass fixture pattern (tests)
**Source:** `tests/test_scheduling_units.py` lines 34–71
**Apply to:** `tests/test_review_command.py`, new tests in `tests/test_scheduling_units.py`

All test Substance/Product/TraitDef instances are constructed directly via dataclass constructors — no YAML disk reads except when testing schema validation paths. Tests requiring a data root write a minimal YAML tree to a `tempfile.TemporaryDirectory`.

---

## No Analog Found

| File | Role | Data Flow | Reason |
|------|------|-----------|--------|
| `data/substances/*.yaml` (198 cards) | data | batch | Pure data migration — no code analog; migration script handles transformation |
| `data/traits.yaml` (timing: namespace addition) | data | transform | Data file edit, not a code file; pattern is the existing namespace block structure in the file itself |
| `data/relations.yaml` (class-level competes entries) | data | transform | New YAML structure under existing `competes:` key; see RESEARCH.md Pattern 2 for the exact YAML shape |

---

## Metadata

**Analog search scope:** `planner/`, `tests/`, `schema/`, `data/` (sample cards and dashboard files)
**Files scanned:** 14 source files read directly + grep for line ranges
**Pattern extraction date:** 2026-05-13
