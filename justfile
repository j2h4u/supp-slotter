default: test lint typecheck

test:
    uv run pytest tests/

lint:
    uv run ruff check .

lint-fix:
    uv run ruff check --fix .

typecheck:
    uv run pyright

check: lint typecheck test

fmt:
    uv run ruff format .
