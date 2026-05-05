# Codebase Concerns

**Analysis Date:** 2026-05-05

## Tech Debt

**Single-file planner combines CLI, validation, scoring, search, and persistence:**
- Issue: `planner.py` owns YAML loading, JSON Schema validation, cross-reference checks, inventory refresh, score computation, search, schedule rendering, and CLI argument parsing in one 692-line file.
- Files: `planner.py:48`, `planner.py:56`, `planner.py:120`, `planner.py:261`, `planner.py:318`, `planner.py:368`, `planner.py:427`, `planner.py:662`
- Impact: Changes to one concern can regress unrelated behavior. Validation logic and scheduling logic are hard to test in isolation because the CLI path reads and writes real repository files.
- Fix approach: Split into small modules while preserving CLI behavior: `planner_io.py` for YAML/schema loading, `validators.py` for `check_*`, `scheduler.py` for scoring/search, and a thin `planner.py` CLI wrapper. Keep `uv run planner.py check|refresh|plan` as the public interface.

**Substance and product terminology is overloaded:**
- Issue: Current "product" cards in `data/products/*.yaml` are semantically substance cards, while `schema/product.schema.json` and `planner.py` still use product naming.
- Files: `idea.md:290`, `idea.md:292`, `idea.md:625`, `planner.py:29`, `planner.py:105`, `schema/product.schema.json:3`, `data/products/magnesium_glycinate.yaml`
- Impact: New code can put dose, brand, or product-instance details in the wrong place. Multi-component products remain hard to model because `components` is an opaque string map rather than first-class substance references.
- Fix approach: Keep new universal chemistry/timing traits in `data/products/<id>.yaml` only until the planned split. When implementing the split, rename current cards to `data/substances/`, create real product cards under `data/products/`, and update `data/inventory.yaml` to reference product ids.

**Domain gaps are encoded as INFO-only strings instead of planner semantics:**
- Issue: Many cards carry `unmatched_concerns` for clinically meaningful or scheduling-relevant facts, but `planner.py check` only prints them as INFO and `cmd_plan()` ignores them entirely.
- Files: `planner.py:163`, `planner.py:249`, `data/products/tadalafil.yaml:8`, `data/products/l_citrulline_malate.yaml:11`, `data/products/nattokinase.yaml:10`, `data/products/trace_minerals.yaml:11`
- Impact: Important domain facts such as nitrate contraindication, additive hypotension, fibrinolytic risk, thyroid interactions, glucose effects, dose splitting, and formulation effects are visible in text but not represented in warnings, constraints, or schedule explanations.
- Fix approach: Promote repeated unmatched-concern categories into explicit traits or structured metadata. Use `risk:*` traits for safety warnings, `family:*` or interaction metadata for separation/co-administration rules, and dose-distribution fields for split-dose behavior before relying on generated schedules.

**Generated schedule is committed without provenance checks:**
- Issue: `schedule.yaml` is a generated artifact written by `planner.py plan`, but there is no check that the committed schedule matches current `data/*.yaml` inputs.
- Files: `planner.py:638`, `schedule.yaml:1`, `tests/test_phase_01.py:156`
- Impact: Contributors can edit `data/inventory.yaml`, `data/traits.yaml`, or cards and forget to regenerate `schedule.yaml`; `planner.py check` still passes because it validates inputs, not generated output freshness.
- Fix approach: Add a test that runs `uv run planner.py plan` in a temporary copy or restores bytes, then compares the generated schedule to committed `schedule.yaml`. Alternatively mark `schedule.yaml` as generated output and avoid treating it as source of truth.

**Handoff documentation conflicts with current data shape:**
- Issue: `HANDOFF.md` states the project has four slots and 16 traits, while current data contains six slots including `pre_workout` and `post_workout`, plus the `activity` namespace.
- Files: `HANDOFF.md:39`, `HANDOFF.md:40`, `data/slots.yaml:35`, `data/slots.yaml:42`, `data/traits.yaml:163`, `tests/test_phase_01.py:78`
- Impact: Agents resuming from `HANDOFF.md` can ask already-resolved questions or plan duplicate slot-model work.
- Fix approach: Update or archive `HANDOFF.md`. Treat `data/slots.yaml`, `data/traits.yaml`, `tests/test_phase_01.py`, and current `.planning/phases/*` artifacts as the authoritative state.

## Known Bugs

**Single-product check falsely rejects valid `prefer_with` references:**
- Symptoms: `uv run planner.py check data/products/creatine.yaml` exits 1 with `prefer_with target 'l_citrulline_malate' has no matching product card`, while full `uv run planner.py check` passes.
- Files: `planner.py:120`, `planner.py:154`, `planner.py:166`, `planner.py:291`, `data/products/creatine.yaml:10`
- Trigger: Run `uv run planner.py check data/products/creatine.yaml`.
- Workaround: Run full `uv run planner.py check` for cards that declare `prefer_with`.
- Fix approach: In single-target mode, validate the target card's id/traits/schema against the target file, but resolve `prefer_with` targets against all cards in `data/products/*.yaml`.

**Single-target check skips inventory and goal reference validation:**
- Symptoms: `uv run planner.py check <target>` validates a product card but intentionally bypasses inventory alignment and goal refs.
- Files: `planner.py:300`, `planner.py:301`, `planner.py:310`, `planner.py:312`, `idea.md:148`
- Trigger: Run `uv run planner.py check data/products/<id>.yaml` after adding or renaming a card.
- Workaround: Always run full `uv run planner.py check` before accepting data changes.
- Fix approach: Keep single-target mode fast, but print an explicit note that inventory and goal checks are skipped. Add a separate `check-card` command if single-card validation should have narrower semantics.

**Malformed core YAML can crash outside guarded loaders:**
- Symptoms: `cmd_check()` catches YAML errors for product and goal files, but `data/slots.yaml`, `data/traits.yaml`, and `data/inventory.yaml` are loaded through `load_yaml()` without `yaml.YAMLError` handling.
- Files: `planner.py:48`, `planner.py:272`, `planner.py:273`, `planner.py:305`, `planner.py:323`
- Trigger: Introduce invalid YAML syntax into `data/slots.yaml`, `data/traits.yaml`, or `data/inventory.yaml`, then run `uv run planner.py check`.
- Workaround: Use editor YAML validation or run tests after each edit.
- Fix approach: Add a shared `load_mapping_yaml(path)` helper that returns structured validation errors for parse failures, empty files, and non-mapping roots. Use it for all planner inputs.

## Security Considerations

**Medical-safety warnings are incomplete and text-only:**
- Risk: The tool schedules supplements and medication-adjacent substances, but risk handling is limited to `risk:manual_review` warnings and free-text `unmatched_concerns`.
- Files: `data/products/tadalafil.yaml:4`, `data/products/tadalafil.yaml:11`, `data/products/l_citrulline_malate.yaml:9`, `data/products/nattokinase.yaml:8`, `data/products/trace_minerals.yaml:9`, `planner.py:626`
- Current mitigation: Several products include `risk:manual_review`, and `schedule.yaml` lists warning entries for active products with that trait.
- Recommendations: Add explicit traits or structured risk metadata for nitrate/PDE5 contraindications, anticoagulant/fibrinolytic risk, hypotension stacking, thyroid medication interactions, potassium/hyperkalemia risk, glucose effects, and narrow therapeutic windows. Treat `unmatched_concerns` containing contraindication language as a warning until a better taxonomy exists.

**Tadalafil is active but has no risk trait:**
- Risk: `tadalafil` is an active daily item and notes a nitrate contraindication, but `traits: []` means it produces no `risk:manual_review` warning in `schedule.yaml`.
- Files: `data/products/tadalafil.yaml:4`, `data/products/tadalafil.yaml:11`, `data/inventory.yaml:75`, `data/inventory.yaml:79`, `schedule.yaml:12`, `schedule.yaml:24`
- Current mitigation: `data/inventory.yaml` documents an operator override, and `data/products/tadalafil.yaml` includes free-text unmatched concerns.
- Recommendations: Use a structured override such as `risk_acknowledged` or `warning_suppressed_reason` instead of removing warning semantics from the card. Keep safety-relevant warnings machine-readable even when the operator accepts the risk.

**Personal health and medication data is stored in tracked repo files:**
- Risk: The repo contains personal supplement inventory, doses, brands, off-label medication use, and health-goal metadata.
- Files: `data/inventory.yaml:1`, `data/goals/vascular_health.yaml:1`, `data/goals/mitochondrial_health.yaml:1`, `current-inventory.md:1`
- Current mitigation: `.planning/phases/01-training-stacks-goals-ontology/01-SECURITY.md` classifies the tool as local-only and accepts inventory disclosure risk under the current threat model.
- Recommendations: Keep the repository private. Do not add sync, web UI, issue templates, logs, or CI artifacts that publish `data/*.yaml` contents without a privacy review.

**No dependency lockfile or project config pins the CLI environment:**
- Risk: The script uses PEP 723 inline dependencies but there is no committed lockfile, `pyproject.toml`, or runner config for reproducible dependency resolution.
- Files: `planner.py:1`, `planner.py:3`, `planner.py:4`, `planner.py:5`
- Current mitigation: `uv run planner.py ...` resolves `pyyaml>=6.0` and `jsonschema>=4.21` on demand.
- Recommendations: Add a lockfile or a minimal `pyproject.toml`/`uv.lock` if this tool becomes shared or automated. Keep `pyyaml` and `jsonschema` patched because all source data is parsed through them.

## Performance Bottlenecks

**Scheduler recomputes scores repeatedly during local search:**
- Problem: `total_score()` recalculates every assigned substance score and every prefer pair on each tentative move.
- Files: `planner.py:528`, `planner.py:530`, `planner.py:535`, `planner.py:560`, `planner.py:564`
- Cause: The current implementation favors clarity over cached per-substance/per-slot scores and incremental objective deltas.
- Improvement path: Precompute `score_by_substance_slot[(sid, slot)]`, keep slot-load penalties incremental, and compute prefer-pair deltas only for pairs touching the moved substance. Current scale is small; optimize only when inventory or slots grow enough to make `planner.py plan` slow.

**Validation reloads schemas and files repeatedly:**
- Problem: Each `schema_errors()` call reloads schema JSON from disk, and planner commands reload YAML after a successful check.
- Files: `planner.py:52`, `planner.py:56`, `planner.py:430`, `planner.py:436`, `planner.py:437`, `planner.py:438`
- Cause: There is no in-memory context object carrying loaded slots, traits, inventory, products, and schemas between validation and planning.
- Improvement path: Add a `PlannerContext` built once per command. It should include parsed data, schema validators, card-id maps, and validation info. This also makes unit tests cheaper and easier to isolate.

## Fragile Areas

**Greedy search can fail even when a valid assignment exists:**
- Files: `planner.py:503`, `planner.py:510`, `planner.py:518`, `planner.py:544`
- Why fragile: The initial assignment greedily selects the first valid high-scoring slot by most-constrained ordering. It does not backtrack if an early choice blocks a later substance through `separate_from`.
- Safe modification: Replace the greedy phase with a small backtracking search or OR-Tools-style constraint solver only for hard constraints, then keep local search for soft objective improvement.
- Test coverage: Existing tests cover the current data set in `tests/test_phase_01.py:156`, but no test creates a scenario where greedy fails and backtracking succeeds.

**Trait effect matching accepts under-validated values:**
- Files: `schema/traits.schema.json:42`, `planner.py:94`, `planner.py:377`
- Why fragile: `effects[].match` is any non-empty object. `planner.py` checks keys against slot fields, but schema and code do not validate value type or membership against the corresponding slot field enum. A typo like `activity: preworkout` passes schema and only silently never matches if the key is valid.
- Safe modification: Validate match values against the actual values present in `data/slots.yaml`, or generate a stricter trait schema from the slot schema. Add negative tests for known-key/wrong-value matches.
- Test coverage: `tests/test_phase_01.py:74` asserts exact current activity effects, but there is no generic validator test for bad match values.

**Tests assert snapshot counts instead of invariant behavior in several places:**
- Files: `tests/test_phase_01.py:107`, `tests/test_phase_01.py:110`, `tests/test_phase_01.py:112`, `tests/test_phase_01.py:132`, `tests/test_phase_01.py:177`
- Why fragile: Adding a valid product or goal member requires changing hard-coded counts and substance sets, even if planner behavior remains correct.
- Safe modification: Keep one or two explicit fixture assertions for phase requirements, but add more invariant tests: every non-inactive inventory id appears exactly once in `schedule.yaml`; every inactive id appears zero times; every active training item is placed only in training slots; every active daily item is placed only in daily slots.
- Test coverage: Current suite passes (`pytest -q` gives 7 passed), but it has no property-style or fixture-based coverage for future inventories.

**Tests mutate repository files in place:**
- Files: `tests/test_phase_01.py:156`, `tests/test_phase_01.py:182`
- Why fragile: Tests restore bytes with `try/finally`, but an interrupted process can leave `schedule.yaml` or `data/goals/vascular_health.yaml` modified in the working tree.
- Safe modification: Use `tmp_path` copies for destructive tests, or make `planner.py` accept `--root`/path overrides so tests can run against temporary fixture directories.
- Test coverage: The current restore-path test checks post-restore `planner.py check` at `tests/test_phase_01.py:204`, but interruption safety is not testable with the current in-place pattern.

## Scaling Limits

**Search approach is tuned for a small personal inventory:**
- Current capacity: Current checked data has 23 inventory entries, 15 scheduled non-inactive entries, and 6 slots.
- Limit: Greedy plus single-substance local search can get trapped in local optima as slots, hard separation constraints, pair preferences, and dose timing constraints grow.
- Scaling path: Separate hard feasibility from soft optimization. Use backtracking/branch-and-bound for hard constraints and score cached candidate assignments. Introduce explicit tests with synthetic inventories larger than the personal dataset.

**Taxonomy is discrete and sparse:**
- Current capacity: Current traits cover intake, time, broad class, family separation, manual review, and workout timing.
- Limit: Free-text concerns already cover categories beyond the modeled trait set: cardiovascular mechanisms, formulation-dependent delivery, regulatory status, dose ceilings, thyroid interactions, glucose effects, hydration context, and dose splitting.
- Scaling path: Add only traits that drive concrete planner behavior. Keep low-signal biological categories in `unmatched_concerns` until they affect warnings, constraints, grouping, or schedule explanations.

## Dependencies at Risk

**`uv` is assumed but not declared in repo config:**
- Risk: Tests and documented commands call `uv`, but there is no local config or fallback command.
- Impact: New environments without `uv` cannot run `planner.py` or the test suite as documented.
- Migration plan: Add a short setup note or `pyproject.toml` with equivalent dependencies. Keep the PEP 723 script block for convenient `uv run planner.py` usage.

**No CI configuration is present:**
- Risk: `planner.py check` and `pytest` are manual gates only.
- Impact: Data edits can merge with invalid schedules, skipped full checks, or broken CLI behavior.
- Migration plan: Add a minimal CI job that runs `uv run planner.py check` and `uv run --with pytest --with pyyaml pytest -q`.

## Missing Critical Features

**No structured interaction model for safety-critical combinations:**
- Problem: The data records several important interactions, but the planner has no first-class model for interaction type, severity, acknowledgement, or mitigation.
- Blocks: Reliable warnings for tadalafil plus nitrates/PDE5 interactions, citrulline plus tadalafil hypotension stacking, nattokinase plus anticoagulants, potassium plus ACE/ARB/K-sparing diuretics, thyroid-related mineral interactions, and dose-ceiling toxicity.

**No dose math or daily total validation:**
- Problem: `data/inventory.yaml` stores doses as free-form strings, and `schema/inventory.schema.json` only validates them as non-empty strings.
- Blocks: The tool cannot calculate elemental totals, upper-limit proximity, duplicate active ingredients across products, or split-dose schedules.

**No routine calendar/day model:**
- Problem: Slots are static and global; there is no day type, workout-day toggle, variable training time, or aerobic/strength distinction.
- Blocks: Schedules cannot differ between training and rest days, and pre/post-workout placement is always present even when no workout occurs.

## Test Coverage Gaps

**Single-target CLI behavior:**
- What's not tested: `uv run planner.py check data/products/<id>.yaml`, including valid `prefer_with` references and the skipped inventory/goal checks.
- Files: `planner.py:291`, `planner.py:300`, `tests/test_phase_01.py`
- Risk: The documented single-card command fails for valid cards or gives users a false sense that all references were checked.
- Priority: High

**Malformed YAML handling for core files:**
- What's not tested: Parse errors, empty files, and non-mapping roots for `data/slots.yaml`, `data/traits.yaml`, and `data/inventory.yaml`.
- Files: `planner.py:272`, `planner.py:273`, `planner.py:305`, `tests/test_phase_01.py`
- Risk: Bad edits can crash the CLI instead of returning actionable validation errors.
- Priority: Medium

**Scheduler hard-constraint feasibility:**
- What's not tested: Cases where `separate_from` constraints require backtracking, cases where all slots are blocked, and cases where a valid assignment exists but greedy ordering prevents it.
- Files: `planner.py:411`, `planner.py:510`, `planner.py:518`, `tests/test_phase_01.py:156`
- Risk: Future trait additions can make `planner.py plan` fail or produce low-quality schedules without a focused regression explaining why.
- Priority: Medium

**Risk warning coverage:**
- What's not tested: Every active product with safety-relevant unmatched concerns either has `risk:manual_review` or a structured acknowledgement.
- Files: `data/products/tadalafil.yaml:4`, `data/products/tadalafil.yaml:8`, `schedule.yaml:24`, `tests/test_phase_01.py`
- Risk: Safety-sensitive substances can appear in schedules without warning entries.
- Priority: High

**Generated schedule freshness:**
- What's not tested: Committed `schedule.yaml` equals the planner output for current YAML inputs.
- Files: `planner.py:638`, `schedule.yaml:1`, `tests/test_phase_01.py:156`
- Risk: The checked-in schedule can drift from the source data unnoticed.
- Priority: Medium

---

*Concerns audit: 2026-05-05*
