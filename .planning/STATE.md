---
gsd_state_version: 1.0
milestone: v1.1
milestone_name: Training Stacks + Goals Ontology
current_phase: 9
status: completed
last_updated: "2026-05-16T13:36:31.036Z"
progress:
  total_phases: 9
  completed_phases: 5
  total_plans: 23
  completed_plans: 23
  percent: 56
---

# State

**Current milestone:** Training + Goals Ontology Extension
**Current phase:** 9
**Status:** Milestone complete

## Phase 1 progress

- [x] Discuss-phase equivalent: design discussion completed in conversation; captured in `phases/1-training-stacks-and-goals/CONTEXT.md`
- [x] Schemas updated (`slots`, `inventory`, new `goal`) — already on disk before GSD pivot
- [x] PLAN.md generated: 4 plans in `.planning/phases/01-training-stacks-goals-ontology/`
- [x] Execution
- [x] Verification

## Last action

2026-05-16 - Completed quick task 260516-poi: Add pytest-cov dep, coverage config ([tool.coverage.*]), and just coverage recipe; fail_under=83 from measured 85% baseline. Commits ad89148, 150394b.

### Quick Tasks Completed

| # | Description | Date | Commit | Status | Directory |
|---|-------------|------|--------|--------|-----------|
| 260506-iex | Simplify inventory to stack product lists: remove redundant item-id/product duplication, remove traits_override and notes from inventory, keep inventory as only stack membership | 2026-05-06 | eb9d81e |  | [260506-iex-simplify-inventory-to-stack-product-list](./quick/260506-iex-simplify-inventory-to-stack-product-list/) |
| 260506-kt5 | Normalize trait ontology axes and remove unused/overlapping traits | 2026-05-06 | 05b8ba2 |  | [260506-kt5-normalize-trait-ontology-axes-and-remove](./quick/260506-kt5-normalize-trait-ontology-axes-and-remove/) |
| 260508-m3i | Improve review layer and pillbox guardrails from expert-panel recommendations | 2026-05-08 | bd42f31 | Verified | [260508-m3i-improve-review-layer-and-pillbox-guardra](./quick/260508-m3i-improve-review-layer-and-pillbox-guardra/) |
| 260508-x91 | Split planner.py into a planner/ package with five modules (io, cards, maintenance, engine, __main__) | 2026-05-09 | f167f20 |  | [260508-x91-split-planner-py-into-a-planner-package-](./quick/260508-x91-split-planner-py-into-a-planner-package-/) |
| 260509-ka3 | Migrate to dataclass contracts, enable strict pyright, remove back-compat scaffolding | 2026-05-09 | 430565d | Incomplete (479 strict-pyright errors deferred) | [260509-ka3-migrate-to-dataclass-contracts-enable-st](./quick/260509-ka3-migrate-to-dataclass-contracts-enable-st/) |
| 260509-uo9 | Phase 4 KQ1 — Code Quality Quick Wins (7 trivial fixes: dead fixture_id calls, liar test, conditional assertion, unused param, log prefixes, noise docstrings) | 2026-05-09 | ac96af8 |  | [260509-uo9-phase-4-kq1-code-quality-quick-wins](./quick/260509-uo9-phase-4-kq1-code-quality-quick-wins/) |
| 260509-v19 | Phase 5 KQ2 — Code Quality Critical Correctness Fixes (liar test CC-01, 4 silent CardLoadError CC-02, lock failures CC-03, schema routing CC-04 verified, committed-artifact test CC-05) | 2026-05-09 | 64da490 |  | [260509-v19-phase-5-kq2-code-quality-critical-correc](./quick/260509-v19-phase-5-kq2-code-quality-critical-correc/) |
| 260509-vcm | Phase 6 KQ3 — Code Quality Structural Improvements (SI-01–03 write-failure hardening, SI-04–08 unit tests +16, SI-09–10 relations dedup, SI-11 _slot_is_blocked, SI-12 rename copy_planner_runtime) | 2026-05-09 | 72a366b |  | [260509-vcm-phase-6-kq3-code-quality-structural-impr](./quick/260509-vcm-phase-6-kq3-code-quality-structural-impr/) |
| 260510-0nt | Phase 7 KQ4 — Code Quality Long-term Refactoring (LR-01 cmd_plan→4 helpers, LR-02 _normalize_card_dir, LR-03 warning_action lookup tables, LR-04 humanize_warning decomposed, LR-05 8 docstrings) | 2026-05-10 | f39434e |  | [260510-0nt-phase-7-kq4-code-quality-long-term-refac](./quick/260510-0nt-phase-7-kq4-code-quality-long-term-refac/) |
| 260510-39y | KQ5 — Close remaining review findings (A: 5 naming renames, B: _declares_against + _explain_effect_for_slot lifted, C: 3 observability fixes, D: 18 docstrings) | 2026-05-10 | f30e1c2 |  | [260510-39y-kq5-close-remaining-review-findings-nami](./quick/260510-39y-kq5-close-remaining-review-findings-nami/) |
| 260510-41b | KQ6 — Close cosmetic tail (8 B&B solver renames: item_traits/scored_slots_by_item/etc, 5 test helper renames, _member_label lifted, _substance_fallback_name, stack_groups removed, assigned_item_ids) | 2026-05-10 | 727e379 |  | [260510-41b-kq6-close-cosmetic-tail-rename-solver-lo](./quick/260510-41b-kq6-close-cosmetic-tail-rename-solver-lo/) |
| 260510-4rs | plan.py: extract _run_plan_search + _compute_assignment_total, harden cmd_plan error paths (CardLoadError, write OSError, exhausted-search diagnostic), require trait_sources | 2026-05-10 | 8c8481c |  | [260510-4rs-fix-plan-py-reduce-complexity-fix-naming](./quick/260510-4rs-fix-plan-py-reduce-complexity-fix-naming/) |
| 260510-4rz | maintenance.py + io.py: load_yaml/load_schema error wrapping, stacks.yaml write guard, stderr on CardLoadError skip, relations.yaml non-mapping warning, None sentinel on auto_maintenance_needed | 2026-05-10 | f77b354 |  | [260510-4rz-fix-maintenance-py-and-io-py-silent-fail](./quick/260510-4rz-fix-maintenance-py-and-io-py-silent-fail/) |
| 260510-is4 | C4+C5 critical test gaps: food-axis tests for compute_slot_score (match/mismatch/block), block test score==0 assertion, support-relation warning-direction test (target active/source absent) | 2026-05-10 | 0c819a3 |  | [260510-is4-close-c4-and-c5-add-food-axis-coverage-t](./quick/260510-is4-close-c4-and-c5-add-food-axis-coverage-t/) |
| 260510-iwv | Issues A: rename remaining_score_upper_bound/feasible_slots_by_item/item_id_sequence (plan.py), needs_new_id (maintenance.py), group_items_by_stack (tests), cmd_check message fix, 4 noise docs removed | 2026-05-10 | 17eacb8 |  | [260510-iwv-issues-a-naming-renames-and-comment-nois](./quick/260510-iwv-issues-a-naming-renames-and-comment-nois/) |
| 260510-jb4 | Issues B: split 6 multi-invariant tests, remove tautological assertion, +10 humanize_warning coverage tests, +4 review-substance error-path tests (95 total tests passing) | 2026-05-10 | 0d00ba5 |  | [260510-jb4-issues-b-test-quality-split-6-invariant-](./quick/260510-jb4-issues-b-test-quality-split-6-invariant-/) |
| 260510-jb9 | Issues C: review_context_key→_CONTEXT_KEY_RULES table, rewrite_substance_refs→2 helpers, _build_schedule_output 20→15 params via PlanInputs+ActiveIndex NamedTuples, pyright 0/0/0 | 2026-05-10 | 5932a76 |  | [260510-jb9-issues-c-structural-complexity-build-sch](./quick/260510-jb9-issues-c-structural-complexity-build-sch/) |
| 260510-k5m | Recommendations pass: strip_root_prefix rename, reasons local, make_* test factories, RelationSide Literal alias, dead helper deleted, registry skip summaries, 8 docstrings, 3 noise lines | 2026-05-10 | e019786 |  | [260510-k5m-recommendations-pass-naming-micro-rename](./quick/260510-k5m-recommendations-pass-naming-micro-rename/) |
| 260510-l2m | Add show command: regenerates schedule, prints pillbox layout to terminal in plain prose, footer notes schedule.yaml sections; also fixed uv run --project for all integration tests (99/99 pass) | 2026-05-10 | a0d92b4 |  | [260510-l2m-add-show-command-regenerates-schedule-an](./quick/260510-l2m-add-show-command-regenerates-schedule-an/) |
| 260512-h6p | Refactor relations ontology: add severity field to all relation types; fix dead antagonizes (wire to warning generator); add D3→Magnesium as supports with severity critical; update ontology-facts.md | 2026-05-12 | 62fec09 |  | [260512-h6p-refactor-relations-ontology-add-severity](./quick/260512-h6p-refactor-relations-ontology-add-severity/) |
| 260512-ib5 | Refactor test suite: delete 10 LIVE_DATA tests, add planner check CI gate, refactor cmd_* to return structured results, convert 10 subprocess tests to direct function calls | 2026-05-12 | a778ffb |  | [260512-ib5-refactor-test-suite-delete-live-data-tes](./quick/260512-ib5-refactor-test-suite-delete-live-data-tes/) |
| 260512-j8x | Convert remaining subprocess tests to direct cmd_* calls — 5 run_planner calls remain (--help + 4 CLI error-path tests) | 2026-05-12 | c317a76 |  | [260512-j8x-convert-remaining-subprocess-tests-to-di](./quick/260512-j8x-convert-remaining-subprocess-tests-to-di/) |
| 260516-oph | Replace _root_patch mutation with Paths dataclass threaded through all loaders + commands; delete _root_patch.py | 2026-05-16 | 2e18b7e | Verified | [260516-oph-replace-root-patch-mutation-with-paths-d](./quick/260516-oph-replace-root-patch-mutation-with-paths-d/) |
| 260516-poi | Add pytest-cov dep, coverage config, and just coverage recipe; fail_under=83 from measured 85% baseline | 2026-05-16 | ad89148 | Verified | [260516-poi-add-pytest-cov-dependency-and-coverage-t](./quick/260516-poi-add-pytest-cov-dependency-and-coverage-t/) |

## Accumulated Context

### Roadmap Evolution

- Phase 2 added: Substance/Product YAML model split
- Phase 2 planned: 4 plans across 3 waves for direct YAML Substance/Product/InventoryItem split
- Phase 2 plan 01 completed: schema/data migration to substances, product formulas, inventory product refs, near/food slots, and practical ontology traits.
- Phase 2 plan 02 completed: split-model planner loaders, validation, target-path checks, product-backed refresh, and isolated refresh regression coverage.
- Phase 2 plan 03 completed: scheduler assigns inventory item ids, preserves product/component explanation context, and validates intra- vs inter-product conflict behavior.
- Phase 2 plan 04 completed: regression tests preserve Phase 1 topology boundaries while asserting split-model data shape, product inseparability, refresh isolation, goal/formula refs, conflicts, and substance-level `prefer_with`.
- Phase 2 plan 05 completed: verification gaps closed for target-mode `prefer_with` registry validation and malformed inventory entry handling.
- Phase 3 added: Product Facts + Stack-Oriented Inventory.
- Phase 4 added: Code Quality — Quick Wins (7 trivial fixes: dead code, hardcoded prefixes, noise docstrings).
- Phase 5 added: Code Quality — Critical Correctness Fixes (liar test type mismatch, 4 silent CardLoadError handlers, lock failures, schema error routing, committed-artifact test).
- Phase 6 added: Code Quality — Structural Improvements (3 write-failure data-integrity fixes, 5 unit-test coverage gaps, 4 deduplication extractions).
- Phase 7 added: Code Quality — Long-term Refactoring (cmd_plan decomposition, normalization generic, warning dispatch table, 8 missing API contracts).

### Decisions

- Plan 02-02: no legacy product-as-substance reader; universal traits load from `data/substances`.
- Plan 02-02: missing inventory product refs are fatal; product formulas without inventory refs are refresh candidates.
- Plan 02-02: product component traits aggregate onto one schedulable inventory item.
- Plan 02-03: intra-product `separate_from` conflicts are warning-only; inter-product conflicts still block co-location.
- Plan 02-03: substance-level `prefer_with` resolves to exactly one active inventory item before awarding a bonus; ambiguous targets warn and receive no bonus.
- Plan 02-04: Phase 1 regression tests assert stack topology boundaries rather than exact daily slot placement.
- Plan 02-04: refresh and negative-reference probes stay isolated in `tmp_path` or restore mutated files before returning.
- Plan 02-05: target substance checks validate local card content while resolving `prefer_with` refs through the full substance registry.
- Plan 02-05: inventory deep checks skip non-mapping supplement entries and leave malformed-entry reporting to JSON schema validation.
- Phase 3: inventory becomes top-level `stacks.daily/training/inactive`; per-item `stack` is removed.
- Phase 3: product facts such as brand and label/component amounts belong in `data/products/*.yaml`, not `data/inventory.yaml`.
- Phase 3: no separate `regimen.yaml`; keep the model to substances, products, and inventory.
- Phase 3: split generic `vitamin_b6` into `b6_pyridoxal_5_phosphate` and `b6_pyridoxine_hcl`; do not add broad B-vitamin family/class traits without an actual planner/validator/warning use.
- Plan 08-01: from_traits resolution is union (logical OR) across all namespace groups — no AND semantic. A substance is a member if ANY (namespace, slug) pair matches.
- Plan 08-01: dashboard: namespace excluded from scheduling traits — curation marker only, no slot effects.
- Plan 08-01: 6 substances had dual intake:fat_meal_required + intake:food_required; kept fat_meal_required only (more specific, food_required is redundant when fat present).
- Plan 08-02: is: and dashboard: are review-classification axes — excluded from slot scoring; the other four namespaces (intake, effect, risk, activity) drive scheduling behavior.
- Plan 08-02: from_traits resolution is union (logical OR) across entire from_traits object — no AND semantic across namespace groups.
- Plan 08-02: rename-ghost risk accepted as known limitation — operator hygiene + review-substance output is the mitigation; no schema check can distinguish stale from deliberate membership.

### Performance Metrics

- 02-substance-product-yaml-model-split / plan 02: 7min, 4 tasks, 3 files.
- 02-substance-product-yaml-model-split / plan 03: 7min, 4 tasks, 3 files.
- 02-substance-product-yaml-model-split / plan 04: 4min, 4 tasks, 3 files.
- 02-substance-product-yaml-model-split / plan 05: 15min, 3 tasks, 2 files.
- quick-260510-k5m / plan 01: 10min, 4 tasks, 10 files.
- 08-grouped-trait-shape-dashboard-membership-via-tags / plan 08-01: ~120min, 15 tasks, 235 files (schema+data+contracts+tests atomic migration).
