set shell := ["bash", "-uc"]
export UV_LINK_MODE := "hardlink"

# Show available repo commands.
default:
    @just --list

# Compile Python sources for syntax errors.
_compile:
    uv run python -m compileall -q planner scripts tests

# Verify uv.lock is synchronized with pyproject.toml.
_lock-check:
    uv lock --check

# Lint with ruff across the whole repo.
_lint:
    uv run ruff check .

# Check preview-only complexity/refactor rules explicitly.
_preview-complexity-lint:
    uv run ruff check --preview --select PLR0914,PLR0916,PLR0917 planner scripts tests

# Check formatting without writing.
_fmt-check:
    uv run ruff format --check .

# Check import-layer architecture contracts.
_import-contracts:
    uv run lint-imports

# Check GitHub Actions workflow syntax and expressions.
_actionlint:
    uv run actionlint

# Guard obvious supply-chain drift in workflows and container image references.
_supply-chain-pins:
    uv run python scripts/check_supply_chain_pins.py

# Check declared Python dependencies against imports.
_deptry:
    uv run deptry planner scripts tests --known-first-party planner --known-first-party scripts --known-first-party tests --per-rule-ignores "DEP004=coverage|pytest_crap|radon|linkml"

# Run the canonical static type checker.
_typecheck:
    uv run basedpyright planner scripts

# Scan for dead code with vulture.
_dead-code:
    uv run vulture

# Auto-fix ruff findings and formatting.
fix:
    uv run ruff check --fix .
    uv run ruff format .

# Static quality gate: format, lint, types, test types, imports, workflows, compile, dead code.
check: _fmt-check _lint _preview-complexity-lint _lock-check _typecheck typecheck-tests _import-contracts _actionlint _supply-chain-pins _deptry _compile _dead-code

# Type-check tests separately so production and fixture issues stay easy to read.
typecheck-tests:
    uv run basedpyright tests --warnings

# Unit tests and planner schema/domain check.
unit:
    uv run python -m planner check
    uv run pytest -q -n auto -m "not integration and not slow" tests/

# Full local gate for agents before claiming completion.
verify: check typecheck-tests unit

coverage:
    uv run pytest tests/ --cov=planner --cov-report=term-missing

# Blocking coverage floor.
coverage-check:
    uv run pytest -q -n auto tests/ --cov=planner --cov-report=term-missing

# Human CRAP report over the full suite.
crap:
    uv run pytest tests/ --cov=planner --cov-report=term-missing --crap --crap-threshold=30 --crap-top-n=30

# Hard CRAP gate: every function must stay at or below CRAP 30.
crap-check:
    coverage_file="$(mktemp /tmp/supp-slotter-crap-coverage.XXXXXX)"; \
    trap 'rm -f "$coverage_file"' EXIT; \
    COVERAGE_FILE="$coverage_file" uv run pytest tests/ --cov=planner --cov-report=; \
    uv run python -m scripts.crap_gate --coverage "$coverage_file" --src planner --threshold 30
