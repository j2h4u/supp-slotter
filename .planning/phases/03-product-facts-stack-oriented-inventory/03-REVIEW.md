---
phase: 03
status: clean
reviewed_at: 2026-05-06
scope:
  - planner.py
  - schema/*.schema.json
  - data/**/*.yaml
  - tests/test_phase_01.py
  - tests/test_phase_02.py
  - tests/test_phase_03.py
---

# Code Review - Phase 03

## Findings

No open findings.

## Fixed During Review

### Duplicate inventory ids across stacks

Severity: warning

The new stack-oriented inventory shape made it possible to put the same inventory item id under two stack groups. JSON Schema cannot express cross-object uniqueness for keys in different stack objects, and the first implementation normalized entries into a dict keyed by item id, which would silently keep the later entry.

Fix:
- Added `check_inventory_duplicate_items()` in `planner.py`.
- Added `test_duplicate_inventory_item_across_stacks_is_rejected()` in `tests/test_phase_03.py`.

Verification:
- `uv run planner.py check`
- `uv run pytest tests/test_phase_03.py -q`
- `uv run pytest`

## Residual Risk

No known code-review residual risk. Product label facts still depend on the source data currently captured in YAML; unknown label forms remain explicit via `unmatched_concerns`.
