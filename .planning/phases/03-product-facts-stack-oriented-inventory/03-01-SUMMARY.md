---
phase: 03-product-facts-stack-oriented-inventory
plan: 01
status: complete
commits:
  - b2c728f
  - 512b972
---

# Plan 03-01 Summary - Product Fact Preservation

## What Changed

- Added Phase 3 regression tests for product fact ownership.
- Copied known non-unknown inventory brands into product cards.
- Routed current dose and note strings before inventory stripping:
  - label-backed/simple product amounts moved to product component `amount`;
  - ambiguous multi-component labels stayed in product `notes`;
  - operator usage doses for magnesium glycinate and tadalafil stayed in inventory `notes`.
- Verified existing product schema already supports the required product fact fields.

## Verification

- `uv run pytest tests/test_phase_03.py -q` - passed, 3 tests.
- `uv run planner.py check` - passed.

## Deviations from Plan

None - plan executed exactly as written.

## Self-Check: PASSED

Known product facts are preserved on product cards, no product has fake `brand: unknown`, and inventory still carries legacy source fields for Plan 03-02.
