---
phase: 01
slug: training-stacks-goals-ontology
status: verified
nyquist_compliant: true
wave_0_complete: true
created: 2026-05-05
verified_at: 2026-05-05T16:59:39Z
---

# Phase 01 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest via `uv run --with pytest --with pyyaml` |
| **Config file** | none — command-scoped test dependencies |
| **Quick run command** | `uv run --with pytest --with pyyaml pytest tests/test_phase_01.py -q` |
| **Full suite command** | `uv run --with pytest --with pyyaml pytest tests/test_phase_01.py -q` |
| **Estimated runtime** | ~2 seconds |

---

## Sampling Rate

- **After every task commit:** Run `uv run --with pytest --with pyyaml pytest tests/test_phase_01.py -q`
- **After every plan wave:** Run `uv run --with pytest --with pyyaml pytest tests/test_phase_01.py -q`
- **Before `$gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** ~2 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 01-01-01 | 01-01 | 1 | TRAIN-01 | T-01-01 | Slot schema/topology is valid and training slots exist. | pytest | `pytest tests/test_phase_01.py::test_training_slots_and_activity_traits -q` | yes | green |
| 01-01-02 | 01-01 | 1 | TRAIN-03 | T-01-04 | Activity namespace has exact asymmetric scoring definitions. | pytest | `pytest tests/test_phase_01.py::test_training_slots_and_activity_traits -q` | yes | green |
| 01-01-03 | 01-01 | 1 | TRAIN-02 | T-01-01 / T-01-05 | Inventory has no stale `active` keys and exact stack histogram. | pytest | `pytest tests/test_phase_01.py::test_inventory_stack_partition -q` | yes | green |
| 01-02-01 | 01-02 | 1 | TRAIN-03 | T-01-04 | Four training product cards carry expected `activity:*` traits and no `goals` field. | pytest | `pytest tests/test_phase_01.py::test_training_products_have_expected_activity_traits -q` | yes | green |
| 01-02-02 | 01-02 | 1 | GOAL-01 / GOAL-02 | T-01-03 | Goal cards exist with expected members and member shapes. | pytest | `pytest tests/test_phase_01.py::test_goal_cards_have_expected_members -q` | yes | green |
| 01-02-03 | 01-02 | 1 | GOAL-01 / GOAL-02 | T-01-03 | Mitochondrial goal card supports one substance ref plus name-only candidates. | pytest | `pytest tests/test_phase_01.py::test_goal_cards_have_expected_members -q` | yes | green |
| 01-03-01 | 01-03 | 1 | TRAIN-03 / TRAIN-02 | T-01-05 | `planner.py check` accepts activity namespace and stack inventory. | pytest | `pytest tests/test_phase_01.py::test_phase_01_check_passes -q` | yes | green |
| 01-03-02 | 01-03 | 1 | TRAIN-02 | T-01-05 | `planner.py plan` produces a stack-partitioned schedule. | pytest | `pytest tests/test_phase_01.py::test_plan_generates_stack_partitioned_schedule -q` | yes | green |
| 01-03-03 | 01-03 | 1 | GOAL-03 | T-01-03 / T-01-07 | Goal ref validator rejects missing product cards without crashing. | pytest | `pytest tests/test_phase_01.py::test_goal_ref_validator_rejects_missing_product_and_restores_file -q` | yes | green |
| 01-04-01 | 01-04 | 2 | TRAIN-01 / TRAIN-02 / TRAIN-03 / GOAL-01 / GOAL-02 | T-01-09 | End-to-end check, plan, and topology assertions are repeatable. | pytest | `pytest tests/test_phase_01.py -q` | yes | green |
| 01-04-02 | 01-04 | 2 | GOAL-03 | T-01-08 / T-01-09 | Negative ref test restores the goal card and proves failure path. | pytest | `pytest tests/test_phase_01.py::test_goal_ref_validator_rejects_missing_product_and_restores_file -q` | yes | green |

---

## Wave 0 Requirements

Existing infrastructure now covers all phase requirements:

- [x] `tests/test_phase_01.py` — repeatable checks for TRAIN-01, TRAIN-02, TRAIN-03, GOAL-01, GOAL-02, GOAL-03
- [x] command-scoped pytest runner via `uv run --with pytest --with pyyaml`

---

## Manual-Only Verifications

All phase behaviors have automated verification.

---

## Validation Audit 2026-05-05

| Metric | Count |
|--------|-------|
| Gaps found | 6 |
| Resolved | 6 |
| Escalated | 0 |

Generated test file:

- `tests/test_phase_01.py`

Latest run:

- `uv run --with pytest --with pyyaml pytest tests/test_phase_01.py -q`
- Result: `7 passed in 1.09s`

---

## Validation Sign-Off

- [x] All tasks have automated verify coverage or Wave 0 dependencies
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all MISSING references
- [x] No watch-mode flags
- [x] Feedback latency < 2 seconds
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** approved 2026-05-05
