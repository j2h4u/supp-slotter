---
phase: quick-260516-pz4
plan: "01"
subsystem: maintenance
tags: [atomicity, refactor, testing]
dependency_graph:
  requires: []
  provides: [atomic-auto-maintenance]
  affects: [planner/maintenance.py, tests/test_maintenance.py]
tech_stack:
  added: [dataclasses.dataclass, os.replace]
  patterns: [plan-stage-commit-abort lifecycle, .tmp sibling staging]
key_files:
  created: []
  modified:
    - planner/maintenance.py
    - tests/test_maintenance.py
decisions:
  - "_EditPlan lives in maintenance.py as a private module-level dataclass (no new module) — it is consumed by exactly one function and splitting would create circular imports"
  - "Only plan entries for cards that actually need work (needs_new_id or filename rename) — skipping unchanged cards preserves yaml byte-identity invariant"
  - "os.replace chosen as commit primitive — atomic on POSIX, overwrites target in a single syscall"
  - ".tmp.<pid>.<urandom-4-hex> suffix chosen — never matches *.yaml glob, avoids inter-run collisions"
  - "data dir chmod(0o555) used in stacks-write-fails test instead of stacks.yaml chmod(0o444) — rename(2) overwrites read-only targets in writable directories, so the old mechanism no longer triggers a staging failure"
metrics:
  duration: "~25 min"
  completed: "2026-05-16"
  tasks: 1
  files: 2
---

# Phase quick-260516-pz4 Plan 01: Atomic Auto-Maintenance Stage-Edits Summary

**One-liner:** Replaced three independent sequential-write phases in `_run_auto_maintenance_unlocked` with a single `_EditPlan` lifecycle (plan → stage via `.tmp` siblings → commit via `os.replace` → cleanup), so a mid-run failure leaves the data directory byte-identical to its pre-call state.

## Approach

### _EditPlan design

`_EditPlan` is a private dataclass at module scope in `planner/maintenance.py`.  It holds a list of `_EditPlanEntry` (final_path, new_content, obsolete_path) and a `_staged` list of `(tmp_path, final_path)` pairs built during staging.

- **stage()** — iterates entries, writes each to `final_path + ".tmp.<pid>.<hex>"`, appends to `_staged` on success. On any `OSError`, unlinks all already-staged tmps and returns `False`.
- **commit()** — iterates `_staged`, calls `os.replace(tmp_path, final_path)` for each. After all renames, unlinks `obsolete_path` entries (old card paths for renames). On `os.replace` failure, cleans up remaining tmps and re-raises with a loud stderr diagnostic.
- **abort()** — idempotent; unlinks any leftover tmps (called when stage returns False or externally).

### Plan-builder helpers

Two new private helpers build plan entries without touching disk:

- `_plan_card_dir(cards_dir, canonical_fn, id_prefix, plan)` — computes desired final state for all YAML cards. Critically, **only appends a plan entry when `needs_new_id` or `path != final_path`** — cards already in their canonical form are skipped entirely. This preserves the byte-identity invariant (no yaml.safe_dump reformat of unchanged files).
- `_plan_substance_ref_rewrites(data_dir, substance_renames, plan, already_planned)` — computes post-rewrite dicts for products, dashboards, and substances (prefer_with); adds entries only for files that actually changed AND aren't already in the plan from `_plan_card_dir`.

### _run_auto_maintenance_unlocked pipeline

```
1. Plan substances (_plan_card_dir) → substance_renames, substance_file_moves
2. Plan substance-ref rewrites (_plan_substance_ref_rewrites)
3. Plan products (_plan_card_dir) → product_renames, product_file_moves
4. Plan stacks rewrite (if product_renames non-empty)
5. edit_plan.stage() → return 1 on False
6. edit_plan.commit() → return 1 on OSError
7. Print summary (same counter logic as before)
```

### Legacy helpers preserved

`normalize_substances` and `_normalize_card_dir` keep their public signatures and direct-write semantics (internally they now build a plan and execute it, but callers see identical behavior). They were only called internally within `_run_auto_maintenance_unlocked` in this codebase, but kept callable per plan spec.

## Test adaptations

### test_run_auto_maintenance_returns_1_when_stacks_write_fails (adapted)

Changed failure injection from `stacks_path.chmod(0o444)` to `(tmp_path / "data").chmod(0o555)` with `0o755` restore in `finally`. The old mechanism stopped working because `os.replace` (rename(2)) can overwrite a read-only target file as long as the containing directory is writable — so chmod on the target file no longer blocked the staging write. Making the data directory itself read-only causes the `.tmp` sibling write to fail with EACCES. Test name and assertions (`result == 1`, `"stacks.yaml" in captured.err`) are unchanged.

### test_run_auto_maintenance_rolls_back_on_partial_stage_failure (new)

Uses `_build_rename_tree` to create a rename-eligible substance/product/stacks tree. Snapshots all file paths + byte content before calling `run_auto_maintenance`. Monkeypatches `_EditPlan.stage` to fail `Path.write_text` on the second call (first `.tmp` succeeds, proving rollback exercises the "already staged" cleanup path). Asserts:
- `result == 1`
- Every original file still exists at its original path with original bytes
- No `*.tmp.*` orphans under `data/` (recursive glob)
- `maintenance_lock` does not exist (released)

## Coverage delta

`planner/maintenance.py` coverage: ~64% (up from ~58% estimated for the old code given the new lines added). Total coverage: **83.08%** (threshold 83%).

The lower per-module percentage reflects the new uncovered legacy-helper bodies (the old `_normalize_card_dir` direct-write path, the stacks commit-failure diagnostic, etc.) — these are defensive code paths that are difficult to exercise without a test that catches the commit phase.

## Known Stubs

None.

## Threat Flags

None — no new network endpoints, auth paths, or trust boundaries introduced.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] yaml.safe_dump reformat of unchanged cards**
- **Found during:** Implementation verification (git status showed 90+ data/*.yaml files modified after `uv run python -m planner`)
- **Issue:** `_plan_card_dir` initially added a plan entry for every card in the directory, causing `yaml.safe_dump` to reformat YAML that was already canonical (whitespace reflow in long string values). This violated the no-op byte-identity invariant.
- **Fix:** Guard plan-entry creation: only append an entry when `needs_new_id or path != final_path`. Unchanged cards are now skipped entirely.
- **Files modified:** `planner/maintenance.py` (same commit)

**2. [Rule 1 - Bug] os.replace overwrites 0o444 targets**
- **Found during:** Adapting the existing stacks-write-fails test
- **Issue:** The old test used `stacks_path.chmod(0o444)` to trigger an OSError. After the refactor, writes go through a `.tmp` sibling which is then renamed via `os.replace`. The rename(2) syscall overwrites a read-only target file as long as the directory is writable, so the test passed unexpectedly (result was 0 instead of 1).
- **Fix:** Changed failure injection to `data_dir.chmod(0o555)` — making the directory read-only prevents the `.tmp` write with EACCES.
- **Files modified:** `tests/test_maintenance.py` (same commit)

## Eligible CONCERNS.md Closure

The entry `Auto-maintenance performs multi-file rewrites without transaction rollback` is now eligible to be marked CLOSED. The implementation satisfies the concern: a failure in the plan or stage phase leaves the data directory byte-identical to its pre-call state; the only remaining partial-mutation window is a crash mid-commit (after at least one `os.replace` has landed), which is documented and announced loudly on stderr.

## Self-Check: PASSED
