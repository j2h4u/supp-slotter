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

# Verify generated ontology artifacts are fresh and loadable.
ontology-check:
    uv run python scripts/generate_ontology.py --check

# Check repository RDF projection against generated SHACL shapes.
ontology-projection-check:
    scripts/run_bounded.sh -- uv run python scripts/ontology_check_benchmark.py --check-only

# Benchmark repository RDF projection + SHACL validation using committed generated artifacts.
ontology-check-benchmark:
    scripts/run_bounded.sh -- uv run python scripts/ontology_check_benchmark.py

# Benchmark the full ontology compile + repository RDF projection + SHACL path.
ontology-full-check-benchmark:
    scripts/run_bounded.sh -- uv run python scripts/ontology_check_benchmark.py --include-compile --cold-limit-seconds 30 --warm-limit-seconds 30

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
    uv run deptry planner scripts tests --known-first-party planner --known-first-party scripts --known-first-party tests --per-rule-ignores "DEP004=coverage|linkml|linkml_runtime"

# Run the canonical static type checker.
_typecheck:
    scripts/run_bounded.sh -- uv run basedpyright planner scripts

# Scan for dead code with vulture.
_dead-code:
    uv run vulture

# Auto-fix ruff findings and formatting.
fix:
    uv run ruff check --fix .
    uv run ruff format .

# Static quality gate: format, lint, types, imports, workflows, compile, dead code.
check: ontology-check _fmt-check _lint _preview-complexity-lint _lock-check _typecheck _import-contracts _actionlint _supply-chain-pins _deptry _compile _dead-code

# Self-test the bounded runner without invoking the project test suite.
bounded-runner-test:
    scripts/test_run_bounded.sh

# Print the stable suite boundaries without running planner or pytest.
suite-inventory:
    uv run python scripts/run_unit_gate.py --list-suites

# Fast vertical user-scenario smoke loop (~10-30s). Use this first during development.
smoke:
    scripts/run_bounded.sh -- uv run python scripts/run_unit_gate.py --suite smoke

# Curated fast unit loop (target <=60s): pure/runtime logic and short vertical
# tests only. Ontology compiler/artifact tests stay in `ontology-contract`.
fast-unit:
    scripts/run_bounded.sh -- uv run python scripts/run_unit_gate.py --suite fast-unit

# Heavy ontology compiler/artifact/runtime contract tests.
ontology-contract:
    scripts/run_bounded.sh -- uv run python scripts/run_unit_gate.py --suite ontology-contract

# Release runtime scenario tests over curated modules and cardinality nodes.
runtime-scenarios:
    scripts/run_bounded.sh -- uv run python scripts/run_unit_gate.py --suite runtime-scenarios

# Real repository corpus projection through RDF/SHACL against generated shapes.
corpus-projection: ontology-projection-check

# Bounded targeted test loop for development; pair with `fast-unit` and the
# relevant contract gates before publishing.
unit-target target:
    scripts/run_bounded.sh -- uv run pytest -q -m "not integration and not slow" "{{target}}"

# Focused tests for the isolated unit gate runner.
unit-gate-test:
    scripts/run_bounded.sh -- uv run pytest -q tests/test_run_unit_gate.py

# Lint, type-check, and compile the isolated unit gate implementation.
unit-gate-check:
    uv run ruff check scripts/run_unit_gate.py tests/test_run_unit_gate.py
    uv run ruff format --check scripts/run_unit_gate.py tests/test_run_unit_gate.py
    scripts/run_bounded.sh -- uv run basedpyright scripts/run_unit_gate.py tests/test_run_unit_gate.py --warnings
    uv run python -m compileall -q scripts/run_unit_gate.py tests/test_run_unit_gate.py

# Default local development confidence gate. Heavy gates stay explicit.
verify: check smoke fast-unit corpus-projection

# Full release candidate gate. Run before review/merge, not in small loops.
# Coverage is the blocking full-suite release gate.
release: check _release-unit corpus-projection

# One bounded release-unit run; the runner owns all six pytest stages.
_release-unit:
    coverage_file="$(mktemp /tmp/supp-slotter-quality-coverage.XXXXXX)"; \
    trap 'rm -f "$coverage_file"' EXIT; \
    scripts/run_bounded.sh -- env COVERAGE_FILE="$coverage_file" uv run python scripts/run_unit_gate.py --suite release && \
    COVERAGE_FILE="$coverage_file" uv run coverage report

# Blocking coverage floor from one bounded curated-suite execution.
coverage-check:
    coverage_file="$(mktemp /tmp/supp-slotter-quality-coverage.XXXXXX)"; \
    trap 'rm -f "$coverage_file"' EXIT; \
    scripts/run_bounded.sh -- env COVERAGE_FILE="$coverage_file" uv run python scripts/run_unit_gate.py --suite coverage && \
    COVERAGE_FILE="$coverage_file" uv run coverage report
