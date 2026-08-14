# Sacred Invariants Discovery: supp-slotter

Date: 2026-07-07
Task lens: ontology, scheduler/reviewer split, product facts, relation surface, downstream audit handoff
Stage: rough codebase-first reconnaissance
Overall confidence: Medium-high

## Executive Reconstruction

`supp-slotter` is a local, deterministic, YAML-first supplement stack planner. Its product job is to turn real bottles and reusable substance knowledge into a generated pillbox schedule plus review surfaces for interactions, risks, pathways, and dashboard membership. It is not a medical advice engine, dose optimizer, regimen tracker, evidence grader, or journal.

The current architecture is stage-separated:

| Stage | Authority | Evidence |
|---|---|---|
| YAML cards | Source truth for products, substances, relations, dashboards, stacks, traits, pillboxes | README.md:158-178, docs/domain-model.md:90-94 |
| Dataclass loaders and schemas | Field shape, stable IDs, reference integrity | SKILL.md:139-168, planner/contracts.py:1-16 |
| In-memory SurrealDB read model | Query/projection only, not storage | README.md:178, docs/domain-model.md:90-94 |
| Planner | Product-level slot assignment using schedule traits and `competes` relations | docs/domain-model.md:96-109, planner/engine/_scheduling.py:10-43 |
| Review/audit surfaces | Advisory diagnostics and review context | SKILL.md:160-168, planner/engine/audit.py:1-5 |
| `schedule.yaml` | Disposable generated report | README.md:108, SKILL.md:210-219 |
| Import-linter contracts | Static package authority boundaries between cards, query model, engine, maintenance, and writer | pyproject.toml:110-200 |

## Candidate Invariants

| id | Candidate invariant | Confidence | Evidence |
|---|---|---|---|
| C-SI-001 | Product, substance, stack, dashboard, and schedule state have separate ownership. Product cards are physical label-backed items; substances are reusable knowledge; stacks own only membership. | Proven | docs/domain-model.md:7-25, docs/domain-model.md:310-321 |
| C-SI-002 | Scheduling is intentionally narrow: `schedule.intake`, `schedule.timing`, `schedule.activity`, `prefer_with`, and `competes` affect placement; most `knowledge.*` fields are reviewer-only. | Proven | docs/domain-model.md:49-74, docs/domain-model.md:191-225, planner/engine/_scheduling.py:10-43 |
| C-SI-003 | The product is interaction/review-first, not amount-computation-first. Component amounts are optional label metadata and source-completion hints, not dose-quality gates. | Proven | docs/domain-model.md:324-333, docs/ontology-facts.md:32-42, docs/mcp-position.md:47-54 |
| C-SI-004 | Substance-to-substance relations are centralized and typed. Endpoint breadth is a decision right, not a YAML-shortening trick. | Likely | docs/domain-model.md:228-308, planner/cards/relations.py:87-153 |
| C-SI-005 | Dashboard clusters and broad axes are neutral review membership, not recommendation, coverage, adequacy, safety, or scheduling proof. | Proven | docs/domain-model.md:74-84, docs/domain-model.md:108-110, docs/domain-model.md:132-133 |
| C-SI-006 | Tests must not depend on the owner's live personal stack. Behavior tests should use synthetic roots and fixtures. | Proven | tests/test_architecture_contracts.py:32-45, tests/planner_fixture.py:108-187 |
| C-SI-007 | SurrealDB is a command-scoped read model. YAML remains the source of truth and Surreal must not become persistent authority. | Proven | docs/domain-model.md:90-94, planner/query_model/session.py:10-26 |
| C-SI-008 | `check` is the hard validator. `review` and `audit` are advisory surfaces and may expose soft review hints without blocking. | Proven | SKILL.md:155-168, SKILL.md:189-201 |
| C-SI-009 | Package layers must preserve their authority: card loaders do not import engine/read model, query model does not import command layers, and schedule writer remains publication-only. | Proven | pyproject.toml:110-200 |

## Boundary Notes

### Product Facts vs Substance Knowledge

The repo encodes a clean split: product cards own label reality and user-specific stack state; substance cards own reusable biology/form facts. This matches the current product direction: the system helps reason about interactions, synergies, antagonism, risks, pathways, and review surfaces. Amounts can be recorded when the label provides them, but absence of an amount is not automatically a data failure.

### Scheduler vs Reviewer

The strongest boundary is the scheduler/reviewer split. The scheduler aggregates only schedule traits from product components, then uses those traits against slot effects. Review facts can alter warnings and generated review context, but must not silently change placement unless explicitly promoted to scheduling traits or `competes`.

### Relation Endpoint Breadth

Relation endpoints encode scope. `source_name` applies to all current and future forms sharing the name; `source_substance` applies to one concrete card; `source_trait` applies to current and future trait members; `source_class` is restricted to broad `competes`. A downstream agent must treat endpoint broadening as a product decision.

### Generated and Advisory Outputs

`schedule.yaml` is not edited directly. `review` and `audit` are not validators. Audit warnings such as knowledge-only cards, unassigned products, source gaps, duplicate candidates, and unknown amounts are review hints unless `check` reports a hard error.

### Static Layer Contracts

The QA surface now encodes architectural boundaries, not only style. Import-linter contracts keep `planner.cards`, `planner.query_model`, `planner.engine`, `planner.maintenance*`, core modules, and `planner.schedule_writer` from taking neighboring authority accidentally. This supports the sacred boundary by making source loading, projection, mutation, scheduling, and publication harder to collapse.

## Contradictions and Weak Evidence

| id | Observation | Interpretation | Risk |
|---|---|---|---|
| D-001 | `.planning/PROJECT.md` still names older artifacts such as `data/inventory.yaml`, `data/slots.yaml`, and single-file `data/traits.yaml`. | Likely historical planning drift; current README, SKILL, and domain model are fresher. | Agents may follow stale planning language and reintroduce old concepts. |
| D-002 | `.planning/STATE.md` is marked completed but has stale progress metrics and a 2026-05 timestamp. | Treat as archive/state history, not current truth. | Low if docs keep routing to current domain model. |
| D-003 | CLI helper defaults still expose the repo root for `--help` tests and future misuse. | Low current risk because behavior tests are guarded, but the helper can let new tests recouple to live data. | Medium future regression risk. |

## Owner Questions

No interactive questions were asked; the following owner questions remain open.

| Priority | Question | Default assumption if unanswered | Why it matters |
|---|---|---|---|
| P1 | Should `.planning/PROJECT.md` and `.planning/STATE.md` be explicitly marked archival when they conflict with current docs? | Treat current README, SKILL, and domain model as authoritative. | Prevents downstream agents from reviving stale `inventory/slots/traits.yaml` shapes. |
| P1 | Should unassigned products remain state-by-absence, or should a future field distinguish depleted, reference, candidate, and not-owned? | Absence from stacks remains sufficient. | This affects future MCP/tool surfaces more than current planner behavior. |
| P2 | Should broad relation endpoints require a preview step before apply in future tooling? | Yes for agent-facing tools; manual YAML edits rely on review/audit. | Prevents accidental relation inheritance for future substance cards. |

## Reconnaissance Inputs

Human-maintained docs: README.md, SKILL.md, docs/domain-model.md, docs/ontology-facts.md, docs/mcp-position.md, docs/audit/260524-ontology.md, docs/audit/260524-ontology-second.md.

Architecture/config: pyproject.toml import-linter contracts, justfile gates, planner/contracts.py, planner/query_model/session.py, planner/query_model/loaders.py, planner/engine/plan.py, planner/engine/show.py, planner/engine/check.py, planner/engine/_scheduling.py, planner/engine/_plan_active_index.py, planner/engine/_plan_output.py, planner/cards/relations.py, planner/engine/audit.py, planner/maintenance_atomic.py.

Tests: tests/test_architecture_contracts.py, tests/planner_fixture.py, scheduling, relation, audit, review, and CLI-surface evidence from the test lane.
