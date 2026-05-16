# Codebase Concerns

**Analysis Date:** 2026-05-14 (status updated 2026-05-15 after SurrealDB POC merge + follow-up debt sweep; 2026-05-16 after plan.py decomposition + _root_patch elimination + coverage thresholds)

## Tech Debt

**[CLOSED 2026-05-16] Scheduler module size and mixed responsibilities:**
- Issue: `planner/engine/plan.py` was 927 lines and owned input loading, active-stack indexing, relation conflict checks, search ordering, branch-and-bound scheduling, warning aggregation, schedule rendering, and disk writes.
- Files: `planner/engine/plan.py`, `planner/engine/_scheduling.py`, `planner/cards/schedule.py`, `planner/cards/warnings.py`
- Impact: Scheduling changes required reasoning across many mutable indexes; small fixes could change assignment ordering, warning contents, or emitted YAML shape together.
- Resolution: Strategy 2 decomposition shipped across three commits `e2f4834` → `10f2440` → `ffcba21`. plan.py shrunk 927 → 215 LoC (orchestrator only). Three new modules: `_plan_inputs.py` (load/index/prefer-pair, 251 LoC), `_plan_output.py` (schedule dict assembly, 218 LoC), `_plan_search.py` (feasibility precompute + B&B search + slot_is_blocked, 347 LoC). schedule.yaml byte-identical, 107/107 tests pass, ~24s runtime. Closure-based search intentionally preserved — the `nonlocal`-shared state is the natural form for backtracking.

**[CLOSED 2026-05-16] Global path patching for tests:**
- Issue: In-process command tests relied on mutating module-level path constants across a hard-coded `_MODULES` list in `planner/engine/_root_patch.py`.
- Files: `planner/engine/_root_patch.py`, `planner/io.py`, tests using `data_root=tmp_path`
- Impact: Any new module that imported `DATA_DIR`, `STACKS_PATH`, `RELATIONS_PATH`, or `SCHEDULE_PATH` had to be added to `_MODULES`; otherwise tests using `data_root` would silently read or write the real repo. The anti-pattern cost a test cycle during the SurrealDB POC (A2) and was a near-miss for the `_plan_inputs.py` extraction.
- Resolution: Quick task `260516-oph` (commit `2e18b7e`, doc commit `62daaf7`). Introduced `Paths` frozen dataclass in `planner/io.py` with `from_root` / `default` factories; threaded `paths: Paths` through all 13+ loaders + commands; deleted `planner/engine/_root_patch.py` and all 8 module-level path constants from `planner/io.py` (only `ROOT` and `SCHEMA_DIR` remain). The registry no longer exists — there is nothing to forget. New loaders simply take `paths: Paths` as a parameter; pyright strict enforces it. `schedule.yaml` byte-identical; `just check` exits 0 (107/107, ruff, pyright strict).

**Auto-maintenance performs multi-file rewrites without transaction rollback:**
- Issue: Maintenance writes IDs, renames card files, rewrites substance references, and rewrites `data/stacks.yaml` as a sequence of independent filesystem operations.
- Files: `planner/maintenance.py`, `planner/cards/product.py`, `planner/cards/substance.py`, `data/stacks.yaml`
- Impact: A failure after earlier writes can leave normalized cards committed but downstream references partially updated. The code detects some duplicate destinations and write failures, but it does not stage all edits and commit them atomically.
- Fix approach: Build an explicit edit plan first, write through temporary files, then rename as the final step. Keep `run_auto_maintenance_unlocked()` internal and route command callers through `run_auto_maintenance()` so the lock is always held.

**[CLOSED 2026-05-15] Relation semantics are split between planner, reviewer, and schema:**
- Issue: Relation loading, active-stack classification, missing-pair warnings, class-level competition, and intra-product conflict detection were distributed across several modules.
- Files: `planner/cards/relations.py`, `planner/engine/plan.py`, `planner/engine/review.py`, `schema/relations.schema.json`, `data/relations.yaml`
- Impact: A new relation type or endpoint shape required edits in multiple places. The scheduler had a special exception where it read `Substance.is_` only for class-level `competes`, blurring planner and knowledge-model boundaries.
- Resolution: SurrealDB POC merged to main at `8fff99a` (16 commits). All relation queries — active-stack classification, missing-pair warnings, intra-product conflicts, class-level competes — now live in `planner/cards/relations_surreal.py` as SurrealQL against an in-memory session. `planner/cards/relations.py` retains only `load_global_relations` (raw-YAML loader) and `check_global_relations` (pre-DB validator) by design. See `POC-NOTES.md` for the full migration log.

## Known Bugs

**[CLOSED 2026-05-15] Review command can classify unchecked relation data:**
- Symptoms: `planner review` loaded relations directly and classified them without first running schema/reference-integrity validation.
- Files: `planner/engine/review.py`, `planner/cards/relations.py`
- Trigger: Running `planner review` on a repo where `data/relations.yaml` was malformed in a way `load_global_relations()` silently tolerated, or class endpoints were schema-shaped but semantically invalid.
- Resolution: Commit `2fa08e9` — `_review_inner` now loads trait_defs and runs `check_global_relations` on the raw relations YAML before classifying. Errors are printed to stderr and the command returns exit_code 1 with a "refusing — run `planner check`" message. Test `test_cmd_review_refuses_on_invalid_relations` covers an unregistered-class case. Lightweight gate chosen (not full cmd_check) to keep review side-effect-free.

**[CLOSED 2026-05-15] Class-level relation endpoints are not validated against registered classes:**
- Symptoms: `source_class` and `target_class` in `data/relations.yaml` were schema-checked as slug strings, but not checked against registered `is:` traits.
- Files: `planner/cards/relations.py`, `planner/engine/check.py`, `data/traits.yaml`, `data/relations.yaml`
- Trigger: A misspelled class-level `competes` relation passed schema validation while `_slot_is_blocked()` silently never matched it.
- Resolution: Commit `d6f13b6` — `check_global_relations` now takes `trait_defs` and validates each `source_class` / `target_class` against `{td.short_name for td in trait_defs.values() if td.namespace == "is"}`. Hard error mirrors the existing source_name / source_substance reference-integrity checks. Test `test_relation_validation_rejects_unregistered_class` covers the misspelled-class case.

**[CLOSED 2026-05-15] Auto-maintenance lock is opt-in for internal callers:**
- Symptoms: The public `run_auto_maintenance()` acquired the maintenance lock, but a public `run_auto_maintenance_unlocked()` was importable and performed writes without acquiring it.
- Files: `planner/maintenance.py`, `tests/test_maintenance.py`
- Trigger: A future caller could import the unlocked variant and bypass the lock.
- Resolution: Commit `2edbc10` — renamed to `_run_auto_maintenance_unlocked` (private). Only `run_auto_maintenance` (which holds the lock) calls it. The existing write-failure-path test was rewritten to drive through the public entry point, eliminating any external import of the private function.

## Security Considerations

**No secret files detected in scanned root:**
- Risk: Not applicable for current repo scan; no `.env`, `.env.*`, `*secret*`, `*credential*`, private key, or package-auth files were detected under the scanned depth.
- Files: `.planning/codebase/CONCERNS.md`
- Current mitigation: Project data is committed YAML under `data/`, schemas under `schema/`, and Python source under `planner/`.
- Recommendations: Keep secrets out of `data/*.yaml` because generated review and schedule outputs quote card text directly.

**Generated schedule and review output can expose sensitive health notes if card text becomes private:**
- Risk: Substance and product `concerns`, `notes`, and warnings are printed by CLI commands and can be serialized into `schedule.yaml`.
- Files: `planner/engine/review.py`, `planner/engine/plan.py`, `planner/io.py`, `data/substances/`, `data/products/`, `schedule.yaml`
- Current mitigation: The repository appears designed as a local YAML-first planner, and no network or external API calls are used.
- Recommendations: Treat `data/` and `schedule.yaml` as sensitive if they contain personal regimen or medical context. Add a redaction/export policy before sharing generated outputs.

**YAML parsing uses safe loaders:**
- Risk: Low. YAML reads use `yaml.safe_load()` through `planner/io.py` and scripts also use safe loading.
- Files: `planner/io.py`, `scripts/migrate_substance_cards.py`, `tests/`
- Current mitigation: No `yaml.load()` use was detected; schema validation uses `jsonschema`.
- Recommendations: Preserve safe loading for all new card readers and migration scripts.

## Performance Bottlenecks

**Branch-and-bound scheduler scales combinatorially with active items and slots:**
- Problem: `_run_plan_search()` explores feasible slot assignments recursively, checking slot conflicts against existing items at each candidate.
- Files: `planner/engine/plan.py`, `planner/engine/_scheduling.py`, `tests/test_scheduling_units.py`
- Cause: The search prunes with a greedy seed, upper-bound score estimates, and balance lower bounds, but worst-case growth still depends on active item count times feasible slots times relation checks.
- Improvement path: Keep new constraints cheap and deterministic. Add benchmark-style tests before increasing active stack size or relation complexity, and consider memoizing conflict checks by `(item, slot_items)` or splitting independent stacks.

**Full data audit performs broad pairwise/name scans over all substances:**
- Problem: Cleanup audit includes similar-name clustering and dashboard membership scans over the full `data/substances/` and `data/dashboards/` set.
- Files: `planner/engine/audit.py`, `planner/cards/substance.py`, `planner/cards/dashboards.py`
- Cause: `collect_similar_substances()` compares substance terms pairwise, and dashboard audit resolves memberships from card traits on every run.
- Improvement path: Fine for current scale of 197 substances, 57 products, and 13 dashboards. If data grows substantially, cache normalized search terms and dashboard membership indexes within the audit run.

## Fragile Areas

**Domain data quality remains an active operational risk:**
- Files: `data/substances/`, `data/products/`, `data/traits.yaml`, `data/relations.yaml`, `planner/engine/audit.py`
- Why fragile: `uv run python -m planner audit --full` reports 34 cleanup candidates and 29 full-audit prompts, including 11 used stubs, 6 missing `is:` classifications, and 12 intake review candidates.
- Safe modification: Run `uv run python -m planner check`, `uv run python -m planner audit --full`, and `uv run python -m planner review` after editing cards or ontology files.
- Test coverage: Schema and command tests exist, but source-label correctness and medical/domain assertions remain human-reviewed data work.

**Concern and warning model is not dose-aware:**
- Files: `planner/contracts.py`, `planner/cards/warnings.py`, `planner/cards/relations.py`, `planner/engine/plan.py`, `data/products/`, `data/substances/`
- Why fragile: Product component amounts are strings, and relations/warnings reason about presence, class, and traits rather than numeric dose ceilings or cumulative daily totals.
- Safe modification: Do not encode dose-threshold behavior as simple presence/absence unless the output remains clearly review-only.
- Test coverage: Scheduling and warning behavior is covered by unit tests, but dose arithmetic is not implemented or tested.

**Name-based relation endpoints are brittle around duplicate or generic substance names:**
- Files: `data/relations.yaml`, `planner/cards/relations.py`, `planner/cards/substance.py`, `planner/engine/audit.py`
- Why fragile: Relations can target exact names as well as IDs, while audit reports many similar-name clusters and used stubs for generic names such as `Vitamin B12`, `Zinc`, and `Selenium`.
- Safe modification: Prefer `source_substance` and `target_substance` IDs for new high-impact relations. Use name endpoints only for intentionally generic family-level relations.
- Test coverage: Relation integrity checks catch missing names/IDs, but not ambiguous name intent.

**Generated `schedule.yaml` is an output file with source-like importance:**
- Files: `schedule.yaml`, `planner/engine/plan.py`, `planner/io.py`, `justfile`
- Why fragile: `cmd_plan()` writes `schedule.yaml` directly, while lint excludes it. Users may be tempted to edit the generated schedule instead of source cards under `data/`.
- Safe modification: Edit `data/stacks.yaml`, `data/pillboxes.yaml`, `data/products/`, `data/substances/`, `data/traits.yaml`, and `data/relations.yaml`; regenerate with `uv run python -m planner`.
- Test coverage: Tests validate generated schedule behavior through temp roots, but there is no snapshot/contract test for every top-level output comment or display field.

## Scaling Limits

**Current card volume:**
- Current capacity: 271 YAML files under `data/`, including 197 substance cards, 57 product cards, and 13 dashboard cards.
- Limit: Scheduler and audit code are optimized for local single-user operation, not multi-user concurrent editing or very large card catalogs.
- Scaling path: Introduce in-memory indexes for substance lookups, relation endpoints, dashboard memberships, and similar-name terms before growing into thousands of cards.

**Single-process filesystem workflow:**
- Current capacity: Local CLI commands over committed YAML files.
- Limit: Concurrent command execution can contend around auto-maintenance and generated output writes; only maintenance normalization has a lock.
- Scaling path: Add command-level write serialization or move generated outputs to temp-and-rename writes if multiple tools invoke planner commands concurrently.

## Dependencies at Risk

**[CLOSED — superseded] Python 3.14 runtime versus declared 3.11 target:**
- Risk: At time of audit, local runs were on 3.14.2 while `pyproject.toml` declared `requires-python = ">=3.11"` and pyright targeted 3.11.
- Resolution: `pyproject.toml` now declares `requires-python = ">=3.14"`, `tool.ruff.target-version = "py314"`, and `tool.pyright.pythonVersion = "3.14"`. The runtime/declared mismatch no longer exists — minimum supported Python is 3.14. This was a personal-use script with no broader compatibility obligation, so the resolution was to bump the floor rather than constrain the syntax.

**[CLOSED — workaround in effect] Unpinned dependency lower bounds:**
- Risk: Runtime and dev dependencies use lower bounds only — future major releases can change parsing, validation messages, lint behavior, or type-checking strictness.
- Resolution: The stated workaround is in effect. `uv.lock` is committed to the repo and `uv sync` is used for reproducible local runs. Upper bounds are not added preemptively (per the original migration plan: only when an upstream release breaks the workflow). De-facto resolved via the chosen mitigation; no further action planned.

## Missing Critical Features

**Dose model and cumulative daily totals:**
- Problem: Amounts are preserved as labels/strings, so the planner cannot calculate cumulative vitamin/mineral/drug dose, upper-limit risk, dose splitting, or threshold-specific interaction severity.
- Blocks: Automated safety checks for selenium, vitamin A, vitamin B6, potassium, aspirin/bleeding load, and other dose-sensitive warnings.

**Machine-readable provenance for card facts:**
- Problem: Product and substance cards contain notes and concerns, but the source confidence/provenance model is not consistently structured.
- Blocks: Automated review of label conflicts, stale products, and secondary-source facts; current `planner review` surfaces data-quality concerns for human follow-up.

**[CLOSED 2026-05-16] Coverage thresholds for tests:**
- Problem: Test commands ran `pytest` without any coverage tool or minimum coverage threshold.
- Resolution: Quick task `260516-poi` (commit `ad89148`). Added `pytest-cov>=7` to `[dependency-groups].dev`, `[tool.coverage.run]` (source = planner; omit tests/, scripts/, `__main__.py`) and `[tool.coverage.report]` (`fail_under = 83`) blocks in `pyproject.toml`, and a `just coverage` recipe. Threshold derived honestly: measured baseline 84.63% → `fail_under = floor(85) - 2 = 83` (margin for incidental drift). `just check` still passes 107/107; `just coverage` exits 0 with 84.63% TOTAL.

## Test Coverage Gaps

**[CLOSED 2026-05-16] No enforced coverage metric:**
- What was not tested: There was no `pytest-cov` dependency, coverage config, or `just` command enforcing coverage.
- Resolution: Same as Missing Features → Coverage thresholds (commit `ad89148`). `just coverage` reports 84.63% line coverage on `planner/`; threshold pinned at 83 to catch regression below the current baseline. The "Risk: large modules can accumulate untested branches" surface is now observable per-file via `term-missing` report.

**Migration and audit scripts are lightly covered or not covered as CLI tools:**
- What's not tested: Script entry paths and output contracts for `scripts/migrate_substance_cards.py` and `scripts/card_audit.py`.
- Files: `scripts/migrate_substance_cards.py`, `scripts/card_audit.py`, `tests/`
- Risk: One-off migrations can rewrite YAML incorrectly or produce stale audit expectations without CI catching it.
- Priority: Medium

**End-to-end command behavior is covered, but display output is mostly behavioral rather than snapshot-based:**
- What's not tested: Full stable text contracts for `planner show`, `planner review`, `planner audit --full`, and generated `schedule.yaml` comments.
- Files: `planner/engine/show.py`, `planner/engine/review.py`, `planner/engine/audit.py`, `planner/io.py`, `tests/`
- Risk: Human-facing output can drift in ways that affect operator review without breaking core scheduling assertions.
- Priority: Low

---

*Concerns audit: 2026-05-14*
