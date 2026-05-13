---
phase: 9
reviewers: [opencode, codex]
reviewed_at: 2026-05-13T00:00:00Z
plans_reviewed:
  - 09-01-PLAN.md
  - 09-02-PLAN.md
  - 09-03-PLAN.md
  - 09-04-PLAN.md
  - 09-05-PLAN.md
---

# Cross-AI Plan Review — Phase 9

## OpenCode Review

The five-wave sequential plan set is well-reasoned and coherent. Each wave builds a narrow vertical slice of the migration, with explicit cross-plan dependency tracking and extensive inline verification. The dual-format loader strategy correctly handles the transition window, and the 198-card migration script is appropriately defensive with its dry-run mode and idempotency guarantee. The phase goal — a hard boundary between Planner (`schedule:`) and Reviewer (`knowledge:`) ontologies with separate CLI surfaces — is fully achievable through these plans.

### Strengths

- **Explicit trust boundaries and STRIDE per plan.** Each plan carries a threat model table — unusual and valuable for a local CLI tool. The T-09-02-02 acceptance (risk-warning suspension window) is honestly documented with rationale.
- **Inline `<verify>` blocks with executable assertions.** Every task has automated verification commands, not just prose.
- **Cross-plan `must_haves` encode the integration contract.** Plan 01 explicitly states `planner check` is EXPECTED to fail after plan 01 — this frames the error state as intentional rather than a regression.
- **Migration script idempotency is verified.** Running the script twice produces `done: 0/198 cards updated`. The `--dry-run` flag plus defensive `ValueError` on residual v1 keys provides strong safety rails.
- **The `is:` namespace exception is documented inline.** Plan 04 states the Planner reads `knowledge.is:` only for class-level competes, with a comment at the call site in `_slot_is_blocked`.
- **`substance_carries` defensive guard.** Plan 03b adds `if not hasattr(substance, field_name): return False`.

### Concerns

- **[MEDIUM] v1 fallback path in `load_substance` is never removed.** RESEARCH §Pattern 1 says "After all 198 cards are migrated, the fallback is removed." But none of the 5 plans include a task to delete the v1 branch. After plan 03, the v1 path becomes dead code that silently masks schema regression.
- **[MEDIUM] `knowledge.effect`, `knowledge.risk`, `knowledge.pathway` become unvalidated free-text fields.** A typo in `knowledge.risk: [manual_reviw]` will never be caught — `planner check` exits 0, but `planner review` will emit a flag under a misspelled slug the operator never notices.
- **[LOW] Migration script writes in-place with no atomicity.** If killed mid-run, dataset is partially migrated. Recoverable via `git checkout -- data/substances/` but plans don't mention this recovery path.
- **[LOW] Plan 05's `cmd_review` re-invents dashboard membership resolution inline** instead of calling the existing `build_dashboard_review(...)` function. Maintainability concern.

### Suggestions

- Add a v1-path-removal task to plan 05 or a follow-on quick task.
- Consider a Reviewer-side slug registry for `knowledge.risk` / `knowledge.effect` as a Phase 10 item.
- Use `build_dashboard_review` in `cmd_review` instead of re-implementing dashboard membership resolution.
- Add a `--backup` flag note or `git` checkpoint note in migration script docs.

### Risk Assessment: LOW

The sequential wave structure is appropriate for an atomic migration. The dual-format loader correctly handles the transition period, and the 198-card migration benefits from idempotency and dry-run safeguards. The only structural gap is the v1 fallback path never being removed, which is a maintenance hazard but not a correctness issue.

---

## Codex Review

The plan set is directionally strong and mostly achieves Phase 9. The biggest problem is the Wave 2 dual-format loader strategy: **as written, the v2-only schema validation happens before the loader discriminator, so v1 cards will not actually reach the v1 fallback branch.** That needs to be fixed before execution. Viable after tightening the transition path.

### Strengths

- The wave ordering is basically right: registry first, code contract second, data migration third, relation mechanics fourth, command surface fifth.
- The actor split is clear: `schedule.*` feeds slot assignment; `knowledge.*` feeds review, with a narrow `knowledge.is` exception for class-level competes.
- The migration is designed as an explicit script with dry run, idempotency check, and post-migration `planner check`.
- Plan 04 correctly moves durable conflict semantics into `relations.yaml` instead of keeping hidden per-trait `separate_from`.
- Plan 05 closes the risk-warning gap by moving `risk:` surfacing to `planner review`.

### Concerns

- **[HIGH] Plan 02 dual-format loader is not actually dual-format if the schema is rewritten to v2 first.** Current `load_substance` calls `schema_errors(data, "substance", path)` before constructing `Substance`. With a v2-only `schema/substance.schema.json`, flat v1 cards fail schema validation before the `"schedule" in data` fallback can run. Same issue affects the ambiguous-card guard.
- **[HIGH] Plan 02 and Plan 03 disagree on when flat-form schema rejection is expected.** Plan 02 says it is dual-format, but also says schema rejects flat top-level fields. Those cannot both be true under the current loader shape. Clean fix: transitional schema in Plan 02, v2-only tightening in Plan 03 after migration.
- **[MEDIUM] Migration script idempotency too permissive for partial/mixed cards.** `if "schedule" in data or "knowledge" in data: return unchanged` means a partially migrated card with `schedule:` plus stale flat keys is silently skipped.
- **[MEDIUM] Plan 03 internal contradiction around non-timing `effect` slugs.** Interface says non-timing `effect` slug is a data error, but mapping says non-timing effects move to `knowledge.effect`. These cannot both be true.
- **[MEDIUM] Plan 04 promises `_class_level_competes_blocked` helper but task text describes inlining.** Prefer the named helper for testability.
- **[MEDIUM] Plan 04 test setup may drift from live `active_components` semantics.**
- **[MEDIUM] Plan 05 temp-root test instructions overcomplicate schema handling.** `SCHEMA_DIR` does not need symlinking into temp root.
- **[LOW] `REGISTERED_NAMESPACES` keeps `risk` — policy around `knowledge.risk` slugs needs to be explicit.**
- **[LOW] Executor should be told not to commit between plans 01 and 03.**

### Suggestions

- **Change Plan 02 schema strategy:** make `schema/substance.schema.json` transitional (accept v1 flat OR v2 nested via `oneOf`), then tighten to v2-only in Plan 03 after migration completes.
- Move ambiguous-card guard before schema validation if the explicit error needs to be observable.
- Make `migrate_card` reject mixed partial form (has `schedule:` plus flat keys → raise `ValueError`).
- Remove "non-timing effect slug is data error" language from Plan 03 unless that is the actual intent; non-timing effects belong under `knowledge.effect`.
- Add a post-Plan 03 schedule invariance check: compare slot assignments before and after migration.
- In Plan 05 tests, rely on the real schema directory; only create `data/` under the temp root.

### Risk Assessment: MEDIUM-HIGH before revisions, MEDIUM after

The architecture is sound and the sequential migration is the right shape. The main risk is transition mechanics — the current Plan 02 schema/loader ordering blocks the migration because v1 cards fail validation before the dual-format loader can route them.

---

## Consensus Summary

### Agreed Strengths

- **Sequential wave ordering is correct** for this atomic migration — both reviewers agree registry → contracts → data → logic → commands is the right sequence.
- **Migration script design is sound** — dry-run, idempotency, and `planner check` post-run are appropriate safeguards.
- **Threat model documentation and risk-warning suspension window** are transparent and well-documented (both reviewers noted T-09-02-02 as correctly handled).
- **`knowledge.is` exception for class-level competes** is cleanly isolated (one call site, documented inline).

### Agreed Concerns

1. **[HIGH — Codex only, but structurally important] Plan 02 schema/loader ordering breaks dual-format.** If `schema/substance.schema.json` is rewritten to v2-only in Plan 02, the `schema_errors()` call at the top of `load_substance` will reject all flat v1 cards before the `"schedule" in data` discriminator runs. The v1 fallback is unreachable. **Fix: make the schema transitional in Plan 02 (accept both shapes via `oneOf` or `anyOf`), tighten to v2-only in Plan 03 after all cards are migrated.**

2. **[MEDIUM] v1 loader fallback is never explicitly removed.** After Plan 03 migrates all 198 cards, the v1 branch becomes dead code that silently hides regressions. A cleanup task should be added (Plan 05 or follow-on).

3. **[MEDIUM] Unvalidated `knowledge.*` free-text fields.** `knowledge.risk`, `knowledge.effect`, and `knowledge.pathway` have no registry — typos pass silently. Consider a follow-on Reviewer-side slug registry (Phase 10 scope).

4. **[MEDIUM] Plan 03 migration script mixed-card handling.** A card with `schedule:` plus leftover flat keys is currently skipped silently. It should raise `ValueError` to prevent partial migrations from going undetected.

### Divergent Views

- **Overall risk rating:** OpenCode says LOW (plans achieve the goal), Codex says MEDIUM-HIGH (schema/loader ordering is broken). Codex's finding is the more precise technical observation — the schema issue is real and blocks execution if not addressed.
- **`cmd_review` dashboard logic:** OpenCode flags reuse of `build_dashboard_review`; Codex does not mention it. Minor maintainability gap only.
- **Plan 05 temp-root test strategy:** Codex says no schema symlinking needed; OpenCode flags `_write_minimal_data_root` as overcomplicated. Codex's read is likely correct — schema files are static and can be read from the real repo root.

---

## Actionable Before Execution

Priority order:

1. **[MUST] Fix Plan 02 schema strategy** — make `schema/substance.schema.json` transitional (accept v1 flat + v2 nested), tighten to v2-only in Plan 03. This is a blocker: without it, Plans 02+03 cannot work as written.
2. **[SHOULD] Add v1-fallback removal task** to Plan 05 or as a dedicated cleanup step after Plan 03.
3. **[SHOULD] Tighten `migrate_card` to reject mixed partial cards** (has `schedule:` + flat keys → `ValueError`).
4. **[NICE] Add post-Plan-03 schedule invariance check** (before vs after migration slot assignment comparison).
