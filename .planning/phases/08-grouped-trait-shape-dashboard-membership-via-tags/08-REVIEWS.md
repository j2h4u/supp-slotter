---
phase: 8
reviewers: [codex, opencode]
reviewed_at: 2026-05-11T14:38:33Z
plans_reviewed:
  - 08-01-PLAN.md
  - 08-02-PLAN.md
  - 08-03-PLAN.md
  - 08-04-PLAN.md
  - 08-05-PLAN.md
---

# Cross-AI Plan Review — Phase 8

## Codex Review

### Summary

The plan set is mostly coherent and matches the phase goal: Stage 1 handles the risky schema/data/contract pivot atomically, while Stage 2 keeps docs, agent guidance, review output, and lifecycle warnings additive. The main risks are migration correctness and semantic ambiguity: the plans need a stricter preflight/snapshot step for the current flat traits and dashboard `taking[]` data, a clear rule for removed/unknown namespaces like `mechanism`, and an explicit definition of `from_traits` matching semantics before code and docs spread slightly different interpretations.

### PLAN 08-01: Stage 1 — Core Schema + Data + Contracts

#### Strengths

- Correctly treats Stage 1 as one atomic commit. That is the right boundary because schema, loaders, YAML data, checks, and generated output are mutually dependent.
- Good load-bearing order: schema/contract changes before data rewrite, then checks/tests, then generated `schedule.yaml`.
- Correctly calls out the Python `is` keyword issue via `Substance.is_`.
- Excludes `dashboard:` from scheduling traits, preserving the locked scoring contract.
- Adds FK-like reference integrity, which is exactly the right compensating control for file-based YAML data.

#### Concerns

- **[HIGH]** No explicit preflight inventory step before migration. The plan should first snapshot all existing trait prefixes, all dashboard `taking[]` memberships, duplicate trait entries, and unknown prefixes. This matters especially because `mechanism` is removed from `REGISTERED_NAMESPACES`; the plan says remove it but does not say whether existing `mechanism:*` data is absent, migrated, rejected, or intentionally dropped.
- **[HIGH]** DT-04 depends on current dashboard `taking[]` lists, but DT-06 deletes/replaces those files. The plan should require building and preserving a migration map before any dashboard YAML rewrite.
- **[HIGH]** `from_traits` matching semantics are underspecified. Is membership `AND` across namespaces and `OR` within a namespace? Or any listed trait? The roadmap says grouped `from_traits`, but implementation details say "matching namespace/slug pairs," which is not enough for future `is:` projections.
- **[MEDIUM]** Dashboard schema should constrain `from_traits` keys to registered namespaces and values to arrays of slugs. Otherwise malformed namespace groups can slip past schema and only fail later.
- **[MEDIUM]** The plan says `collect_dashboard_substance_refs()` returns empty, but doctor/ref tracking must verify it does not silently remove useful references from orphan detection. This is called out in research, but should be a must-have.
- **[MEDIUM]** Generated `schedule.yaml` is a committed artifact and prior work found `pytest` can restore or alter it. The plan should require running `plan` after tests, not before, and verifying the final git diff contains the regenerated schedule.
- **[LOW]** "All 200 substance YAML files" should be expressed as "all current files under `data/substances/*.yaml`" so the plan does not bake in a stale count.

#### Suggestions

- Add DT-00 preflight: dump current trait prefix counts, dashboard `taking[]` membership map, dashboard file count, and all unknown/removed prefixes; fail migration if any prefix has no explicit policy.
- Define `from_traits` resolution explicitly: recommended rule is `AND` across namespace groups, `OR` within each group. For the Stage 1 dashboard-tag migration, every dashboard can still use `{dashboard: [slug]}`.
- Add migration idempotence checks: no `traits:` keys remain in substances, no `class:` prefixes remain, no `taking:` keys remain in dashboards, no `vasodilation_no_pathway` references remain.
- Preserve deterministic YAML formatting: stable namespace order, sorted/deduped slugs, stable file ordering. This will make review possible across ~200 files.
- Add a focused verification command after full migration: count dashboards in `schedule.yaml`, assert exactly 13, assert `vascular_health` contains the former `vasodilation_no_pathway` members, and assert the deleted dashboard is absent.

#### Risk Assessment: HIGH

The design is sound, but the migration has a large data blast radius and several silent-failure modes: dropped namespaces, lost dashboard membership, ambiguous `from_traits` semantics, and generated artifact churn.

---

### PLAN 08-02: Stage 2a — Documentation

#### Strengths

- Correctly depends on Stage 1, so docs describe the real post-migration shape.
- Covers the main operator-facing concepts: grouped namespaces, dashboard membership, intensional vs extensional semantics.
- Includes a grep guard against stale flat-form examples.

#### Concerns

- **[MEDIUM]** `grep -rn 'traits:' docs/` may produce false positives because `from_traits:` legitimately contains `traits:` as a substring. The check should distinguish stale `traits:` YAML keys from valid `from_traits`.
- **[MEDIUM]** Docs need to explicitly mention that `dashboard:` traits are classification/membership metadata and do not influence scheduling.
- **[LOW]** README "may be no-op" is fine, but the plan should still require a checked result, not an assumed no-op.

#### Suggestions

- Use a more precise stale-form check: match line-start YAML keys like `^\s+traits:` or examples containing namespace-prefixed list items.
- Add one doc example for dashboard membership by tag and one for projection by `is:`, even if Stage 1 uses only `dashboard:` tags.
- Include cardinality examples for `intake` and `activity` max-one behavior.

#### Risk Assessment: LOW to MEDIUM

The doc scope is appropriate, but stale-example detection needs refinement.

---

### PLAN 08-03: Stage 2b — SKILL.md Agent Entrypoint

#### Strengths

- Good agentic focus: updates workflows, minimal shapes, validation contract, and membership flow.
- Removes hardcoded class-marker enumeration, which should reduce drift.
- Adds doctor warning playbook where an operator/agent is likely to need it.

#### Concerns

- **[MEDIUM]** DT-12f documents DT-14 warning classes before DT-14 is implemented if Stage 2 tasks run in parallel. Since 08-03 and 08-05 both depend only on 08-01, the docs may claim warnings exist before they do.
- **[MEDIUM]** `.planning/PROJECT.md` update is mixed into a SKILL.md docs task. That may be fine, but it is planning metadata, not agent-entrypoint content.
- **[LOW]** "Which namespace?" guidance needs to avoid implying every new dashboard requires a new `dashboard:` tag. Some dashboards may be legitimate `is:` projections.

#### Suggestions

- Either make 08-03 depend on 08-05 for the Doctor Warning Playbook, or phrase that section as "planned warning classes" until DT-14 lands.
- Add a validation command list to SKILL.md: `check`, `doctor`, `plan`, and test command.

#### Risk Assessment: MEDIUM

Content is valuable, but sequencing with DT-14 needs tightening.

---

### PLAN 08-04: Stage 2c — review-substance Audit

#### Strengths

- Correctly updates `class:` to `is:`.
- Correctly recognizes `is:` and `dashboard:` are classification axes, not scheduling drivers.
- Requires review output to surface all six groups.

#### Concerns

- **[HIGH]** The must-haves appear internally inconsistent: `readable_traits()` excludes `dashboard:`, but review-substance output must show `dashboard:` namespace entries with descriptions. This can work only if `readable_traits()` is specifically for scheduling-driver display and another path renders grouped namespace details. The plan should state that boundary clearly.
- **[MEDIUM]** "Unknown slugs surface in unknown section" conflicts with Stage 1 reference-integrity errors if unknown slugs prevent normal loading/checking. The review command needs a tolerant parse path if it is supposed to inspect invalid cards.
- **[LOW]** May need fixture updates if review output tests already exist.

#### Suggestions

- Rename or document `readable_traits()` policy as "schedule-readable traits" if it excludes classification namespaces.
- Add one golden-output test for `review-substance` showing grouped `is`, `intake`, `effect`, `risk`, `activity`, and `dashboard`.
- Decide whether `review-substance` is strict or diagnostic on unknown slugs.

#### Risk Assessment: MEDIUM

Display policy is currently muddled and could hide dashboard tags from the one command meant to audit them.

---

### PLAN 08-05: Stage 2d — Doctor Lifecycle Warnings

#### Strengths

- The four warning classes cover the right lifecycle failures for tag-based membership.
- Actionable "Resolution:" text is appropriate for an operator-maintained YAML system.
- Clean-exit on healthy repo is the right usability contract.

#### Concerns

- **[HIGH]** `dashboard.slug_mismatch` overlaps with Stage 1 hard reference-integrity errors. If a dashboard YAML references a missing dashboard trait, should `check` fail, `doctor` warn, or both? The boundary needs to be explicit.
- **[MEDIUM]** `dashboard.orphan_registration` and `dashboard.slug_mismatch` can overlap for "trait exists but no dashboard YAML exists." The plan should define deduplication or precedence.
- **[MEDIUM]** `dashboard.empty_cluster` depends on the same `from_traits` matching semantics that Stage 1 currently underspecifies.
- **[MEDIUM]** `collect_orphans()` returning dict keys for warning classes may affect existing consumers. Must preserve existing keys.
- **[LOW]** Whether warnings cause nonzero exit or remain advisory is unspecified.

#### Suggestions

- Define check-vs-doctor boundary: `planner check` fails on invalid references; `doctor` warns on valid-but-suspicious lifecycle states.
- Add tests for each warning class using minimal temp YAML fixtures.
- Add warning precedence rules.
- Ensure doctor uses the same grouped membership resolver as Stage 1.

#### Risk Assessment: MEDIUM

Warning set is useful, but overlap with hard validation and unclear resolver semantics could create noisy diagnostics.

---

### Cross-Plan Recommendations (Codex)

- Add a Stage 1 preflight artifact or test that captures current dashboard `taking[]` membership before mutation.
- Define `from_traits` semantics once and reuse it in loader, dashboard review, schedule generation, docs, SKILL.md, and doctor.
- Treat removed namespaces explicitly. `class -> is` is clear; `mechanism` removal needs a verified policy.
- Make final Stage 1 verification order: migrate → tests/check → regenerate `schedule.yaml` → inspect generated artifact → commit.
- Add a data migration test that runs against a temporary sample with duplicate traits, `class:*`, dashboard membership tags, max-one violations, and an unknown namespace.
- Keep Stage 2 additive but avoid documenting doctor warnings as available before DT-14 has landed.

**Overall risk: HIGH for Stage 1, MEDIUM for the full phase.** The architecture is aligned with the goal, but the core migration touches every substance card, every dashboard, schema contracts, validation, generated output, and review tooling. With a preflight map, explicit matching semantics, and final artifact verification, the plan becomes solid enough to execute.

---

## OpenCode Review

> Reviewer model: deepseek-v4-pro (via opencode)

### Summary

The plan set is a well-structured multi-stage migration. Stage 1's atomic-commit strategy for ~215 files is the dominant risk. The design decisions (6 namespace groups, `DashboardMember` removal, `from_traits` intensional membership, reference integrity in `planner check`) are well-reasoned and align with the architecture's locked decisions.

### PLAN 08-01: Stage 1 — Core Schema + Data + Contracts

#### Strengths

- **Load-bearing task order is correct** — schema before contracts, contracts before YAML migration, migration before integrity checks. The dependency chain DT-01→DT-05→DT-03→DT-07→DT-02/DT-04/DT-06→DT-08→DT-10→DT-09 is sound.
- **Python keyword handling** explicitly called out (`is_` field name vs YAML key `is:`) — prevents a common footgun.
- **`dashboard:` exclusion from scheduling** is correctly identified in `effective_stack_item_traits()` — trait namespaces with no `effects` blocks should not influence slot scores.
- **DT-03 + DT-06 slug design** — dashboard slugs defined in `traits.yaml` first, then substances tagged, then dashboard YAMLs reference the same slugs. Well-sequenced.
- **Reference-integrity errors (DT-08)** are prescriptive, like FK constraints.
- **`vasodilation_no_pathway` deletion** is justified (strict 5/5 subset) and data-losing operations are explicitly called out.

#### Concerns

- **[HIGH]** Atomic-commit scope is too large (~215 files in one transaction). If the migration script has a bug, reverting means losing ALL changes. Consider: migrate into a temp directory first, validate with `check`, then `rsync` atomically into place. Or split into two commits: (1) contracts + schemas + traits.yaml, (2) YAML migration + integrity checks.
- **[HIGH]** DT-04 depends on DT-06 knowledge but appears before it in task order. To tag substances with `dashboard:slug`, you need to read the current dashboard `taking[]` lists. DT-06 maps old `taking[]` → new `from_traits`. If DT-04 runs before DT-06, the migration script must independently parse old-format dashboard YAMLs to build the tag map — two independent systems must agree on the substance→dashboard mapping. Consider merging DT-04 + DT-06 into a single migration step.
- **[MEDIUM]** Doctor produces false positives after Stage 1. `collect_dashboard_substance_refs()` returns `set()` after refactor. Doctor's `substance_refs` loses the dashboard contribution. Substances tagged with `dashboard:vascular_health` but not referenced by products/prefer_with/relations may appear in `substances.unused`. Add a must-have: `uv run python -m planner doctor` produces acceptable output.
- **[MEDIUM]** `review.py` accesses `set(substance.traits)` — broken by refactor silently. After DT-07, `Substance` has no `.traits` field. `review-substance` crashes with `AttributeError`. DT-13 (Plan 08-04) addresses this but only in Stage 2. If the fix is trivial (reconstruct set from 6 fields), fold it into DT-07.
- **[MEDIUM]** `schedule.yaml` uses `readable_traits()` for `review_tags` — after DT-07, this function receives `is:antioxidant` instead of `class:antioxidant`. The `startswith("class:")` check silently passes through, so `is:*` traits would appear in review_tags where they didn't before. DT-13 fixes this in Stage 2 — not a correctness bug (only display), but schedule output regresses during Stage 1.
- **[LOW]** `from_traits` as `dict[str, tuple[str,...]]` allows `from_traits: { intake: [food_preferred], effect: [energy_like] }` — structural flexibility not restricted by schema. The plan says all 13 dashboards use `from_traits: { dashboard: [<slug>] }` but schema doesn't enforce it.
- **[LOW]** `build_dashboard_review()` rewrite is not described in detail. This function drives 2 out of 8 schedule.yaml sections — verify correctness after migration.
- **[LOW]** `data/traits.yaml` — `dashboard:` namespace traits may need `label`, `description`, `applies_when` per schema. Dashboard traits are marker-only; `applies_when` would be empty/N/A. Verify this passes schema.
- **[LOW]** Migration script idempotency — running DT-02 migration twice on a partially-migrated file would produce broken YAML. Add guard clauses.

#### Suggestions

- **Split Stage 1 into 2 commits:** Commit A (DT-01, DT-03, DT-05, DT-07) = contracts + schemas + Python code. Commit B = YAML migration + regeneration. Commit A schemas can accept BOTH old and new format temporarily.
- **Add a rollback script** — document that `git checkout data/` restores. Include this as an explicit step.
- **Fold DT-04 into DT-06** — a single migration script that reads old-format dashboards, builds the `substance_id → dashboard_slug` map, tags substances, and writes new-format dashboards in one pass. Eliminates double-parse fragility.
- **Add explicit migration-script test** — create a temporary directory with 3 sample old-format substance files, 1 old-format dashboard, run the migration, assert the output.

#### Risk Assessment: MEDIUM-HIGH

Justification: The atomic-commit scope (~215 files) amplifies single-point-of-failure risk. The migration script is the most error-prone component. The dependency between DT-04 and DT-06 creates a fragile double-parse path. However, the task ordering is logically correct and the must-haves are comprehensive. If the migration script is well-tested on a sample, risk drops to MEDIUM.

---

### PLAN 08-02: Stage 2a — Documentation

#### Strengths

- "Decided: Not Solving — rename-ghost" entry documents the naming change for future archaeology.
- "Intensional vs extensional from_traits semantics note" is critical for understanding the membership model.
- Testable must-haves — grep checks eliminate stale examples.

#### Concerns

- **[LOW]** Trait Ontology section needs to explicitly describe `dashboard:` as "review-classification only, no scheduling effects" — this differs from the other 5 namespaces that drive slot assignment.

#### Risk Assessment: LOW

Documentation-only, testable, no code impact.

---

### PLAN 08-03: Stage 2b — SKILL.md Agent Entrypoint

#### Strengths

- "Register in traits.yaml FIRST, then create yaml, then tag substances" workflow — enforces reference integrity at the agent workflow level. Most important procedural addition.
- Membership Flow subsection traces both directions of the tag→dashboard relationship.
- Doctor Warning Playbook documents WHEN to run doctor (4 triggers) and per-warning resolution.
- No ASCII art — good discipline for agent-processable documentation.

#### Concerns

- **[MEDIUM]** DT-12f depends on DT-14 content but both are Wave 2. If DT-14 warning messages change during implementation, SKILL.md must be updated to match. Consider: implement DT-14 first, then write DT-12f.
- **[LOW]** "Which namespace?" decision block is constrained to 3 lines — may be too tight for clear disambiguation.

#### Suggestions

- Re-sequence: implement Plan 08-05 (DT-14) before Plan 08-03 (DT-12), so Doctor Warning Playbook is written against real warning messages.
- Add a "What NOT to put in dashboard:" section — prevents agents from adding scheduling traits to the `dashboard:` namespace.

#### Risk Assessment: LOW

Documentation-only. Cross-plan dependency on DT-14 is manageable if sequenced correctly.

---

### PLAN 08-04: Stage 2c — review-substance Audit

#### Strengths

- Clear separation of concerns — `readable_traits()` for schedule display vs `grouped_trait_defs()` + `print_trait_details()` for review-substance.
- Explicit policy comment ("is: and dashboard: are review-classification axes, not scheduling drivers").

#### Concerns

- **[MEDIUM]** DT-13b must-haves say review-substance shows `dashboard:` entries with descriptions, but for dashboard traits these fields may be sparse (just slug name, no `applies_when`/`effects`). The must-have is achievable but output may look thin.
- **[MEDIUM]** `review.py` line 79 `set(substance.traits)` broke in Stage 1. This crashes `review-substance` with `AttributeError` until DT-13 fixes it. Either fold the fix into DT-07 or document the regression explicitly.

#### Suggestions

- Move the `review.py` line 79 fix into DT-07 — changing `set(substance.traits)` to reconstruct from 6 fields is trivial and should be part of the Python contracts change.
- Consider dashboard trait `description` values — if 13 dashboard traits have meaningful descriptions, review-substance output will be richer.

#### Risk Assessment: LOW-MEDIUM

The `review-substance` regression during Stage 1 is the main concern. If the `set(substance.traits)` fix is folded into DT-07, risk drops to LOW.

---

### PLAN 08-05: Stage 2d — Doctor Lifecycle Warnings

#### Strengths

- 4 warning classes are orthogonal and complementary: orphan_registration (zombie trait), unused_trait (dangling reference), slug_mismatch (naming inconsistency), empty_cluster (empty dashboard).
- Actionable resolution text with A/B/C options — explicitly required.
- doctor exits 0 on clean repo is a clear verification criterion.

#### Concerns

- **[MEDIUM]** No check for `from_traits` slug ≠ filename convention. If `vascular_health.yaml` has `from_traits: { dashboard: [wrong_name] }`, the 4 warnings catch this indirectly through slug_mismatch + unused_trait triangulation but there's no direct "dashboard yaml should self-reference its own slug" warning.
- **[MEDIUM]** `collect_orphans()` integration adds 4 new section keys. Existing test assertions on doctor output (in test_phase_03.py) may fail if they check exact section names or counts. Plan doesn't mention updating these tests in DT-14.
- **[LOW]** `substance.traits` access in doctor.py line 55 breaks after DT-07. DT-07d covers this — verify implementation.
- **[LOW]** O(S × D) scan for warning detection (200 substances × 13 dashboards = 2600 checks) is negligible now.

#### Suggestions

- Add a self-reference convention check — verify each dashboard YAML's `from_traits[dashboard]` contains the dashboard's own slug.
- Update existing doctor tests in the must-haves — add "existing doctor tests pass" to verification criteria.

#### Risk Assessment: MEDIUM

New logic with 4 complementary warnings. Test impact is not fully scoped. Warning classes are well-defined and must-haves are testable.

---

### Cross-Plan Concerns (OpenCode)

**`substance.traits` attribute disappears in Stage 1 — multiple files break:**
These files access `substance.traits` directly and must change at DT-07 time:
- `planner/engine/_scheduling.py:50` — `effective_stack_item_traits()`
- `planner/engine/doctor.py:55` — `collect_orphans()` trait_refs collection
- `planner/engine/review.py:79` — `cmd_review_substance()`

Plan 08-01's DT-07d covers doctor and scheduling. But `review.py` isn't in the "Files modified" list for Plan 08-01. Either it's an oversight or `review-substance` is intentionally broken until DT-13. **Recommendation:** Add `review.py` to Plan 08-01's modified files list.

**Test fixture impact understated:**
The plan says "Add 6 new schema + ref-integrity tests" but doesn't quantify the fixture update scope. Current tests that reference `traits: [class:...]` span `test_phase_01.py`, `test_phase_02.py`, `test_phase_03.py`, and `test_scheduling_units.py`. If trait IDs change from `class:antioxidant` to `is:antioxidant`, scoring tests need updates too. At least 10-15 test functions likely need fixture updates.

**The atomic-commit premise is fragile:**
An alternative staged approach: (1) update schemas to accept BOTH old and new format, (2) update Python contracts with backward-compatible loader, (3) migrate YAML files, (4) remove old format. This adds 3 commits but eliminates single-point-of-failure risk.

---

## Consensus Summary

Two external AI reviewers (Codex, OpenCode) independently reviewed all 5 plans. Claude Code (this session) is the executing agent and did not generate a self-review.

### Agreed Strengths

- **Correct task ordering** — both reviewers confirm the DT-01→DT-05→DT-03→DT-07→DT-02/DT-04/DT-06→DT-08→DT-10→DT-09 chain is load-bearing and sound.
- **Python `is_` keyword handling** — both call this out as important and correctly handled.
- **`dashboard:` exclusion from scheduling** — both agree this is correctly placed in `effective_stack_item_traits()`.
- **Reference-integrity errors (DT-08)** — both praise the FK-constraint-style error approach.
- **`vasodilation_no_pathway` deletion** — both confirm it is justified and correctly called out.
- **Stage 2 additive structure** — both approve of docs/SKILL.md/doctor being separate additive commits.
- **Doctor warning actionable text** — both agree "Resolution:" with A/B/C options is the right UX for agentic sessions.
- **Membership Flow and Doctor Warning Playbook in SKILL.md** — both independently flag these as high-value additions.

### Agreed Concerns

1. **[HIGH] Atomic-commit blast radius** — both reviewers independently flag that ~215 files in one transaction creates a single-point-of-failure risk. Preferred mitigation: split into contracts/schemas commit + YAML migration commit, or run migration into temp directory first.

2. **[HIGH] DT-04 / DT-06 double-parse fragility** — both note that DT-04 (tagging substances from `taking[]`) and DT-06 (rewriting dashboard YAMLs from `taking[]`) independently parse the same source data. If they diverge, dashboard memberships will be silently wrong. Recommended fix: merge DT-04 + DT-06 into a single migration script.

3. **[HIGH] `from_traits` matching semantics underspecified** — both reviewers note the resolution rule is ambiguous. Codex formulates it as "AND across namespaces, OR within each group." This needs to be stated once and reused in loader, doctor, schedule generation, and docs.

4. **[MEDIUM] `review.py` `substance.traits` access breaks silently in Stage 1** — both reviewers identify that `review-substance` will crash with `AttributeError` after DT-07. The fix is trivial (reconstruct from 6 fields) and should be folded into DT-07, not deferred to DT-13.

5. **[MEDIUM] Doctor false positives after `collect_dashboard_substance_refs()` returns empty** — both reviewers note that substances previously referenced by dashboards may appear as "unused" in doctor output after Stage 1. Should be documented or verified as acceptable.

6. **[MEDIUM] Stage 2 sequencing: 08-05 before 08-03** — both reviewers independently recommend implementing DT-14 (doctor warnings) before writing DT-12f (Doctor Warning Playbook in SKILL.md), so SKILL.md describes actual implemented messages not plan descriptions.

7. **[MEDIUM] Test fixture scope understated** — both note the test impact covers more than 6 new tests; existing fixtures across test_phase_01.py, test_phase_02.py, test_phase_03.py, test_scheduling_units.py likely all need updating when trait IDs change from `class:*` to `is:*`.

### Divergent Views

- **Atomic-commit strategy:** Codex frames it as "the right boundary" while still flagging scale risk; OpenCode is more forceful about splitting into 2-3 commits. The core concern is shared; the preferred remedy differs. Operator should decide based on tolerance for migration script bugs.
- **`from_traits` flexibility in schema:** OpenCode flags that `dict[str, tuple[str,...]]` allows arbitrary namespace combinations (e.g., `intake:` + `effect:` in one dashboard) — should schema restrict to `dashboard:` only for Stage 1? Codex doesn't explicitly raise this. Worth considering but YAGNI if all 13 dashboards use only `dashboard:` projection.
- **Plan 08-04 severity:** OpenCode rates the `readable_traits` / `review-substance` concern as MEDIUM overall while Codex rates it HIGH specifically for the must-have inconsistency (exclude dashboard from readable_traits vs show dashboard in review-substance). Both agree the fix is clear: document that these are two separate rendering paths.

---

## Action Items for Planning

Before executing Phase 8, the following items should be addressed in the plans:

1. **Add explicit `from_traits` resolution rule** to 08-01 context: "OR within each namespace group, AND across namespace groups" — one statement, linked everywhere.
2. **Merge DT-04 + DT-06** into a single migration step that reads old-format dashboards once, builds substance→dashboard map, tags substances, and rewrites dashboards.
3. **Add `review.py` to 08-01 files_modified** and include the `substance.traits` → 6-field reconstruction fix in DT-07d.
4. **Add preflight must-have to 08-01**: verify no `mechanism:*` data exists in substances or dashboards before removing the namespace.
5. **Add doctor acceptable-output must-have to 08-01**: `uv run python -m planner doctor` runs without crash (not necessarily clean exit given Stage 2 warnings not yet implemented).
6. **Tighten grep checks in 08-02**: use `grep -rn '^\s*traits:' docs/` not `'traits:'` to avoid `from_traits:` false positives.
7. **Clarify 08-04 dual rendering paths**: `readable_traits()` = schedule display (excludes `is:` and `dashboard:`); `grouped_trait_defs()` + `print_trait_details()` = review-substance display (includes all namespaces). State this boundary in must-haves.
8. **Re-sequence Stage 2**: execute 08-05 (doctor warnings) before 08-03 (SKILL.md), then write Doctor Warning Playbook against implemented messages.
