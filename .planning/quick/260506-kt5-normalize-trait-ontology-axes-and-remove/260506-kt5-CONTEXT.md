---
quick_id: 260506-kt5
status: ready_for_planning
created: 2026-05-06
---

# Quick Task 260506-kt5: Normalize trait ontology axes - Context

## Task Boundary

Normalize the current trait ontology where responsibilities are already clear. Reduce unused and overlapping traits without building a future medical ontology.

## Locked Decisions

- Normalize `intake:*` into one explicit food-axis.
- Rename absorption-conflict `family:*_like` traits to `competition:*_absorption`.
- Do not normalize or rename `effect:*` in this quick task.
- Keep `mechanism:*` as marker-only traits.
- Delete unused `risk:*` traits instead of reserving warning taxonomy for the future.
- Make `class:*` marker-only; scheduling effects belong in intake/timing traits, not classes.

## Implementation Direction

- Keep planner mechanics dumb and declarative: execute `effects`, `separate_from`, and `warning`; do not add inference.
- Update substance refs, tests, schedule, and docs together.
- Use `uv run planner.py orphans` as the cleanup gate after the rename/removal.
