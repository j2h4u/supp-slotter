default: test lint typecheck

test:
    uv run python -m planner check
    uv run pytest tests/

lint:
    uv run ruff check .

lint-fix:
    uv run ruff check --fix .

typecheck:
    uv run pyright

check: lint typecheck test

coverage:
    uv run pytest tests/ --cov=planner --cov-report=term-missing

fmt:
    uv run ruff format .

# Dead-code sieve (advisory — vulture has false positives, read with judgment).
deadcode:
    uv run vulture
