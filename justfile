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
    uv run --group ontology python scripts/generate_ontology.py --check

# Regenerate checked-in ontology artifacts from canonical sources.
ontology-generate:
    scripts/run_bounded.sh -- uv run --group ontology python scripts/generate_ontology.py

# Check repository RDF projection against generated SHACL shapes.
ontology-projection-check:
    scripts/run_bounded.sh -- uv run --group ontology python scripts/ontology_check_benchmark.py --check-only

# Benchmark repository RDF projection + SHACL validation using committed generated artifacts.
ontology-check-benchmark:
    scripts/run_bounded.sh -- uv run --group ontology python scripts/ontology_check_benchmark.py

# Benchmark the full ontology compile + repository RDF projection + SHACL path.
ontology-full-check-benchmark:
    scripts/run_bounded.sh -- uv run --group ontology python scripts/ontology_check_benchmark.py --include-compile --cold-limit-seconds 30 --warm-limit-seconds 30

# Check import-layer architecture contracts.
_import-contracts:
    uv run lint-imports

# Check the declared module dependency graph independently of named import contracts.
_module-boundaries:
    uv run tach check

# Check GitHub Actions workflow syntax and expressions.
_actionlint:
    uv run actionlint

# Guard obvious supply-chain drift in workflows and container image references.
_supply-chain-pins:
    uv run python scripts/check_supply_chain_pins.py

# Audit the exact locked Python dependency set for known vulnerabilities.
deps-audit:
    #!/usr/bin/env bash
    set -euo pipefail
    tmp="$(mktemp)"
    trap 'rm -f "$tmp"' EXIT
    uv export --locked --all-groups --no-emit-project --no-emit-workspace --no-emit-local --no-header --no-annotate --no-editable > "$tmp"
    uv run pip-audit -r "$tmp" --strict --no-deps

# Check declared Python dependencies against imports.
_deptry:
    uv run deptry planner scripts tests --known-first-party planner --known-first-party scripts --known-first-party tests --per-rule-ignores "DEP004=coverage|linkml|linkml_runtime|pyshacl|pytest_crap|rdflib"

# Run the canonical static type checker.
_typecheck:
    scripts/run_bounded.sh -- uv run basedpyright planner scripts

# Type-check the complete test suite separately from production code.
_typecheck-tests:
    scripts/run_bounded.sh -- uv run basedpyright --project pyright-tests.json --warnings

# Scan for dead code with vulture.
_dead-code:
    uv run vulture --ignore-names selector_kinds

# Auto-fix ruff findings and formatting.
fix:
    uv run ruff check --fix .
    uv run ruff format .

# Static quality gate: format, lint, types, imports, workflows, compile, dead code.
check: _fmt-check _lint _preview-complexity-lint _lock-check _typecheck _typecheck-tests _import-contracts _module-boundaries _actionlint _supply-chain-pins _deptry _compile _dead-code

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

# Exact acceptance witnesses for the executable canonical-runtime boundary.
canonical-runtime:
    scripts/run_bounded.sh -- uv run --group ontology python scripts/run_unit_gate.py --suite canonical-runtime

# Private tests-only variant used by `verify`: the current-shelf command owns
# the one planner validation for that composition.  Standalone `fast-unit`
# remains self-validating.
_fast-unit-tests:
    scripts/run_bounded.sh -- uv run python scripts/run_unit_gate.py --suite fast-unit-tests

# Run the current shelf through canonical inference and the exact optimizer.
# The test copies its data root before planning, so repository inputs stay read-only.
current-shelf-smoke:
    scripts/run_bounded.sh -- uv run pytest -q -m "not integration and not slow" tests/test_cutover_vertical_scenarios.py::test_real_shelf_daily_episodic_and_training_products_are_complete

# Heavy ontology compiler/artifact/runtime contract tests.
ontology-contract:
    scripts/run_bounded.sh -- uv run --group ontology python scripts/run_unit_gate.py --suite ontology-contract

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
    uv run ruff check scripts/check_mutation_gate.py scripts/crap_gate.py scripts/run_unit_gate.py tests/test_crap_gate.py tests/test_run_unit_gate.py
    uv run ruff format --check scripts/check_mutation_gate.py scripts/crap_gate.py scripts/run_unit_gate.py tests/test_crap_gate.py tests/test_run_unit_gate.py
    scripts/run_bounded.sh -- uv run basedpyright scripts/check_mutation_gate.py scripts/crap_gate.py scripts/run_unit_gate.py tests/test_crap_gate.py tests/test_run_unit_gate.py --warnings
    uv run python -m compileall -q scripts/check_mutation_gate.py scripts/crap_gate.py scripts/run_unit_gate.py tests/test_crap_gate.py tests/test_run_unit_gate.py

# Default local development confidence gate. The private unit suite does not
# validate; `current-shelf-smoke` calls cmd_plan, which owns exactly one check.
# Ontology, formal, corpus, and release gates remain explicit.
verify: check _fast-unit-tests current-shelf-smoke

# Product-focused release gate: static contracts, fresh ontology artifacts,
# exact inference/optimizer witnesses, the real shelf, and full corpus SHACL.
# Exhaustive regression and quality analytics remain explicit, non-release gates.
release: check ontology-check canonical-runtime current-shelf-smoke corpus-projection

# Blocking CRAP threshold from one bounded curated-suite execution.
crap-check:
    coverage_file="$(mktemp /tmp/supp-slotter-quality-crap.XXXXXX)"; \
    trap 'rm -f "$coverage_file"' EXIT; \
    scripts/run_bounded.sh -- env COVERAGE_FILE="$coverage_file" uv run python scripts/run_unit_gate.py --suite coverage && \
    uv run python scripts/crap_gate.py --coverage "$coverage_file" && \
    COVERAGE_FILE="$coverage_file" uv run coverage report

# Focused mutation gate over scheduling inference, optimization, and publication.
mutation-check children="4":
    scripts/run_bounded.sh -- uv run mutmut run --max-children {{children}}
    uv run mutmut export-cicd-stats
    uv run mutmut results > mutants/mutmut-results.txt
    uv run python scripts/check_mutation_gate.py mutants/mutmut-cicd-stats.json --results mutants/mutmut-results.txt --baseline scripts/mutation-survivor-baseline.txt
