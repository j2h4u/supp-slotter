<!-- refreshed: 2026-05-14 -->
# Architecture

**Analysis Date:** 2026-05-14

## System Overview

```text
+-------------------------------------------------------------+
|                         CLI Layer                            |
|                 `planner/__main__.py`                        |
+-------------+-------------+------------+---------+----------+
|   check     |    plan     |   show     | review  |  find    |
| `engine/`   | `engine/`   | `engine/`  |`engine/`|`engine/` |
+------+------+------+------+-----+------+----+----+----+-----+
       |             |            |           |         |
       v             v            v           v         v
+-------------------------------------------------------------+
|                   Command Engine Layer                       |
| `planner/engine/check.py`, `plan.py`, `show.py`,             |
| `review.py`, `find.py`, `audit.py`, `_scheduling.py`         |
+-----------------------------+-------------------------------+
                              |
                              v
+-------------------------------------------------------------+
|             Typed Card + Validation Layer                    |
| `planner/cards/*.py`, `planner/contracts.py`, `planner/io.py`|
+-----------------------------+-------------------------------+
                              |
                              v
+-------------------------------------------------------------+
|       YAML Source Data + JSON Schemas + Generated Output      |
| `data/`, `schema/`, generated `schedule.yaml`                |
+-------------------------------------------------------------+
```

## Component Responsibilities

| Component | Responsibility | File |
|-----------|----------------|------|
| CLI entry point | Defines `check`, `audit`, `find`, `review`, and `review-substance`; default no-arg path renders the schedule through `cmd_show()` | `planner/__main__.py:18` |
| Engine exports | Re-exports command handlers and result dataclasses for the CLI | `planner/engine/__init__.py:1` |
| Result contracts | Provides structured return values for command paths so tests can assert fields instead of stdout strings | `planner/engine/results.py:1` |
| Repo paths and constants | Defines canonical data/schema/output paths, scoring weights, trait namespaces, ID policy, and schedule YAML comments | `planner/io.py:1` |
| YAML and schema I/O | Loads YAML with mtime caching, loads JSON Schemas, validates Draft 2020-12 schemas, and writes schedule YAML comments | `planner/io.py:60`, `planner/io.py:249` |
| Dataclass contracts | Defines frozen typed shapes for substances, products, dashboards, relations, traits, slots, pillboxes, concerns, and CLI search results | `planner/contracts.py:1` |
| Auto-maintenance | Assigns stable IDs, normalizes card filenames, rewrites references, and guards deterministic rewrites with a lock | `planner/maintenance.py:1` |
| Check command | Runs maintenance, schema validation, and cross-file integrity checks across pillboxes, traits, substances, relations, products, stacks, and dashboards | `planner/engine/check.py:33` |
| Plan command | Builds active product indexes, scores feasible slots, runs branch-and-bound assignment, builds warnings/review output, and writes `schedule.yaml` | `planner/engine/plan.py:685` |
| Scheduling helpers | Aggregates scheduling traits from product components, scores trait effects against slots, and explains placement choices | `planner/engine/_scheduling.py:12` |
| Show command | Regenerates `schedule.yaml` through `cmd_plan()` and prints the human pillbox layout | `planner/engine/show.py:25` |
| Review command | Prints concerns, relation status, risk flags, pathway memberships, and dashboard coverage for active stack substances | `planner/engine/review.py:269` |
| Find command | Validates and normalizes before fuzzy-searching substance/product card text | `planner/engine/find.py:30` |
| Card loaders | Convert YAML mappings into dataclass instances and provide validation/search/formatting helpers per card type | `planner/cards/substance.py:27`, `planner/cards/product.py:15`, `planner/cards/dashboards.py:17`, `planner/cards/pillboxes.py:12`, `planner/cards/traits.py:37`, `planner/cards/relations.py:18` |
| Authoring scripts | Provide one-off audit and migration helpers outside the primary CLI command surface | `scripts/card_audit.py:1`, `scripts/migrate_substance_cards.py:1` |

## Pattern Overview

**Overall:** YAML-first local CLI with schema-guarded domain cards, typed dataclass loaders, command-oriented engine modules, and generated schedule output.

**Key Characteristics:**
- Keep source-of-truth domain facts in YAML under `data/`; executable policy lives in `planner/`.
- Load YAML through `planner/cards/*` modules into frozen dataclasses from `planner/contracts.py` before planning or review logic.
- Run deterministic maintenance before validation/search/planning so IDs, filenames, and references stay canonical.
- Treat `schedule.yaml` as generated output; change source cards under `data/` and regenerate.
- Separate scheduling facts (`schedule:` fields on substances) from reviewer facts (`knowledge:` fields on substances).
- Keep product components together as the schedulable unit; substances contribute traits, warnings, dashboards, and relations.

## Layers

**Command Layer:**
- Purpose: Parse CLI arguments and route to engine handlers.
- Location: `planner/__main__.py`
- Contains: `argparse` setup for `check`, `audit`, `find`, `review`, and `review-substance`; default no-arg execution calls `cmd_show()`.
- Depends on: Re-exported command functions from `planner/engine/__init__.py`.
- Used by: `uv run python -m planner`, `just test`, tests under `tests/`.

**Engine Layer:**
- Purpose: Implement user-visible workflows as composable command functions.
- Location: `planner/engine/`
- Contains: Validation workflow in `planner/engine/check.py`, scheduling in `planner/engine/plan.py`, display in `planner/engine/show.py`, review in `planner/engine/review.py`, search in `planner/engine/find.py`, audit in `planner/engine/audit.py`, and pure scheduling helpers in `planner/engine/_scheduling.py`.
- Depends on: `planner/cards/*`, `planner/contracts.py`, `planner/io.py`, `planner/maintenance.py`.
- Used by: CLI entry point and pytest tests.

**Card Layer:**
- Purpose: Own per-domain-object parsing, validation, formatting, search, and relationship helpers.
- Location: `planner/cards/`
- Contains: `substance.py`, `product.py`, `dashboards.py`, `pillboxes.py`, `traits.py`, `relations.py`, `stacks.py`, `warnings.py`, `schedule.py`, `search.py`, `_common.py`.
- Depends on: YAML/schema primitives from `planner/io.py` and dataclasses from `planner/contracts.py`.
- Used by: Engine command modules.

**Contract Layer:**
- Purpose: Define stable in-memory shapes for YAML cards and command results.
- Location: `planner/contracts.py`, `planner/engine/results.py`
- Contains: Frozen dataclasses for domain cards and result dataclasses for command return values.
- Depends on: Standard-library dataclasses and typing.
- Used by: Engine, card loaders, tests.

**Persistence Layer:**
- Purpose: Store editable domain data, JSON Schemas, and generated planner output.
- Location: `data/`, `schema/`, `schedule.yaml`
- Contains: Product cards, substance cards, stacks, pillboxes, relations, traits, dashboards, schemas, and generated schedule report.
- Depends on: JSON Schema files under `schema/`.
- Used by: `planner/io.py`, `planner/cards/*`, `planner/engine/*`.

**Documentation and Agent Guidance Layer:**
- Purpose: Keep human/agent operating rules close to the repo.
- Location: `SKILL.md`, `README.md`, `docs/`
- Contains: Domain model, ontology stress tests, onboarding/editing workflow, and project overview.
- Depends on: Current data model and CLI behavior.
- Used by: Humans and coding agents before data/model edits.

## Data Flow

### Primary Request Path

1. User runs `uv run python -m planner` with no args; `main()` dispatches to `cmd_show()` (`planner/__main__.py:18`).
2. `cmd_show()` calls `cmd_plan()` before rendering so output reflects current source cards (`planner/engine/show.py:25`).
3. `cmd_plan()` runs `cmd_check()` as its preflight (`planner/engine/plan.py:685`).
4. `cmd_check()` runs `run_auto_maintenance()` and then validates schemas/cross-file references (`planner/engine/check.py:33`, `planner/maintenance.py:382`).
5. `cmd_plan()` loads pillboxes, traits, stacks, substances, products, relations, and dashboards into `PlanInputs` (`planner/engine/plan.py:47`).
6. `_build_active_index()` converts active stack entries into product/component/trait/conflict indexes (`planner/engine/plan.py:95`).
7. `_run_plan_search()` uses greedy seeding plus branch-and-bound search to assign active stack items to slots (`planner/engine/plan.py:478`).
8. `_build_schedule_output()` creates summary, pillboxes, benefits, risks, warnings, kept-together pairs, and explanations (`planner/engine/plan.py:274`).
9. `cmd_plan()` writes generated `schedule.yaml` via `dump_schedule_yaml()` (`planner/engine/plan.py:872`, `planner/io.py:164`).
10. `cmd_show()` reads `schedule.yaml` and prints the non-empty pillbox layout (`planner/engine/show.py:45`).

### Validation Flow

1. `cmd_check()` enters optional test-data root patching through `maybe_patch_root()` (`planner/engine/check.py:33`, `planner/engine/_root_patch.py`).
2. `run_auto_maintenance()` detects missing IDs or non-canonical filenames and acquires `.planner-maintenance.lock` only when work is needed (`planner/maintenance.py:382`).
3. Schema checks validate `data/pillboxes.yaml`, `data/traits.yaml`, `data/relations.yaml`, `data/stacks.yaml`, and all collection files under `data/substances/`, `data/products/`, and `data/dashboards/` (`planner/io.py:249`).
4. Cross-reference checks enforce unique slot IDs, registered trait namespaces, valid `prefer_with` references, relation endpoints, product component references, stack product references, and dashboard `from_traits` references (`planner/engine/check.py:33`).
5. Errors and info lines flow through `report()` and are returned as `CheckResult` (`planner/io.py:238`, `planner/engine/results.py:10`).

### Review Flow

1. `cmd_review()` loads substance/product registries, stack entries, global relations, and dashboard files (`planner/engine/review.py:269`).
2. Active substances are derived from product components referenced by non-inactive stack entries (`planner/engine/review.py:36`).
3. Output groups concerns, relation status, risk flags, pathway memberships, and dashboard coverage (`planner/engine/review.py:74`).
4. `cmd_review_substance()` validates a single `data/substances/*.yaml` path, loads the substance, prints central relation matches, and renders grouped trait checklist details (`planner/engine/review.py:291`).

**State Management:**
- Runtime state is local and file-backed. Source state lives in `data/`; generated state lives in `schedule.yaml`.
- In-memory state uses immutable dataclasses for card objects and plain dictionaries/lists for generated schedule structures.
- Cross-test state is isolated by `data_root` parameters and `planner/engine/_root_patch.py`.
- The only explicit lock is `.planner-maintenance.lock`, used while auto-maintenance performs file rewrites.

## Key Abstractions

**Substance:**
- Purpose: Reusable active ingredient/form card with scheduling and reviewer traits.
- Examples: `planner/contracts.py`, `planner/cards/substance.py`, `data/substances/*.yaml`, `schema/substance.schema.json`
- Pattern: YAML card -> schema validation -> frozen `Substance` dataclass.

**Product:**
- Purpose: Physical label-backed item that owns brand/name, URLs, and component substance references.
- Examples: `planner/contracts.py`, `planner/cards/product.py`, `data/products/*.yaml`, `schema/product.schema.json`
- Pattern: Product ID is the schedulable stack item; product components stay together.

**TraitDef:**
- Purpose: Declarative rule/classification loaded from grouped namespaces in `data/traits.yaml`.
- Examples: `planner/contracts.py`, `planner/cards/traits.py`, `data/traits.yaml`, `schema/traits.schema.json`
- Pattern: `namespace:short_name` IDs; scheduling namespaces produce slot effects, reviewer namespaces produce review context.

**Pillbox and Slot:**
- Purpose: Convert stack-level organizers and slot metadata into flattened scheduling targets.
- Examples: `planner/contracts.py`, `planner/cards/pillboxes.py`, `data/pillboxes.yaml`, `schema/pillboxes.schema.json`
- Pattern: Each pillbox maps to a stack; slots expose `near` and `food` fields for trait-effect matching.

**Relation:**
- Purpose: Centralized substance-to-substance and class-to-class review/scheduling links.
- Examples: `planner/contracts.py`, `planner/cards/relations.py`, `data/relations.yaml`, `schema/relations.schema.json`
- Pattern: `balance`, `supports`, `competes`, and `antagonizes`; `competes` can block co-slot placement.

**Dashboard:**
- Purpose: Benefit/risk review cluster resolved dynamically from `from_traits`.
- Examples: `planner/contracts.py`, `planner/cards/dashboards.py`, `data/dashboards/*.yaml`, `schema/dashboard.schema.json`
- Pattern: Dashboard YAML contains narrative text and projection rule, while substance cards carry membership traits.

**PlanInputs and ActiveIndex:**
- Purpose: Internal scheduling data bundles that separate static loaded inputs from active-stack derived indexes.
- Examples: `planner/engine/plan.py:29`, `planner/engine/plan.py:40`
- Pattern: NamedTuple bundles used to keep plan search helpers explicit and testable.

## Entry Points

**Planner CLI:**
- Location: `planner/__main__.py`
- Triggers: `uv run python -m planner`, `uv run python -m planner check`, `uv run python -m planner review`, `uv run python -m planner audit`, `uv run python -m planner find <words>`, `uv run python -m planner review-substance <path>`.
- Responsibilities: Parse args and dispatch to engine commands.

**Default schedule display:**
- Location: `planner/engine/show.py`
- Triggers: `uv run python -m planner`.
- Responsibilities: Regenerate `schedule.yaml` and print a compact pillbox view.

**Validation command:**
- Location: `planner/engine/check.py`
- Triggers: `uv run python -m planner check`, `just test`, `cmd_plan()`.
- Responsibilities: Normalize deterministic card metadata and enforce schema/cross-reference constraints.

**Schedule generation command:**
- Location: `planner/engine/plan.py`
- Triggers: `uv run python -m planner` through `cmd_show()`, direct `cmd_plan()` calls, and tests.
- Responsibilities: Validate, solve slot assignment, generate schedule review report, and write `schedule.yaml`.

**Review commands:**
- Location: `planner/engine/review.py`
- Triggers: `uv run python -m planner review`, `uv run python -m planner review-substance data/substances/<card>.yaml`.
- Responsibilities: Surface reviewer-only knowledge, concerns, relations, and trait checklist output.

**Search command:**
- Location: `planner/engine/find.py`
- Triggers: `uv run python -m planner find <words>`.
- Responsibilities: Schema-check, normalize, then fuzzy-search products and substances.

**Maintenance scripts:**
- Location: `scripts/card_audit.py`, `scripts/migrate_substance_cards.py`
- Triggers: Direct `uv run python scripts/<name>.py` execution.
- Responsibilities: One-off deeper card audit and v1-to-v2 substance-card migration support.

## Architectural Constraints

- **Threading:** Single-process, synchronous CLI execution. No async runtime or worker pool is used.
- **Global state:** Path constants and scoring constants live in `planner/io.py`; tests can patch repo-root paths through `planner/engine/_root_patch.py`.
- **Generated output:** `schedule.yaml` is generated by `cmd_plan()` and must not be hand-edited.
- **Deterministic rewrites:** `check`, `plan`, `find`, and `show` can trigger auto-maintenance writes for IDs, filenames, and references through `planner/maintenance.py`.
- **Locking:** `.planner-maintenance.lock` protects maintenance rewrites; there is no broader database transaction layer.
- **Circular imports:** No circular import chain is exposed by the current module structure; `planner/engine/__init__.py` only re-exports command functions and result types.
- **Data model scope:** Keep regimen tracking, medical decisioning, dose optimization, evidence grading, and SaaS/app concerns outside the runtime unless a concrete planner/checker need exists; this constraint is documented in `SKILL.md` and `README.md`.

## Anti-Patterns

### Editing Generated Schedule

**What happens:** `schedule.yaml` is modified directly.
**Why it's wrong:** The next `cmd_plan()` or default `cmd_show()` run replaces it from `data/` inputs.
**Do this instead:** Edit source cards under `data/`, then run `uv run python -m planner` to regenerate the schedule through `cmd_show()` / `cmd_plan()`.

### Putting Relations In Substance Cards

**What happens:** Substance-to-substance interaction facts are added to `data/substances/*.yaml`.
**Why it's wrong:** Relation matching, relation review, and co-slot conflict logic read `data/relations.yaml`.
**Do this instead:** Add `balance`, `supports`, `competes`, or `antagonizes` entries to `data/relations.yaml` and let `planner/cards/relations.py` resolve endpoints.

### Using Dashboard YAML As A Member List

**What happens:** A dashboard is treated as owning explicit substance members.
**Why it's wrong:** Dashboards resolve membership from `from_traits`; direct member-list semantics are not part of `schema/dashboard.schema.json`.
**Do this instead:** Add dashboard membership tags to `knowledge.dashboard` on substance cards and keep dashboard projection rules in `data/dashboards/*.yaml` (`planner/cards/dashboards.py:79`).

### Bypassing Card Loaders

**What happens:** Engine code hand-parses card dictionaries instead of using `planner/cards/*` loaders.
**Why it's wrong:** The loaders centralize schema validation, dataclass conversion, formatting, search text, and file naming rules.
**Do this instead:** Add loader/check/format behavior to the owning `planner/cards/<domain>.py` module and consume its dataclasses in `planner/engine/*`.

## Error Handling

**Strategy:** Fail fast on malformed source data, collect cross-reference errors where useful, and return structured command results with exit codes.

**Patterns:**
- Use `CardLoadError` for card read/parse/schema/required-field failures (`planner/contracts.py:26`).
- Return result dataclasses such as `CheckResult`, `PlanResult`, and `ReviewResult` from engine commands (`planner/engine/results.py`).
- Print human-facing validation errors through `report()` for check-style commands (`planner/io.py:238`).
- Continue past malformed optional cards only where the command can safely skip them, such as registry loading warnings in `planner/cards/product.py` and `planner/cards/substance.py`.
- Use `validate_schemas()` before commands that search or inspect cards outside full planning (`planner/io.py:249`, `planner/engine/find.py:30`, `planner/engine/review.py:291`).

## Cross-Cutting Concerns

**Logging:** Console stdout/stderr only. User-facing commands print summaries; validation errors go to stderr through `report()` and direct command messages.

**Validation:** JSON Schema validation in `planner/io.py` plus cross-file Python validation in `planner/engine/check.py` and `planner/cards/*`.

**Authentication:** Not applicable. The application is a local CLI over local YAML files.

**Search:** `planner/engine/find.py` uses normalized card text and scoring helpers from `planner/cards/search.py`; it searches products and substances only.

**Testing:** Pytest tests under `tests/` cover schema shape, maintenance, scheduling units, phase contracts, review command behavior, and primary-component scoring.

---

*Architecture analysis: 2026-05-14*
