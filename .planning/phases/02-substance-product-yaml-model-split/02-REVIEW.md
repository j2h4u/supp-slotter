---
phase: 02-substance-product-yaml-model-split
status: issues_found
depth: standard
files_reviewed: 75
findings:
  critical: 0
  warning: 2
  info: 0
  total: 2
reviewed_at: 2026-05-05T19:26:57Z
---

# Phase 02 Code Review

## Scope

Reviewed Phase 2 source, schema, data, generated schedule, and regression-test outputs derived from the phase summaries:

- `planner.py`
- `schedule.yaml`
- `schema/inventory.schema.json`
- `schema/product.schema.json`
- `schema/slots.schema.json`
- `schema/substance.schema.json`
- `schema/traits.schema.json`
- `data/inventory.yaml`
- `data/slots.yaml`
- `data/traits.yaml`
- `data/products/*.yaml`
- `data/substances/*.yaml`
- `tests/test_phase_01.py`
- `tests/test_phase_02.py`

## Findings

### WR-01: Malformed inventory entries can crash validation after schema errors

- Severity: Warning
- File: `planner.py:349`
- Affected path: `uv run planner.py check data/inventory.yaml`

`validate_inventory()` collects JSON Schema errors but then continues into cross-reference checks unconditionally. If an inventory supplement value is not a mapping, the schema validator correctly detects the shape error, but `check_inventory_alignment()` immediately calls `entry.get("product")` and raises `AttributeError` before the CLI can report validation errors.

Reproduction used an isolated copy with `supplements.vitamin_d3` replaced by a scalar:

```text
AttributeError: 'str' object has no attribute 'get'
```

This makes the validator fail open as an exception path for malformed user data. Keep schema errors, but skip deeper alignment/override checks for entries whose shape is not a mapping, or return immediately from `validate_inventory()` when schema validation has already found structural errors that make downstream assumptions unsafe.

### WR-02: Single-file substance checks falsely reject valid `prefer_with` references

- Severity: Warning
- File: `planner.py:416`
- Affected path: `uv run planner.py check data/substances/creatine.yaml`

Targeted substance validation re-runs `check_substances([target], trait_ids)`. That helper validates `prefer_with` references against only the one-file `seen_ids` map it just built, so a valid cross-file reference is reported as missing even though the full registry was loaded immediately before the target branch.

Observed output:

```text
ERROR: data/substances/creatine.yaml: prefer_with target 'l_citrulline_malate' has no matching substance card
```

This breaks Phase 2 target-mode validation for any substance card with a valid `prefer_with` edge. The target path should validate the target card's local shape and traits while checking reference fields against the full `substance_ids` registry.

## Verification

- `uv run planner.py check` passes against the current repository data.
- `uv run pytest -q` passes: 15 tests.
- `uv run planner.py check data/substances/creatine.yaml` reproduces WR-02.
- An isolated malformed-inventory probe reproduces WR-01 without modifying repository data.

## Residual Risk

The Phase 2 regression suite covers the main split-model happy path and several negative cross-reference cases, but it does not cover malformed inventory item shape handling or single-file substance validation with `prefer_with`.
