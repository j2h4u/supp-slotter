# Codebase Structure

**Analysis Date:** 2026-05-05

## Directory Layout

```text
supp-slotter/
├── planner.py                 # Single production CLI and scheduling implementation
├── schedule.yaml              # Generated schedule output from `uv run planner.py plan`
├── data/                      # Authoritative YAML domain data
│   ├── slots.yaml             # Schedulable daily/training slot definitions
│   ├── traits.yaml            # Trait taxonomy and scheduling effects
│   ├── inventory.yaml         # Operator shelf, stack partition, dose/brand metadata
│   ├── products/              # Product/substance cards, one YAML file per id
│   └── goals/                 # Goal cards and membership edges
├── schema/                    # JSON Schema contracts for YAML data files
├── tests/                     # Pytest behavior and architecture invariant tests
├── .planning/                 # GSD project state, roadmap, phase artifacts, codebase docs
├── brief.md                   # Product-card authoring instructions
├── idea.md                    # Full domain spec and deferred design notes
├── current-inventory.md       # Informal inventory source material
└── HANDOFF.md                 # Session handoff document
```

## Directory Purposes

**Root:**
- Purpose: Holds the CLI, generated schedule, project docs, and high-level source material.
- Contains: `planner.py`, `schedule.yaml`, `brief.md`, `idea.md`, `current-inventory.md`, `HANDOFF.md`.
- Key files: `planner.py`, `schedule.yaml`.

**`data/`:**
- Purpose: Store canonical YAML input data consumed by `planner.py`.
- Contains: Slot definitions, trait taxonomy, inventory, product cards, and goal cards.
- Key files: `data/slots.yaml`, `data/traits.yaml`, `data/inventory.yaml`, `data/products/*.yaml`, `data/goals/*.yaml`.

**`data/products/`:**
- Purpose: Store supplement/product cards.
- Contains: One YAML file per product id.
- Key files: `data/products/creatine.yaml`, `data/products/l_citrulline_malate.yaml`, `data/products/magnesium_glycinate.yaml`.

**`data/goals/`:**
- Purpose: Store goal-master cards and membership metadata.
- Contains: Active health-goal YAML cards.
- Key files: `data/goals/vascular_health.yaml`, `data/goals/mitochondrial_health.yaml`.

**`schema/`:**
- Purpose: Define validation contracts for YAML files.
- Contains: Draft 2020-12 JSON Schemas.
- Key files: `schema/slots.schema.json`, `schema/traits.schema.json`, `schema/product.schema.json`, `schema/inventory.schema.json`, `schema/goal.schema.json`.

**`tests/`:**
- Purpose: Lock behavior and cross-file invariants with pytest.
- Contains: CLI smoke tests, topology assertions, and negative referential-integrity tests.
- Key files: `tests/test_phase_01.py`.

**`.planning/`:**
- Purpose: Store GSD project metadata, roadmap, state, phase plans, verification artifacts, and codebase maps.
- Contains: `.planning/PROJECT.md`, `.planning/ROADMAP.md`, `.planning/STATE.md`, `.planning/phases/`, `.planning/codebase/`.
- Key files: `.planning/PROJECT.md`, `.planning/ROADMAP.md`, `.planning/STATE.md`.

## Key File Locations

**Entry Points:**
- `planner.py`: Production CLI entry point and all planner behavior.
- `tests/test_phase_01.py`: Pytest entry for current behavior coverage.

**Configuration:**
- `planner.py:1`: PEP 723 script metadata declaring Python `>=3.11` and runtime dependencies.
- `planner.py:26`: Canonical path configuration for data, schema, products, goals, inventory, and schedule output.
- `schema/*.schema.json`: Data-shape configuration for YAML files.
- `data/traits.yaml`: Trait namespace/effect configuration for scheduling behavior.
- `data/slots.yaml`: Slot configuration for daily and training schedules.
- `data/inventory.yaml`: Active/inactive and daily/training stack configuration.

**Core Logic:**
- `planner.py:56`: JSON Schema validation helper.
- `planner.py:73`: Trait namespace, `separate_from`, and slot-field validation.
- `planner.py:120`: Product-card validation and product id mapping.
- `planner.py:176`: Inventory/product-card alignment validation.
- `planner.py:218`: Goal-card validation and `members[].substance` reference validation.
- `planner.py:318`: Inventory refresh command.
- `planner.py:368`: Inventory trait override merge.
- `planner.py:377`: AND-only slot matching.
- `planner.py:385`: Trait-effect score computation.
- `planner.py:411`: Symmetric `separate_from` conflict detection.
- `planner.py:427`: Stack-aware planner command.

**Testing:**
- `tests/test_phase_01.py:66`: CLI `check` smoke test.
- `tests/test_phase_01.py:74`: Slot and activity trait topology tests.
- `tests/test_phase_01.py:107`: Inventory stack partition tests.
- `tests/test_phase_01.py:120`: Product-card activity traits and no product-embedded goals tests.
- `tests/test_phase_01.py:128`: Goal-card membership tests.
- `tests/test_phase_01.py:156`: Generated schedule stack partition tests.
- `tests/test_phase_01.py:182`: Negative goal-reference validator test.

**Generated Output:**
- `schedule.yaml`: Generated by `uv run planner.py plan`; do not treat as canonical input for behavior changes.
- `.pytest_cache/`: Generated by pytest; ignore for source changes.

## Naming Conventions

**Files:**
- Product cards use snake_case ids and matching YAML filenames: `data/products/l_citrulline_malate.yaml` contains `id: l_citrulline_malate`.
- Goal cards use snake_case filenames and ids: `data/goals/vascular_health.yaml` contains `id: vascular_health`.
- Schema files use `<domain>.schema.json`: `schema/product.schema.json`, `schema/goal.schema.json`.
- Tests use pytest naming: `tests/test_phase_01.py`.
- GSD phase artifacts use zero-padded phase/plan names: `.planning/phases/01-training-stacks-goals-ontology/01-01-PLAN.md`.

**Directories:**
- Domain data directories use short plural names: `data/products/`, `data/goals/`.
- Schema directory is singular: `schema/`.
- Tests live in `tests/`.
- GSD artifacts live under `.planning/`.

**Identifiers:**
- Product, inventory, slot, and goal ids use lowercase snake_case matching schema pattern `^[a-z][a-z0-9_]*$`.
- Trait ids use `namespace:name` with lowercase namespaces, matching schema pattern `^[a-z]+:[a-z][a-z0-9_]*$`.
- Registered trait namespaces are `intake`, `effect`, `class`, `family`, `risk`, and `activity` in `planner.py:35`.
- Inventory `stack` values are exactly `daily`, `training`, or `inactive`.

## Where to Add New Code

**New Product Card:**
- Primary code/data: Add `data/products/<id>.yaml` using a matching `id`.
- Inventory: Run `uv run planner.py refresh` or manually add `data/inventory.yaml` entry with `stack: inactive` until activated.
- Tests: Extend `tests/test_phase_01.py` when the product changes stack topology, goal membership, or expected activity traits.

**New Goal Card:**
- Primary code/data: Add `data/goals/<goal_id>.yaml`.
- Schema: Use `schema/goal.schema.json` fields; put relationship-specific text in `members[].role`.
- Tests: Add assertions in `tests/test_phase_01.py` if the goal is part of locked behavior.

**New Trait or Namespace:**
- Primary code/data: Add trait definitions to `data/traits.yaml`.
- Namespace registry: Update `REGISTERED_NAMESPACES` in `planner.py:35` if introducing a new namespace.
- Schema: Update `schema/traits.schema.json` only when the shape or id grammar changes.
- Tests: Add coverage in `tests/test_phase_01.py` for scheduling effects, namespace validation, or conflict behavior.

**New Slot Type:**
- Primary code/data: Add slot definitions to `data/slots.yaml`.
- Schema: Update `schema/slots.schema.json` if adding new matchable slot fields or enum values.
- Planner: Existing trait matching automatically sees new non-meta slot fields through `derive_slot_fields()` in `planner.py:66`.
- Tests: Update slot topology and generated schedule tests in `tests/test_phase_01.py`.

**New Planner Behavior:**
- Implementation: Add helper functions near the existing planning helpers in `planner.py:368` through `planner.py:411`.
- Command path: Wire command behavior through `cmd_plan()` in `planner.py:427` or a new subcommand in `main()` at `planner.py:662`.
- Tests: Add CLI-level pytest coverage in `tests/test_phase_01.py` or a new `tests/test_<feature>.py`.

**Utilities:**
- Shared helpers: Keep helper functions in `planner.py` while the production code remains a single-module CLI.
- Split modules only when helper groups become independently testable domains; preserve path constants and command entry wiring.

## Special Directories

**`.planning/`:**
- Purpose: GSD project management and codebase mapping artifacts.
- Generated: Partly.
- Committed: Yes.

**`.planning/codebase/`:**
- Purpose: Codebase analysis documents consumed by GSD planning and execution agents.
- Generated: Yes.
- Committed: Yes.

**`.planning/phases/`:**
- Purpose: Phase plans, summaries, review, verification, validation, and security artifacts.
- Generated: Yes.
- Committed: Yes.

**`.pytest_cache/`:**
- Purpose: Pytest runtime cache.
- Generated: Yes.
- Committed: No source changes should target this directory.

**`data/products/`:**
- Purpose: Authoritative product/substance records.
- Generated: No.
- Committed: Yes.

**`schedule.yaml`:**
- Purpose: Generated planner output.
- Generated: Yes.
- Committed: Yes in current repo state.

---

*Structure analysis: 2026-05-05*
