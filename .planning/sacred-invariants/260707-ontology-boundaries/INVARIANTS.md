# Sacred Invariants Report: supp-slotter

Date: 2026-07-07
Task lens: ontology and scheduling/review authority
Downstream consumers: audit agents, contract-test agents, docs agents, future MCP/tool-design agents
Overall confidence: Medium-high
Stage: final handoff

## Start Here

- Strongest suspected boundary: reviewer ontology and source-completion metadata must not silently become scheduler authority.
- Required first-pass downstream action: ACT-001 in AGENT_HANDOFF.md.
- Top downstream tasks: prove scheduler/reviewer split, clarify unassigned-product lifecycle only if needed, harden CLI test-root guard if future tests drift.
- Safe immediately: docs-only clarification of stale planning artifacts; synthetic contract tests that preserve current behavior.
- Blocked on product decision: explicit depleted/reference/candidate lifecycle; any MCP write surface; any dose/ratio engine.
- Minimal verification packet: `uv run python -m planner check`, `uv run python -m planner`, `uv run python -m planner review`, `uv run python -m planner audit`, `just check`, `just unit`, `just coverage-check`, `just crap-check`.
- Do not implement without approval: amount computation, medical recommendation status, raw MCP CRUD over YAML, scheduler behavior from broad `knowledge.*` facts.

## Sacred Invariants

| invariant_id | Statement | Forbidden condition | Evidence | Confidence | First proof / audit |
|---|---|---|---|---|---|
| SI-001 | YAML source files and dataclass/schema contracts are authoritative; generated schedules and SurrealDB are projections. | Treat `schedule.yaml` or SurrealDB as persistent source truth. | README.md:108, README.md:158-178, docs/domain-model.md:90-94 | Proven | Verify commands regenerate output from source and query_model does not write source data. |
| SI-002 | Physical products, reusable substances, and stack membership have separate ownership. | Put brand, label facts, or user shelf state into substance cards; put scheduling traits or product facts into stacks. | docs/domain-model.md:7-25, docs/domain-model.md:310-321 | Proven | Schema/loader audit plus product/substance fixture test. |
| SI-003 | Scheduling authority is explicit and narrow: `schedule.intake`, `schedule.timing`, `schedule.activity`, `prefer_with`, and `competes`. | Reviewer facts, dashboard membership, amounts, or source gaps change slots implicitly. | docs/domain-model.md:49-74, docs/domain-model.md:191-225, planner/engine/_scheduling.py:10-43 | Proven | ACT-001 synthetic namespace probe. |
| SI-004 | Review knowledge is first-class but advisory. `knowledge.effect`, `knowledge.risk`, `knowledge.context`, `knowledge.pathway`, dashboards, and non-`competes` relations surface review context. | Treat review facts as recommendations, adequacy judgments, or slot constraints. | docs/domain-model.md:145-157, docs/domain-model.md:302-308, SKILL.md:160-168 | Proven | Review output changes without schedule placement change. |
| SI-005 | Component amounts are optional label/context metadata, not a dose-computation contract or quality gate. | Fail tasks or audits solely because amount is unknown when the decision does not depend on it. | docs/domain-model.md:324-333, SKILL.md:164-168, docs/ontology-facts.md:32-42 | Proven | Audit `--full` remains advisory; no planner scoring reads component amount. |
| SI-006 | Relation endpoints encode scope and inheritance. Endpoint broadening requires semantic intent. | Use name/trait/class endpoints merely to shorten YAML or accidentally apply to future forms. | docs/domain-model.md:260-308, planner/cards/relations.py:87-153 | Likely | Relation endpoint preview/audit for broad endpoints. |
| SI-007 | Dashboard clusters are neutral membership projections, not explicit member lists or recommendation status. | Edit nonexistent member lists, infer coverage, or use broad dashboard axes as scheduler facts. | docs/domain-model.md:74-84, docs/domain-model.md:108-133 | Proven | Fixture proves OR membership and no slot influence. |
| SI-008 | Behavior tests must be independent from the owner's live personal stack. | Test failures after another person replaces `data/products` and `data/stacks.yaml` with their own data. | tests/test_architecture_contracts.py:32-45, tests/planner_fixture.py:108-187 | Proven | Keep architecture test green; add no live product ID assertions. |
| SI-009 | `check` is hard validation; `review` and `audit` are soft operator surfaces. | Treat audit/review hints as automatic blockers or deletion commands. | SKILL.md:155-168, SKILL.md:189-201, planner/engine/audit.py:62-126 | Proven | Command exit-code and result-shape tests. |
| SI-010 | This repo is not currently an MCP server; MCP remains deferred until product workflows are clearer and deterministic. | Add raw CRUD MCP tools over YAML or LLM behavior inside the server. | docs/mcp-position.md:1-57 | Proven | Docs/tooling review before any MCP work. |
| SI-011 | Static package boundaries preserve stage authority. Cards, query model, maintenance, engine, and schedule writer must not collapse into each other. | Business logic migrates into `schedule_writer`, card loaders import command/read-model layers, or query_model reaches into engine commands. | pyproject.toml:110-200 | Proven | `uv run lint-imports`; review any import-linter contract weakening as architecture change. |

## Relevant Boundary Patterns

| Pattern | Why relevant | Rule or risk | First proof |
|---|---|---|---|
| stage-specific authority | The system deliberately separates source, validation, projection, scheduling, publication, and operator guidance. | Each stage owns only its decision. Neighboring decisions require explicit promotion. | ACT-001 |
| source/model contamination | YAML, SurrealDB, and generated schedule coexist in one repo workflow. | Projection convenience must not become source authority. | SI-001 audit |
| phase-scope boundary | MCP, explicit lifecycle state, dose modeling, and recommendation status have primitives or discussion, but not product ownership. | Do not implement prepared/future surfaces as if already accepted. | Owner decision before expansion |

## Questions Or Drift

No interactive questions were asked; the following owner questions remain open.

| Priority | Question / drift | Why it matters | Evidence | Default assumption | Risk if unanswered |
|---|---|---|---|---|---|
| P1 | `.planning/PROJECT.md` and `.planning/STATE.md` contain stale model names and state. | Agents may revive removed inventory/slot/trait shapes. | .planning/PROJECT.md:14-27, .planning/STATE.md:1-20 | Treat as historical unless updated. | Low-medium |
| P1 | Should unassigned products get explicit lifecycle state? | Future tool/MCP surfaces may need to distinguish depleted/reference/candidate. | docs/domain-model.md:40-43, docs/domain-model.md:100-102 | Absence from stacks is enough for now. | Medium |
| P2 | Should broad relation endpoint previews become a hard workflow? | Prevents accidental category inheritance. | docs/domain-model.md:86-87, docs/domain-model.md:260-308 | Manual review remains enough. | Medium |

## Downstream Probes

| invariant_id | Positive proof | Negative probe | Required real-data shape | Expected outcome | Suggested agent |
|---|---|---|---|---|---|
| SI-003 | A `schedule.intake/timing/activity` mutation changes slot feasibility or score. | Equivalent `knowledge.effect/risk/context/pathway` mutation does not change slot assignment. | Synthetic tmp_path fixture with two slots and one product. | Same slot for review-only changes; changed review output where relevant. | contract-test |
| SI-005 | Product amount appears in product/audit source context. | Unknown amount does not fail `check` or move slot. | Synthetic product with missing amount. | Advisory only. | audit |
| SI-006 | Tests pass against synthetic stack after live data replacement. | No behavior test calls command layer without `data_root`. | AST guard and fixture builders. | Architecture contract stays green. | contract-test |

## Anchor Manifest

| anchor_id | File | Lines | Claim supported | Checked? |
|---|---|---|---|---|
| A-001 | README.md | 3-9 | Product is deterministic visibility/review system, not medical advice. | yes |
| A-002 | README.md | 158-178 | YAML source truth and generated/report boundaries. | yes |
| A-003 | SKILL.md | 42-48 | Small model, no backward-compat baggage, no dose engine unless asked. | yes |
| A-004 | SKILL.md | 160-168 | Review/audit advisory vs hard check boundary; unknown amounts acceptable when irrelevant. | yes |
| A-005 | docs/domain-model.md | 7-25 | Product/substance/personal-state ownership. | yes |
| A-006 | docs/domain-model.md | 49-74 | Scheduler/reviewer trait split. | yes |
| A-007 | docs/domain-model.md | 96-109 | Product is scheduling unit; dashboard output is review-only. | yes |
| A-008 | docs/domain-model.md | 228-308 | Relation type and endpoint semantics. | yes |
| A-009 | docs/domain-model.md | 324-333 | Amounts optional and audit hints are not gates. | yes |
| A-010 | docs/mcp-position.md | 1-57 | MCP is deferred and deterministic-only if revisited. | yes |
| A-011 | tests/test_architecture_contracts.py | 32-45 | Tests must not call command layer against live root. | yes |
| A-012 | tests/planner_fixture.py | 108-187 | Synthetic fixture construction for behavior tests. | yes |
| A-013 | planner/engine/_scheduling.py | 10-43 | Scheduler aggregates only schedule traits. | yes |
| A-014 | planner/engine/_plan_output.py | 98-155 | Schedule output composes dashboard/review warnings after assignment. | yes |
| A-015 | planner/query_model/session.py | 10-26 | SurrealDB protocol is narrow query/session facade. | yes |
| A-016 | pyproject.toml | 110-200 | Import-linter contracts preserve package authority boundaries. | yes |
