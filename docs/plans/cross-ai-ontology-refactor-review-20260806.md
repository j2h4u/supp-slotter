# CrossAI ontology refactor review checklist

Source review run: `.adversarial-reviews/ontology-refactor-completeness-20260806/20260806T103637Z`

Purpose: preserve the CrossAI recommendations as a tracked product/architecture checklist while keeping raw review logs out of git.

## Consolidated verdict

Current branch status after the first CrossAI pass: `PARTIAL / IMPROVED`.

Current branch status after slices through `d59cff8`: `READY FOR FINAL CROSSAI REVIEW`.

The refactor has moved most scheduling/governance/vocabulary facts into ontology files, but Python is not yet only glue. The remaining work is limited to ontology leaks identified by the reviewers.

## Required slices

1. Formalize slot/effect match vocabulary. **Done.**
   - Source leak: `SlotNear` and valid effect match keys are duplicated in Python and JSON Schema.
   - Acceptance: runtime policy declares effect match dimensions and slot anchor values; Python validates from the runtime program instead of hard-coded domain sets.

2. Formalize warning presentation policy. **Done.**
   - Source leak: warning labels/actions live in Python dictionaries.
   - Acceptance: warning type labels/actions and trait action overrides are read from ontology runtime policy.
   - Must fix the emitted `intra_product_scheduling_constraint_conflict` category/action mismatch.

3. Formalize relation warning rules. **Done.**
   - Source leak: relation-warning mappings are encoded as Python/SurrealQL string literals.
   - Acceptance: relation-warning collectors are driven by ontology runtime policy rows.

## Follow-up fixes after final-slice review

- Relation schema type/severity validation now derives loaded JSON Schema enums from authored ontology/generated runtime artifacts instead of static schema literals.
- Runtime `relation_warning_rules.filter_value` references are checked by the ontology compiler against authored assertion values for `assertion_kind` and `semantic_family`.
- Relation type metadata now explicitly labels `directional` and selector forms as assertion/review metadata, not hidden scheduler placement policy.
- The two worst ontology artifact harness debts were moved off subprocess/full copied-repository paths; targeted checks now use direct in-process seams.

## Out of scope for this pass

- No TypeDB implementation.
- No dose/personalized clinical model.
- No test harness refactor.
- No new fat-meal slot model unless current data/rules require it for lossless extraction.

## Final gate

After the slices are complete:

1. Run repo-approved `just` gates.
2. Check this document's acceptance bullets against code.
3. Repeat CrossAI review with DeepSeek, GLM, and Claude Opus.
