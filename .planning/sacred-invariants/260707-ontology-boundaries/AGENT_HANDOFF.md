# Agent Handoff: supp-slotter

Date: 2026-07-07
Task lens: ontology boundaries, scheduler/reviewer split, product amount non-goal
Prepared for: downstream audit, contract-test, docs, and future tool-design agents
Overall confidence: Medium-high

## Start Here

- Artifact read order: `AGENT_HANDOFF.md` first, then `INVARIANTS.md`, then `LEAD_ARCHITECT_SYNTHESIS.md`, then `DISCOVERY.md`, then `DRIFT.md`.
- Strongest suspected boundary: reviewer-only ontology and source-completion metadata must not silently become scheduler authority.
- Required first-pass action: ACT-001.
- Top downstream tasks: ACT-001 required; ACT-002 follow-up; ACT-003 conditional.
- Current-stage proofs vs prepared-but-deferred lifecycle behavior: current proof is YAML+CLI deterministic scheduling/review. MCP, explicit depleted/reference lifecycle, dose calculations, and recommendation status are deferred behavior.
- Actions blocked on product/security/architecture decisions: explicit unassigned-product lifecycle; MCP write tools; dose/ratio computation; recommendation/adequacy semantics.
- Minimal verification packet: `uv run python -m planner check`; `uv run python -m planner`; `uv run python -m planner review`; `uv run python -m planner audit`; `just check`; `just unit`; `just coverage-check`; `just crap-check`.
- Do not implement without approval: amount calculators, medical advice/recommendation scoring, raw MCP CRUD over YAML, schedule effects from broad `knowledge.*` facts, deletion of knowledge-only cards just because they are not active.

## Action Queue

| action_id | Finding | Type | Actionability | Requires decision? | Files / anchors | Acceptance criteria |
|---|---|---|---|---|---|---|
| ACT-001 | SI-003 scheduler/reviewer authority boundary needs a crisp negative proof. | contract-test / audit | required_first_pass | no | A-006, A-013, A-014 | A synthetic fixture proves that changing `knowledge.effect`, `knowledge.risk`, `knowledge.context`, or `knowledge.pathway` does not change slot assignment, while an explicit `schedule.*` trait or `competes` relation can. Review/dashboard output may change where intended. |
| ACT-002 | Unassigned product cards currently encode depleted/reference/candidate/not-owned by absence from stacks. | product / docs | follow_up | yes | A-005, A-009 | Either document that implicit state remains accepted, or design an explicit lifecycle field before MCP/tooling work. No scheduler behavior should be inferred from filenames or live stack examples. |
| ACT-003 | Behavior tests are mostly live-data independent, but CLI helper defaults can let future tests reattach to repo-root data. | contract-test | conditional | no | A-011, A-012 | If new CLI behavior tests appear, they must use synthetic roots or an architecture guard that prevents default live-root command execution outside help/version-only smoke tests. |

## Anchor Manifest

| anchor_id | File | Lines | Claim supported | Checked? |
|---|---|---|---|---|
| A-001 | README.md | 3-9 | Deterministic visibility/review product, not medical advice. | yes |
| A-002 | README.md | 158-178 | YAML source truth; schedule report; Surreal query layer. | yes |
| A-003 | SKILL.md | 42-48 | Keep model small; no compatibility baggage by default. | yes |
| A-004 | SKILL.md | 160-168 | Check is hard; review/audit are advisory; unknown amounts can be acceptable. | yes |
| A-005 | docs/domain-model.md | 7-25 | Product/substance/personal-state ownership. | yes |
| A-006 | docs/domain-model.md | 49-74 | Planner vs Reviewer trait authority. | yes |
| A-007 | docs/domain-model.md | 96-109 | Product is schedulable unit; dashboard output review-only. | yes |
| A-008 | docs/domain-model.md | 228-308 | Relation type and endpoint authority. | yes |
| A-009 | docs/domain-model.md | 324-333 | Amounts optional; audit hints are not automatic wrongness. | yes |
| A-010 | docs/mcp-position.md | 1-57 | MCP is deferred and deterministic-only if revisited. | yes |
| A-011 | tests/test_architecture_contracts.py | 32-45 | Behavior tests should not use live default data root. | yes |
| A-012 | tests/planner_fixture.py | 108-187 | Synthetic fixtures build isolated roots. | yes |
| A-013 | planner/engine/_scheduling.py | 10-43 | Scheduler aggregates only schedule traits from components. | yes |
| A-014 | planner/engine/_plan_output.py | 98-155 | Schedule output adds review/dashboard/warnings after assignment assembly. | yes |
| A-015 | planner/query_model/session.py | 10-26 | Surreal session boundary is a narrow facade. | yes |
| A-016 | pyproject.toml | 110-200 | Import-linter contracts preserve layer authority. | yes |

## Preserve

- YAML-first source authority and generated `schedule.yaml` as disposable report.
- Product cards as physical label-backed items; substances as reusable knowledge.
- Stack membership as the scheduling activation surface.
- Scheduler/reviewer namespace split.
- Relations as centralized typed edges with explicit endpoint breadth.
- Advisory status of `review` and `audit`.
- Synthetic behavior tests independent of the owner's live stack.
- Import-linter contracts that keep cards, read model, commands, maintenance, and publication layers separated.

## Prove First

- Prove the negative side of SI-003 before doing broader ontology cleanup: reviewer facts can surface information but cannot move slots without explicit promotion.

## Do Not Change Without Approval

- Do not add a dose engine, evidence grader, medical recommendation status, or adequacy/coverage inference.
- Do not make missing `amount` a hard quality gate.
- Do not build MCP CRUD over raw YAML.
- Do not collapse dashboard membership into recommendation status.
- Do not delete knowledge-only or tracked-unassigned cards because they are not active.
