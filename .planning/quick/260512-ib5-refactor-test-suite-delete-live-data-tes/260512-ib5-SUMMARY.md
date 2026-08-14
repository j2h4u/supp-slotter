---
phase: 260512-ib5
plan: "01"
subsystem: planner/engine + tests
tags: [refactor, test-suite, cmd-api, dataclasses, ci]
dependency_graph:
  requires: []
  provides: [cmd_* result dataclasses, planner check CI gate, direct in-process test seam]
  affects: [planner/engine, tests/test_phase_03.py, tests/test_phase_02.py, justfile, .github/workflows/test.yml]
tech_stack:
  added: [planner/engine/results.py, planner/engine/_root_patch.py]
  patterns: [frozen dataclass result API, contextmanager root patching, thin CLI adapter]
key_files:
  created:
    - planner/engine/results.py
    - planner/engine/_root_patch.py
  modified:
    - planner/engine/check.py
    - planner/engine/plan.py
    - planner/engine/doctor.py
    - planner/engine/find.py
    - planner/engine/review.py
    - planner/engine/show.py
    - planner/engine/audit.py
    - planner/engine/__init__.py
    - planner/__main__.py
    - tests/helpers.py
    - tests/test_phase_02.py
    - tests/test_phase_03.py
    - tests/test_schemas.py
    - justfile
    - .github/workflows/test.yml
  deleted:
    - tests/test_phase_01.py
decisions:
  - PlanResult.warnings carries raw pre-humanize dict list (keys: type/source_name/target_name/reason/action/severity); humanize_warning stays in stdout/yaml path only
  - patch_planner_root moved to planner/engine/_root_patch.py; tests/helpers.py re-exports it unchanged for back-compat
  - _maybe_patch renamed to maybe_patch_root (public) to avoid pyright reportPrivateUsage cross-module errors
  - DoctorResult.sections entries are full display strings (e.g. "Zinc -> Copper: reason..."); test assertions use substring check not equality
  - FindResult.substances/products are raw scored tuples (float, str, str, Path); CLI banner text assertions dropped from find tests
metrics:
  duration: ~25min
  completed: "2026-05-12"
  tasks: 3
  files: 15
---

# Phase 260512-ib5 Plan 01: Refactor Test Suite — Delete Live Data Tests Summary

**One-liner:** Introduced typed result dataclasses for all 7 cmd_* functions with optional `data_root` parameter, deleted 10 LIVE_DATA snapshot tests, added `planner check` as CI/justfile gate, and converted 10 subprocess tests to direct in-process cmd_* calls.

## What Was Built

### Task 1: Result dataclasses + cmd_* refactor + __main__ adapter (38952d0)

Created `planner/engine/results.py` with 7 frozen dataclasses:
- `CheckResult(exit_code, errors, info)`
- `PlanResult(exit_code, schedule_written, warnings, slot_loads, prefer_pairs_declared, prefer_pairs_together)`
- `DoctorResult(exit_code, sections)`
- `FindResult(exit_code, query, substances, products)`
- `ReviewResult(exit_code, output="", stderr="")`
- `ShowResult(exit_code, output="")`
- `AuditResult(exit_code, by_kind)`

Created `planner/engine/_root_patch.py` with `patch_planner_root` (moved from tests/helpers.py) and `maybe_patch_root` contextmanager. `tests/helpers.py` now re-exports `patch_planner_root` for back-compat.

Each cmd_* refactored to accept `data_root: Path | None = None` and return its dataclass. `PlanResult.warnings` carries the raw pre-humanize dict list captured immediately before the `humanize_warning` comprehension in `_build_schedule_output`. `planner/__main__.py` is now a thin adapter that calls `sys.exit(result.exit_code)`.

### Task 2: Delete LIVE_DATA tests + add planner check CI gate (a64db41)

Deleted exactly 10 tests (T-IB5-04 audit trail preserved in commit body):
- `tests/test_phase_01.py` (entire file): `test_phase_01_check_passes`, `test_dashboard_ref_validator_rejects_unknown_from_traits_slug_and_restores_file`
- `tests/test_phase_02.py` (7 tests): `test_substances_registry_card_id_matches_directory_key`, `test_products_lack_substance_only_fields_and_reference_known_substances`, `test_stack_items_carry_no_dose_or_brand_fields_and_reference_known_products`, `test_pillbox_slots_use_known_near_values_and_whitelisted_fields`, `test_trait_effects_omit_deprecated_time_and_activity_match_keys`, `test_specific_substance_product_and_trait_invariants`, `test_sub_877c24aad4_formula_schedules_as_one_product_item`
- `tests/test_schemas.py` (1 test): `test_repo_passes_schema_validation`

Removed now-unused helpers: `plan_against_live_repo`, `load_yaml` (local), `load_cards`, `B_COMPLEX_SUBSTANCES`, `SLOT_FIELDS`, `SLOT_NEAR_VALUES` from test_phase_02.py.

Added `planner check` gate:
- `justfile`: `uv run python -m planner check` runs before `uv run pytest tests/`
- `.github/workflows/test.yml`: new "Planner check" step inserted between "Type check" and "Run tests"

### Task 3: Convert eligible subprocess tests to direct cmd_* calls (a778ffb)

Converted 10 tests in `test_phase_03.py` from `run_planner()` to direct cmd_* calls:

| Test | Cmd | Result fields asserted |
|------|-----|----------------------|
| test_review_substance_prints_grouped_trait_checklist | cmd_review_substance(data_root=ROOT) | result.output |
| test_review_substance_prints_central_relation_matches | cmd_review_substance(data_root=ROOT) | result.output |
| test_find_searches_multiple_fuzzy_words | cmd_find(data_root=ROOT) | result.substances, result.products |
| test_find_supports_partial_word_matches | cmd_find(data_root=ROOT) | result.substances, result.products |
| test_orphans_command_lists_cleanup_candidates | cmd_doctor(data_root=tmp_path) | result.sections[...] |
| test_doctor_lists_similar_substance_cards | cmd_doctor(data_root=tmp_path) | result.sections[...] |
| test_balance_relation_warns_when_related_substance_missing | cmd_doctor + cmd_plan(data_root=tmp_path) | plan_result.warnings raw dict keys |
| test_support_relation_warns_when_supporter_missing | cmd_doctor(data_root=tmp_path) | result.sections[...] |
| test_support_relation_accepts_alternate_active_supporter_form | cmd_doctor(data_root=tmp_path) | result.sections[...] |
| test_doctor_warns_empty_cluster | cmd_doctor(data_root=tmp_path) | result.sections["dashboard.empty_cluster"] |

The `test_balance_relation_warns_when_related_substance_missing` test asserts on raw dict keys from `PlanResult.warnings`: `type == "missing_balance_substance"`, `severity == "medium"`, `"Zinc"` in `source_name`, `"Copper"` in `target_name`, `reason` key present, `action` key present.

All 4 tests in `<keep_subprocess>` were left unchanged (error-path/argv tests).

## Deviations from Plan

**1. [Rule 1 - Bug] Renamed _maybe_patch to maybe_patch_root**
- **Found during:** Task 1 pyright check
- **Issue:** pyright strict reports `reportPrivateUsage` when a name-mangled `_maybe_patch` is imported across module boundaries within the same package
- **Fix:** Renamed to `maybe_patch_root` (public, no underscore prefix) across all 7 import sites
- **Files modified:** `planner/engine/_root_patch.py` and all 6 cmd_* modules
- **Commit:** 38952d0

**2. [Rule 1 - Bug] DoctorResult.sections entries are full display strings**
- **Found during:** Task 3 test run
- **Issue:** The plan spec and old tests used exact string match `"Zinc -> Copper" in sections["relations.balance_missing"]` but the section entries are full formatted strings including the relation reason (e.g. `"Zinc -> Copper: Long-term..."`)
- **Fix:** Changed assertions to `any("Zinc -> Copper" in entry for entry in ...)` substring check; same fix for supports_missing test
- **Files modified:** `tests/test_phase_03.py`
- **Commit:** a778ffb

## Final Counts

- Tests before: 96 (including 10 LIVE_DATA)
- Tests after: 86 (10 deleted, 0 replaced)
- pyright: 0 errors, 0 warnings, 0 informations
- ruff: All checks passed
- `just test` (planner check + pytest): 86 passed

## Self-Check: PASSED
