---
phase: 9
slug: planner-reviewer-ontology-split
status: draft
nyquist_compliant: true
wave_0_complete: true
created: 2026-05-13
---

# Phase 9 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest |
| **Config file** | `pyproject.toml` |
| **Quick run command** | `just check` |
| **Full suite command** | `just check` |
| **Estimated runtime** | ~10 seconds |

---

## Sampling Rate

- **After every task commit:** Run `just check`
- **After every plan wave:** Run `just check`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 15 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 9-01-01 | 01 | 1 | schema | — | N/A | unit | `just check` | ❌ W0 | ⬜ pending |
| 9-01-02 | 01 | 1 | migration | — | N/A | unit | `just check` | ❌ W0 | ⬜ pending |
| 9-02-01 | 02 | 2 | loader | — | N/A | unit | `just check` | ❌ W0 | ⬜ pending |
| 9-03-01 | 03 | 3 | planner | — | N/A | unit | `just check` | ❌ W0 | ⬜ pending |
| 9-04-01 | 04 | 4 | reviewer | — | N/A | unit | `just check` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

Tests are authored inline at the wave where they are needed (no dedicated Wave-0 plan):

- [x] `tests/test_schemas.py` — schema acceptance/rejection tests for v2 substance shape and traits.yaml namespaces (Plan 03, Task 3)
- [x] `tests/test_scheduling_units.py` — scheduler isolation tests: reads `schedule.*` only, `knowledge.is_` for competes (Plan 03, Task 3)
- [x] `tests/test_review_command.py` — `planner review` command behavioral tests (Plan 05, Task 3)

*All tasks have self-contained automated verify blocks — no MISSING references exist.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| `planner review` output readability | Phase 9 goal | Human judgment on advisory text format | Run `planner review` on a test schedule; verify warnings are meaningful |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 15s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
