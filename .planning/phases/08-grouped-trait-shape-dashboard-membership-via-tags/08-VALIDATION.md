---
phase: 8
slug: grouped-trait-shape-dashboard-membership-via-tags
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-05-11
---

# Phase 8 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest |
| **Config file** | `pyproject.toml` |
| **Quick run command** | `uv run pytest tests/ -x -q` |
| **Full suite command** | `uv run pytest tests/` |
| **Estimated runtime** | ~15 seconds |

---

## Sampling Rate

- **After every task commit:** Run `uv run pytest tests/ -x -q`
- **After every plan wave:** Run `uv run pytest tests/`
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 15 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| DT-01 | schema | 1 | DT-01 | — | Grouped substance schema validates; flat form rejected | unit | `uv run pytest tests/test_schemas.py -x -q` | ❌ W0 | ⬜ pending |
| DT-05 | schema | 1 | DT-05 | — | Dashboard from_traits schema validates; taking form rejected | unit | `uv run pytest tests/test_schemas.py -x -q` | ❌ W0 | ⬜ pending |
| DT-03 | traits | 1 | DT-03 | — | `check_traits()` passes with is:/dashboard: namespaces | unit | `uv run pytest tests/ -x -q` | ✅ | ⬜ pending |
| DT-07 | contracts | 1 | DT-07 | — | Substance dataclass has per-namespace fields; loader reads grouped YAML | unit | `uv run pytest tests/test_scheduling_units.py tests/test_schemas.py -x -q` | ❌ W0 | ⬜ pending |
| DT-02 | migration | 1 | DT-02 | — | All 200 substance cards pass schema validation after migration | integration | `uv run python -m planner check` | ✅ | ⬜ pending |
| DT-04 | migration | 1 | DT-04 | — | dashboard: tags added to substance cards; resolved membership matches baseline taking[] counts | integration | `uv run python -m planner check` | ✅ | ⬜ pending |
| DT-06 | dashboards | 1 | DT-06 | — | 13 dashboard files use from_traits; vasodilation_no_pathway deleted; all pass schema | integration | `uv run python -m planner check` | ✅ | ⬜ pending |
| DT-08 | ref-integrity | 1 | DT-08 | — | check errors on unknown namespace slug in substance card and dashboard from_traits | unit | `uv run pytest tests/ -x -q` | ❌ W0 | ⬜ pending |
| DT-09 | schedule | 1 | DT-09 | — | schedule.yaml benefits/risks output matches pre-refactor baseline for 13 clusters | integration | `uv run python -m planner plan && uv run pytest tests/test_phase_01.py -x -q` | ✅ | ⬜ pending |
| DT-10 | tests | 1 | DT-10 | — | Full test suite passes on migrated codebase | integration | `uv run pytest tests/` | ✅ | ⬜ pending |
| DT-11 | docs | 2 | DT-11 | — | domain-model.md and ontology-facts.md updated sections verified by review | manual | — | ✅ | ⬜ pending |
| DT-12 | skill | 2 | DT-12 | — | SKILL.md sections updated; no stale class: references remain | manual | `grep -rn "class:" SKILL.md` | ✅ | ⬜ pending |
| DT-13 | review-sub | 2 | DT-13 | — | review-substance shows all namespace groups; dashboard: section visible; readable_traits() excludes is: and dashboard: | unit | `uv run pytest tests/test_phase_03.py -x -q` | ✅ | ⬜ pending |
| DT-14 | doctor | 2 | DT-14 | — | doctor emits 4 warning classes with actionable resolution text; clean repo shows no false positives | integration | `uv run python -m planner doctor` | ✅ | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_schemas.py` — add test cases for grouped substance schema (accept grouped, reject flat, enforce maxItems:1 on intake), and from_traits dashboard schema
- [ ] `tests/test_scheduling_units.py` — update `make_substance()` fixture to use new per-namespace fields; add tests for `effective_stack_item_traits()` with grouped substance
- [ ] New tests for ref-integrity: unknown slug in substance `is:`, `intake:`, `dashboard:` fails `check_substances()`; unknown slug in dashboard `from_traits` fails `check_dashboards()`

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| SKILL.md no stale class: namespace references | DT-12 | Doc review; no automated content check | `grep -n "class:" SKILL.md` must show zero hits for `class:*` trait format; `class=` CSS or similar non-trait uses are acceptable |
| docs/domain-model.md trait section reads correctly under grouped model | DT-11 | Prose quality check | Read updated Trait Ontology section; verify each namespace described with cardinality rules |
| doctor output readable and actionable for each DT-14 warning class | DT-14 | Requires artificially broken data state to trigger each warning | Manually introduce each warning condition (orphan trait, unused trait, slug mismatch, empty cluster), run doctor, verify message is prescriptive |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 15s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
