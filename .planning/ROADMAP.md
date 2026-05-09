# Roadmap: Supplement Slot Planner

**Core Value:** Personal supplement scheduling that respects food state, time of day, training routine, and health-goal clusters — without manual slot management.

## Milestones

- [x] **v1.1 Training Stacks + Goals Ontology** — Phase 1 (executed and verified)

<details>
<summary>Pre-GSD MVP (informational, not numbered)</summary>

The MVP system was built before GSD was introduced to this project: 23 substance cards, 4 physical slots, 16 traits in 5 namespaces, working `planner.py` with check/refresh/plan subcommands. `idea.md` is the authoritative SPEC.

</details>

### Phase 2: Substance/Product YAML model split

**Goal:** Split the YAML model into Substance, Product, and InventoryItem entities; migrate slots to declarative `near + food`; keep products physically inseparable during scheduling; and add only practical ontology improvements for scheduling, warnings, and explanations.
**Requirements**: TBD
**Depends on:** Phase 1
**Plans:** 5 plans

Plans:
- [x] 02-01-PLAN.md — Data/schema migration: Substance/Product/InventoryItem split, near+food slots, practical ontology
- [x] 02-02-PLAN.md — Planner validation: split-model loaders, schema checks, inventory/product refs, goal substance refs
- [x] 02-03-PLAN.md — Scheduler/explainability: schedule inventory products as inseparable units with component-aware reasons and warnings
- [x] 02-04-PLAN.md — Regression verification: Phase 2 tests, Phase 1 topology preservation, regenerated schedule smoke
- [x] 02-05-PLAN.md — Gap closure: target-mode prefer_with registry validation and malformed inventory schema errors

### Phase 3: Product Facts + Stack-Oriented Inventory

**Goal:** Correct data ownership after the product split: make inventory stack-oriented for readability, move product facts such as brand and label/component amounts into product cards, and split generic B6 into concrete label forms without adding unused taxonomy or a separate regimen model.
**Requirements**: TBD
**Depends on:** Phase 2
**Plans:** 4 plans

Plans:
- [x] 03-01-PLAN.md — Product fact preservation: copy known brand/label facts into product cards before stripping inventory
- [x] 03-02-PLAN.md — Stack-oriented inventory schema/data migration and planner loader/refresh normalization
- [x] 03-03-PLAN.md — Concrete B6 forms: P-5-P and pyridoxine HCl without unused taxonomy
- [x] 03-04-PLAN.md — Regression verification and regenerated schedule smoke

### Phase 4: Code Quality — Quick Wins

**Goal:** Apply 7 trivial fixes from the code review: dead code removal, hardcoded log prefixes, misleading log levels, noise docstrings. All changes are pure deletions or one-liners — no design decisions required.
**Requirements**:
- QW-01: Delete 4 blocks of dead `fixture_id()` calls with discarded results: `tests/test_phase_02.py:514–516, 583–584, 697–699, 793–795`
- QW-02: Delete `test_no_regimen_file_exists` (always-green liar test, guards a file that never existed): `tests/test_phase_03.py:843–845`
- QW-03: Fix conditional ordering assertion in `test_find_searches_multiple_fuzzy_words` — make unconditional or remove: `tests/test_phase_03.py:366–368`
- QW-04: Remove `# noqa: ARG001  reserved for future stack-level trait checks` placeholder from `stacks.py:82`; remove the unused `trait_ids` parameter from `filter_stack_items`
- QW-05: Replace hardcoded `"plan:"` prefix with `"warning:"` in `load_substance_registry` (`substance.py:280`) and `load_product_registry` (`product.py:166`)
- QW-06: Remove `WARN:` prefix from informational advisory print in `check_stack_alignment` (`stacks.py:35`)
- QW-07: Delete 4 noise docstrings that restate function names verbatim: `load_substance_registry`, `load_product_registry`, `load_global_relations`, `collect_dashboard_substance_refs`
**Depends on:** Phase 3
**Plans:** 0 plans

Plans:
- [ ] TBD (run /gsd-plan-phase 4 to break down)

### Phase 5: Code Quality — Critical Correctness Fixes

**Goal:** Fix 5 high-impact issues where bugs can go undetected: a liar test with a type mismatch that can never fail, 4 silent CardLoadError handlers that hide broken cards, lock failures that corrupt state silently, schema error output that bypasses path normalization, and a test that validates a committed artifact instead of fresh planner output.
**Requirements**:
- CC-01: Fix liar test `test_inter_product_absorption_relation_blocks_colocation` (`tests/test_phase_02.py:648–652`): `colocated_pairs` checks raw fixture IDs against schedule display strings — they can never match; replace with display names derived via `format_product_name`
- CC-02: Add `print(f"warning: skipping ...: {e.message}", file=sys.stderr)` before bare `continue` in 4 CardLoadError handlers: `substance.py:95`, `product.py:69`, `dashboards.py:92`, `dashboards.py:122`
- CC-03: Fix silent lock failures in `maintenance.py`: log OSError to stderr before `return` in `clear_stale_lock` (:84) and before `pass` in `release_maintenance_lock` (:106–110)
- CC-04: Route `validate_schemas` errors through `display_message()` instead of raw `print` to ensure path normalization consistent with all other error output: `io.py:226–228`
- CC-05: Fix `test_schedule_baseline_remains_stable` (`tests/test_phase_03.py:848`): regenerate `schedule.yaml` at test start (as the sibling test on :904 does) instead of reading the committed file
**Depends on:** Phase 4
**Plans:** 0 plans

Plans:
- [ ] TBD (run /gsd-plan-phase 5 to break down)

### Phase 6: Code Quality — Structural Improvements

**Goal:** Fix three data-integrity risk paths in maintenance write operations, add unit tests for four undertested core functions with no targeted coverage, and deduplicate four repeated code patterns that make changes risky.
**Requirements**:
- SI-01: Fix `acquire_maintenance_lock` pid write failure (`maintenance.py:102`): wrap pid `write_text` in try/except OSError, clean up the lock directory, return False — currently a failed write "acquires" the lock with no pid, causing concurrent processes to unconditionally clear it
- SI-02: Fix partial-write in `rewrite_substance_refs` (`maintenance.py:127–208`): wrap each `path.write_text()` in try/except OSError; abort loop on first failure to avoid partially-rewritten data directory state
- SI-03: Fix in-memory ID mutation before disk write in `normalize_substances` (`maintenance.py:237–244`): wrap write in try/except OSError, return None on failure before proceeding to rename — currently a failed write leaves the in-memory substance dict with a new ID but the file unchanged, corrupting the subsequent rename path
- SI-04: Add unit tests for `compute_slot_score` covering: `prefer_strong` match adds +4, `avoid` match adds -2, `block=True` sets `blocked=True`, no-match effect contributes zero score
- SI-05: Add unit test for `must_separate` symmetry: A-declares-against-B, B-declares-against-A, and neither-declares cases
- SI-06: Add unit tests for `humanize_warning`: known warning type with ID-addressed product, unknown type falls back to `"Review"`, message containing suppressed substring
- SI-07: Add unit tests for `review_context_key`: each keyword branch and None fallback
- SI-08: Add test for `collect_missing_support_relations` non-warning direction: source active, target absent → no `supports_missing` warning emitted
- SI-09: Extract `_endpoint_fields(relation, side) -> (substance_id, name)` from the 4 duplicated `if side == "source" / "target"` branches in `relations.py:70`
- SI-10: Extract `_collect_missing_relation_warnings(relation_type, symmetric, ...)` from the structurally identical bodies of `collect_missing_balance_relations` and `collect_missing_support_relations` (`relations.py:253, 290`)
- SI-11: Extract `_slot_is_blocked(item, slot_name, ...)` shared predicate from the duplicated conflict-check blocks in greedy seed (`plan.py:270–330`) and search (`plan.py:367–392`)
- SI-12: Rename the two `copy_planner_runtime` functions with identical names but different behavior: `test_phase_02.py:47` (copies only `planner/` + `schema/`, returns None) → `copy_planner_runtime_only`; `test_phase_03.py:151` (copies `data/` + `planner/` + `schema/`, returns `temp_data`) → `copy_planner_with_data`
**Depends on:** Phase 5
**Plans:** 0 plans

Plans:
- [ ] TBD (run /gsd-plan-phase 6 to break down)

### Phase 7: Code Quality — Long-term Refactoring

**Goal:** Decompose the 515-line `cmd_plan` into a testable B&B solver, deduplicate substance/product normalization into a shared generic, restructure the warning dispatch table, and add missing contracts on non-obvious public API functions.
**Requirements**:
- LR-01: Extract `_SearchState` dataclass (holding the 10 mutable nonlocal variables) + `_solve_assignment()` module-level function from the 5-closure `cmd_plan` (`plan.py:62`); makes the solver independently testable
- LR-02: Extract `_normalize_cards(cards_dir, canonical_fn, id_prefix, id_key)` generic from the ~60-line duplicated normalization logic in `normalize_substances` and the products block of `run_auto_maintenance_unlocked` (`maintenance.py:210–392`)
- LR-03: Restructure `warning_action` from a 10-branch if/elif chain to a `_ACTION_BY_TYPE: dict[str, str]` lookup table + trait/relation fallback (`warnings.py:13`)
- LR-04: Decompose `humanize_warning` into `_format_warning_entities()` (product/substance name lookups) + `_derive_concern_text()` helpers; remove the `if warning_type == "risk_cluster_load": pass` no-op branch (`warnings.py:102`)
- LR-05: Add docstrings for 8 non-obvious API contracts identified by the docs audit:
  - `effective_stack_item_traits` (`_scheduling.py:13`): document the 3-tuple return values (effective_traits, trait_sources, internal_conflicts)
  - `connected_components` (`_common.py:66`): document the silent singleton-drop (only components with len > 1 returned)
  - `build_action_points` (`schedule.py:8`): document the 8-item hard cap and `manual_review` skip rule
  - `build_placement_notes` (`schedule.py:35`): document the tradeoff-filter criterion (only `why_here` entries containing "tradeoff")
  - `search_score` (`search.py:56`): document AND-gate semantics (any word below threshold → 0.0, not an average)
  - `combined_search_score` (`search.py:76`): document the asymmetric 0.75 penalty when `identity_score == 0`
  - `components_have_global_relation` (`relations.py:352`): document that it is always symmetric regardless of relation type directionality
  - `Slot` (`contracts.py:133`): correct stale attribution from `flatten_pillbox_slots` to `load_pillboxes`
**Depends on:** Phase 6
**Plans:** 0 plans

Plans:
- [ ] TBD (run /gsd-plan-phase 7 to break down)

---

### Phase 1: Training Stacks + Goals Ontology
**Goal**: Add training-stack partition (2 virtual workout slots, `activity:` namespace, stack-aware planner) and goal-cards as first-class entities (vascular_health + mitochondrial_health seed cards, goal-master canonical with referential validator).

**Depends on**: none (extends pre-GSD MVP)

**Requirements**:
- TRAIN-01: Two virtual training slots (`pre_workout`, `post_workout`) usable by the planner
- TRAIN-02: Stack partition (`daily | training | inactive`) replacing `active: true|false` in inventory
- TRAIN-03: New `activity:` trait namespace with three peer traits (`pre_workout`, `post_workout`, `any_workout`) and asymmetric levels
- GOAL-01: Goal-card schema and `data/goals/*.yaml` directory
- GOAL-02: Two seed goal cards (vascular_health, mitochondrial_health) with members, candidates, declined
- GOAL-03: Referential integrity validator — `members[].substance` refs must point to existing substance cards

**Success Criteria** (what must be TRUE):
  1. `uv run planner.py check` passes with no errors after migration
  2. `uv run planner.py plan` produces a `schedule.yaml` where training-stack substances (citrulline, creatine, electrolyte_caps, l_carnitine_l_tartrate) land ONLY in `pre_workout` or `post_workout` slots
  3. Daily-stack substances land ONLY in the original 4 slots (morning_empty, morning_food, day_food, evening_empty); never in training slots
  4. Inactive-stack substances are skipped entirely from `schedule.yaml`
  5. `inventory.yaml` has no `active` field for any entry; every entry has a valid `stack` value
  6. `data/goals/vascular_health.yaml` exists with 4 members in `taking` status (citrulline, nattokinase, tadalafil, vitamin_b5)
  7. `data/goals/mitochondrial_health.yaml` exists with ALCAR (taking) + 2 candidates (CoQ10, ALA, name-only)
  8. Referential validator catches any goal-card `members[].substance` ref that doesn't have a matching substance card
  9. `schema/goal.schema.json` is registered and validates goal cards
  10. l_carnitine_l_tartrate is promoted from inactive to training stack with `activity:any_workout`

**Plans**: 4 plans
- [x] 01-01-PLAN.md — Data foundations: slots.yaml stack partition, traits.yaml activity namespace, inventory.yaml migration (active→stack)
- [x] 01-02-PLAN.md — Substance & goal cards: 4 product cards add activity:* traits; create data/goals/ + 2 seed cards (vascular_health, mitochondrial_health)
- [x] 01-03-PLAN.md — Planner code: register activity namespace, refresh writes stack:inactive, cmd_plan stack-partition filter, cmd_check goal-card referential validator
- [x] 01-04-PLAN.md — Smoke test: end-to-end check + plan + topology assertions; negative test for referential validator
