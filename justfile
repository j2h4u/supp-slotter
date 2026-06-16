set shell := ["bash", "-uc"]

# Show available repo commands.
default:
    @just --list

# Compile Python sources for syntax errors.
_compile:
    uv run python -m compileall -q planner tests

# Lint with ruff across the whole repo.
_lint:
    uv run ruff check .

# Check formatting without writing.
_fmt-check:
    uv run ruff format --check .

# Check import-layer architecture contracts.
_import-contracts:
    uv run lint-imports

# Check GitHub Actions workflow syntax and expressions.
_actionlint:
    uv run actionlint

# Run the canonical static type checker.
_typecheck:
    uv run basedpyright planner

# Scan for dead code with vulture.
_dead-code:
    uv run vulture

# Auto-fix ruff findings and formatting.
fix:
    uv run ruff check --fix .
    uv run ruff format .

# Static quality gate: format, lint, types, test types, imports, workflows, compile, dead code.
check: _fmt-check _lint _typecheck typecheck-tests _import-contracts _actionlint _compile _dead-code

# Type-check tests separately so production and fixture issues stay easy to read.
typecheck-tests:
    uv run basedpyright tests --warnings

# Unit tests and planner schema/domain check.
unit:
    uv run python -m planner check
    uv run pytest -q -n auto tests/

# Full local gate for agents before claiming completion.
verify: check typecheck-tests unit

coverage:
    uv run pytest tests/ --cov=planner --cov-report=term-missing
