---
phase: quick-260512-h6p
plan: 01
subsystem: relations-ontology
tags: [relations, severity, antagonizes, ontology, warnings]
dependency_graph:
  requires: []
  provides: [Relation.severity, collect_antagonizing_relations, antagonizes_substance_present]
  affects: [planner/contracts.py, planner/cards/relations.py, planner/engine/plan.py, planner/io.py, planner/cards/warnings.py, schema/relations.schema.json, data/relations.yaml, docs/ontology-facts.md]
tech_stack:
  added: []
  patterns: [conditional-dict-key-insertion, AND-activeness-predicate-for-antagonizes]
key_files:
  created: []
  modified:
    - planner/contracts.py
    - planner/cards/relations.py
    - planner/engine/plan.py
    - planner/io.py
    - planner/cards/warnings.py
    - schema/relations.schema.json
    - data/relations.yaml
    - docs/ontology-facts.md
    - tests/test_phase_02.py
    - tests/test_phase_03.py
decisions:
  - "Severity flows through humanize_warning to schedule.yaml output (conditional key insertion — absent when None, present when set)."
  - "antagonizes warning fires on AND-of-both-endpoints-active, not the XOR/missing pattern used by balance/supports."
  - "Severity sweep applied per guidance: medium on Zn↔Cu/B12↔B9 balance; medium on chronic-depletion antagonizes (PPI/Metformin→B12, Ginkgo→CYP); high on Methotrexate→B9 and Pyridoxine HCl→Levodopa; medium on VitE/VitA→K1/K2; D3↔Mg supports entry as critical."
metrics:
  duration: ~25min
  completed: "2026-05-12T07:33:57Z"
  tasks: 3
  files: 10
---

# Phase quick-260512-h6p Plan 01: Refactor Relations Ontology — Add Severity + Wire Antagonizes Summary

**One-liner:** Optional severity enum on Relation dataclass + schema + YAML sweep; `collect_antagonizing_relations` wired into plan.py emitting `antagonizes_substance_present` when both endpoints active; D3↔Mg supports edge encoded as critical.

## Tasks Completed

| # | Task | Commit | Files |
|---|------|--------|-------|
| 1 | Severity field — dataclass, schema, loader, YAML data | 71db111 | contracts.py, cards/relations.py, schema/relations.schema.json, data/relations.yaml |
| 2 | Wire antagonizes warnings — collector, plan.py, labels, actions, test | 3d4ab20 | cards/relations.py, engine/plan.py, io.py, cards/warnings.py, tests/test_phase_02.py, tests/test_phase_03.py |
| 3 | Sync docs/ontology-facts.md with new ontology capabilities | 62fec09 | docs/ontology-facts.md |

## What Was Built

**Task 1 — Severity field:**
- `Severity = Literal["critical","high","medium","low"]` alias added to `contracts.py` alongside `RelationType`.
- `Relation.severity: Severity | None = None` added as the final dataclass field.
- `schema/relations.schema.json` declares `severity` as an optional enum property under `$defs.relationList.items.properties` (required because `additionalProperties: false`).
- `load_global_relations` reads `relation.get("severity")` and passes it to the `Relation` constructor.
- `_append_missing_relation_warning` includes `"severity"` key in the warning dict only when `relation.severity is not None` — existing serialization shape unchanged for severity-less relations.
- `data/relations.yaml`: D3↔Mg `supports` entry added (source=Magnesium, target=Vitamin D3, severity=critical). Severity sweep: medium on Zn↔Cu and B12↔B9 balance; medium on five chronic-depletion antagonizes (Metformin/PPIs/H2→B12, Ginkgo→CYP); high on Methotrexate→B9 and Pyridoxine HCl→Levodopa; medium on VitE/VitA→K1/K2 antagonizes.

**Task 2 — Antagonizes wiring:**
- `collect_antagonizing_relations(substances, active_substances, global_relations)` in `planner/cards/relations.py`: iterates antagonizes relations, fires when `relation_endpoint_is_active(source) AND relation_endpoint_is_active(target)`; dedup key `(source_key, "antagonizes", target_key)`; severity included only when set.
- Wired into `planner/engine/plan.py` after the existing `collect_missing_support_relations` loop.
- `planner/io.py` `WARNING_CATEGORY_LABELS`: `"antagonizes_substance_present": "Active antagonist pairing"`.
- `planner/cards/warnings.py` `_ACTION_BY_TYPE`: `"antagonizes_substance_present"` action added.
- `humanize_warning` updated to carry `severity` through to the output dict when present (previously discarded).
- New test `test_antagonizes_warning_fires_and_severity_flows_through` in `tests/test_phase_02.py`: builds fixture with two antagonist substances both active, verifies category and severity in output.
- Updated `test_balance_relation_warns_when_related_substance_missing` in `tests/test_phase_03.py`: snapshot now includes `severity: medium` for Zn↔Cu (correctly reflects Task 1 sweep).

**Task 3 — Doc sync:**
- Encoding Policy `antagonizes` bullet updated: now describes live warning emission (`antagonizes_substance_present`) with note that slot placement is still unchanged.
- New `severity` bullet in Encoding Policy: describes optional field, closed enum, bias-unset policy, flows to schedule.yaml.
- Current Takeaways: antagonizes framing changed from "review-only" to dual-output (schedule warning + substance-card review).
- Ontology Improvement Queue: "Functional opposition versus slot separation" row updated to reflect warnings now exist.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed stale test snapshot in test_phase_03.py**
- **Found during:** Task 2 full suite run
- **Issue:** `test_balance_relation_warns_when_related_substance_missing` asserted the old Zn↔Cu warning shape without `severity: medium`; Task 1 sweep added severity to that relation, so humanized output now includes it.
- **Fix:** Added `"severity": "medium"` to the expected dict in test_phase_03.py.
- **Files modified:** tests/test_phase_03.py
- **Commit:** 3d4ab20

**2. [Rule 2 - Missing functionality] Propagate severity through humanize_warning**
- **Found during:** Task 2 implementation
- **Issue:** `humanize_warning` builds output from scratch and did not carry the `severity` key through — so severity set on the raw warning would silently disappear from `schedule.yaml`. The plan required "assert the warning carries severity" in the humanized output.
- **Fix:** Added conditional `out["severity"] = severity` in `humanize_warning` when `warning.get("severity") is not None`.
- **Files modified:** planner/cards/warnings.py
- **Commit:** 3d4ab20

## Known Stubs

None.

## Threat Flags

None — no new network endpoints, auth paths, or schema changes at trust boundaries.

## Self-Check: PASSED

- `planner/contracts.py` — exists, contains `Severity =` and `severity: Severity | None = None`
- `planner/cards/relations.py` — exists, contains `collect_antagonizing_relations`
- `planner/engine/plan.py` — exists, contains `collect_antagonizing_relations` call
- `planner/io.py` — exists, contains `antagonizes_substance_present`
- `planner/cards/warnings.py` — exists, contains `antagonizes_substance_present`
- `schema/relations.schema.json` — exists, contains `severity`
- `data/relations.yaml` — exists, contains `severity: critical`
- `docs/ontology-facts.md` — exists, contains `severity` and `antagonizes_substance_present`
- `tests/test_phase_02.py` — exists, contains `antagonizes_substance_present`
- Commits 71db111, 3d4ab20, 62fec09 all present in git log
- 96 tests pass, 0 ruff errors, 0 pyright errors/warnings
