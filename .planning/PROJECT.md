# Project: Supplement Slot Planner (supp-slotter)

## Summary

Personal CLI-based supplement scheduling system. Operator authors substance
cards with declarative `traits`. `planner.py` distributes the active inventory
across daily slots based on `slots.yaml` and `traits.yaml`, respecting food
state, time of day, conflicts (separate-from), and load balancing.

Pipeline: `YAML files → planner.py refresh → check → plan → schedule.yaml`.

## Scope

**In scope (MVP and beyond):**
- YAML substance cards (`data/products/*.yaml`) with declarative traits
- Trait taxonomy (`data/traits.yaml`) — namespaces: `intake`, `effect`, `class`, `family`, `risk`, `activity`
- Slot definitions (`data/slots.yaml`) — physical slots tied to operator's pillbox + virtual training slots
- Inventory (`data/inventory.yaml`) — operator's actual shelf with stack assignment
- Goal cards (`data/goals/*.yaml`) — purpose-driven clusters (vascular_health, mitochondrial_health) with members, candidates, declined
- Greedy + first-improvement local search planner
- Stack-aware planning (daily vs training partition)
- JSON-schema validation + referential integrity checks

**Non-goals:**
- UI / database / vector store / graph DB
- Medical ontology, evidence grading, dose modelling, drug interaction taxonomy
- OR-Tools optimization
- Health-metric tracking, history

## Architecture (locked decisions)

- **Slot model:** generic — slot has properties; traits' `effects[].match` matches against slot fields (AND-only)
- **Stack partition:** every substance belongs to exactly one stack (`daily | training | inactive`); planner respects partition, no slot-fragmentation
- **Default-deny on training slots:** achieved via stack partition, not via separate `required_traits` mechanism
- **Trait namespaces:** `intake`, `effect`, `class`, `family`, `risk`, `activity`. Hardcoded list in `planner.py:REGISTERED_NAMESPACES`
- **Goal cards:** goal-master canonical (substance cards do NOT carry `goals:` field). `members[]` with `status: taking | candidate | declined`. `role` is relational metadata, lives on the membership edge
- **Algorithm:** greedy initial assignment + first-improvement local search. Scoring: `slot_scores + prefer_with_bonus − balance_penalty`

## Reference docs

- `idea.md` — full SPEC, 26 sections (pre-GSD authoring; treated as locked SPEC)
- `brief.md` — authoring instructions for substance-card agents
- `current-inventory.md` — operator's informal source list
- `HANDOFF.md` — session handoff (deprecated post-Phase 1; superseded by .planning/STATE.md)

## Current state

Phase 2 (Substance/Product YAML model split) — executed, gap-closed, and
verified. The data model now separates universal substance cards, concrete
product formulas, and inventory items; slots use declarative `near + food`;
the planner schedules physical inventory products as inseparable units with
component-aware explanations and warnings.

Pre-Phase 1 (MVP): 23 substance cards, 4 physical slots, 16 traits in 5 namespaces, working planner with greedy+local search. Baseline `total_score: 32`.
Post-Phase 1: 23 substance cards, 6 slots (4 daily + 2 training), 19 traits in
6 namespaces, 2 goal cards, stack-aware planner. Verified schedule
`total_score: 48.5`.
Post-Phase 2: 43 substance cards, 23 product formulas, 23 inventory entries,
split-model validation, product/component-aware scheduling, and 17-test
regression coverage. Verified schedule quality is 4/5.
