# CrossAI ontology refactor review checklist

Source review runs:

- Initial completeness review: `.adversarial-reviews/ontology-refactor-completeness-20260806/20260806T103637Z`
- Final-slice adversarial review: `.adversarial-reviews/ontology-refactor-final-20260807/20260806T230909Z`
- Final portability review: `.adversarial-reviews/ontology-refactor-final-review-20260807/20260807T110749Z`

Purpose: preserve the CrossAI recommendations as a tracked product/architecture checklist while keeping raw review logs out of git.

## Consolidated verdict

Current branch status after the first CrossAI pass: `PARTIAL / IMPROVED`.

Current branch status after the 2026-08-07 final portability review: `READY WITH CAVEATS`.

DeepSeek and GLM assessed the branch as ready to ship with documented coupling caveats. Opus agreed the factual ontology is portable without data loss, but flagged one safety-surface bug and several architectural caveats. The safety bug was fixed in `6da6f9d` by making intra-product relation conflict matching fail closed for unsupported execution shapes.

The refactor has moved scheduling/governance/vocabulary/relation-review facts into ontology runtime policy and generated runtime artifacts. Python remains responsible for glue mechanics: loading cards, building the in-memory read model, executing searches, evaluating declared rules, rendering output, and failing closed when generated runtime policy is incomplete. Remaining caveats are mostly closed-world Python pins that intentionally constrain which ontology vocabularies the current glue can execute.

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

9. Formalize warning emitter messages. **Done.**
   - Source leak: operator-facing warning text for Python glue warnings lived in emitters.
   - Acceptance: `warning_emitters.default_message` authors fallback/operator messages; Python reads them from `RuntimeProgram`.

10. Formalize concern review and warning/non-warning behavior. **Done.**
    - Source leak: concern membership statuses and non-warning concern behavior were implicit in review/safety code.
    - Acceptance: `concern_review_statuses`, `concern_warning_rules`, and `non_warning_concern_kinds` author active/inactive/fallback statuses and classify every `ConcernKind` as warning-producing or review-only.

11. Remove inert `schedule_axes` runtime projection. **Done.**
    - Source leak: `schedule_axes` looked authoritative but was not consumed by the scheduler and duplicated/contradicted `assignment_axes` / `scope_dimensions`.
    - Acceptance: the dead runtime table/projection is gone; actual scheduling axes remain authored through consumed policy tables.

12. Formalize source-kind taxonomy. **Done.**
    - Source leak: `product` / `component` / `substance` source-kind values existed only as condition literals and Python types.
    - Acceptance: `source_kind_values` authors source kinds and roles; compiler/runtime validation checks source-kind condition literals against the authored taxonomy.

13. Formalize relation warning review status. **Done.**
    - Source leak: relation warnings promoted rows to `actionable_now` through a Python literal.
    - Acceptance: `relation_warning_rules.review_status` authors the review status emitted by each warning rule; classifier reads `rule.review_status`.

14. Fail closed on unsupported relation conflict execution shapes. **Done.**
    - Source leak: intra-product conflict matching skipped unsupported `aggregation`.
    - Acceptance: both advisory matching and relation-conflict warning paths raise `OntologyInfrastructureError` on unsupported `aggregation` / `match_direction`.

## Follow-up fixes after final-slice review

- Relation schema type/severity validation now derives loaded JSON Schema enums from authored ontology/generated runtime artifacts instead of static schema literals.
- Runtime `relation_warning_rules.filter_value` references are checked by the ontology compiler against authored assertion values for `assertion_kind` and `semantic_family`.
- Relation type metadata now explicitly labels `directional` and selector forms as assertion/review metadata, not hidden scheduler placement policy.
- The two worst ontology artifact harness debts were moved off subprocess/full copied-repository paths; targeted checks now use direct in-process seams.
- `scope_dimensions` now author runtime fact adapters and capability fields; `_scope_facts` dispatches through generated runtime policy rather than a dimension-key branch table.

## Final portability review follow-ups

Non-blocking caveats from the 2026-08-07 CrossAI run:

- Closed-world vocabulary pins still exist in compiler/runtime validation for executable glue contracts: source kinds, component-authority outcomes, relation review statuses, relation presence truth table, endpoint selector kinds, concern membership roles, warning emitters, and prefer-with resolver fields. This is currently deliberate fail-closed coupling, but future extensibility would be cleaner if these pins were generated from ontology or expressed as coverage contracts instead of duplicated equality assertions.
- `legacy_preserved` / `legacy_relation_id` remain load-bearing fields in scheduling-constraint provenance. Opus recommends either deleting them or renaming them to non-migration-specific provenance names before a TypeDB/RDF port.
- Stack membership activity still relies on the literal stack name `inactive` across runtime consumers. If stack membership becomes part of the formal ontology, author the active/inactive stack semantics instead of relying on string checks.
- Selector well-formedness grammar for relation selectors remains Python validation. This can become SHACL/TypeDB-native later.
- Static Python `Literal[...]` aliases remain API/output-shape contracts. DeepSeek/GLM accepted this as a caveat; Opus flagged one divergent alias in `schedule_types.py`.
- `ontology/generated/ontology.ttl` is a project schema projection, not a fully useful RDFS/OWL ontology. `shapes.ttl` is the more meaningful RDF/SHACL asset for a future RDF migration.

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
3. Repeat CrossAI review with DeepSeek, GLM, and Claude Opus using the same product/architecture optic: can the ontology be moved to TypeDB/RDF without losing supplement-domain entities, relations, warning policies, and scheduler semantics? **Done:** `.adversarial-reviews/ontology-refactor-final-review-20260807/20260807T110749Z`.
