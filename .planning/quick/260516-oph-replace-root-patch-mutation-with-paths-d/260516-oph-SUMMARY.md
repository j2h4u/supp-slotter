---
status: complete
quick_id: 260516-oph
plan: 260516-oph-01
date: 2026-05-16
commit: 2e18b7e
---

# Quick Task 260516-oph: Replace `_root_patch` mutation with `Paths` dataclass threading

## Outcome

Module-level path-constant mutation across a hardcoded module registry replaced
with an explicit `Paths` dataclass threaded through every loader and command.
`planner/engine/_root_patch.py` deleted. `schedule.yaml` regenerates
byte-identical against live `data/`. `just check` green: 107/107 tests, ruff
clean, pyright strict 0/0/0.

## Changes

### `planner/io.py`

- Added `@dataclass(frozen=True, slots=True) class Paths` with 9 fields
  (`root`, `data_dir`, `substances_dir`, `products_dir`, `dashboards_dir`,
  `stacks_path`, `relations_path`, `schedule_path`, `maintenance_lock_dir`).
- Added classmethods `Paths.from_root(root: Path)` and `Paths.default()`
  (anchored at the planner package's repo root).
- Removed eight module-level path constants: `DATA_DIR`, `SUBSTANCES_DIR`,
  `PRODUCTS_DIR`, `DASHBOARDS_DIR`, `STACKS_PATH`, `RELATIONS_PATH`,
  `SCHEDULE_PATH`, `MAINTENANCE_LOCK_DIR`.
- Kept `ROOT` (used by `Paths.default()`) and `SCHEMA_DIR` (static schemas,
  not test-redirected) as module-level.
- `validate_schemas()` now takes `paths: Paths`.

### Loaders updated to take `paths: Paths`

`planner/cards/stacks.py`, `planner/cards/substance.py`,
`planner/cards/product.py`, `planner/cards/dashboards.py`,
`planner/cards/relations.py`, `planner/cards/relations_surreal.py`,
`planner/maintenance.py`.

Each call site within these modules switched from module-level constant access
(e.g. `STACKS_PATH`) to dataclass field access (`paths.stacks_path`).

### Command entry points

`planner/engine/audit.py`, `planner/engine/check.py`, `planner/engine/plan.py`,
`planner/engine/_plan_inputs.py`, `planner/engine/review.py`,
`planner/engine/show.py`.

Each `cmd_*` function keeps its external API (`data_root: Path | None = None`),
constructs `paths = Paths.from_root(data_root) if data_root else Paths.default()`
at the top, and threads `paths` into every internal call. The
`maybe_patch_root(data_root)` context manager wrappers were removed.

### `planner/__main__.py`

`main()` now accepts `data_root: Path | None = None` and forwards it to the
dispatched `cmd_*`. This is the seam tests use to redirect to `tmp_path`.

### Deletions

- `planner/engine/_root_patch.py` deleted (was 81 lines): `_MODULES` registry,
  `patch_planner_root`, `maybe_patch_root` all gone.
- Every `from planner.engine._root_patch import maybe_patch_root` import
  removed across the codebase.

### Tests

- `tests/helpers.run_planner` rewritten to call `main(data_root=root)` directly
  — no more module patching.
- `tests/test_maintenance.py` and `tests/test_schemas.py` updated to construct
  `Paths.from_root(tmp_path)` for their fixture data roots.

## Hard invariants verified

- `planner/engine/_root_patch.py` absent (grep returns no matches)
- No `from planner.io import DATA_DIR` (or any of the seven deleted constants)
  anywhere in the codebase
- `class Paths` present in `planner/io.py` with both `from_root` and `default`
  factories
- No references to `maybe_patch_root` or `patch_planner_root` in the tree
- All seven `cmd_*` entry points still accept `data_root: Path | None = None`
- `tests/helpers.run_planner` calls `main(data_root=root)` (no patching)
- `schedule.yaml` byte-identical against pre-refactor (verified via diff
  against a pre-task stash)
- `just check` exits 0: ruff clean, pyright strict 0 errors / 0 warnings, 107
  tests pass in ~24s

## Anti-pattern eliminated

The "forgot to add new module to `_MODULES`" silent-failure mode (cost a test
cycle during the SurrealDB POC; the planner.engine._plan_inputs.py extraction
this morning also had to remember to add the new module to `_MODULES`) is now
structurally impossible — there is no registry to forget. New loaders simply
take `paths: Paths` as a parameter; the type checker enforces it.

## Closes

CONCERNS.md entry "Global path patching for tests" — the documented
"fix approach" is now implemented.
