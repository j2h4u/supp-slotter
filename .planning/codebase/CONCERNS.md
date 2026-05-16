# Codebase Concerns

**Analysis Date:** 2026-05-14 (closed entries pruned 2026-05-16 — see git history for archived resolutions)

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

## Missing Critical Features

**Dose model and cumulative daily totals:**
- Problem: Amounts are preserved as labels/strings, so the planner cannot calculate cumulative vitamin/mineral/drug dose, upper-limit risk, dose splitting, or threshold-specific interaction severity.
- Blocks: Automated safety checks for selenium, vitamin A, vitamin B6, potassium, aspirin/bleeding load, and other dose-sensitive warnings.

**Machine-readable provenance for card facts:**
- Problem: Product and substance cards contain notes and concerns, but the source confidence/provenance model is not consistently structured.
- Blocks: Automated review of label conflicts, stale products, and secondary-source facts; current `planner review` surfaces data-quality concerns for human follow-up.

## Test Coverage Gaps

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
