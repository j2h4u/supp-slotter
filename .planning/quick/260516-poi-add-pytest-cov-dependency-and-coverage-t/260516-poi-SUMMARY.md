---
phase: quick-260516-poi
plan: "01"
subsystem: tooling
tags: [coverage, pytest, dev-deps, quality]
dependency_graph:
  requires: []
  provides: [coverage-gate]
  affects: [pyproject.toml, uv.lock, justfile]
tech_stack:
  added: [pytest-cov>=7]
  patterns: [coverage-threshold-from-baseline]
key_files:
  created: []
  modified:
    - pyproject.toml
    - uv.lock
    - justfile
    - .gitignore
decisions:
  - "fail_under set to 83 (measured baseline 85%, gap 2) — honest threshold from measured data"
  - "coverage recipe is opt-in sibling; just check and just test unchanged"
  - "omit list excludes tests/, scripts/, planner/__main__.py per plan brief"
  - ".coverage and htmlcov/ added to .gitignore as generated artifacts"
metrics:
  duration: "~5min"
  completed: "2026-05-16"
  tasks_completed: 1
  files_changed: 4
---

# Phase quick-260516-poi Plan 01: Add pytest-cov dependency and coverage threshold Summary

## One-liner

pytest-cov 7.1.0 wired into dev deps with `just coverage` recipe enforcing `fail_under = 83` derived from measured 85% baseline.

## What Was Done

Added pytest-cov as a dev dependency, configured coverage measurement in `pyproject.toml`, and added a `just coverage` recipe that enforces a threshold derived from the actual measured baseline — not an invented number.

## Coverage Measurement

| Metric | Value |
|--------|-------|
| Measured baseline (TOTAL) | 84.63% (rounded to 85% for threshold arithmetic) |
| Chosen fail_under | 83 |
| Gap to baseline | 2 points |
| pytest-cov version locked | 7.1.0 |
| coverage version locked | 7.14.0 |

Threshold calculation: `floor(85) - 2 = 83`. Hard ceiling (99) not reached.

## Omit List

Exactly as specified in the plan:

```
omit = ["tests/*", "scripts/*", "planner/__main__.py"]
```

No deviations from the plan's omit list.

## Verification Results

- `just check`: 107/107 passed, ruff clean, pyright 0/0/0
- `just coverage`: exits 0, TOTAL 84.63% >= fail_under 83%
- `grep pytest-cov pyproject.toml`: present in `[dependency-groups].dev`
- `grep pytest-cov uv.lock`: present (locked at 7.1.0)
- `grep [tool.coverage.run] pyproject.toml`: present with correct source/omit
- `grep fail_under pyproject.toml`: `fail_under = 83` (between 1 and 99)
- `python -c "import coverage; print(coverage.__version__)"`: `7.14.0`

## Deviations from Plan

### Auto-added (Rule 2 — missing critical functionality)

**1. [Rule 2 - Missing] Added .coverage and htmlcov/ to .gitignore**
- Found during: post-commit untracked file check
- Issue: `uv run pytest --cov` generates `.coverage` file that would remain untracked
- Fix: Added `.coverage` and `htmlcov/` to `.gitignore`
- Files modified: `.gitignore`
- Commit: 150394b

No other deviations — plan executed as written.

## Self-Check: PASSED

- pyproject.toml modified and committed: ad89148
- uv.lock modified and committed: ad89148
- justfile modified and committed: ad89148
- .gitignore modified and committed: 150394b
- `just check` exits 0: confirmed
- `just coverage` exits 0: confirmed
- fail_under = 83, baseline = 85%, gap = 2: confirmed
