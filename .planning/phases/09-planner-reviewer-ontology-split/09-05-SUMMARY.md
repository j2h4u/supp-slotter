---
phase: 09-planner-reviewer-ontology-split
plan: "05"
subsystem: planner-reviewer-split
tags: [cmd_review, reviewer, planner, cli, schema, v2-only, cleanup]
dependency_graph:
  requires: [09-04]
  provides: [cmd_review, planner-review-cli, v2-only-schema]
  affects: [planner/engine/review.py, planner/engine/audit.py, planner/__main__.py, schema/substance.schema.json, SKILL.md]
tech_stack:
  added: []
  patterns: [redirect_stdout-capture, build_dashboard_review-reuse, v2-only-schema]
key_files:
  created:
    - tests/test_review_command.py
  modified:
    - planner/engine/review.py
    - planner/engine/audit.py
    - planner/engine/__init__.py
    - planner/__main__.py
    - planner/cards/substance.py
    - schema/substance.schema.json
    - tests/test_schemas.py
    - SKILL.md
decisions:
  - "cmd_review captures output via redirect_stdout when data_root is set (matches cmd_review_substance pattern)"
  - "Dashboard summary in cmd_review reuses build_dashboard_review (per-09-REVIEWS.md NICE-4); dashboards missing benefit+risk blocks are omitted (matches cmd_show behavior)"
  - "AuditResult.by_kind and .relations_by_status kept as empty dicts for backward compat; tests migrated to cmd_review"
  - "v1 fallback removal and schema tightening committed together (per-09-REVIEWS.md SHOULD-fix 2) to prevent dead-code regression"
  - "schema/substance.schema.json: oneOf and $defs dropped; additionalProperties: false at top level is the sole gate against flat-form keys"
metrics:
  duration: ~60min
  completed: "2026-05-13T14:44:29Z"
  tasks: 4
  files: 8
---

# Phase 9 Plan 05: Planner/Reviewer CLI Split + v1 Schema Cleanup Summary

New `cmd_review` Reviewer entrypoint covering concerns, relations, risk flags, pathway memberships, and dashboard membership; `cmd_audit` slimmed to cleanup candidates; v1 loader fallback and transitional schema both removed in the same commit.

## What Was Built

### Task 1: cmd_review implementation

`planner/engine/review.py` now contains two distinct commands:

- `cmd_review_substance` — unchanged single-card trait checklist
- `cmd_review` — new full active-stack Reviewer output with five sections:
  1. Concerns (safety / data_quality / model_gap) — moved from cmd_audit
  2. Relations (both_active / missing_source / missing_target / neither_active) — moved from cmd_audit
  3. Risk flags — NEW: iterates active substances, groups by `knowledge.risk:` slug
  4. Pathway memberships — NEW: groups active substances by `knowledge.pathway:` slug
  5. Dashboard summary — NEW: REUSES `build_dashboard_review` (per-09-REVIEWS.md NICE-4)

The `_build_active_substance_ids` and `_classify_relations` helpers were moved from `audit.py` to `review.py`. `cmd_audit` was slimmed to cleanup candidates + optional `--full` deep card-quality checks; `by_kind` and `relations_by_status` fields in `AuditResult` kept as empty dicts for backward compat.

### Risk-flag surfacing restored

Risk-flag surfacing was suspended in plan 02 when the pre-Phase-9 scheduler path was refactored. `cmd_review`'s Risk flags section is the new canonical surface — it iterates `active_substances` and groups by `knowledge.risk:` slug, outputting each carrying substance name under its slug group.

### Task 2: CLI dispatch + SKILL.md

`planner/__main__.py` registers `review` as a new subcommand:
```
python -m planner review   # concerns, relations, risk flags, pathways
```

`SKILL.md` updated:
- v2 nested substance YAML shape (`schedule:` / `knowledge:`) in Minimal YAML Shapes
- "Which namespace?" section expanded with scheduling vs reviewer axes + `pathway:`
- "Which actor?" decision rule: slug affects slot assignment → `schedule:`; otherwise → `knowledge:`
- Review Warning Playbook added: when to run `planner review`, risk-flag surfacing guidance
- Audit Warning Playbook updated to reflect slimmed audit scope
- Advisory split documented: review (concerns/relations/risk/pathway) vs audit (cleanup)

### Task 3: tests/test_review_command.py

Five new tests:
1. `test_cmd_review_exits_zero` — live data, exit_code == 0
2. `test_cmd_review_output_has_section_headers` — all four section headers present
3. `test_cmd_review_surfaces_risk_manual_review` — minimal temp data root with one active substance carrying `knowledge.risk: [manual_review]`, verified in Risk flags output
4. `test_cmd_audit_does_not_emit_concerns_or_relations` — audit boundary enforced
5. `test_cmd_review_does_not_emit_cleanup_candidates` — review boundary enforced

### Task 4 (cleanup): v1 loader fallback removed + schema tightened to v2-only

Per-09-REVIEWS.md MEDIUM-2 + SHOULD-fix 2. Both changes in one commit to prevent dead-code regression:

- `schema/substance.schema.json`: `oneOf` and `$defs.v1_flat` deleted; `v2_nested` lifted to top level with `additionalProperties: false` — flat-form namespace keys now rejected by schema
- `planner/cards/substance.py load_substance`: `"schedule" in data` discriminator removed, ambiguous-card guard removed, v1 flat branch removed — unconditional v2 path
- `planner/cards/substance.py check_substances`: `if "schedule" in substance` / else v1 branch removed — v2-only scheduling + reviewer namespace validation
- `tests/test_schemas.py`: deleted `test_substance_schema_accepts_flat_form_during_transition`; added `test_substance_schema_rejects_flat_form` and `test_substance_schema_rejects_flat_is_risk_etc` (covers all 7 v1 flat namespace keys)

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] test_cli_help_exposes_simple_agent_commands expected old subcommand list**
- Found during: Task 3 (just check)
- Issue: Test asserted `{check,audit,find,review-substance}` but CLI now has `{check,audit,find,review,review-substance}`
- Fix: Updated assertion to include `review`
- Files modified: tests/test_phase_02.py
- Commit: 02359e4

**2. [Rule 1 - Bug] test_balance_relation_warns_when_related_substance_missing used cmd_audit for relations**
- Found during: Task 3 (just check)
- Issue: Relations data moved from cmd_audit to cmd_review; test used `audit_result.relations_by_status` which is now empty
- Fix: Migrated test to use `cmd_review(data_root=...)` and assert on output text
- Files modified: tests/test_phase_03.py
- Commit: 02359e4

**3. [Rule 1 - Bug] test_support_relation_warns_when_supporter_missing used cmd_audit for relations**
- Found during: Task 3 (just check)
- Issue: Same as above
- Fix: Migrated to cmd_review output text assertions
- Files modified: tests/test_phase_03.py
- Commit: 02359e4

**4. [Rule 1 - Bug] test_check_substances_rejects_unknown_namespace_slug used flat-form card**
- Found during: Task 4 (just check)
- Issue: Test used `{"is": ["unknown_slug"]}` at top level — rejected by v2-only schema before trait check runs; also `is:` is reviewer-only (not trait-validated). Changed to `schedule: {intake: ["unknown_slug"]}` so trait check fires on a scheduling namespace.
- Files modified: tests/test_schemas.py
- Commit: 28325af

## Pending Follow-on Tasks

1. Delete `scripts/migrate_substance_cards.py` after operator confirms no further migration runs are needed.
2. Optional: rename the default `plan`/`show` command to `schedule` per docs/ontology-v2.md §Commands (RESEARCH §Open Questions A5 — confirm with operator before renaming).

## Self-Check: PASSED
