---
quick_id: 260506-iex
status: planned
created: 2026-05-06
---

# Quick Task 260506-iex: Simplify inventory to stack product lists

## Goal

Make `data/inventory.yaml` answer only one question: which product IDs are in which stacks. Remove redundant item-id/product duplication and remove inventory-owned `notes` / `traits_override`.

## Tasks

1. Convert `data/inventory.yaml` and `schema/inventory.schema.json` so each stack is an array of product IDs.
   - `daily`, `training`, and `inactive` remain required.
   - Every item is a product ID string.
   - No `product`, `notes`, or `traits_override` fields remain.

2. Update `planner.py` for the simplified shape.
   - `normalize_inventory_entries()` should return entries keyed by product ID with `product` and `stack` attached in memory.
   - Duplicate product IDs across stacks remain invalid.
   - `refresh` appends missing products to `stacks.inactive` as strings.
   - Remove runtime handling for `traits_override`.

3. Update tests and run the local gate.
   - Adjust Phase 2/3 tests to expect stack product lists.
   - Remove tests that preserve inventory overrides.
   - Verify `uv run planner.py check`, `uv run planner.py plan`, and `uv run pytest`.
