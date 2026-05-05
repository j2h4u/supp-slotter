# Coding Conventions

**Analysis Date:** 2026-05-05

## Naming Patterns

**Files:**
- Use snake_case for Python modules and tests: `planner.py`, `tests/test_phase_01.py`.
- Use snake_case YAML ids and filenames for substances and goals: `data/products/l_citrulline_malate.yaml`, `data/goals/vascular_health.yaml`.
- Keep JSON Schema filenames aligned with the model name plus `.schema.json`: `schema/product.schema.json`, `schema/goal.schema.json`.

**Functions:**
- Use snake_case verbs for command handlers and validators: `cmd_check`, `cmd_refresh`, `cmd_plan`, `schema_errors`, `check_products` in `planner.py`.
- Prefix CLI subcommand implementations with `cmd_`: `cmd_check`, `cmd_refresh`, `cmd_plan` in `planner.py`.
- Prefix validation helpers with `check_` when they return domain errors: `check_traits`, `check_inventory_alignment`, `check_inventory_overrides`, `check_goals` in `planner.py`.
- Use small loader/helper names for repeated I/O operations: `load_yaml`, `load_schema`, `load_product` in `planner.py` and `tests/test_phase_01.py`.

**Variables:**
- Use snake_case for local variables and compact domain abbreviations where the loop scope is obvious: `slots_data`, `traits_data`, `product_files`, `trait_ids`, `pf`, `pid`, `sid` in `planner.py`.
- Use module-level UPPER_SNAKE_CASE for constants and paths: `ROOT`, `DATA_DIR`, `SCHEMA_DIR`, `PRODUCTS_DIR`, `INVENTORY_PATH`, `SCHEDULE_PATH`, `VALID_LEVELS`, `REGISTERED_NAMESPACES`, `LEVEL_SCORES` in `planner.py`.
- Use id strings as stable cross-file keys. Product ids, inventory ids, and filenames must match: `data/products/l_citrulline_malate.yaml`, `data/inventory.yaml`, `planner.py`.

**Types:**
- Use built-in collection generics and union syntax: `list[str]`, `dict[str, Path]`, `tuple[dict | None, str | None]` in `planner.py`.
- Use broad `object` return types when YAML content is not yet validated: `load_yaml` in `planner.py` and `tests/test_phase_01.py`.
- Use `from __future__ import annotations` in tests: `tests/test_phase_01.py`.
- No custom classes, dataclasses, protocols, or type aliases are currently used.

## Code Style

**Formatting:**
- No formatter configuration is present. Not detected: `pyproject.toml`, `ruff.toml`, `.prettierrc`, `.eslintrc*`, `biome.json`.
- Existing Python style follows Black-like formatting: 4-space indentation, blank lines between top-level functions, wrapped function signatures, and line lengths generally kept readable in `planner.py` and `tests/test_phase_01.py`.
- Preserve PEP 723 inline script metadata at the top of `planner.py`; dependencies and Python version live there instead of in `pyproject.toml`.
- Always specify UTF-8 encoding when adding new file I/O even though current `Path.read_text()` / `write_text()` calls in `planner.py` omit it.

**Linting:**
- No lint configuration is detected.
- Keep code lint-clean by following existing style: module-level imports, no unused imports, explicit return annotations for functions, and no broad exception handlers except around YAML parsing in `planner.py`.
- Prefer pathlib for all filesystem work. Existing code uses `Path` throughout `planner.py` and `tests/test_phase_01.py`.

## Import Organization

**Order:**
1. Future imports when needed: `from __future__ import annotations` in `tests/test_phase_01.py`.
2. Standard library imports: `argparse`, `json`, `sys`, `subprocess`, `collections.Counter`, `pathlib.Path`.
3. Third-party imports: `jsonschema`, `yaml`.
4. Local imports: not applicable; this repo is a single script with no package modules.

**Path Aliases:**
- Not detected. There is no package layout and no import alias configuration.
- Use root-relative `Path` constants rather than import aliases: `ROOT`, `DATA_DIR`, `SCHEMA_DIR`, `PRODUCTS_DIR`, `GOALS_DIR` in `planner.py`.

## Error Handling

**Patterns:**
- Validators collect user-facing error strings in `list[str]` and return them instead of raising: `schema_errors`, `check_traits`, `check_products`, `check_inventory_alignment`, `check_inventory_overrides`, `check_goals` in `planner.py`.
- CLI commands convert validation outcomes to exit codes through `report(errors, info)` in `planner.py`.
- Use LBYL checks for expected domain failures: `Path.exists()`, `isinstance(..., dict)`, membership checks, and explicit empty-file checks in `planner.py`.
- Catch only parser-level `yaml.YAMLError` where third-party YAML parsing can fail: `load_product` and `check_goals` in `planner.py`.
- Use stderr for errors and warnings, stdout for successful output and INFO lines: `report`, `cmd_refresh`, `cmd_plan` in `planner.py`.
- Return `1` for CLI failures and `0` for success from command handlers: `cmd_check`, `cmd_refresh`, `cmd_plan` in `planner.py`.

## Logging

**Framework:** console

**Patterns:**
- Use `print(..., file=sys.stderr)` for hard errors, warnings, and progress banners: `cmd_refresh`, `cmd_plan`, `report` in `planner.py`.
- Use stdout for successful command summaries: `All checks passed.`, `inventory is in sync; no new supplements found`, `schedule written to ...` in `planner.py`.
- Use `INFO:` prefixed lines for non-fatal taxonomy gaps from `unmatched_concerns`: `check_products` and `report` in `planner.py`.
- No structured logging framework is present.

## Comments

**When to Comment:**
- Use comments to label domain sections and algorithm stages, not to restate single lines: `# Inventory cross-check`, `# Symmetric prefer_with pairs`, `# Candidate slots per substance`, `# Most-constrained-first ordering` in `planner.py`.
- YAML files use comments as operator-facing section headers and taxonomy notes: `data/inventory.yaml`, `data/traits.yaml`.
- Keep generated or future-facing notes in planning docs, not inline code, unless they directly explain a validation or scheduling rule.

**JSDoc/TSDoc:**
- Not applicable.
- Python docstrings are used selectively for module overview and non-obvious helpers: module docstring, `load_product`, `check_products`, `check_inventory_alignment`, `check_goals`, `effective_traits`, `slot_matches`, `compute_slot_score`, `must_separate` in `planner.py`.

## Function Design

**Size:** Keep new validators small and return error lists. `planner.py` currently has small validation helpers and larger orchestration functions for `cmd_check` and `cmd_plan`.

**Parameters:** Pass parsed dictionaries and paths explicitly. Avoid hidden reads in validation helpers except for schema loading and product-card loading already centralized in `load_schema`, `load_yaml`, and `load_product` in `planner.py`.

**Return Values:** Prefer explicit domain results:
- `list[str]` for validation errors: `check_traits`, `check_inventory_alignment`, `check_inventory_overrides`, `check_goals`.
- `tuple[list[str], list[str], dict[str, Path]]` when a validator also returns info messages and discovered ids: `check_products`.
- `int` exit codes for CLI commands: `cmd_check`, `cmd_refresh`, `cmd_plan`.
- `tuple[int, bool, list[str]]` for scoring internals: `compute_slot_score`.

## Module Design

**Exports:** There is no package API. `planner.py` is both the CLI entry point and implementation module.

**Barrel Files:** Not applicable.

**Data Modeling:**
- JSON Schema owns shape validation for YAML files: `schema/product.schema.json`, `schema/slots.schema.json`, `schema/traits.schema.json`, `schema/inventory.schema.json`, `schema/goal.schema.json`.
- Python owns cross-reference and semantic validation that JSON Schema cannot express: trait namespace registration, trait existence, id-to-filename matching, duplicate ids, inventory/card alignment, goal member product refs in `planner.py`.
- YAML ids use colon namespaces for traits: `intake:requires_food`, `effect:energy_like`, `activity:any_workout` in `data/traits.yaml`.
- YAML substance ids use lowercase snake_case and must match product-card filenames: `data/products/*.yaml`, `data/inventory.yaml`.

---

*Convention analysis: 2026-05-05*
