---
phase: 8
cycle: 3
reviewers: [codex, opencode]
reviewed_at: 2026-05-11T15:23:22Z
plans_reviewed:
  - 08-01-PLAN.md
  - 08-02-PLAN.md
  - 08-03-PLAN.md
  - 08-04-PLAN.md
  - 08-05-PLAN.md
prior_cycle_highs: 1
---

# Cross-AI Plan Review — Phase 8 (Cycle 3)

> **Context:** This is Cycle 3 of a convergence loop.
> - Cycle 1 found 4 HIGH concerns (all addressed in replan commit 1d633b0).
> - Cycle 2 found 1 PARTIALLY RESOLVED HIGH: "three commands" wording in must_haves/task title should be "five commands." Fixed in commit 4eb6f2c — both occurrences updated.
>
> **PRIMARY task this cycle:** Confirm whether the HIGH-1 "three commands" → "five commands" fix is now FULLY RESOLVED. Both reviewers independently verified the current plan text.

---

## Codex Review

> Reviewer: Codex CLI

### Summary

HIGH-1 is fully resolved for the two requested locations: the Stage 1 `must_haves` truth and task `08-01-14` title both now say five commands. I found no remaining HIGH blockers. The plan is broadly ready for execution, but I would clean up three medium risks first: stale context wording that still describes only `check + pytest + plan`, the unresolved doctor `substance_refs` regression check, and the inconsistent treatment of `is:` as both "scheduling-relevant" and "not a scheduling driver."

### HIGH-1 Resolution Verification

**Verdict: FULLY RESOLVED.**

Evidence from current `08-01-PLAN.md`:

- Must-have truth says: `"Pre-commit verification gate: all five commands (check, pytest, plan, review-substance, doctor) exit 0 before the atomic commit is created"`
- Task title says: `<title>Pre-commit verification gate — run all five commands; ALL must exit 0 before commit</title>`

Task body also reinforces it: `ALL five commands MUST exit 0. If any fails, DO NOT commit.`

### Strengths

- Stage 1 now has the right blast-radius gate: `check`, `pytest`, `plan`, `review-substance`, and `doctor`.
- The migration design is much safer than the earlier split: one snapshot source, one combined migration step, then snapshot cross-checks.
- `from_traits` semantics are explicit and test-backed as union / logical OR.
- The `review-substance` AttributeError fix is correctly moved into Stage 1, avoiding a broken intermediate CLI state.
- Stage 2 dependencies are sensible: SKILL.md waits for doctor warning wording, which avoids documentation drift.
- `review-substance` is correctly specified as tolerant diagnostic output, while `check` owns hard FK enforcement.

### Concerns

- **[MEDIUM] Stage 1 context still describes a weaker gate.** The main HIGH-1 locations are fixed, but `08-01-PLAN.md` context still says the gate "runs check + pytest + plan before any commit." That no longer matches the actual five-command gate and could mislead an executor skimming the context.

- **[MEDIUM] `is:` remains internally inconsistent.** Stage 1 says `effective_stack_item_traits()` reconstructs from "5 scheduling-relevant namespaces" and explicitly includes `is:`. Stage 2 says `is:*` is an "intrinsic category" and "not a scheduling driver." If `is:` traits never carry slot effects, including them may be harmless, but the wording and test expectation lock in a confusing model.

- **[MEDIUM] Doctor `substance_refs` regression is still not directly guarded.** Stage 1 requires doctor not to regress, but the plan still only gates `doctor` exit 0 / no crash, allowing warning-count drift. If dashboard `taking[]` references used to contribute to "used substance" accounting, removing them can change `substances.unused` without failing the gate.

- **[MEDIUM] `.gitignore` handling remains contradictory.** Task 08-01-09 says append throwaway paths to `.gitignore`; task 08-01-14 says `.gitignore` entries may remain or be reverted; final allowed status paths do not include `.gitignore`. Use `.git/info/exclude` or explicitly include `.gitignore` in expected changes.

- **[LOW] Stage 1 must-have says existing orphan/unused logic must not regress, but no concrete comparison or accepted-delta note is provided to make this enforceable.**

### Suggestions

- Update the context sentence to: "runs check + pytest + plan + review-substance + doctor before any commit."
- Decide one of these for `is:`:
  - Treat `is:` as classification-only and exclude it from `effective_stack_item_traits()`.
  - Keep it in the flat trait set, but stop calling that set "scheduling-relevant" and document that only traits with effects influence slot matching.
- Add a pre/post doctor baseline in Stage 1: capture current `substances.unused` and orphan counts before migration, then assert same counts after migration or document intentional deltas.
- Replace `.gitignore` edits for temporary scripts/snapshots with `.git/info/exclude`, since these are local migration artifacts.
- Add one integration-style migration test or verification script that checks: no flat `traits:`, all grouped namespaces load, dashboard memberships match snapshot, and `plan` emits 13 dashboard clusters.

### Risk Assessment: MEDIUM

The prior HIGH wording issue is fixed where it matters most, and the plan has strong verification coverage. The remaining risks are mostly execution-drift and semantic-regression risks around doctor accounting and `is:` namespace treatment. Ready after the small wording cleanup plus one explicit doctor baseline check.

---

## OpenCode Review

> Reviewer model: via opencode

### Summary

Cycle 3 successfully resolves the lone remaining HIGH-1 "three commands" wording drift. The `must_haves` truth and task 08-01-14 title now both correctly state "five commands." The plan set is substantively ready for execution. However, three MEDIUM concerns from Cycle 2 remain unaddressed (`is:` scheduling policy contradiction, doctor `substance_refs` verification gap, and missing migration integration test), plus one LOW cosmetic typo persists.

### HIGH-1 Resolution Verification

**Verdict: FULLY RESOLVED**

Both instances now read "five commands":

**(a) `must_haves` truth (line 51):**
> `"Pre-commit verification gate: all five commands (check, pytest, plan, review-substance, doctor) exit 0 before the atomic commit is created"`

**(b) Task 08-01-14 title (line 578):**
> `<title>Pre-commit verification gate — run all five commands; ALL must exit 0 before commit</title>`

The task body (line 587) also reinforces: `"ALL five commands MUST exit 0. If any fails, DO NOT commit."` Acceptance criteria enumerate all five commands individually. No stale "three commands" references remain in the plan text.

### Strengths

- **HIGH-1 fully resolved.** Both the `must_haves` contract surface and the task title now agree on "five commands." Execution-contract drift is eliminated.
- **Single-pass migration design remains solid.** The preflight snapshot + combined DT-02/DT-04/DT-06 migration (task 08-01-10) with post-write cross-check is a robust single-source-of-truth approach.
- **`from_traits` semantics are canonicalized across all surfaces.** The union/OR rule appears verbatim in the plan context, contracts.py docstring, `build_dashboard_review()` docstring, docs, SKILL.md, and is enforced by `test_from_traits_resolution_is_union_or`.
- **`review.py` AttributeError fix correctly folded into Stage 1** (task 08-01-08), with display polish cleanly separated into Stage 2 (Plan 08-04).
- **08-03 wave 3 dependency on 08-05** is correctly specified — DT-12f Doctor Warning Playbook must read actual DT-14 message wording.
- **Pre-commit gate coverage is comprehensive.** All five commands exercise the full surface area of correctness-critical tools.

### Concerns

**MEDIUM (carried from Cycle 2, still unaddressed)**

- **[MEDIUM] `is:` scheduling policy contradiction between Stage 1 impl and Stage 2 docs.** Task 08-01-07 explicitly includes `is:` in `effective_stack_item_traits()` (5 scheduling-relevant namespaces, excluding only `dashboard:`). The test `test_dashboard_excluded_from_scheduling_traits` asserts "is:nootropic IS in the returned trait set." This is correct — `is:` trait entries can have `effects` blocks that drive slot scoring. However, 08-02-PLAN (task 08-02-01) claims: `"is: — review-classification axis only, NO scheduling effects (excluded from slot scoring)"`. This is factually wrong for `is:`. The docs plan instructs the executor to write incorrect documentation. **Impact:** If 08-02 executes as written, `docs/domain-model.md` will contradict the system's actual behavior.

- **[MEDIUM] Doctor `substance_refs` verification gap still unaddressed.** After Stage 1 (task 08-01-06), `collect_dashboard_substance_refs()` returns `set()`. Substances previously referenced only by dashboard `taking[]` lists would newly appear as `substances.unused`. The must-have says "existing orphan/unused logic must not regress" but the pre-commit gate (task 08-01-14) has no baseline-vs-post comparison for `substances.unused` count.

- **[MEDIUM] No migration-script integration test.** The combined migration script (task 08-01-10) performs ~213 file mutations, is gitignored, and deleted before commit. It is validated only by the in-script cross-check and the 5-command gate — both post-hoc. A format bug (e.g., ruamel.yaml key ordering edge case, field loss on edge-case substance cards) could pass all five gate commands and only surface much later.

**LOW**

- **[LOW] `ROLLBACK RUNBUOK` typo persists.** Flagged in Cycle 1 and Cycle 2, still present. Cosmetic only — the command text in the runbook is correct.

### Suggestions

1. **Fix `is:` policy in 08-02-PLAN before execution.** Change the `is:` namespace description from "review-classification axis only, NO scheduling effects" to match the implementation: `is:` trait entries can carry `effects:` blocks in traits.yaml and ARE included in scheduling traits. Only `dashboard:` is fully excluded from scheduling.
2. **Add doctor `substances.unused` baseline to pre-commit gate (task 08-01-14).** Before any Stage 1 mutations, run `planner doctor`, capture `substances.unused` count. After the migration (in the gate), verify the same count or document the expected delta.
3. **Add migration-script integration test.** A `tmp_path`-based pytest with 2 old-format substance YAMLs + 1 old-format dashboard, exercising the migration script's core logic, asserting grouped keys, `dashboard:` tags, and `from_traits:` in output.
4. **Fix `ROLLBACK RUNBUOK` typo** (lines 658 and 696) → `ROLLBACK RUNBOOK`.
5. **Extract `FROM_TRAITS_RESOLUTION_DOC` as a Python constant** in `planner/contracts.py`, rather than restating the same resolution rule across 5+ docstrings.

### Risk Assessment: MEDIUM (down from Cycle 2 MEDIUM, down from Cycle 1 HIGH)

The execution-blocking concern (stale "three commands" wording creating contract drift) is fully resolved. The remaining MEDIUM concerns are all addressable with one-line plan edits (`is:` policy fix in 08-02) or minor gate additions (doctor baseline, migration test). None affect core migration correctness. The plan set is ready for execution once the three MEDIUM items are addressed.

---

## Consensus Summary

Two external AI reviewers (Codex, OpenCode) independently reviewed all 5 plans for Cycle 3. Claude Code (this session) is the executing agent and did not generate a self-review.

### HIGH-1 Resolution Verdict

| Concern | Codex verdict | OpenCode verdict | Consensus |
|---------|--------------|-----------------|-----------|
| HIGH-1: "three commands" gate wording | **FULLY RESOLVED** | **FULLY RESOLVED** | **FULLY RESOLVED** |

Both reviewers independently confirmed that the Cycle 2 fix (commit 4eb6f2c) updated both required locations:
- `must_haves` truth: "all five commands (check, pytest, plan, review-substance, doctor)"
- Task 08-01-14 title: "run all five commands"

No stale "three commands" references remain anywhere in the plan text.

### Prior HIGH Concerns — Status Summary

| Cycle | Concern | Status at Cycle 3 |
|-------|---------|-------------------|
| HIGH-1 | Atomic-commit blast radius / gate wording | **FULLY RESOLVED** (both reviewers) |
| HIGH-2 | DT-04/DT-06 double-parse fragility | **FULLY RESOLVED** (Cycle 2) |
| HIGH-3 | from_traits semantics underspecified | **FULLY RESOLVED** (Cycle 2) |
| HIGH-4 | review.py AttributeError | **FULLY RESOLVED** (Cycle 2) |

**No HIGH concerns remain unresolved.**

### Agreed Strengths

- **HIGH-1 wording is fully fixed.** Execution-contract drift eliminated — must_haves and task title are in agreement.
- **Single-pass migration design.** Both reviewers confirm the preflight snapshot + combined DT-02/DT-04/DT-06 migration is sound.
- **from_traits canonicalized.** Union/OR rule is consistent across all surfaces and locked by test.
- **Stage 2 sequencing.** 08-03 correctly depends on 08-05 to avoid DT-12f / DT-14 documentation drift.
- **Gate coverage.** Five commands exercise the full correctness surface area.

### Agreed Concerns (MEDIUM — carried from Cycle 2)

1. **[MEDIUM] `is:` scheduling policy contradiction.** Both reviewers flag that Stage 1 includes `is:` in `effective_stack_item_traits()` (correct — `is:` entries can have `effects` blocks) while Stage 2 docs plan (08-02-PLAN task 08-02-01) instructs the executor to document `is:` as "review-classification axis only, NO scheduling effects." This is factually wrong and will produce incorrect documentation if executed as written. **Fix:** Update the `is:` description in 08-02-PLAN to reflect the actual implementation: `is:` CAN carry scheduling effects via `effects:` blocks; only `dashboard:` is definitively excluded from scheduling.

2. **[MEDIUM] Doctor `substance_refs` verification gap.** The pre-commit gate asserts `doctor` exits 0 but does not baseline `substances.unused` before migration. Substances previously counted only via dashboard `taking[]` references could silently shift to `unused` status. **Fix:** Add a pre-Stage-1 doctor snapshot of `substances.unused` count, and verify same count (or document intentional delta) in the gate.

3. **[MEDIUM] No migration-script integration test.** The combined migration script is gitignored and deleted before commit — validated only post-hoc. A `tmp_path`-based pytest fixture with old-format fixture YAMLs would catch format-level migration bugs that the 5-command gate cannot. **Fix:** Add one integration-style test covering the migration script's core logic.

### Divergent Views

- **Context wording drift (Codex only):** Codex additionally flags a MEDIUM that the Stage 1 context narrative still says "runs check + pytest + plan before any commit" (a weaker gate description) even though the must_haves and task title are now correct. OpenCode does not separately flag this since the authoritative must_haves/task body are correct. Both agree the fix is a simple one-line prose update.

- **`.gitignore` handling (Codex only):** Codex flags a MEDIUM that tasks 08-01-09 and 08-01-14 give contradictory instructions for `.gitignore`. OpenCode did not independently raise this. Both would agree `.git/info/exclude` is cleaner for local throwaway artifacts.

### Open Action Items for Next Cycle / Execution

Before executing Phase 8, the following items remain outstanding:

1. **[MEDIUM] Fix `is:` scheduling policy wording in 08-02-PLAN** — task 08-02-01 should say `is:` CAN carry scheduling effects; only `dashboard:` is definitively excluded. This prevents the executor from writing incorrect documentation.
2. **[MEDIUM] Add doctor `substances.unused` baseline to pre-commit gate** — capture count before Stage 1, verify in gate.
3. **[MEDIUM] Add migration-script integration test** — `tmp_path`-based pytest against old-format fixture YAMLs.
4. **[LOW] Fix `ROLLBACK RUNBUOK` typo** in task 08-01-15 acceptance criteria (lines 658 and 696).
5. **[LOW] Update Stage 1 context narrative** gate description from "check + pytest + plan" to "check + pytest + plan + review-substance + doctor" (Codex-only concern, but easy fix).
