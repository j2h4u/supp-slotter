<!-- refreshed: 2026-05-05 -->
# Architecture

**Analysis Date:** 2026-05-05

## System Overview

```text
┌─────────────────────────────────────────────────────────────┐
│                         CLI Layer                            │
├──────────────────┬──────────────────┬───────────────────────┤
│      check       │      refresh     │         plan          │
│  `planner.py`    │  `planner.py`    │     `planner.py`      │
└────────┬─────────┴────────┬─────────┴──────────┬────────────┘
         │                  │                     │
         ▼                  ▼                     ▼
┌─────────────────────────────────────────────────────────────┐
│                  Validation + Planning Core                  │
│ `planner.py`: schema checks, refs, scoring, search, output   │
└─────────────────────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────────┐
│                   YAML Domain Data + Schemas                 │
│ `data/`, `schema/`, generated `schedule.yaml`                │
└─────────────────────────────────────────────────────────────┘
```

## Component Responsibilities

| Component | Responsibility | File |
|-----------|----------------|------|
| CLI entry point | Defines `check`, `refresh`, and `plan` subcommands and dispatches to command handlers | `planner.py:662` |
| Path constants | Defines canonical repo-relative locations for data, schemas, products, goals, inventory, and schedule output | `planner.py:26` |
| YAML/schema loading | Reads YAML data and JSON Schema files for all command paths | `planner.py:48`, `planner.py:52` |
| Schema validation | Runs Draft 2020-12 validation and reports path-specific schema errors | `planner.py:56` |
| Trait validation | Enforces registered trait namespaces, `separate_from` references, and trait effect match keys | `planner.py:73` |
| Product validation | Validates product cards, filename/id alignment, duplicate ids, trait refs, and `prefer_with` refs | `planner.py:120` |
| Inventory validation | Enforces product-card/inventory alignment and validates `traits_override` references | `planner.py:176`, `planner.py:200` |
| Goal validation | Validates goal cards and checks `members[].substance` references against product cards | `planner.py:218` |
| Refresh command | Adds product cards missing from inventory as `stack: inactive` entries | `planner.py:318` |
| Planning command | Validates first, builds active substances, scores candidates, searches assignments, and writes `schedule.yaml` | `planner.py:427` |
| Behavioral tests | Locks stack partitioning, goal references, activity traits, and generated schedule topology | `tests/test_phase_01.py:66` |

## Pattern Overview

**Overall:** Single-file CLI with declarative data model and schema-guarded YAML records.

**Key Characteristics:**
- Keep domain facts in YAML files under `data/`; keep executable policy in `planner.py`.
- Use JSON Schema files under `schema/` as the first validation layer, then enforce cross-file referential integrity in Python.
- Treat `schedule.yaml` as generated planner output, not hand-authored source data.
- Keep goal membership canonical in `data/goals/*.yaml`; product cards do not carry `goals`.
- Keep stack partitioning explicit in `data/inventory.yaml` using `daily`, `training`, or `inactive`.

## Layers

**Command Layer:**
- Purpose: Parse CLI arguments and route to a command implementation.
- Location: `planner.py:662`
- Contains: `argparse` setup for `check`, `refresh`, and `plan`.
- Depends on: Command functions in the same module.
- Used by: `uv run planner.py <subcommand>` and tests in `tests/test_phase_01.py:56`.

**Validation Layer:**
- Purpose: Reject malformed YAML, schema violations, unknown trait namespaces, bad trait references, bad inventory references, and invalid goal members before planning.
- Location: `planner.py:56`, `planner.py:73`, `planner.py:120`, `planner.py:176`, `planner.py:200`, `planner.py:218`, `planner.py:261`
- Contains: Schema validation helpers and cross-file validators.
- Depends on: `data/slots.yaml`, `data/traits.yaml`, `data/products/*.yaml`, `data/inventory.yaml`, `data/goals/*.yaml`, `schema/*.schema.json`.
- Used by: `cmd_check()` directly and `cmd_plan()` as an implicit preflight.

**Domain Data Layer:**
- Purpose: Store the supplement scheduling ontology as editable data.
- Location: `data/`
- Contains: Slot definitions in `data/slots.yaml`, trait taxonomy in `data/traits.yaml`, inventory in `data/inventory.yaml`, product cards in `data/products/*.yaml`, and goal cards in `data/goals/*.yaml`.
- Depends on: Schema contracts in `schema/*.schema.json`.
- Used by: Validation and planning functions in `planner.py`.

**Planning Layer:**
- Purpose: Assign non-inactive supplements to compatible slots and produce explanation-rich output.
- Location: `planner.py:368`, `planner.py:377`, `planner.py:385`, `planner.py:411`, `planner.py:427`
- Contains: Effective trait calculation, slot matching, score calculation, separation checks, greedy assignment, local search, and schedule serialization.
- Depends on: Validated YAML data and scoring constants in `planner.py:38`.
- Used by: `cmd_plan()` and schedule topology tests in `tests/test_phase_01.py:156`.

**Generated Output Layer:**
- Purpose: Persist the current computed schedule with scores, slot assignments, warnings, `prefer_with` co-location, and per-substance explanations.
- Location: `schedule.yaml`
- Contains: `version`, score fields, search metadata, `slots`, `warnings`, `prefer_with_pairs`, and `explanations`.
- Depends on: `planner.py:585`.
- Used by: The operator and tests that validate generated topology.

## Data Flow

### Primary Request Path

1. CLI dispatch parses `uv run planner.py plan` and calls `cmd_plan()` (`planner.py:662`).
2. `cmd_plan()` runs `cmd_check(None)` before scheduling (`planner.py:427`).
3. `cmd_check()` loads slots and traits, validates schemas, validates trait match fields, scans all product cards, validates inventory, and validates goals (`planner.py:261`).
4. `cmd_plan()` loads `data/slots.yaml`, `data/traits.yaml`, and `data/inventory.yaml` after check passes (`planner.py:436`).
5. Active substances are selected from inventory entries whose `stack` is not `inactive`; card traits and inventory overrides are merged (`planner.py:455`, `planner.py:368`).
6. Candidate slots are limited to the same stack as the substance, scored from trait effects, and filtered for blocks (`planner.py:483`).
7. Greedy assignment places the most constrained substances into the best valid slots while enforcing `separate_from` conflicts (`planner.py:503`, `planner.py:506`).
8. First-improvement local search moves substances when total score improves (`planner.py:544`).
9. `schedule.yaml` is written with scores, slots, warnings, preference pairs, and explanations (`planner.py:585`, `planner.py:638`).

### Validation Flow

1. `uv run planner.py check` invokes `cmd_check(target)` (`planner.py:683`).
2. Slots and traits are loaded from `data/slots.yaml` and `data/traits.yaml` and schema-validated (`planner.py:265`, `planner.py:280`).
3. Slot fields are derived from slot definitions so trait `effects[].match` keys must reference real slot fields (`planner.py:66`, `planner.py:286`).
4. Product cards are scanned from `data/products/*.yaml` or a single target file (`planner.py:291`).
5. Full scans validate inventory alignment and goal-card substance references (`planner.py:300`, `planner.py:312`).
6. `report()` prints `INFO:` messages for unmatched concerns, `ERROR:` messages for failures, and returns a shell status code (`planner.py:249`).

### Refresh Flow

1. `uv run planner.py refresh` invokes `cmd_refresh()` (`planner.py:685`).
2. Existing inventory ids are read from `data/inventory.yaml` (`planner.py:323`).
3. Product cards under `data/products/*.yaml` are scanned for ids missing from inventory (`planner.py:331`).
4. Missing ids are appended to `data/inventory.yaml` with `stack: inactive` (`planner.py:345`).

**State Management:**
- Runtime state is local to command functions and helper variables in `planner.py`.
- Persistent source state lives in YAML under `data/`.
- Generated planner state lives in `schedule.yaml`.
- There is no database, server-side session state, cache, or background worker.

## Key Abstractions

**Slot:**
- Purpose: Represents a schedulable time/context target.
- Examples: `data/slots.yaml`, `schema/slots.schema.json`
- Pattern: A named mapping with `label`, `order`, `stack`, and matchable fields such as `time`, `food`, and `activity`.

**Trait:**
- Purpose: Represents reusable scheduling behavior or metadata attached to product cards.
- Examples: `data/traits.yaml`, `schema/traits.schema.json`
- Pattern: Namespaced ids such as `intake:requires_food`; `effects[].match` uses AND-only slot-field matching implemented by `slot_matches()` in `planner.py:377`.

**Product Card:**
- Purpose: Represents a supplement/substance card and its traits.
- Examples: `data/products/creatine.yaml`, `schema/product.schema.json`
- Pattern: File stem must match `id`; traits must reference `data/traits.yaml`; optional `prefer_with` references another product id.

**Inventory Entry:**
- Purpose: Represents the operator's actual shelf state and stack partition.
- Examples: `data/inventory.yaml`, `schema/inventory.schema.json`
- Pattern: Each product id maps to `stack: daily | training | inactive`, optional dose/brand/notes, and optional `traits_override.add/remove`.

**Goal Card:**
- Purpose: Represents purpose-driven clusters with membership metadata.
- Examples: `data/goals/vascular_health.yaml`, `data/goals/mitochondrial_health.yaml`, `schema/goal.schema.json`
- Pattern: `members[]` are either product-backed via `substance` or candidate-style via `name`; `role` belongs on the membership edge.

**Schedule:**
- Purpose: Generated assignment output and audit trail for the planner.
- Examples: `schedule.yaml`
- Pattern: Contains top-level score fields, search metadata, slot lists, risk warnings, `prefer_with_pairs`, and per-substance `explanations`.

## Entry Points

**Planner CLI:**
- Location: `planner.py:662`
- Triggers: `uv run planner.py check`, `uv run planner.py refresh`, `uv run planner.py plan`
- Responsibilities: Parse command-line arguments and call the matching command handler.

**Check Command:**
- Location: `planner.py:261`
- Triggers: CLI `check`; implicit preflight from `cmd_plan()`.
- Responsibilities: Validate schemas and cross-file references. Use `uv run planner.py check data/products/<id>.yaml` for a single product-card validation path.

**Refresh Command:**
- Location: `planner.py:318`
- Triggers: CLI `refresh`.
- Responsibilities: Append inventory entries for newly added product cards using `stack: inactive`.

**Plan Command:**
- Location: `planner.py:427`
- Triggers: CLI `plan`.
- Responsibilities: Validate, compute active stack-aware schedule, write `schedule.yaml`, and print score/load summary.

**Pytest Suite:**
- Location: `tests/test_phase_01.py:66`
- Triggers: `uv run pytest`
- Responsibilities: Exercise CLI behavior and lock architecture invariants for stacks, goals, activity traits, generated schedule topology, and goal-reference errors.

## Architectural Constraints

- **Threading:** Single-process, single-threaded command-line execution in `planner.py`; no async, workers, queues, or services.
- **Global state:** Module-level constants define paths, registered trait namespaces, scoring weights, and score maps in `planner.py:26`, `planner.py:34`, and `planner.py:38`.
- **Circular imports:** Not applicable; there is one production Python module, `planner.py`.
- **Data encoding:** YAML files are read and written with `allow_unicode=True` where planner output is generated (`planner.py:350`, `planner.py:638`); keep Cyrillic domain notes intact.
- **Schema dialect:** JSON Schemas declare Draft 2020-12 in `schema/*.schema.json`; continue using `jsonschema.Draft202012Validator` in `planner.py:58`.
- **Stack isolation:** Planning candidates must keep `inventory.stack` equal to `slot.stack` (`planner.py:487`); do not add training gating through ad hoc required-trait logic.
- **Goal ownership:** Goal membership lives in `data/goals/*.yaml`; keep product cards free of `goals` fields, as enforced by tests in `tests/test_phase_01.py:120`.

## Anti-Patterns

### Product-Embedded Goals

**What happens:** Adding `goals:` fields to `data/products/*.yaml`.
**Why it's wrong:** Goals are canonical goal-card entities with relationship metadata on `members[]`; product-embedded goals split ownership and bypass `check_goals()` in `planner.py:218`.
**Do this instead:** Add or edit membership in `data/goals/*.yaml` and validate with `uv run planner.py check`.

### Unregistered Trait Namespaces

**What happens:** Creating a trait id with a new namespace in `data/traits.yaml` without updating the namespace registry.
**Why it's wrong:** `check_traits()` rejects namespaces not present in `REGISTERED_NAMESPACES` (`planner.py:35`, `planner.py:79`).
**Do this instead:** Add the namespace to `REGISTERED_NAMESPACES` in `planner.py:35`, update `schema/traits.schema.json` only if the id pattern needs to change, and add tests for the new namespace behavior.

### Hand-Editing Generated Schedule as Source

**What happens:** Treating `schedule.yaml` as the authoritative place to change slot assignments.
**Why it's wrong:** `cmd_plan()` rewrites `schedule.yaml` from `data/` inputs (`planner.py:638`), so manual schedule edits are disposable.
**Do this instead:** Change `data/products/*.yaml`, `data/inventory.yaml`, `data/traits.yaml`, or `data/slots.yaml`, then run `uv run planner.py check` and `uv run planner.py plan`.

### Bypassing Stack Partitioning

**What happens:** Making trait effects or planner branches that allow daily substances into workout slots or training substances into daily slots.
**Why it's wrong:** Stack partitioning is the planner's default-deny boundary (`planner.py:487`) and is covered by schedule topology tests (`tests/test_phase_01.py:156`).
**Do this instead:** Set the product's stack in `data/inventory.yaml` and add slot fields or activity traits only within the matching stack.

## Error Handling

**Strategy:** Collect validation errors into lists, report all known issues together, and return non-zero command status. Fatal planner preconditions return early with stderr messages.

**Patterns:**
- Use `schema_errors()` for structured schema failures (`planner.py:56`).
- Use validator-specific error accumulation for cross-file checks (`planner.py:73`, `planner.py:120`, `planner.py:176`, `planner.py:218`).
- Use `report(errors, info)` to print informational unmatched concerns before errors (`planner.py:249`).
- In tests that intentionally mutate files, restore original bytes in `finally` (`tests/test_phase_01.py:182`).

## Cross-Cutting Concerns

**Logging:** Plain `print()` to stdout/stderr in `planner.py`; validation failures use stderr and info messages use stdout.
**Validation:** JSON Schema plus Python referential checks in `planner.py`; command `plan` always runs `check` first.
**Authentication:** Not applicable; local CLI only.
**Safety Review:** `risk:manual_review` traits in `data/traits.yaml` produce schedule warnings in `schedule.yaml` through `planner.py:626`.

---

*Architecture analysis: 2026-05-05*
