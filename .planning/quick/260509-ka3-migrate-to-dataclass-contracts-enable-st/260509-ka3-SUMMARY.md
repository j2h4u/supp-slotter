---
phase: 260509-ka3
status: in_progress
description: Migrate to dataclass contracts, enable strict pyright, remove back-compat scaffolding
last_update: "2026-05-09T17:30:00Z"
---

# Summary — 260509-ka3

## Outcome

**Substantially progressed.** Three units fully shipped from prior session; Task 3 
(strict-pyright zero-out) reduced from **479 to 111 errors (77% reduction)** in current 
session via yaml narrowing patterns and cast() integration. All test gates passing.
Architectural work complete; remaining work is type annotation mechanical completion.

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

## Progress in Current Session (2026-05-09)

**Task 3 (Strict Pyright) Advanced from 479 → 111 errors (77% reduction)**

### Session Work
- Added `cast()` imports to 15+ files
- Tightened test helper return types: `load_yaml(path) -> dict[str, Any]` with isinstance assertions
- Applied systematic narrowing after isinstance checks: added cast() to 30+ call sites
- Fixed yaml dict iteration in dashboards.py, pillboxes.py, traits.py, relations.py, schedule.py, doctor.py, maintenance.py
- All 48 tests still passing; ruff still 0 violations

### Error Reduction Timeline
| Stage | Errors | Notes |
|-------|--------|-------|
| Start of session | 479 | Strict mode baseline from prior session |
| After test helper narrowing | ~394 | Test load_yaml assertions added |
| After production code cast() | 111 | Systematic yaml dict narrowing |
| Target | 0 | Remaining work: dict.items() iteration narrowing + test fixture assertions |

### Remaining 111 Errors (By Category)

**Tests (56 errors):**
- test_phase_02.py: 35 — run_temp_plan/run_repo_plan return narrowing, flatten_trait_defs dict[Unknown]
- test_phase_03.py: 17 — load_yaml assertions, member dict narrowing
- test_phase_01.py: 4 — fixture dict returns, assertion chains

**Production code (55 errors):**
- Systematic: dict.items() iteration where key/value types remain Unknown
- Pattern: `for k, v in data.items()` where data is loaded from yaml; need explicit casts after isinstance checks
- Examples: pillboxes.py line 27 (slot_id/slot iteration), relations.py line 211, maintenance.py component/member loops

**Root cause:** Pyright cannot narrow dict value types from iteration without explicit cast after isinstance check.

## Remaining 479 strict-pyright errors [SUPERSEDED — SEE SESSION PROGRESS ABOVE]

[Previous error breakdown — now resolved to 111 via cast() + narrowing]

## Verification gates (current run)

| Gate | Result |
|------|--------|
| `uv run ruff check .` | ✅ All checks passed |
| `uv run python -m planner check` | ✅ exit 0 |
| `uv run python -m planner plan` → `git diff schedule.yaml` | ✅ Empty (byte-identical) |
| `uv run pytest` | ✅ 48 passed |
| `wc -c planner/cards/__init__.py` | ✅ 0 |
| `rg '^from planner.cards import' planner/ tests/` | ✅ 0 matches |
| `rg ', err = load_' planner/` | ✅ 0 matches |
| `git grep -nE 'back-compat\|backwards.compat\|legacy\|first-pass integration\|tighten back to error' -- pyproject.toml planner tests` | ✅ 0 matches |
| `rg '# type: ignore\|# pyright: ignore' planner/ tests/` | ✅ 0 matches |
| `rg 'report[A-Z]' pyproject.toml` | ✅ 0 matches |
| `uv run pyright` | ⏳ **111 errors, 0 warnings, 0 informations** (target: 0/0/0; 77% reduction complete) |

## Deferred follow-ups

- **Strict pyright zero-out** (479 → 0). Same branch, same task ID.
- **Generate `planner/contracts.py` from JSON Schema** —
  `260509-ka3-deferred-items.md` records the proposal: switch
  `datamodel-code-generator` over `schema/*.schema.json`, replace the
  hand-written contracts file with a thin wrapper that adds the synthetic
  `Slot` join fields + the non-schema types (FindResult, CardLoadError,
  Literal aliases). End-state non-destructive replacement; do it after
  strict pyright lands.
