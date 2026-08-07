# CrossAI ontology refactor review checklist

Source review runs:

- Initial completeness review: `.adversarial-reviews/ontology-refactor-completeness-20260806/20260806T103637Z`
- Final-slice adversarial review: `.adversarial-reviews/ontology-refactor-final-20260807/20260806T230909Z`

Purpose: preserve the CrossAI recommendations as a tracked product/architecture checklist while keeping raw review logs out of git.

## Consolidated verdict

Current branch status after the first CrossAI pass: `PARTIAL / IMPROVED`.

Current branch status after slices through `95ca70c`: `READY FOR FINAL CROSSAI REVIEW`.

The refactor has moved scheduling/governance/vocabulary/relation-review facts into ontology runtime policy and generated runtime artifacts. Python remains responsible for glue mechanics: loading cards, building the in-memory read model, executing searches, evaluating declared rules, rendering output, and failing closed when generated runtime policy is incomplete.

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

4. Formalize relation review status vocabulary. **Done.**
   - Source leak: relation review grouping and descriptions were hard-coded in `relations.py` / `review_render.py`.
   - Acceptance: `relation_review_statuses` are authored in ontology runtime policy; rendering and grouping read status order/descriptions from `RuntimeProgram`.

5. Formalize relation presence semantics. **Done.**
   - Source leak: `both_active`, `missing_target`, `missing_source`, and `neither_active` were minted/mapped/described in Python.
   - Acceptance: `relation_presence_statuses` author the endpoint truth table, active-side mapping, default review status, and descriptions.

6. Formalize broad endpoint presentation policy. **Done.**
   - Source leak: `broad_endpoint_kinds = {"trait"}` and broad endpoint audit threshold lived in Python.
   - Acceptance: `relation_endpoint_policies` author `entity` vs `term`, broad endpoint behavior, match-detail display, audit member limit, and label.

7. Formalize `prefer_with` resolver contract. **Done.**
   - Source leak: `prefer_with` target resolution, same-slot pair behavior, and ambiguous warning message lived in Python.
   - Acceptance: `prefer_with_policy` authors source field, target resolution rule, pair mode, ambiguous warning type, and ambiguous message.

8. Formalize Python glue warning emitters. **Done.**
   - Source leak: `PYTHON_CREATED_WARNING_TYPES` duplicated emitted warning type IDs in Python.
   - Acceptance: `warning_emitters` author the mapping from Python glue emitters to ontology warning types; Python no longer stores a separate emitted warning-type set.

## Follow-up fixes after final-slice review

- Relation schema type/severity validation now derives loaded JSON Schema enums from authored ontology/generated runtime artifacts instead of static schema literals.
- Runtime `relation_warning_rules.filter_value` references are checked by the ontology compiler against authored assertion values for `assertion_kind` and `semantic_family`.
- Relation type metadata now explicitly labels `directional` and selector forms as assertion/review metadata, not hidden scheduler placement policy.
- The two worst ontology artifact harness debts were moved off subprocess/full copied-repository paths; targeted checks now use direct in-process seams.
- `scope_dimensions` now author runtime fact adapters and capability fields; `_scope_facts` dispatches through generated runtime policy rather than a dimension-key branch table.

## Out of scope for this pass

- No TypeDB implementation.
- No dose/personalized clinical model.
- No test harness refactor.
- No new fat-meal slot model unless current data/rules require it for lossless extraction.
- Static `Literal[...]` annotations in Python remain as typed API/output-shape contracts; runtime validation checks them against generated ontology artifacts.
- Interpreter grammar constants such as condition operators and action dispatch remain execution grammar, not supplement-domain truth.

## Final gate

After the slices are complete:

1. Run repo-approved targeted and static `just` gates without using the full heavyweight unit loop for every small slice.
2. Check this document's acceptance bullets against code.
3. Repeat CrossAI review with DeepSeek, GLM, and Claude Opus using the same product/architecture optic: can the ontology be moved to TypeDB/RDF without losing supplement-domain entities, relations, warning policies, and scheduler semantics?
