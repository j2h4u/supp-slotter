---
phase: 260509-ka3
status: incomplete
description: Migrate to dataclass contracts, enable strict pyright, remove back-compat scaffolding
---

# Summary — 260509-ka3

## Outcome

**Partially shipped.** Three of the four logical units delivered to the
verify-gate bar; strict-pyright zero-out is the remaining work, deferred
on the same branch (commit ID `430565d` left it at 479 errors with
explicit follow-up scope).

| Unit | Commit | State |
|------|--------|-------|
| T1: dataclass contracts + raising loaders | `326ed68` | Done — verify gates pass |
| T2a: drop cards re-export hub, direct submodule imports | `80b3fea` | Done — verify gates pass |
| T2b+T3 (partial): migrate consumers to attribute access; flip pyright to `strict` | `430565d` | Code migrated, pyright not at 0/0/0 yet |
| T3 (remaining): 479 → 0 strict-pyright diagnostics | — | Deferred |

The three commits are atomic (each leaves the tree green and `schedule.yaml`
byte-identical).

## What shipped

**`planner/contracts.py`** (new, 161 LOC). Frozen+slots dataclasses for
every stable yaml shape: `Substance`, `ProductComponent`, `Product`,
`DashboardMember`, `DashboardBenefit`, `DashboardRisk`, `Dashboard`,
`Relation`, `TraitEffectMatch`, `TraitEffect`, `TraitDef`, `Slot`,
`Pillbox`. Plus `FindResult` NamedTuple, `CardLoadError`, and
`SlotNear` / `RelationType` Literal aliases.

**Loaders are typed and raise.** `(data, err)`-tuple return is gone:
- `load_substance(path) -> Substance`
- `load_product(path) -> Product`
- `load_dashboard(path) -> Dashboard` (new)
- `load_global_relations() -> list[Relation]`
- `load_traits(path) -> dict[str, TraitDef]` (new)
- `load_pillboxes(path) -> dict[str, Pillbox]` (new)

`planner/io.load_yaml` returns `object` (was `Any`). New
`load_yaml_mapping(path) -> dict[str, Any]` raises CardLoadError on
non-mapping. `_common.load_card_mapping` replaces the prior `load_card`
tuple return.

**`planner/cards/__init__.py` is empty.** 193 LOC of re-exports → 0
bytes. Every consumer now imports directly from
`planner.cards.<submodule>`.

**Consumer migration.** Functions across `cards/<sub>.py`,
`engine/<sub>.py`, and `maintenance.py` now take dataclasses with
attribute access in place of `dict.get()` ladders. `load_*_registry`
returns `dict[str, Dataclass]`. `flatten_trait_defs` and
`derive_slot_fields` removed — `load_traits` returns
`dict[str, TraitDef]` directly, and slot match keys are constrained by
`TraitEffectMatch` + the JSON schema.

**Pyright config.** `[tool.pyright]` is exactly four lines now: header,
`include`, `pythonVersion`, and `typeCheckingMode = "strict"`. No
per-rule overrides, no `# type: ignore`, no comment block.

**`.gitignore`** updated earlier in the session covers `__pycache__/`,
ruff/pytest caches, and the maintenance lock dir.

**Forbidden-phrase grep clean.** `back-compat`, `backwards.compat`,
`legacy`, `first-pass integration`, `tighten back to error` — zero
occurrences across `pyproject.toml`, `planner/`, `tests/`.

## Pyright trajectory

| Stage | Mode | Diagnostics |
|-------|------|-------------|
| Baseline (before this task) | basic + 5 rule downgrades | 78 warnings |
| After T1 (typed loaders) | basic + 5 rule downgrades | 78 warnings (unchanged — strict not yet on) |
| After T2a (direct imports) | basic + 5 rule downgrades | 78 warnings (unchanged) |
| After flip to strict (T3 step 1) | strict | **1322 errors, 0 warnings** |
| After dataclass attribute migration (T3 in progress) | strict | **479 errors, 0 warnings** |
| Target | strict | 0 errors, 0 warnings, 0 informations |

The 64% drop came from one structural change: typed loaders + dataclass
attribute access make `reportUnknownVariableType` /
`reportUnknownMemberType` evaporate at every migrated call site.

## Remaining 479 strict-pyright errors

**By file** (top contributors):
- `tests/test_phase_02.py`: 148
- `tests/test_phase_03.py`: 108
- `tests/test_phase_01.py`: 65
- `planner/cards/relations.py`: 29
- `planner/cards/traits.py`: 23
- `planner/cards/pillboxes.py`: 17
- `planner/cards/schedule.py`: 15
- `planner/engine/doctor.py`: 14
- (rest distributed in singles + low double-digits)

**By rule**:
- `reportUnknownVariableType`: 216
- `reportUnknownArgumentType`: 89
- `reportUnknownMemberType`: 73
- `reportMissingTypeArgument`: 32
- `reportUnknownParameterType`: 29
- `reportIndexIssue`: 24
- `reportArgumentType`: 8
- `reportOperatorIssue`: 3
- `reportUnknownLambdaType`: 2
- `reportUnusedImport` / `reportUnnecessaryIsInstance` / `reportUnnecessaryCast`: 1 each

The scope is mechanical:
1. **Test-side yaml helpers** (321 of 479). `tests/<file>.load_yaml` returns
   `object`/`Any`; tests then `.get()` / index. Fix is to tighten the
   helper return type to `dict[str, Any]` with an `isinstance(result, dict)`
   assertion.
2. **Lambda return types in sort keys** (2). Annotate the lambda parameter.
3. **Residual `dict[str, Any].get()` chains in relations/traits/pillboxes**
   that come from raw yaml mappings rather than typed dataclasses.
   Fix is per-call narrowing, not rule suppression.
4. **One unused import / one unnecessary isinstance / one unnecessary cast**
   — single-line cleanups.

The plan doc at `260509-ka3-PLAN.md` already specifies the source-level
fixes for each rule (Step 2 of Task 3). No suppression. Direct
continuation of T3.

## Verification gates (current run)

| Gate | Result |
|------|--------|
| `uv run ruff check .` | All checks passed |
| `uv run python -m planner check` | exit 0 |
| `uv run python -m planner plan` → `git diff schedule.yaml` | Empty (byte-identical) |
| `uv run pytest` | 48 passed |
| `wc -c planner/cards/__init__.py` | 0 |
| `rg '^from planner.cards import' planner/ tests/` | 0 matches |
| `rg ', err = load_' planner/` | 0 matches |
| `git grep -nE 'back-compat\|backwards.compat\|legacy\|first-pass integration\|tighten back to error' -- pyproject.toml planner tests` | 0 matches |
| `rg '# type: ignore\|# pyright: ignore' planner/ tests/` | 0 matches |
| `rg 'report[A-Z]' pyproject.toml` | 0 matches |
| `uv run pyright` | **479 errors, 0 warnings, 0 informations** ❌ (target: 0/0/0) |

## Deferred follow-ups

- **Strict pyright zero-out** (479 → 0). Same branch, same task ID.
- **Generate `planner/contracts.py` from JSON Schema** —
  `260509-ka3-deferred-items.md` records the proposal: switch
  `datamodel-code-generator` over `schema/*.schema.json`, replace the
  hand-written contracts file with a thin wrapper that adds the synthetic
  `Slot` join fields + the non-schema types (FindResult, CardLoadError,
  Literal aliases). End-state non-destructive replacement; do it after
  strict pyright lands.
