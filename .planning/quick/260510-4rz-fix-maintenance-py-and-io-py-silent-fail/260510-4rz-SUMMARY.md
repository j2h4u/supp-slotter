---
phase: quick-260510-4rz
plan: "01"
subsystem: planner/io, planner/maintenance, planner/cards/relations
tags: [error-handling, silent-fail, CardLoadError, observability]
dependency_graph:
  requires: []
  provides: [descriptive-io-errors, guarded-stacks-write, vocal-CardLoadError-skips, disambiguated-maintenance-sentinel]
  affects: [planner/io.py, planner/maintenance.py, planner/cards/relations.py, tests/test_maintenance.py]
tech_stack:
  added: []
  patterns: [CardLoadError wrapping, tri-state return, stderr-warning-before-skip]
key_files:
  created: [tests/test_maintenance.py]
  modified: [planner/io.py, planner/maintenance.py, planner/cards/relations.py]
decisions:
  - "load_yaml wraps both OSError and yaml.YAMLError into CardLoadError with path prefix"
  - "load_schema raises RuntimeError (not CardLoadError) to match existing call-site conventions"
  - "CardLoadError import promoted to module-level in io.py; no import cycle (contracts.py is a leaf)"
  - "auto_maintenance_needed returns bool | None; None is a hard error distinct from False (no work)"
  - "cmd_check misleading message flagged for follow-up; not modified in this task"
  - "EH8 (clear_stale_lock TOCTOU) deferred per scope"
metrics:
  duration: "~20min"
  completed: "2026-05-10"
  tasks_completed: 4
  tests_added: 11
  files_modified: 4
---

# Phase quick-260510-4rz Plan 01: Fix maintenance.py and io.py silent failures — Summary

**One-liner:** Wrapped load_yaml/load_schema raw OS/YAML/JSON errors into descriptive CardLoadError/RuntimeError, guarded stacks.yaml write with OSError handler, made all three CardLoadError-skip sites in rewrite_substance_refs vocal, added non-mapping warning to load_global_relations, and disambiguated auto_maintenance_needed's False/None return sentinel.

## Per-Finding Status

| Finding | Description | Fix | Test | Commit |
|---------|-------------|-----|------|--------|
| EH1 | load_yaml raised bare FileNotFoundError/OSError | Wrapped in CardLoadError naming the path | `test_load_yaml_missing_file_raises_card_load_error` | 8c3f8f9 |
| EH2 | load_yaml raised bare yaml.YAMLError; load_schema raised bare FileNotFoundError/JSONDecodeError | Wrapped in CardLoadError / RuntimeError naming the file | `test_load_yaml_malformed_yaml_raises_card_load_error`, `test_load_schema_missing_raises_runtime_error_naming_schema`, `test_load_schema_malformed_json_raises_runtime_error` | 8c3f8f9 |
| C1 | stacks.yaml write_text() could traceback after product renames committed | try/except OSError → stderr message + return 1 | `test_run_auto_maintenance_unlocked_returns_1_when_stacks_write_fails` | 5b4291a |
| EH7 | Three except CardLoadError: continue sites in rewrite_substance_refs were silent | Added print warning before each continue | `test_rewrite_substance_refs_warns_on_corrupted_product` | a6377cd |
| EH9 | load_global_relations returned [] silently on non-mapping data | Added print warning naming path and actual type | `test_load_global_relations_warns_on_non_mapping`, `test_load_global_relations_quiet_on_mapping` | a6377cd |
| EH10 | auto_maintenance_needed returned False on CardLoadError, conflating "no work" with "read error" | Changed signature to bool | None; CardLoadError → print + return None; run_auto_maintenance handles three-valued return | `test_auto_maintenance_needed_returns_none_on_card_load_error`, `test_run_auto_maintenance_returns_1_without_acquiring_lock_on_load_error`, `test_auto_maintenance_needed_still_returns_false_when_clean` | f77b354 |

## Commits

| Hash | Message |
|------|---------|
| 8c3f8f9 | fix(io): convert load_yaml and load_schema raw errors into descriptive CardLoadError/RuntimeError |
| 5b4291a | fix(maintenance): catch OSError on stacks.yaml write and exit non-zero with a reconciliation hint |
| a6377cd | fix(maintenance,relations): print stderr warning before silent CardLoadError skip and on non-mapping relations.yaml |
| f77b354 | fix(maintenance): return None from auto_maintenance_needed on CardLoadError; abort lock acquisition on error |

## Other callers of auto_maintenance_needed

Only one production caller exists: `run_auto_maintenance` in `planner/maintenance.py`. Confirmed via `rg -n "auto_maintenance_needed" --type py`. That caller was updated to handle all three return values explicitly.

## cmd_check message accuracy flag

`cmd_check` in `planner/engine/check.py:34` prints `"check: skipped (maintenance lock held)"` whenever `run_auto_maintenance` returns non-zero. After EH10, `run_auto_maintenance` also returns 1 when `auto_maintenance_needed` returns `None` (card load error) — no lock is acquired in that path. The printed message is therefore misleading: it says "lock held" when the real cause is a card read failure.

**Flagged for follow-up**: update `cmd_check` to distinguish the two non-zero cases (lock-held vs card-load-error), likely by checking `maintenance_result` against a richer return type or by `run_auto_maintenance` printing the error before returning.

## Deferred Items

- **EH8** (clear_stale_lock TOCTOU): `clear_stale_lock` reads the PID and then removes the lock dir in separate syscalls — another process could create a new legitimate lock between those steps. Deferred per scope constraints; candidate for next pass.
- **cmd_check misleading message** (see above): not modified in this task.

## Deviations from Plan

None — plan executed exactly as written. The test fixture for `test_auto_maintenance_needed_still_returns_false_when_clean` used hardcoded filenames that didn't match canonical form; fixed by computing the canonical filename dynamically using `canonical_substance_filename` / `canonical_product_filename`. This is a test-only deviation (no production code affected).

## Final Metrics

- `python3 -m pytest tests/test_maintenance.py` — 11 passed, 0 failed
- `python3 -m pyright planner/` — 0 errors, 0 warnings
- Tests added: 11 (4 for EH1/EH2, 1 for C1, 3 for EH7/EH9, 3 for EH10)

## Self-Check: PASSED

- tests/test_maintenance.py: FOUND
- planner/io.py: FOUND (load_yaml wraps OSError+YAMLError, load_schema wraps OSError+JSONDecodeError)
- planner/maintenance.py: FOUND (guarded stacks write, vocal skips, None sentinel)
- planner/cards/relations.py: FOUND (vocal non-mapping warning)
- Commits 8c3f8f9, 5b4291a, a6377cd, f77b354: all in git log
