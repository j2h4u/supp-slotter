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

### Phase 8: Grouped trait shape + dashboard membership via tags

**Goal:** Restructure substance card representation from a flat `traits:` list with namespace-prefixed strings to top-level grouped keys per namespace (`is:`, `intake:`, `effect:`, `risk:`, `activity:`, new `dashboard:`), each holding bare slugs. Replace dashboard manual `taking[]` lists with computed membership via grouped `from_traits:`. The `class:*` namespace becomes the `is:` top-level key (rename happens automatically as part of substance card rewrite). Introduce reference-integrity error in `planner check` so file-based cross-references behave like FK constraints. Optional doctor lifecycle warnings deferred to Stage 2.

**Execution model:** Sonnet — Haiku has misapplied trait-ontology rules in this codebase previously (see memory `feedback_subagent_models.md`).

**Context:** `.planning/notes/ontology-dashboard-trait-namespace.md` captures full design rationale: expert panel convergence (ontology + taxonomy + architect + PM + Kaizen + agent DX), alternatives evaluated, supporting data (0/106 unused `reason`/`note` grep), decision to defer `is_class:`/`is_property:` split, decision to kill `vasodilation_no_pathway` (PM finding: strict 5/5 subset of `vascular_health`).

**Internal stages** (per Kaizen migration specialist — reduces atomicity risk):
- **Stage 1 (atomic single commit):** core schema/migration/planner pivot (DT-01 through DT-10). All correctness changes land together so `check` is never broken between commits.
- **Stage 2 (separate additive commits):** documentation, review-substance audit, optional doctor warnings (DT-11 through DT-14).

**Requirements**:

**Stage 1 — Core (atomic single commit; correctness changes land together):**

- DT-01: Substance schema overhaul — `schema/substance.schema.json` replaces top-level `traits: array of strings` with top-level grouped keys: `is:`, `intake:`, `effect:`, `risk:`, `activity:`, `dashboard:` — each as array of bare slugs (no namespace prefix in slug). Set `additionalProperties: false` on the substance object so the namespace key set is closed (no agent-invented `note:`/`meta:`/etc. drift). Per-namespace constraints: `intake:` and `activity:` `maxItems: 1`; `is:`, `effect:`, `risk:`, `dashboard:` polyhierarchical (no max). All groups optional (a substance card may omit any namespace it doesn't need)
- DT-02: Substance card migration — rewrite all ~50 `data/substances/*.yaml` from flat `traits: [namespace:slug, ...]` to the grouped form. Existing `class:antioxidant` → goes under top-level `is:` as bare slug `antioxidant`. This is the operation that effectively performs the `class:` → `is:` rename (no separate rename step needed — the rename is just choosing the right top-level key). Substance cards with no scheduling traits keep their `notes`/`concerns` etc. unchanged
- DT-03: Add `dashboard:*` namespace block in `data/traits.yaml`. One entry per operator-curated cluster currently using explicit `taking:` lists. Skip pure-class clusters (`antioxidant_protection` → projects from `is:antioxidant`; `electrolyte_hydration_support` → `is:electrolyte`; `neurocognitive_support` → `is:nootropic`; `workout_performance` → `is:ergogenic`). Each new entry has `label` and `description` matching existing traits.yaml convention
- DT-04: Tag substance cards with `dashboard:<slug>` entries under their `dashboard:` group, mechanically migrated from current dashboard `taking[]` lists. Example: 8 members of `connective_tissue_support.yaml` each get `connective_tissue_support` added under their `dashboard:` list. Pure-class dashboards need no `dashboard:*` tags (membership via existing `is:*`)
- DT-05: Dashboard schema overhaul — `schema/dashboard.schema.json` removes `taking[]` and its `substance`/`name`/`note`/`reason` sub-fields (0/106 adoption confirmed by grep); adds `from_traits:` as a grouped object keyed by namespace (`is:`, `dashboard:`, `intake:`, `effect:`, `risk:`, `activity:`), each holding array of bare slugs. `additionalProperties: false` on the `from_traits` object. Resolution semantics: union over all listed slugs across all namespaces. Keep existing `anyOf` requirement for `benefit`/`risk`
- DT-06: Rewrite all 13 `data/dashboards/*.yaml` to use grouped `from_traits:`. Pure-class clusters get `from_traits: { is: [antioxidant] }` etc. Operator-curated clusters get `from_traits: { dashboard: [<slug>] }`. **KILL `data/dashboards/vasodilation_no_pathway.yaml`** — PM finding: strict 5/5 subset of `vascular_health` with no unique monitoring intent (operator confirmed: agent verbosity, not deliberate axis). 14 → 13 dashboards
- DT-07: Planner contract + loader overhaul — `Substance` dataclass in `planner/contracts.py` changes from `traits: list[str]` to per-namespace fields (`is: list[str]`, `intake: list[str]`, `effect: list[str]`, `risk: list[str]`, `activity: list[str]`, `dashboard: list[str]`). Update `planner/cards/substance.py` loader to read grouped shape. Update `planner/cards/dashboards.py` — replace `taking[]`-based loading with grouped `from_traits` resolution (scan each substance's per-namespace lists for any bare slug listed in the corresponding `from_traits` namespace key). Remove dead `taking:` parsing. Note `effective_stack_item_traits` and similar helpers — they may need to flatten back to a single set internally for slot scoring; preserve behavior, change only internal representation
- DT-08: Reference-integrity error in `planner check`. Error when: (a) a substance card slug under namespace `<ns>:` is not registered in `data/traits.yaml` under that namespace; (b) a `from_traits[<ns>][i]` slug is not registered in `traits.yaml` under that namespace. CardLoadError-style errors with file context. **Make error messages prescriptive** (per agent DX recommendation): `"Unknown trait 'cardiovascular' under namespace 'dashboard:' in substances/foo.yaml:14 — register it in data/traits.yaml under 'dashboard:' first (with label and description)."`
- DT-09: Regenerate `schedule.yaml`. Verify each surviving dashboard's `covered/inactive/missing` partitioning is identical to pre-refactor baseline for the 12 retained operator clusters (excluding the killed `vasodilation_no_pathway`); for `vascular_health` confirm the merged-in substances now appear correctly
- DT-10: Minimal test coverage for Stage 1 correctness — new substance schema accepts grouped form; old flat form fails validation; grouped `from_traits` resolution produces expected membership; reference-integrity errors trigger on both substance side and dashboard side. Update existing fixtures to the new shape

**Stage 2 — Follow-on (separate additive commits; can land independently after Stage 1):**

- DT-11: Documentation reference layer — `docs/domain-model.md`: rewrite "Trait" and "Dashboard cluster" entries under Core Objects; full "Trait Ontology" section under grouped model (each namespace described with its cardinality rules); refresh all "Adding Data" YAML examples to grouped form; update "Ownership Rules" bullets that mention "Put broad benefit/risk groupings in dashboard clusters". `docs/ontology-facts.md`: rewrite "Decided: Not Encoding" entries that mention "encode as dashboard cluster" to reflect the new tag-on-card mechanism; update "Encoding Policy" final bullet; add explicit one-paragraph note about intensional vs extensional semantics in `from_traits` (`is:[antioxidant]` is intensional/open-world — any future antioxidant joins; `dashboard:[foo]` is extensional/curated — only what was explicitly tagged); add new "Decided: Not Solving" entry for the rename-ghost risk (substance renamed but stale `dashboard:` tag remains valid-looking — no automatic detection possible, relies on operator hygiene + grep). `README.md` if it references the old shape
- DT-12: Agent entrypoint — `SKILL.md`:
  - File Tree section: refine `data/dashboards/` description to mention membership-via-tags + canonical serialization rule "grouped at rest, grouped in queries"
  - "Add Or Enrich A Substance" workflow line 121: **drop the hardcoded class-marker enumeration entirely** (per agent DX: staleness trap); replace with "see `data/traits.yaml` for the full namespace registry; run `python -m planner review-substance <path>` to inspect a card's current tags grouped by namespace"
  - Add a 3-line **"Which namespace?"** decision block (per agent DX): (1) use `is:` when the property is true regardless of stack goals; (2) use `dashboard:` when a curator decided this substance belongs in a named cluster; (3) leave unencoded if neither applies
  - "Add Or Update A Dashboard" workflow: rewrite `taking:` workflow to grouped `from_traits:`; explain when to project from `is:` (pure-class clusters) vs `dashboard:` (operator-curated); drop "sort taking alphabetically" rule; spell out the bootstrap sequence: verify `dashboard:<slug>` exists in `traits.yaml` BEFORE tagging substance cards
  - "Minimal YAML Shapes" section: substance card example in grouped form; dashboard example with grouped `from_traits:`
  - "Validation Contract" section: enumerate new reference-integrity errors from DT-08 and all four DT-14 doctor lifecycle warning classes
  - Add a brief **"Membership Flow"** subsection as a textual decision tree (per agent DX explicit: NOT ASCII visual — agents paraphrase visuals inconsistently across sessions): trace substance per-namespace tags → dashboard grouped `from_traits` → resolved membership
  - Add a **"Doctor Warning Playbook"** subsection (load-bearing because agents are the primary `doctor` consumer and have no persistent memory): explicit "WHEN to run `python -m planner doctor`" — after any substance card edit, after any dashboard yaml edit, after any `traits.yaml` change, and once at the end of a session before commit. Plus per-warning-class decision tree: for each of DT-14 (a)–(d), spell out "if this fires, here are the resolution options A/B/C and how to choose between them based on operator intent". This is the bridge that compensates for agent statelessness — without it, doctor output is noise the agent doesn't know how to act on
  `.planning/PROJECT.md` line 17: namespace list refresh under grouped model.
  Out of scope (do NOT touch): `docs/private/2026-05-11-expert-panel-round-*.md` — historical session snapshots
- DT-13: Verify `review-substance` shows state across all namespace groups with no hidden filtering. Post-refactor: each top-level namespace group (`is:`, `intake:`, `effect:`, `risk:`, `activity:`, `dashboard:`) appears as a section with per-trait checkboxes; typos like an unknown slug under `dashboard:` surface in "unknown" section; `print_trait_details` renders descriptions for the new `dashboard:*` namespace. Audit `readable_traits()` filter at `planner/cards/traits.py:146` (currently filters `class:` prefix substring): under grouped model the function works on different input shape — refactor to namespace-aware filter; decide policy (probably: hide `is:*` and `dashboard:*` from plan narrative since both are review-axes not scheduling rules); document the chosen policy in a code comment
- DT-14: Doctor lifecycle warnings — **required** (the primary consumer is agentic sessions, which are stateless across runs; SKILL.md instructs agents to run `doctor` after substance/dashboard edits, so warnings carry their consumer with them). Four warning classes, each with **actionable resolution guidance** in the warning text (per agent DX requirement: "Orphan warnings are ambiguous without operator intent — text must spell out the remediation choices"):
  - (a) `dashboard:*` trait registered in `traits.yaml` but no substance card carries it. Text: *"Orphan registration: `dashboard:gut_motility` defined in `data/traits.yaml` but no substance card has it under its `dashboard:` group. Likely cause: trait registered for a planned cluster but substance tagging not yet done. Resolution: tag relevant substance cards under `dashboard:`, OR remove the trait entry from `traits.yaml` if the cluster is abandoned."*
  - (b) `dashboard:*` trait is carried by substances but no `data/dashboards/*.yaml` references it via `from_traits`. Text: *"Unused trait: `dashboard:cholinergic_load` is carried by 8 substance cards but no dashboard yaml references it. Likely cause: dashboard yaml deleted while tags remained, OR yaml not yet created. Resolution: create `data/dashboards/cholinergic_load.yaml` referencing it, OR remove the tag from the 8 substance cards and the entry from `traits.yaml`."*
  - (c) Slug↔trait convention break: `data/dashboards/<slug>.yaml` exists without matching `dashboard:<slug>` trait in `traits.yaml`, or vice versa. Text spells out which direction was violated and the canonical fix sequence.
  - (d) Dashboard whose grouped `from_traits` resolves to empty substance set. Text: *"Empty cluster: `data/dashboards/sleep_quality.yaml` has `from_traits: { dashboard: [sleep_quality] }` but no substance carries `sleep_quality` under its `dashboard:` group. Resolution: tag substances under `dashboard:`, OR remove the dashboard yaml if abandoned. (If this is an intentional watch-slot for future use, suppress with a `notes:` field explaining the intent.)"*

**Depends on:** Phase 3 data model (post-substance/product split). Phases 4–7 (code quality refactors completed as quick tasks per STATE.md) do not constrain this work
**Plans:** 0 plans

Plans:
- [ ] TBD (run /gsd-plan-phase 8 to break down)

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
