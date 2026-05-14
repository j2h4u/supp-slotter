# Codebase Structure

**Analysis Date:** 2026-05-14

## Directory Layout

```text
supp-slotter/
├── SKILL.md                  # Agent operating guide for this repository
├── README.md                 # Human-facing project overview and workflow
├── pyproject.toml            # Python package, dependency, lint, and type config
├── justfile                  # Test/lint/typecheck command aliases
├── uv.lock                   # Locked Python dependency graph
├── schedule.yaml             # Generated schedule report from planner commands
├── planner/                  # CLI/runtime Python package
│   ├── __main__.py           # `python -m planner` argparse entry point
│   ├── contracts.py          # Frozen domain dataclasses and CardLoadError
│   ├── io.py                 # Repo paths, YAML/schema I/O, constants, reporting
│   ├── maintenance.py        # Deterministic ID/filename/reference normalization
│   ├── cards/                # Per-card-type loaders, validators, formatters
│   └── engine/               # Command implementations and scheduling solver
├── data/                     # Authoritative editable YAML domain data
│   ├── stacks.yaml           # Product stack membership: daily/training/inactive
│   ├── pillboxes.yaml        # Pillbox and slot definitions
│   ├── traits.yaml           # Trait namespaces and effects
│   ├── relations.yaml        # Centralized substance relation graph
│   ├── products/             # 57 physical product cards
│   ├── substances/           # 197 concrete substance/form cards
│   └── dashboards/           # 13 benefit/risk dashboard clusters
├── schema/                   # JSON Schema contracts and YAML templates
├── docs/                     # Domain model and ontology reference docs
├── scripts/                  # One-off audit and migration helpers
├── tests/                    # Pytest regression suite
└── .planning/                # GSD roadmap, phases, reviews, and codebase maps
```

## Directory Purposes

**Root:**
- Purpose: Holds repository-level workflow files, generated schedule output, and project overview.
- Contains: `SKILL.md`, `README.md`, `pyproject.toml`, `justfile`, `uv.lock`, `schedule.yaml`.
- Key files: `SKILL.md`, `README.md`, `pyproject.toml`, `justfile`, `schedule.yaml`.

**`planner/`:**
- Purpose: Runtime implementation for validation, planning, review, search, and maintenance.
- Contains: CLI entry point, shared contracts/I/O, command engines, card-domain modules.
- Key files: `planner/__main__.py`, `planner/contracts.py`, `planner/io.py`, `planner/maintenance.py`.

**`planner/engine/`:**
- Purpose: User-visible command workflows and scheduling internals.
- Contains: `cmd_*` implementations, command result exports, root patch helper, slot-assignment helpers.
- Key files: `planner/engine/check.py`, `planner/engine/plan.py`, `planner/engine/show.py`, `planner/engine/review.py`, `planner/engine/find.py`, `planner/engine/audit.py`, `planner/engine/_scheduling.py`, `planner/engine/results.py`.

**`planner/cards/`:**
- Purpose: Domain-card loaders, validators, search/format helpers, and schedule/review helper logic.
- Contains: One module per domain object plus common/search/warning helpers.
- Key files: `planner/cards/substance.py`, `planner/cards/product.py`, `planner/cards/relations.py`, `planner/cards/traits.py`, `planner/cards/pillboxes.py`, `planner/cards/dashboards.py`, `planner/cards/stacks.py`, `planner/cards/warnings.py`, `planner/cards/schedule.py`.

**`data/`:**
- Purpose: Authoritative YAML source data for the local supplement stack.
- Contains: Stack membership, pillboxes, traits, centralized relations, product cards, substance cards, dashboard cards.
- Key files: `data/stacks.yaml`, `data/pillboxes.yaml`, `data/traits.yaml`, `data/relations.yaml`, `data/products/*.yaml`, `data/substances/*.yaml`, `data/dashboards/*.yaml`.

**`data/products/`:**
- Purpose: Store one physical label-backed product card per product ID.
- Contains: YAML files named `<brand_slug>__<product_slug>__<prd_id>.yaml`.
- Key files: `data/products/*.yaml`.

**`data/substances/`:**
- Purpose: Store one reusable substance/form card per substance ID.
- Contains: YAML files named `<substance_slug>__<sub_id>.yaml`.
- Key files: `data/substances/*.yaml`.

**`data/dashboards/`:**
- Purpose: Store dashboard cluster metadata and `from_traits` projection rules.
- Contains: Benefit/risk dashboard YAML cards.
- Key files: `data/dashboards/*.yaml`.

**`schema/`:**
- Purpose: Define machine-checked contracts for source YAML files and starter templates for new cards.
- Contains: Draft JSON Schemas and YAML card templates.
- Key files: `schema/substance.schema.json`, `schema/product.schema.json`, `schema/dashboard.schema.json`, `schema/traits.schema.json`, `schema/relations.schema.json`, `schema/stacks.schema.json`, `schema/pillboxes.schema.json`, `schema/templates/product.yaml`, `schema/templates/substance.yaml`.

**`docs/`:**
- Purpose: Human-readable domain model and ontology pressure/reference material.
- Contains: Current domain model and ontology fact stress tests.
- Key files: `docs/domain-model.md`, `docs/ontology-facts.md`.

**`scripts/`:**
- Purpose: One-off maintenance helpers that are outside the primary CLI surface.
- Contains: Card audit and v1-to-v2 substance migration scripts.
- Key files: `scripts/card_audit.py`, `scripts/migrate_substance_cards.py`.

**`tests/`:**
- Purpose: Regression coverage for schemas, validation, maintenance, scheduling behavior, review output, and scoring rules.
- Contains: Pytest files and shared helpers.
- Key files: `tests/conftest.py`, `tests/helpers.py`, `tests/test_schemas.py`, `tests/test_maintenance.py`, `tests/test_scheduling_units.py`, `tests/test_review_command.py`, `tests/test_primary_component_scoring.py`, `tests/test_phase_02.py`, `tests/test_phase_03.py`.

**`.planning/`:**
- Purpose: GSD planning state, phase artifacts, reviews, notes, and codebase maps.
- Contains: `.planning/codebase/`, `.planning/phases/`, `.planning/quick/`, `.planning/reviews/`, `.planning/notes/`.
- Key files: `.planning/codebase/ARCHITECTURE.md`, `.planning/codebase/STRUCTURE.md`.

## Key File Locations

**Entry Points:**
- `planner/__main__.py`: CLI entry point for `python -m planner`.
- `planner/engine/show.py`: Default no-arg schedule display path.
- `planner/engine/check.py`: Validation and maintenance preflight command.
- `planner/engine/plan.py`: Schedule generation and solver command.
- `planner/engine/review.py`: Stack review and single-substance review commands.
- `planner/engine/find.py`: Product/substance fuzzy search command.
- `scripts/card_audit.py`: One-off deeper substance audit script.
- `scripts/migrate_substance_cards.py`: One-off substance card migration script.

**Configuration:**
- `pyproject.toml`: Python version, dependencies, Ruff config, and Pyright config.
- `justfile`: Standard `test`, `lint`, `typecheck`, `check`, and `fmt` commands.
- `uv.lock`: Dependency lockfile.
- `planner/io.py`: Runtime path constants, scoring constants, registered namespaces, output comments.
- `data/traits.yaml`: Trait registry and scheduling effects.
- `data/pillboxes.yaml`: Slot definitions for schedulable stacks.
- `data/stacks.yaml`: Active/inactive product membership.
- `schema/*.schema.json`: YAML data contracts.

**Core Logic:**
- `planner/contracts.py`: Domain dataclass contracts.
- `planner/io.py`: YAML parsing, schema loading, validation, reporting, schedule serialization.
- `planner/maintenance.py`: Stable ID generation, canonical filename normalization, reference rewrites, maintenance lock.
- `planner/engine/check.py`: Full repository data validation.
- `planner/engine/plan.py`: Active index construction, prefer-with pairing, branch-and-bound assignment, schedule output.
- `planner/engine/_scheduling.py`: Trait aggregation, slot scoring, placement explanation.
- `planner/cards/substance.py`: Substance loading/search/validation/naming.
- `planner/cards/product.py`: Product loading/search/validation/naming.
- `planner/cards/relations.py`: Relation loading, matching, validation, warning/blocking helpers.
- `planner/cards/dashboards.py`: Dashboard loading, `from_traits` resolution, dashboard review output.
- `planner/cards/traits.py`: Trait flattening, namespace validation, readable trait rendering.
- `planner/cards/pillboxes.py`: Pillbox/slot loading and schedule skeleton creation.
- `planner/cards/stacks.py`: Stack entry normalization and validation.
- `planner/cards/warnings.py`: Warning collection and humanization.
- `planner/cards/schedule.py`: Schedule summary and placement note helpers.

**Testing:**
- `tests/conftest.py`: Pytest setup.
- `tests/helpers.py`: Shared test helpers.
- `tests/test_schemas.py`: Schema/data shape coverage.
- `tests/test_maintenance.py`: Auto-maintenance and canonicalization coverage.
- `tests/test_scheduling_units.py`: Scheduling helper behavior.
- `tests/test_primary_component_scoring.py`: Primary/secondary component scoring behavior.
- `tests/test_review_command.py`: Review command output behavior.
- `tests/test_phase_02.py`, `tests/test_phase_03.py`: Phase-level regression contracts.

**Documentation:**
- `SKILL.md`: Agent-specific operating rules and edit workflow.
- `README.md`: Project overview, quick start, non-goals, and structure.
- `docs/domain-model.md`: Authoritative domain model and ontology ownership rules.
- `docs/ontology-facts.md`: Ontology stress-test facts.

## Naming Conventions

**Files:**
- Python modules use lowercase snake_case: `planner/engine/_scheduling.py`, `planner/cards/_common.py`.
- Private helper modules use leading underscore: `planner/engine/_root_patch.py`, `planner/cards/_common.py`.
- Product card filenames use `<brand_slug>__<product_slug>__<prd_id>.yaml`: `data/products/*.yaml`.
- Substance card filenames use `<substance_slug>__<sub_id>.yaml`: `data/substances/*.yaml`.
- JSON Schemas use `<domain>.schema.json`: `schema/product.schema.json`, `schema/substance.schema.json`.
- Tests use `test_<behavior>.py`: `tests/test_maintenance.py`, `tests/test_review_command.py`.

**Directories:**
- Runtime package directories are plural by domain grouping: `planner/cards/`, `planner/engine/`.
- Data collection directories are plural: `data/products/`, `data/substances/`, `data/dashboards/`.
- Template files live under `schema/templates/`.

## Where to Add New Code

**New CLI Command:**
- Primary code: add `cmd_<name>()` in `planner/engine/<name>.py`.
- CLI dispatch: add parser and dispatch branch in `planner/__main__.py`.
- Re-export: add command/result exports in `planner/engine/__init__.py`.
- Tests: add focused tests under `tests/test_<name>.py` or extend the nearest existing test file.

**New Card Type:**
- Implementation: add loader/check/format helpers in `planner/cards/<domain>.py`.
- Contract: add dataclass shape in `planner/contracts.py`.
- Schema: add `schema/<domain>.schema.json`.
- Data: add source files under `data/<domain>/` or a single `data/<domain>.yaml` depending on cardinality.
- Validation: integrate checks into `planner/engine/check.py`.
- Tests: add schema and cross-reference coverage under `tests/`.

**New Scheduling Rule:**
- Trait config: add/update namespace entries in `data/traits.yaml`.
- Schema constraints: update `schema/traits.schema.json` or `schema/substance.schema.json` if the data shape changes.
- Runtime scoring: update `planner/engine/_scheduling.py` when the rule changes how traits aggregate, score, block, or explain slots.
- Plan integration: update `planner/engine/plan.py` when the rule needs active-index, global-search, or output changes.
- Tests: add unit coverage in `tests/test_scheduling_units.py` or behavior coverage in a new scheduling test.

**New Review Signal:**
- Data model: prefer `data/relations.yaml`, `data/dashboards/*.yaml`, or `knowledge:` fields in `data/substances/*.yaml` according to `docs/domain-model.md`.
- Runtime output: update `planner/engine/review.py`, `planner/cards/warnings.py`, or `planner/cards/dashboards.py`.
- Tests: add review-output coverage in `tests/test_review_command.py`.

**New Product/Substance Data:**
- Product cards: create from `schema/templates/product.yaml` into `data/products/`.
- Substance cards: create from `schema/templates/substance.yaml` into `data/substances/`.
- Do not invent stable IDs for new cards; run `uv run python -m planner check` to assign IDs and canonical filenames through `planner/maintenance.py`.
- Search first with `uv run python -m planner find "<name form brand>"`.

**Utilities:**
- Shared card helpers: `planner/cards/_common.py`.
- Shared command result types: `planner/engine/results.py`.
- Shared runtime constants and I/O helpers: `planner/io.py`.
- One-off migration/audit helpers: `scripts/`.

## Special Directories

**`data/`:**
- Purpose: Editable source-of-truth domain data.
- Generated: No.
- Committed: Yes.

**`schedule.yaml`:**
- Purpose: Generated schedule/review report.
- Generated: Yes.
- Committed: Yes, but edit source data rather than this file.

**`schema/templates/`:**
- Purpose: Starter YAML card templates for products and substances.
- Generated: No.
- Committed: Yes.

**`.planning/`:**
- Purpose: GSD workflow state, phase artifacts, reviews, and codebase maps.
- Generated: Partly.
- Committed: Project-dependent; codebase maps are written here for planner/executor agents.

**`.pytest_cache/` and `.ruff_cache/`:**
- Purpose: Tool caches.
- Generated: Yes.
- Committed: No.

**`__pycache__/`:**
- Purpose: Python bytecode cache.
- Generated: Yes.
- Committed: No.

**`.planner-maintenance.lock`:**
- Purpose: Runtime lock directory for deterministic auto-maintenance rewrites.
- Generated: Yes, transient.
- Committed: No.

---

*Structure analysis: 2026-05-14*
