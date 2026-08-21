# Execution-Engine Boundary Audit — 2026-08-21

## Scope and authority model

This audit covers the executable ontology/runtime tree on
`origin/feature/executable-ontology-contract` at
`70940b359d81f6ba7fa102d7d310f08ae43df56b` (the current checkout adds only
decision documentation). It was read together with
`docs/decisions/ontology-cutover-decision-20260821.md` and `AGENTS.md`.
No code or data was changed and no test gate was run.

The requested classification is deliberately about reimplementation risk:

* **formally authored + generic Python** — the domain value/parameter is in a
  canonical ontology/card source and Python performs a generic interpretation;
* **documented but Python-authoritative** — a formal name or policy exists, but
  the externally visible algorithm is fixed in Python and is not specified
  sufficiently for an independent engine;
* **hidden domain knowledge in Python** — a supplement-domain rule or value is
  present only in executable Python (there are very few in this branch);
* **pure implementation detail** — an algorithm/data structure may change if
  it preserves the declared observable contract.

“Formal” here means authored in `ontology/*.yaml`, `ontology/*.ttl`, card
schemas, or source cards and represented in the verified runtime projection. A
generated artifact is not an independent authority.

## Executive boundary result

The feature branch is not a TypeQL-only scheduler. Its formal layer already
declares IDs, selector shapes, schedule axes, slot observations, policy levels,
constraint metadata, relation warning rules, stack-state truth tables, and
objective parameter names. The following still require reading Python to
reproduce exactly: selector fan-out and exact-form guard behavior, component
policy grouping and rounding, `prefer_with` ambiguity handling, dynamic hard
blocking and advisory matching, candidate priority/search/pruning, objective
tie semantics, and warning query/deduplication precedence.

This is a finite execution-engine gap, not evidence that the ontology has no
value. The smallest remedy is a versioned engine protocol plus conformance
fixtures for those observable algorithms; it does not require putting the
branch-and-bound implementation or a TypeDB deployment into the ontology.

## Required semantic map

| Required semantic | Formal source and current runtime | Classification | What a future engine cannot infer without Python today |
|---|---|---|---|
| Selector forms and exact-form behavior | `ontology/scheduling-model.yaml` defines entity/name/category-term selector shapes; `ontology/runtime-policy.yaml` declares `entity_id`, `name`, and `term`; `planner/ontology/selector.py` resolves them. Constraint `scope: exact_form` is declared in the schema and checked in `planner/scheduling_constraint_execution.py`. | **documented but Python-authoritative** | Entity ID means one exact stable card; name means exact-name fan-out across all cards; term means canonical vocabulary membership projected from card assertions. The exact-form guard rejects an unscoped ID when same-name siblings exist, but the resolution result and sibling rule are not a standalone protocol. |
| Component vote aggregation | Substance schedule assertions and policy effects are authored; `ontology/runtime-policy.yaml` says `sum_unique_component_assignments`; `planner/engine/_scheduling.py` projects one assignment per component/axis and groups rows by policy ID. | **documented but Python-authoritative** | Grouping is by `policy_id`, weight is the number of contributing assignment rows, each policy effect is scored once at that weight, and the score is `round(float(score) * weight)` before summing. Duplicate component IDs fail closed. The grouping key, duplicate rule, and rounding point are not formal pseudocode. |
| Active/inactive/unassigned stack state | `data/stacks.yaml` authors membership; runtime glue declares `inactive` as the inactive stack; `ontology/runtime-policy.yaml` contains the exhaustive active/inactive/tracked dashboard truth table. `planner/cards/stacks.py`, `planner/engine/_plan_active_index.py`, and `planner/query_model/facts.py` interpret it. | **formally authored + generic Python** for state facts, **documented but Python-authoritative** for planner partitioning | Any stack other than the configured inactive name is active for planning; a product outside all stacks is unassigned and excluded from plan items; missing cards are skipped with diagnostics. The exact normalized record and “all non-inactive stacks are active” rule should be protocolized. |
| Episodic presentation | Product `use_pattern` is modeled and validated; feature cards use `not_every_day`; `planner/cards/schedule.py` groups daily products into `daily_base` and `not_every_day`. | **documented but Python-authoritative** | `not_every_day` changes presentation only, while the item remains in the daily scheduling stack. No recurrence, dose, or calendar semantics exist. The literal is duplicated in Python (`NOT_EVERY_DAY_USE_PATTERN`) rather than consumed from the runtime vocabulary. |
| Hard/advisory operations | `ontology/scheduling-constraints.yaml` authors operation, selectors, rationale, action and optional overrides; runtime policy declares `separate_products_same_slot`, symmetric matching, `blocks_slots`, `scores_advisory`, and `score_delta`. | **formally authored + generic Python** for operation metadata, **documented but Python-authoritative** for matching | The only supported handler is `separate_products_same_slot`. Symmetric mode matches source→target or target→source across two products. A hard plan is filtered by `blocks_slots`; an advisory plan is included by `scores_advisory`; a plan can be both hard and advisory. Pair matching and the effect of `score_delta` are Python behavior. |
| `prefer_with` resolution and conflict handling | Substance cards author `prefer_with`; runtime policy declares source field, `exactly_one_active_item`, and `undirected_same_slot_bonus`; `planner/engine/_plan_active_index.py` resolves it. | **documented but Python-authoritative** | Targets are looked up as substance IDs in the active component index. Exactly one target product creates an unordered pair; zero targets silently creates no pair; multiple target products emit `ambiguous_prefer_with` and award no bonus; self-pairs are ignored; duplicate/reverse declarations collapse into a set. These zero/one/many semantics are not encoded as a formal truth table. |
| Candidate feasibility | Assignment axes/cardinality, effect-match dimensions, slot-near vocabulary and policy effects are formal; `planner/engine/_plan_feasibility.py` enumerates slots whose `slot.stack` equals the item stack and computes base scores. Hard constraints are applied dynamically in search. | **documented but Python-authoritative** | The precomputed candidate set does not apply pairwise hard constraints; every same-stack slot starts as a candidate. Dynamic blocking is checked only against already assigned items. Candidate priority is fewest candidates, then highest candidate score, then original item sequence. The candidate trace currently has no populated hard-block contributors. |
| Objective and score arithmetic | Runtime policy authors score levels (`+4,+2,-2,-4`), objective name, balance expression, `balance_weight=0.5`, and `prefer_with_bonus=3`; `planner/engine/_plan_search.py` implements them. | **documented but Python-authoritative** | Total = slot score + advisory penalties + same-slot prefer bonus − `0.5 * sum(slot_count²)` over all slots. Slot score is integer; balance is float. The exact placement of advisory penalties and empty-slot counts is implementation behavior. |
| Search, pruning, and tie-breaking | Runtime policy names `stable_slot_order`; `planner/engine/_plan_search.py` implements greedy seeding, branch-and-bound, admissible upper bounds, `FLOAT_TIE_EPSILON=1e-9`, and lexicographic slot keys. | **pure implementation detail** for algorithm choice, **documented but Python-authoritative** for observable tie behavior | The result is selected by maximum total, then equal-total lexicographic slot-order tuple in original `item_id_sequence`. Candidate ordering is dynamic adjusted score descending then slot order. Item order comes from normalized stack/YAML insertion order. The protocol does not currently state whether another engine must match exact assignment or only score-equivalent output. |
| Warning and relation truth rules | Runtime policy authors warning types/emitters, relation filters, active sides, four endpoint presence states, selector display capabilities, and dashboard truth tables. `planner/query_model/relation_warnings.py`, `relations.py`, `relation_conflicts.py`, and `_plan_output.py` execute them. | **formally authored + generic Python** for rule values, **documented but Python-authoritative** for query semantics | Active substance IDs are components of products in any non-inactive stack. Endpoint truth is `ANYINSIDE active` / `NONEINSIDE active`; relation rules filter relation type plus `assertion_kind` or `semantic_family` and active side. Relation classification returns the first matching warning rule. Warning collection reverses endpoints when authored, deduplicates by `(src_key, relation, tgt_key)`, and emits intra-product conflicts separately. These precedence/dedupe rules are not formal. |

No supplement names, pair assertions, or placement preferences are hard-coded
in the engine. `IMPLEMENTED_*` lists in `planner/ontology/glue_capabilities.py`
are execution capability IDs, not domain knowledge. The one conspicuous
domain-facing duplication is the presentation token `not_every_day` in
`planner/cards/schedule.py`; the full episodic behavior is otherwise a card
field plus generic grouping.

## Detailed observable contract currently implemented

### 1. Selector resolution

The hydrated selector union is closed: either `entity {entity_id}`,
`entity {name}`, or `{category, term}`. Entity ID resolution returns exactly
that ID if the card exists; absent IDs are `unsupported_selector`, not an
empty match. Name resolution compares `Substance.name` exactly and returns a
sorted tuple of all matching IDs; a miss is `unsupported_selector`. Term
resolution first requires a generated category predicate and canonical term,
then tests each substance’s projected terms; a known term with no matching
cards is `empty`.

Scheduling constraint compilation combines endpoint outcomes. Malformed or
unsupported endpoints fail closed. `require_nonempty` rejects an empty
resolution. A constraint with resolved selectors is executable; no silent
zero-effect constraint is allowed. An ID selector with same-name siblings must
declare `scope: exact_form`; scope is only allowed with an entity ID. The
current engine therefore supports exact identity, broad exact-name fan-out,
and vocabulary-term fan-out, but does not define a general form comparator
beyond stable ID plus the sibling guard.

### 2. Component projection and votes

For each product component, Python emits one generic `assignment` source row
from that substance’s authored schedule assertions. Each declared axis
(`intake`, `timing`, `activity`) accepts zero or one assertion per component.
An axis/value maps to a policy ID such as `intake:food_preferred`; missing
policy or undeclared axis is malformed.

Rows are grouped by policy ID. The group weight is the count of component
assignment rows in that group, so multiple known components voting for one
policy accumulate. Each matching policy effect contributes its authored score
level multiplied by that weight and rounded to an integer. Unknown scheduling
facts contribute no row and therefore no vote. This is generic code, but the
grouping and arithmetic need to be made explicit for a non-Python engine.

### 3. Stack and episodic state

`normalize_stack_entries` rejects duplicate product IDs and cross-stack
membership. The planner uses the runtime-configured inactive stack name as the
only excluded partition. Daily and training entries become active items and
are assigned only to slots from the matching pillbox stack. Cards absent from
all stacks remain tracked/unassigned for audits and dashboards but are not
plan items. Inactive cards remain catalogued but are excluded from planning,
relation warnings, and slot assignment.

The dashboard truth table is exhaustive over three booleans:
active stack membership, inactive stack membership, and tracked product
presence. It yields `current`, `on_shelf`, `unassigned`, or `not_current`, and
separately yields `tracked_product` or `no_tracked_product`. This is a good
formal portable contract. The planner’s use of only “stack != inactive” for
active partitioning is the small glue rule still worth writing down.

`use_pattern: not_every_day` is presentation grouping only. It does not change
candidate slots, score, stack membership, frequency, dosage, or calendar
recurrence.

### 4. Constraint operation semantics

The current authored operation catalog contains one executable operation:
`separate_products_same_slot`. Its resolved execution row contains source and
target substance ID arrays, direction, aggregation, selector outcome, block
flag, advisory flag, and score delta. The generic interpreter checks whether
the incoming item and existing slot item contain matching source/target IDs.
Symmetric direction also checks the reverse orientation.

Hard blocking checks every existing item already in a candidate slot and every
executable plan with `blocks_slots=true`. Advisory evaluation canonicalizes
the slot’s item IDs, checks each unordered product pair, and adds one
`score_delta` per matched constraint ID, not one penalty per matching component
pair. A hard plan may also be advisory; its same-slot candidate is blocked, so
the advisory score is only observable in otherwise permitted evaluations.
Intra-product component pairs cannot be separated and produce a dedicated
warning instead of a block.

### 5. Preference accumulation

The active component index maps each substance ID to sorted active item IDs.
For every component’s `prefer_with` target, Python resolves the target in that
index. One target creates a `frozenset` pair; multiple targets create a
warning with candidate items and no pair; no target creates neither; a target
on the same item is ignored. The set removes duplicate/reverse declarations.
At a complete assignment each pair contributes the authored bonus if both
items share a slot. No conflict resolver chooses among multiple target
products; ambiguity is surfaced and neutralized.

### 6. Candidate and search behavior

Candidate slots are all slots in the item’s stack. Base scores come from the
projected component votes. Candidates are sorted for search by dynamic base
score plus advisory penalty, descending, then slot insertion order. Global
item priority is smallest candidate count, highest maximum base score, then
the item’s original sequence position.

Search seeds a greedy feasible assignment, then explores branch-and-bound.
Hard constraints are checked against assignments already in each slot. The
upper bound ignores dynamic advisory penalties (they are non-positive), adds
the maximum remaining base score and all possible prefer bonuses, and subtracts
a relaxed balance lower bound. At complete assignments it recomputes advisory
penalties, objective metrics, and a lexicographic slot-order key. A candidate
wins on higher total, or on equal total within `1e-9` when its slot-order tuple
is lexicographically smaller.

This is enough to explain current outputs, but an independent implementation
would otherwise have to discover the priority, rounding, bound, epsilon,
insertion-order, and tie-key rules from source.

### 7. Warning and relation truth behavior

The plan output warning stream combines dashboard warnings, active trait-review
warnings, intra-product constraint conflicts, ambiguous `prefer_with`, safety
concerns, and read-model relation warnings, then humanizes and filters selected
review tags. Warning types and default action text are formal; warning ordering
is the output pipeline order in Python.

For relation presence, the read model computes endpoint activity from whether
each endpoint’s resolved substance ID array intersects the active substance
set. The four states are `both_active`, `missing_target`, `missing_source`,
and `neither_active`. Authored warning rules select relation type, one filter
field/value, and an active side. Relation classification returns the first
matching warning rule; relation warning collection runs all declared rules for
a relation/warning pair and deduplicates endpoint/type triples. Reverse-output
rules swap presentation fields without changing the underlying assertion.

## Smallest finite externalization needed

The following is the minimum protocol delta that removes semantic archaeology
without freezing implementation technology:

1. **Version the engine contract.** Add a machine-readable
   `engine_contract` section to the runtime projection with a protocol version,
   observable-result mode (`exact_assignment` or `score_equivalent`), and
   capability IDs. Keep unsupported capabilities fail-closed.

2. **Publish selector resolution rows.** For every authored selector, publish
   selector form, scope, resolved IDs (sorted), outcome, and sibling/form
   rationale. Specify exact ID, exact-name fan-out, term fan-out, empty versus
   unsupported, and `require_nonempty` behavior.

3. **Publish schedule projection rows and arithmetic.** Define the ordered
   component assignment rows, axis cardinality, policy grouping key, duplicate
   rule, group weight, score-level mapping, rounding rule, and zero-vote rule.

4. **Publish normalized stack facts.** Emit product ID, stack, active flag,
   inactive flag, unassigned flag, and presentation group. State that only the
   configured inactive stack is excluded from planning and that
   `not_every_day` has no recurrence semantics.

5. **Publish an operation registry and pair evaluator.** Each operation must
   specify input arrays, direction, aggregation, hard/advisory flags, whether
   one penalty is charged per constraint or per pair, and intra-product
   behavior. Include conformance rows for forward, reverse, same-product, and
   multi-component matches.

6. **Publish preference-resolution truth tables.** Define target key space,
   zero/one/many active target behavior, self-pair behavior, dedupe key,
   warning payload, and bonus application.

7. **Publish candidate/search semantics.** Define candidate generation and
   hard-block timing, candidate and item ordering, advisory re-evaluation,
   objective arithmetic, balance scope, branch-bound admissibility, float
   tolerance, and the exact tie key. A future engine may use another search
   algorithm if it produces the declared observable mode.

8. **Publish warning/relation evaluation rows.** Define active-set
   construction, endpoint truth table, rule precedence when multiple rules
   match, reverse presentation, dedupe key, warning ordering, and the
   intra-product conflict rule. Add fixtures for all four endpoint states.

9. **Add finite conformance fixtures, not a second implementation.** Use a
   small synthetic corpus covering one component vote, conflicting component
   votes, unknown vote, one hard pair, one advisory pair, an ambiguous
   preference, each stack state, all four relation states, and a score tie.
   The fixtures should assert protocol rows and one end-to-end assignment.

These changes externalize the observable semantics while leaving generic
Python mechanics—joins, collection traversal, database adapters, search data
structures, pruning, serialization, and human-readable rendering—replaceable.

## Remaining uncertainty and boundary conclusions

* The runtime snapshot rejects any objective/scoring descriptor not equal to
  the Python implementation constants. This is a useful fail-closed interlock,
  but it means changing objective syntax still requires coordinated runtime
  support until the protocol above replaces the closed string expressions.
* Exact assignment parity versus score-equivalent portability is not yet a
  declared product requirement. Stable slot order and item insertion order
  currently make exact parity possible but fragile across storage engines.
* The formal relation and dashboard truth tables are substantially more
  portable than their query execution, precedence, and output dedupe behavior.
* No dose engine, recurrence scheduler, TypeDB deployment, or medical inference
  engine is required to close this boundary. The unresolved work is a finite
  protocol/conformance layer around the existing solver.

This audit records the current engine boundary and migration requirements. It
does not recommend a branch, authorize a cutover, or change runtime behavior.
