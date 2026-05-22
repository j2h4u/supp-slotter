# Technology Stack

**Analysis Date:** 2026-05-22

## Languages

**Primary:**
- Python >=3.11 - application runtime, CLI, data validation, maintenance code, and tests in `planner/` and `tests/`.

**Secondary:**
- YAML - source data cards, generated schedule output, GitHub Actions, and schema templates in `data/`, `schedule.yaml`, `.github/workflows/test.yml`, and `schema/templates/`.
- JSON Schema - machine-checked YAML contracts in `schema/*.schema.json`.
- Markdown - project, domain, and agent-facing documentation in `README.md`, `SKILL.md`, and `docs/`.

## Runtime

**Environment:**
- CPython 3.11+ - declared by `requires-python = ">=3.11"` in `pyproject.toml`; type checker target is `pythonVersion = "3.11"` in `pyproject.toml`.

**Package Manager:**
- uv - documented in `README.md`, used by `justfile`, and installed in CI by `.github/workflows/test.yml`.
- Lockfile: present at `uv.lock`.

## Frameworks

**Core:**
- Standard-library CLI with `argparse` - command dispatch lives in `planner/__main__.py`; supported commands are `check`, `audit`, `find`, `review`, and `review-substance`.
- Dataclass contracts - immutable runtime models for YAML shapes live in `planner/contracts.py`.
- YAML-first local planner - `planner/yaml_io.py` reads source files from `data/`; `planner/engine/plan.py` builds the generated schedule; `planner/schedule_writer.py` writes `schedule.yaml`.
- JSON Schema validation - `planner/schema_validation.py` loads `schema/*.schema.json` and validates YAML via `jsonschema.Draft202012Validator`.

**Testing:**
- pytest >=8, locked as 9.0.3 - tests live in `tests/`; CI runs `uv run pytest tests/` in `.github/workflows/test.yml`.
- pyright >=1.1.380, locked as 1.1.409 - strict type checking covers `planner` and `tests` via `pyproject.toml`.

**Build/Dev:**
- Ruff >=0.7, locked as 0.15.12 - lint and format tool configured in `pyproject.toml`; commands live in `justfile`.
- GitHub Actions - `.github/workflows/test.yml` runs dependency sync, lint, type check, planner check, and tests.
- just - task runner in `justfile`; use `just check` for lint, typecheck, planner check, and tests.

## Key Dependencies

**Critical:**
- PyYAML >=6.0, locked as 6.0.3 - primary runtime YAML parser/emitter used in `planner/yaml_io.py`, `planner/cards/_common.py`, `planner/schedule_writer.py`, `planner/maintenance.py`, and tests.
- jsonschema >=4.21, locked as 4.26.0 - validates YAML inputs against contracts in `schema/` via `planner/schema_validation.py`.
- ruamel-yaml >=0.19.1, locked as 0.19.1 - declared runtime dependency in `pyproject.toml`; direct runtime imports were not detected in `planner/`.

**Infrastructure:**
- pytest 9.0.3 - regression runner for `tests/`.
- ruff 0.15.12 - lint and formatting gate for the repo.
- pyright 1.1.409 - strict static type gate for `planner/` and `tests/`.
- attrs 26.1.0, referencing 0.37.0, rpds-py 0.30.0, jsonschema-specifications 2025.9.1 - transitive `jsonschema` dependencies recorded in `uv.lock`.
- nodeenv 1.10.0 and typing-extensions 4.15.0 - transitive `pyright` dependencies recorded in `uv.lock`.

## Configuration

**Environment:**
- No `.env` files detected in repo root or first three directory levels.
- No runtime environment-variable reads detected in `planner/`; `os.getpid()` and `os.kill()` are used only for local maintenance locking in `planner/maintenance.py`.
- The repo is configured through committed files: `pyproject.toml`, `uv.lock`, `justfile`, `.github/workflows/test.yml`, `schema/`, and `data/`.

**Build:**
- `pyproject.toml`: package metadata, runtime dependencies, dev dependency group, Ruff rules, and Pyright settings.
- `uv.lock`: locked package graph for runtime and dev dependencies.
- `justfile`: local commands for `test`, `lint`, `lint-fix`, `typecheck`, `check`, and `fmt`.
- `.github/workflows/test.yml`: CI pipeline for pushes to `main` and pull requests.

## Platform Requirements

**Development:**
- Install Python 3.11+ and uv.
- Use `uv sync --group dev` to install dependencies, matching `.github/workflows/test.yml`.
- Use `uv run python -m planner` for the default generated schedule view; use `uv run python -m planner check`, `uv run python -m planner audit`, `uv run python -m planner find <words>`, `uv run python -m planner review`, and `uv run python -m planner review-substance <path>` for the explicit CLI commands implemented in `planner/__main__.py`.
- Use `just check` when `just` is available; it runs `uv run ruff check .`, `uv run pyright`, `uv run python -m planner check`, and `uv run pytest tests/`.

**Production:**
- Not a service deployment. The project is a local CLI and YAML data repository; generated output is `schedule.yaml`.
- CI target is GitHub-hosted Ubuntu via `.github/workflows/test.yml`.
- No Dockerfile, Compose file, web server, package entry point, or hosted deployment configuration detected.

---

*Stack analysis: 2026-05-22*
