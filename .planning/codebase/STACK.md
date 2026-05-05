# Technology Stack

**Analysis Date:** 2026-05-05

## Languages

**Primary:**
- Python >=3.11 - CLI implementation in `planner.py`; script metadata declares `requires-python = ">=3.11"` in `planner.py`.
- YAML 1.x - Domain data, inventory, goals, generated schedules, and planner inputs in `data/*.yaml`, `data/products/*.yaml`, `data/goals/*.yaml`, and `schedule.yaml`.
- JSON Schema Draft 2020-12 - Validation contracts in `schema/*.schema.json`; loaded by `planner.py`.

**Secondary:**
- Markdown - Project/spec/operator documentation in `idea.md`, `brief.md`, `current-inventory.md`, `HANDOFF.md`, and `.planning/*.md`.
- JSON - Schema documents in `schema/goal.schema.json`, `schema/inventory.schema.json`, `schema/product.schema.json`, `schema/slots.schema.json`, and `schema/traits.schema.json`.

## Runtime

**Environment:**
- Python >=3.11 - Required by the PEP 723 script header in `planner.py`; current local interpreter is Python 3.13.5.
- Single-process CLI runtime - `planner.py` runs as a local command and exits through `sys.exit(...)` in `planner.py`.

**Package Manager:**
- uv 0.11.3 - Operational command surface uses `uv run planner.py <subcommand>` in `planner.py`, `.planning/PROJECT.md`, `.planning/ROADMAP.md`, `.planning/STATE.md`, and `tests/test_phase_01.py`.
- Lockfile: missing - no `uv.lock`, `requirements.txt`, `pyproject.toml`, `poetry.lock`, `Pipfile`, or `setup.py` detected at the repository root.
- Dependency source: PEP 723 inline script metadata in `planner.py` lists `pyyaml>=6.0` and `jsonschema>=4.21`.

## Frameworks

**Core:**
- argparse from Python standard library - CLI subcommand parser in `planner.py`.
- pathlib/json/sys from Python standard library - filesystem, schema loading, output, and exit handling in `planner.py`.
- PyYAML >=6.0 - Reads and writes YAML via `yaml.safe_load` and `yaml.safe_dump` in `planner.py`; tests read YAML in `tests/test_phase_01.py`.
- jsonschema >=4.21 - Validates local JSON Schema Draft 2020-12 documents via `jsonschema.Draft202012Validator` in `planner.py`.

**Testing:**
- pytest 8.3.5 - Test runner for `tests/test_phase_01.py`.
- subprocess from Python standard library - Integration-style tests invoke `uv run planner.py ...` from `tests/test_phase_01.py`.

**Build/Dev:**
- No build system detected - no `pyproject.toml`, `setup.py`, `Makefile`, `justfile`, or `Dockerfile` detected at the repository root.
- No formatter/linter config detected - no `.prettierrc`, `.eslintrc*`, `eslint.config.*`, `biome.json`, `ruff.toml`, or `pyproject.toml` detected at the repository root.
- No container runtime config detected - no `Dockerfile` or `docker-compose*.yml` detected at the repository root.

## Key Dependencies

**Critical:**
- `pyyaml>=6.0` - Required to parse domain inputs from `data/slots.yaml`, `data/traits.yaml`, `data/inventory.yaml`, `data/products/*.yaml`, and `data/goals/*.yaml`; required to write `schedule.yaml` and refresh `data/inventory.yaml` in `planner.py`.
- `jsonschema>=4.21` - Required to validate local schemas from `schema/*.schema.json`; `planner.py` uses `Draft202012Validator`.
- Python standard library `argparse` - Defines `check`, `refresh`, and `plan` subcommands in `planner.py`.

**Infrastructure:**
- Local filesystem - `planner.py` reads from `data/`, `schema/`, and writes `schedule.yaml` plus `data/inventory.yaml` during `refresh`.
- pytest - `tests/test_phase_01.py` verifies the CLI, schema/reference validation, schedule generation, stack partitioning, and restoration of temporary test mutations.

## Configuration

**Environment:**
- No `.env`, `.env.*`, or `*.env` files detected at the repository root or first two directory levels.
- No environment variables are required by `planner.py`; all paths are module-relative constants in `planner.py`.
- Runtime configuration is file-based: `data/slots.yaml`, `data/traits.yaml`, `data/inventory.yaml`, `data/products/*.yaml`, `data/goals/*.yaml`, and `schema/*.schema.json`.

**Build:**
- No build config files detected.
- No package manifest detected; use `uv run planner.py check`, `uv run planner.py refresh`, and `uv run planner.py plan` as documented in `planner.py` and `.planning/PROJECT.md`.
- Test command is `pytest`, with the concrete tests in `tests/test_phase_01.py`.

## Platform Requirements

**Development:**
- Python >=3.11 available on PATH, as required by `planner.py`.
- uv available on PATH for the repo's documented `uv run planner.py ...` workflow in `planner.py` and tests in `tests/test_phase_01.py`.
- Network is only needed for first-time dependency resolution by uv; `planner.py` itself does not perform network calls.

**Production:**
- Local CLI execution only - no hosted service, web server, container, package artifact, or deployment target detected.
- Persistent state is committed/working-tree files under `data/` and generated output in `schedule.yaml`.

---

*Stack analysis: 2026-05-05*
