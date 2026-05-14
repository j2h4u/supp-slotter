# Coding Conventions

**Analysis Date:** 2026-05-14

## Naming Patterns

**Files:**
- Use snake_case Python module names under `planner/`, such as `planner/engine/_scheduling.py`, `planner/cards/substance.py`, and `planner/maintenance.py`.
- Prefix private implementation modules with `_` when they are internal support code, such as `planner/engine/_root_patch.py`, `planner/engine/_scheduling.py`, and `planner/cards/_common.py`.
- Name tests by behavior area with `test_*.py`, such as `tests/test_scheduling_units.py`, `tests/test_schemas.py`, and `tests/test_review_command.py`.
- Keep one-off operational scripts under `scripts/`, such as `scripts/card_audit.py` and `scripts/migrate_substance_cards.py`.

**Functions:**
- Use snake_case for functions and command handlers, such as `planner.engine.check.cmd_check`, `planner.engine.plan._build_active_index`, and `planner.cards.substance.load_substance`.
- Prefix private helpers with `_`, such as `planner.engine.plan._load_plan_inputs`, `planner.engine.plan._resolve_prefer_pairs`, and `planner.cards.substance._substance_fallback_name`.
- Use `cmd_<name>` for public CLI command entrypoints returning result dataclasses, such as `cmd_check`, `cmd_audit`, `cmd_review`, `cmd_show`, and `cmd_find` in `planner/engine/`.
- Use `load_<entity>`, `check_<entity>`, `collect_<thing>`, `build_<thing>`, and `format_<thing>` verbs consistently in card modules, such as `planner/cards/product.py`, `planner/cards/dashboards.py`, and `planner/cards/relations.py`.

**Variables:**
- Use snake_case local names and explicit collection names, such as `trait_defs`, `stack_entries`, `global_relations`, `dashboard_files`, `item_traits`, and `secondary_traits_by_item` in `planner/engine/plan.py`.
- Use uppercase module constants for shared configuration and path constants, such as `ROOT`, `DATA_DIR`, `SCHEMA_DIR`, `STACKS_PATH`, `LEVEL_SCORES`, and `WARNING_CATEGORY_LABELS` in `planner/io.py`.
- Use short domain IDs only when they mirror persisted YAML identifiers, such as `sid`, `prd_id`, `sub_id`, and `card_id` in `planner/cards/substance.py`, `planner/cards/product.py`, and `tests/test_phase_02.py`.

**Types:**
- Model stable YAML inputs as frozen dataclasses with slots in `planner/contracts.py`, for example `Substance`, `Product`, `ProductComponent`, `Dashboard`, `Relation`, `TraitDef`, `Slot`, and `Pillbox`.
- Use `NamedTuple` for tuple-shaped structured internal bundles in `planner/engine/plan.py`, such as `PlanInputs` and `ActiveIndex`.
- Use result dataclasses for command outputs in `planner/engine/results.py`, such as `CheckResult`, `PlanResult`, `ReviewResult`, and `AuditResult`.
- Use `Literal` aliases for constrained domain strings in `planner/contracts.py`, such as `SlotNear`, `RelationType`, `Severity`, and `ConcernKind`.

## Code Style

**Formatting:**
- Use Ruff formatting via `uv run ruff format .`; the command is declared in `justfile`.
- Use a 120-column line length from `[tool.ruff]` in `pyproject.toml`.
- Target Python 3.11 from `[project].requires-python`, `[tool.ruff].target-version`, and `[tool.pyright].pythonVersion` in `pyproject.toml`.
- Keep `from __future__ import annotations` at the top of Python modules, as used in `planner/io.py`, `planner/contracts.py`, `planner/engine/plan.py`, and all test files under `tests/`.

**Linting:**
- Use Ruff via `uv run ruff check .`; `justfile` exposes this as `just lint`.
- Enforced Ruff rule groups in `pyproject.toml` are `E`, `F`, `I`, `B`, and `UP`.
- `E501` is ignored in `pyproject.toml`; keep long docstrings readable when wrapping would hurt clarity.
- Keep imports sortable by Ruff/isort. Do not hand-maintain unusual import grouping unless Ruff accepts it.
- Use narrowly scoped suppressions with an inline reason only where needed, such as `# noqa: PLC0415` in `tests/helpers.py`, `# noqa: C901` in `planner/engine/review.py`, and `# type: ignore[reportPrivateUsage]` in `tests/test_scheduling_units.py`.

## Import Organization

**Order:**
1. Future imports: `from __future__ import annotations`, as in `planner/engine/check.py`.
2. Standard library imports: `sys`, `Path`, `Any`, `cast`, `contextlib`, `io`, `tempfile`, and similar modules.
3. Third-party imports: `yaml`, `pytest`, and `jsonschema` where needed.
4. First-party imports from `planner.*` and `tests.*`, as in `planner/engine/plan.py` and `tests/test_phase_02.py`.

**Path Aliases:**
- No Python package path aliases are configured in `pyproject.toml`.
- Tests add the repo root to `sys.path` in `tests/conftest.py`; use normal absolute imports such as `from planner.engine import cmd_check` and `from tests.helpers import run_planner`.
- Use `planner.engine.__init__` exports for command/result imports in tests when the symbol is re-exported, as seen in `tests/test_phase_02.py`.

## Error Handling

**Patterns:**
- Raise `planner.contracts.CardLoadError` for YAML card read, parse, schema, and required-field failures; include the file path in the message, as in `planner/io.py`, `planner/cards/_common.py`, `planner/cards/substance.py`, and `planner/cards/product.py`.
- Wrap low-level exceptions with cause chaining using `raise ... from e`, as in `planner/io.py`, `planner/cards/substance.py`, `planner/cards/dashboards.py`, and `planner/cards/pillboxes.py`.
- Return structured command result dataclasses with `exit_code` instead of forcing callers to parse stdout, as in `planner/engine/check.py`, `planner/engine/plan.py`, `planner/engine/review.py`, and `planner/engine/results.py`.
- Print operator-facing command errors to `stderr` and status/info to `stdout`, using `planner.io.report` for check-style output and explicit `print(..., file=sys.stderr)` in command modules.
- For recoverable scan paths, skip malformed cards with visible warnings and continue, as in `planner/cards/substance.py`, `planner/cards/product.py`, `planner/cards/dashboards.py`, and `planner/maintenance.py`.
- Use `None` only for meaningful sentinel outcomes, such as `auto_maintenance_needed` returning `bool | None` in `planner/maintenance.py`; tests cover this distinction in `tests/test_maintenance.py`.

## Logging

**Framework:** console

**Patterns:**
- Use direct `print()` for CLI output in `planner/engine/show.py`, `planner/engine/review.py`, `planner/engine/audit.py`, `planner/engine/find.py`, and `planner/cards/relations.py`.
- Use `print(..., file=sys.stderr)` for warnings and errors in `planner/io.py`, `planner/engine/check.py`, `planner/engine/plan.py`, `planner/maintenance.py`, and loader/search modules.
- Do not introduce a logging framework unless the command surface changes from local CLI behavior; no `logging` usage is present under `planner/` or `tests/`.

## Comments

**When to Comment:**
- Use module docstrings to state ownership and command purpose, as in `planner/io.py`, `planner/contracts.py`, `planner/engine/plan.py`, and `planner/engine/audit.py`.
- Use short comments for non-obvious domain or safety constraints, such as `SECONDARY_TRAIT_WEIGHT` in `planner/io.py`, `SCHEMA_DIR` behavior in `planner/engine/_root_patch.py`, and schema migration notes in `tests/test_schemas.py`.
- Keep comments tied to current behavior and file paths. Avoid historical notes unless they explain an active compatibility or test constraint in files such as `tests/test_scheduling_units.py`.

**JSDoc/TSDoc:**
- Not applicable. This repository is Python-only for application code.
- Use Python docstrings on public helpers, command handlers, loader functions, and tests with subtle domain rules, as in `planner/cards/search.py`, `planner/cards/substance.py`, `planner/engine/check.py`, and `tests/test_review_command.py`.

## Function Design

**Size:** Keep pure helper functions small and single-purpose in card modules such as `planner/cards/search.py`, `planner/cards/_common.py`, and `planner/cards/schedule.py`. Larger orchestration functions are acceptable in CLI flows such as `planner/engine/plan.py` and `planner/engine/review.py` when they assemble many domain checks.

**Parameters:** Pass `Path` objects for filesystem roots and files, not raw strings, in core functions such as `cmd_check(data_root: Path | None)`, `cmd_plan(data_root: Path | None)`, `load_substance(path: Path)`, and `patch_planner_root(new_root: Path)`.

**Return Values:** Prefer typed dataclasses, tuples with documented meaning, or explicit dictionaries of domain records:
- Command functions return result dataclasses from `planner/engine/results.py`.
- Validation functions return lists/tuples such as `(errors, info, seen_ids)` in `planner/cards/substance.py` and `planner/cards/product.py`.
- Planner assembly helpers return `NamedTuple` bundles or `None` on early failure in `planner/engine/plan.py`.

## Module Design

**Exports:** Keep domain contracts centralized in `planner/contracts.py`, result contracts in `planner/engine/results.py`, path/config constants in `planner/io.py`, and CLI command implementations in `planner/engine/`.

**Barrel Files:** Use package `__init__.py` files as narrow re-export surfaces:
- `planner/engine/__init__.py` exposes command handlers and result types for tests and CLI modules.
- `planner/cards/__init__.py` is present but card logic lives in entity modules such as `planner/cards/product.py`, `planner/cards/substance.py`, and `planner/cards/relations.py`.
- Avoid adding broad `utils` modules. Put shared card helpers in `planner/cards/_common.py`, shared search helpers in `planner/cards/search.py`, and shared test helpers in `tests/helpers.py`.

---

*Convention analysis: 2026-05-14*
