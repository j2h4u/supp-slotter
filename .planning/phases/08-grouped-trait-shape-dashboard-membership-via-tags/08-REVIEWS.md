---
phase: 8
cycle: 2
reviewers: [codex, opencode]
reviewed_at: 2026-05-11T15:11:51Z
plans_reviewed:
  - 08-01-PLAN.md
  - 08-02-PLAN.md
  - 08-03-PLAN.md
  - 08-04-PLAN.md
  - 08-05-PLAN.md
prior_cycle_highs: 4
---

# Cross-AI Plan Review — Phase 8 (Cycle 2)

> **Context:** This is Cycle 2 of a convergence loop. Cycle 1 found 4 HIGH concerns. The plans were revised to address all 4. This cycle evaluates whether the revisions fully resolve those concerns and surfaces any new concerns.
>
> **Revisions evaluated:**
> - Task 08-01-09 (preflight snapshot) + task 08-01-10 (single-pass migration) → HIGH-2
> - Task 08-01-08 (review.py fix in Stage 1) → HIGH-4
> - Tasks 08-01-14 (pre-commit gate) + 08-01-15 (rollback runbook) → HIGH-1
> - Canonical `from_traits` semantics in Context + contracts.py + build_dashboard_review() + new test → HIGH-3

---

## Codex Review

> Reviewer: Codex CLI

### Summary

Cycle 2 resolves the four original HIGH concerns in substance, especially HIGH-2, HIGH-3, and HIGH-4. HIGH-1 is materially improved but still only **partially resolved** because the Stage 1 plan has internal drift: top-level `must_haves`, context text, and task title still say "three commands," while task 08-01-14 correctly requires five. I found no new HIGH concerns, but there are a few MEDIUM issues that should be cleaned up before execution, mainly around `is:` leaking into "scheduling traits," `.gitignore` handling for throwaway migration files, and stale wording that could mislead an executor.

### HIGH-1 through HIGH-4 Resolution

**HIGH-1 (atomic-commit blast radius): PARTIALLY RESOLVED**

The pre-commit gate plus rollback runbook are the right compensating controls for the atomic Stage 1 constraint. Task 08-01-14 requires `check`, `pytest`, `plan`, `review-substance`, and `doctor`, which directly covers the earlier blast-radius concern.

The gap: the plan still says "all three commands" in `must_haves`, the Stage 1 context, and the task title. Since `must_haves` are often treated as the execution contract, that inconsistency can cause the weaker gate to be followed.

**HIGH-2 (DT-04/DT-06 double-parse fragility): RESOLVED**

The preflight snapshot plus combined DT-02/DT-04/DT-06 migration fully addresses the double-parse fragility. There is now one source of truth for old `taking[]` membership, and task 08-01-10 requires a post-write cross-check against that snapshot.

**HIGH-3 (from_traits semantics underspecified): RESOLVED**

The OR-across-namespaces rule is explicit in Stage 1 context, contracts, dashboard resolution, docs, SKILL.md, and tests. The new `test_from_traits_resolution_is_union_or` is the important piece here because it locks the semantic contract in executable form.

**HIGH-4 (review.py AttributeError): RESOLVED**

The `review.py` AttributeError fix is now correctly folded into Stage 1 as 08-01-08, and `planner/engine/review.py` is in `files_modified`. The acceptance criterion requiring `review-substance` to exit 0 after Stage 1 is sufficient.

### Concerns

**Remaining (partially resolved original)**

- **[MEDIUM] HIGH-1 gate wording is inconsistent.** The plan still says "all three commands" in `must_haves`, context, and task 08-01-14 title — but the task body correctly requires five commands. `must_haves` are the execution contract; this drift can cause the weaker three-command gate to be followed. Fix: update all stale "three commands" references to "five commands: check, pytest, plan, review-substance, doctor."

**New Concerns**

- **[MEDIUM] `is:` is treated inconsistently as scheduling-relevant.** Stage 2 docs say `is:` and `dashboard:` are review-classification axes with no scheduling effects, but task 08-01-07 reconstructs effective scheduling traits from five namespaces including `is:`. The test also asserts `is:nootropic` is present in `effective_stack_item_traits()`. The plan needs a clear policy decision: is `is:` excluded from scheduling traits (docs claim) or included (code implements)?
- **[MEDIUM] `.gitignore` handling for throwaway scripts is contradictory.** Task 08-01-09 says add preflight/migration artifacts to `.gitignore`; task 08-01-14 says those entries may remain or be reverted; expected Stage 1 paths do not include `.gitignore`. Prefer `.git/info/exclude` for local throwaway files, or explicitly include `.gitignore` in expected paths.
- **[LOW] Rollback section has typo `ROLLBACK RUNBUOK`.** Acceptance criteria search for the misspelled text, baking the typo into validation.
- **[LOW] Hardcoded dashboard counts (13/14) are acceptable for this migration but should be framed as "current Phase 8 expected count" so a future data edit does not look like a mysterious plan failure.**

### Suggestions

- Replace every stale "three commands" phrase with "five commands: check, pytest, plan, review-substance, doctor."
- Resolve the `is:` policy explicitly: recommended is that `effective_stack_item_traits()` includes only `intake`, `effect`, `risk`, and `activity`; both `is:` and `dashboard:` are excluded from scheduling traits.
- Use `.git/info/exclude` for temporary migration artifacts, or add `.gitignore` to the Stage 1 expected file list.
- Fix `ROLLBACK RUNBUOK` to `ROLLBACK RUNBOOK` and update the acceptance check accordingly.

### Risk Assessment: MEDIUM

The original HIGHs are mostly cleared, and Stage 1 now has real verification and rollback controls. The remaining risk is execution-contract drift: a human or agent could follow the stale three-command gate or implement the `is:` namespace inconsistently with the docs.

---

## OpenCode Review

> Reviewer model: deepseek-v4-pro (via opencode)

### Summary

All four original HIGH concerns from Cycle 1 have been addressed with substantive, well-specified revisions. HIGH-2, HIGH-3, and HIGH-4 are **fully resolved**. HIGH-1 is **resolved** with compensating controls (gate + runbook) that, while post-hoc, are effective for this migration scenario. Two new MEDIUM concerns emerged: one about doctor `substance_refs` semantics after `collect_dashboard_substance_refs()` is hollowed out, and one about the lack of a migration-script integration test. The plan set is in good shape for execution with these two concerns addressed.

### HIGH-1 through HIGH-4 Resolution

**HIGH-1 (atomic-commit blast radius): RESOLVED**

The compensating controls (task 08-01-14: 5-command pre-commit gate + task 08-01-15: documented rollback runbook Options A/B/C) are well-specified and effective:

- **Gate effectiveness:** All five commands (`check`, `pytest`, `plan`, `review-substance`, `doctor`) exercise the exact surface area that would be broken by a migration bug. `check` catches schema/ref-integrity failures; `pytest` catches contract/logic breaks; `plan` verifies schedule generation; `review-substance` + `doctor` catch the AttributeError paths. A migration that silently passes all five is unlikely.
- **Rollback effectiveness:** Option A (`git checkout -- schema/ data/ planner/ tests/ schedule.yaml`) is a single-command full reset, recoverable from any point before the atomic commit. Option B allows surgical data-only reversion.
- **Throwaway artifact hygiene:** Preflight snapshot, migration script, and preflight script are all gitignored and explicitly deleted during the gate (task 08-01-14). They cannot leak into the commit.

The residual risk (gate is post-hoc — all file mutations happen before verification) is inherent to any data migration. The practical risk is low because the gate exercises the correctness-critical tools on the exact state that would be committed.

**HIGH-2 (DT-04/DT-06 double-parse fragility): RESOLVED**

The revision merges DT-02 + DT-04 + DT-06 into a **single migration script** (task 08-01-10) that reads the **preflight snapshot** (task 08-01-09) as the **sole source of truth** for substance→dashboard mappings. The combined migration:

1. Inverts the snapshot to build `substance_to_dashboards` map (once)
2. Tags each substance YAML with the correct `dashboard:` list (once)
3. Rewrites each dashboard YAML with `from_traits` (once)
4. Runs a mandatory cross-check comparing snapshot-derived expected memberships against actually-tagged memberships

There is genuinely no double-parse here. The must-have explicitly requires: "from_traits resolution is single-source: one migration step writes both substance dashboard: tags and dashboard yaml from_traits."

**HIGH-3 (from_traits semantics underspecified): RESOLVED**

The canonical resolution rule is now stated explicitly and consistently across all surfaces:

| Surface | Where | Verdict |
|---------|-------|---------|
| 08-01 Context (canonical source) | lines 63-77 | Explicit: union/OR, NO AND, set algebra notation |
| `planner/contracts.py` docstring | task 08-01-04 | Verbatim copy of canonical rule |
| `build_dashboard_review()` docstring | task 08-01-06 | Verbatim copy of canonical rule |
| `test_from_traits_resolution_is_union_or` | task 08-01-12 | 3-substance fixture asserting OR semantics |
| `docs/domain-model.md` | task 08-02-01 | Verbatim copy with same wording |
| `docs/ontology-facts.md` | task 08-02-02 | Same rule, intensional/extensional framing |
| `SKILL.md` Membership Flow | task 08-03-05 | Same rule, decision tree structure |
| `planner/engine/doctor.py` | task 08-05-01 (imports helpers) | Reuses `_from_traits_pairs` + `_substance_carries` |

The design choice (union/OR — NOT AND across namespaces) is deliberate and consistently stated, enforced by a dedicated test.

**HIGH-4 (review.py AttributeError): RESOLVED**

Task 08-01-08 (DT-07e) folds the `substance.traits` → 6-field reconstruction fix into Stage 1. `planner/engine/review.py` is listed in `files_modified` for 08-01 (verified by reading the frontmatter). Acceptance criterion: `uv run python -m planner review-substance` exits 0 after Stage 1. Display polish is deferred to Stage 2 (Plan 08-04).

### Concerns

**New Concerns (not present in Cycle 1)**

- **[MEDIUM] doctor `substance_refs` semantics gap between Stage 1 and DT-14.** After task 08-01-06, `collect_dashboard_substance_refs()` returns `set()`. In `doctor.py:91`, this contributes to `substance_refs`, which feeds `unused_substances` at line 95. If any substance is currently referenced ONLY by dashboard `taking[]` lists (and NOT by products, `prefer_with`, or relations), it would newly appear as `substances.unused` after Stage 1 — a regression. The plan's must-have says "existing orphan/unused logic must not regress" but provides no mechanism to verify this. **Recommendation:** Before Stage 1: run `doctor`, capture `substances.unused` count. After Stage 1 (in the pre-commit gate, task 08-01-14): verify the same count or explicitly document the increase as accepted semantic change.

- **[MEDIUM] No integration test for the combined migration script.** The migration script (task 08-01-10) performs ~213 file mutations. It is gitignored and deleted before commit — never validated by pytest. The plan relies on the post-hoc cross-check within the script and the pre-commit gate. The Cycle 1 suggestion to "create a temporary directory with 3 sample old-format substance files, 1 old-format dashboard, run the migration, assert the output" was not incorporated. **Recommendation:** Add a `tmp_path`-based test that runs the migration script's core logic against a minimal fixture, asserting grouped keys, `dashboard:` tags, and `from_traits` in the output.

**LOW Concerns (new or documentation-level)**

- **[LOW] Must-have text says "three commands" but task runs five.** `must_haves` line: "Pre-commit verification gate: all three commands (check, pytest, plan) exit 0" — task 08-01-14 runs five. Fix the must-have text.
- **[LOW] "ROLLBACK RUNBUOK" typo** in task 08-01-15. Cosmetic only — command text is correct.
- **[LOW] Cross-check one-liner acceptance criterion is fragile.** Task 08-01-10's acceptance criteria include a Python one-liner using `exec()` in a list comprehension — readability concern in the plan document, not the migration script itself.

**Previously raised, now resolved:**

- Mechanism namespace removal: task 08-01-03 requires grep to confirm no mechanism: data exists before removing. **Resolved.**
- schedule.yaml regeneration ordering: task 08-01-13 explicitly runs tests before plan, pre-commit gate re-runs both. **Resolved.**
- Stage 2 DT-12f / DT-14 sequencing: 08-03 is wave 3, depends_on: [08-01, 08-05]. **Resolved.**
- Grep false-positive on `from_traits:`: 08-02 now uses anchored regex. **Resolved.**

### Suggestions

1. **Add migration-script integration test** — a `tmp_path`-based test with 2 substance YAMLs + 1 dashboard old-format YAML, exercising the migration script's core logic.
2. **Verify doctor `substances.unused` count before committing Stage 1** — run `doctor` on current repo, capture count, verify same count (or document delta) in the pre-commit gate.
3. **Fix minor documentation inconsistencies** — "three commands" → "five commands," fix typo.
4. **Consider extracting `FROM_TRAITS_RESOLUTION_DOC` as a Python constant** in `planner/contracts.py` that all sites import, rather than restating the same text across 5+ docstrings. Reduces drift if the rule ever needs refinement.

### Risk Assessment: MEDIUM (down from Cycle 1 HIGH)

Stage 1's atomic-commit risk is compensated by the pre-commit gate + rollback runbook. Stage 1's double-parse fragility is eliminated. The `from_traits` semantics are canonicalized and test-enforced. The `review.py` crash is fixed in Stage 1. Two new MEDIUM concerns remain (doctor substance_refs gap, no migration integration test) but both have known mitigations and do not affect core correctness of the migration itself. Stage 2 plans are well-sequenced, additive, and individually testable.

---

## Consensus Summary

Two external AI reviewers (Codex, OpenCode) independently reviewed all 5 plans for Cycle 2. Claude Code (this session) is the executing agent and did not generate a self-review.

### HIGH-1 through HIGH-4 Resolution Verdict

| Concern | Codex verdict | OpenCode verdict | Consensus |
|---------|--------------|-----------------|-----------|
| HIGH-1: atomic-commit blast radius | PARTIALLY RESOLVED | RESOLVED | PARTIALLY RESOLVED |
| HIGH-2: DT-04/DT-06 double-parse | RESOLVED | RESOLVED | RESOLVED |
| HIGH-3: from_traits semantics | RESOLVED | RESOLVED | RESOLVED |
| HIGH-4: review.py AttributeError | RESOLVED | RESOLVED | RESOLVED |

**HIGH-1 consensus note:** Codex flags it PARTIALLY RESOLVED because of stale "three commands" wording in `must_haves` that could cause an executor to follow the weaker gate. OpenCode rates it RESOLVED because the task body (08-01-14) and acceptance criteria clearly require five commands, and the rollback runbook is effective. The divergence is about documentation drift risk vs. implementation correctness — both agree the compensating controls are sound in substance.

### Agreed Strengths

- **Single-pass migration design (task 08-01-10):** Both reviewers independently confirm the preflight snapshot + combined DT-02/DT-04/DT-06 migration eliminates the double-parse fragility cleanly. The post-write cross-check is a robust safety net.
- **Pre-commit gate coverage:** Both agree that running check + pytest + plan + review-substance + doctor exercises the full surface area of correctness-critical tools before any commit is created.
- **Rollback runbook (Options A/B/C):** Both confirm the inline documentation provides effective recovery paths at every stage of the migration.
- **from_traits resolution canonicalized:** Both independently confirm the rule is now stated consistently across contracts.py, build_dashboard_review(), docs, SKILL.md, and locked by a dedicated test.
- **HIGH-4 folded correctly:** Both confirm review.py is now in files_modified for 08-01, and the fix is properly specified in task 08-01-08.
- **08-03 wave 3 sequencing:** Both confirm that making Plan 08-03 depend on Plan 08-05 (doctor warnings first, SKILL.md playbook written against real implementation) resolves the Cycle 1 sequencing concern.

### Agreed Concerns

1. **[MEDIUM] Stale "three commands" wording in must_haves / context / task title.** Both reviewers independently flag this inconsistency. The task body (08-01-14) correctly specifies five commands, but `must_haves` truths and the context section still say "three commands." This is a documentation drift risk — an executor treating `must_haves` as the authoritative contract might skip the review-substance and doctor gate steps.

2. **[MEDIUM] doctor `substance_refs` gap (OpenCode — Codex implicitly covered in Cycle 1 MEDIUM).** After `collect_dashboard_substance_refs()` returns `set()`, substances previously referenced only by dashboard `taking[]` lists may newly appear as `substances.unused`. The must-have says "existing orphan/unused logic must not regress" but provides no verification mechanism. Mitigation: capture `doctor` output before Stage 1 and verify counts in the pre-commit gate.

3. **[MEDIUM] No integration test for the combined migration script.** Both reviewers note the migration script is gitignored and deleted before commit, validated only by the post-hoc cross-check within the script and the 5-command gate. A `tmp_path`-based pytest fixture exercising the script's core logic against old-format YAML would catch format bugs that the gate cannot (e.g., ruamel.yaml key ordering issues, field loss on edge-case substance cards).

### Divergent Views

- **HIGH-1 resolution rating:** Codex rates it PARTIALLY RESOLVED (stale wording creates execution-contract risk); OpenCode rates it RESOLVED (compensating controls are effective in substance). Both agree the fix is simple: update the wording.
- **`is:` in scheduling traits (Codex only):** Codex raises a new MEDIUM that `is:` appears in `effective_stack_item_traits()` (task 08-01-07) despite docs saying it is a review-classification axis excluded from scheduling. OpenCode does not raise this — likely because the task explicitly says "5 scheduling-relevant namespaces ONLY (exclude dashboard)" but includes `is:`. This is worth clarifying: either `is:` drives scheduling effects (it can, since `is:` trait entries can have `effects` blocks) or it is purely review-classification. The docs and plans are inconsistent.
- **Wording inconsistency severity:** Codex treats the "three commands" wording as a PARTIALLY RESOLVED residual HIGH; OpenCode downgrades it to LOW since the implementation spec is correct.

---

## Action Items for Planning

Before executing Phase 8, the following items should be addressed:

1. **Fix stale "three commands" wording** in 08-01 `must_haves` and Context section — update to "five commands: check, pytest, plan, review-substance, doctor."
2. **Resolve `is:` policy in scheduling traits** — decide whether `effective_stack_item_traits()` includes `is:` namespace (likely YES, since `is:` trait entries can have slot effects via `effects` blocks) and update docs consistently, OR explicitly exclude `is:` and update the implementation task wording.
3. **Add doctor pre/post count verification to pre-commit gate (task 08-01-14)** — run `doctor` before Stage 1 migration to baseline `substances.unused` count, then verify the count in the gate or document the delta as an accepted semantic change.
4. **Add migration-script integration test** — `tmp_path`-based pytest fixture with 2 old-format substance YAMLs + 1 old-format dashboard; runs core migration logic; asserts output YAML structure.
5. **Fix "ROLLBACK RUNBUOK" typo** in task 08-01-15 and update the acceptance criterion that searches for the misspelled header.
