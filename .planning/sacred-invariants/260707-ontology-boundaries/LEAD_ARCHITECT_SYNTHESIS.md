# Lead Architect Synthesis: supp-slotter

Date: 2026-07-07
Task lens: ontology boundaries after QA hardening and live-data decoupling
Inputs reviewed: discovery evidence, docs lane, tests lane, architecture source anchors
Overall confidence: Medium-high

## Start Here

- Strongest suspected product boundary: scheduling authority must not leak into reviewer ontology or amount/source-completion metadata.
- Requested task-lens boundary to preserve first: YAML source truth -> read model projection -> scheduler decision -> advisory review output.
- Required first-pass downstream proof: demonstrate that reviewer-only knowledge changes can alter review output but cannot alter slot placement unless promoted through an explicit scheduling trait or `competes`.
- Highest-risk rough-discovery assumption: stale `.planning` project state is archival, not current authority.
- Owner question that could change the architecture: whether unassigned products need explicit lifecycle state before any MCP/tool surface is designed.
- Do not let downstream work start with: CRUD surfaces, amount calculators, or broad ontology cleanup disconnected from a live review/scheduling behavior.

## Rough Discovery Challenge

| Rough claim | Judgment | Why | Confidence |
|---|---|---|---|
| YAML is source of truth and SurrealDB is projection only. | Keep | Multiple docs and package boundaries agree; import-linter also prevents read-model leakage into source layers. | Proven |
| Product amounts matter because product schemas allow them. | Challenge | Current docs state amounts are optional label/context metadata and not a quality gate by themselves. | Proven |
| Dashboards are goal coverage. | Discard | Domain model says dashboard output is neutral relevance/membership and not recommendation, adequacy, or safety. | Proven |
| Stacks are inventory. | Refine | Stacks are only current membership. Products can be inactive or outside all stacks as reference/depleted/candidate entries. | Proven |
| Relations are merely warning text. | Refine | Most are review warnings, but `competes` is also a scheduler relation and class-level `competes` reads `knowledge.is` narrowly. | Proven |

## Authority-Lifecycle Kernel

| Field | Staff-level answer |
|---|---|
| Decision at stake | Which facts may affect slot placement versus which facts may only inform review, warning, audit, or dashboard output. |
| Current owner | Domain model and trait namespace contract; implemented by loaders, scheduler trait aggregation, relation read model, and tests. |
| Ownership start | When a fact is entered into a substance card, relation, product card, dashboard, or stack membership file. |
| Ownership token / evidence boundary | Namespace plus location: `schedule.*` for Planner traits; `knowledge.*` for Reviewer facts; `data/relations.yaml` relation type for pair/category interactions; product component fields for label facts. |
| Allowed mutation | Add review facts, relation warnings, dashboard projections, product label metadata, and stack membership when their authority is explicit. |
| Forbidden neighboring decision | Do not make reviewer-only facts, source gaps, amount strings, dashboard membership, or broad effects change slot placement implicitly. |
| Transfer / override / removal / expiry | Promote to scheduling only by adding an explicit schedule trait/effect or `competes` relation; remove/defer by leaving as notes, concerns, review relations, or ontology pressure point. |
| Uncertainty posture | defer visibly; expose as review/audit hint; do not compute hidden dose or medical inference. |
| Supporting contract | namespace split, relation endpoint validation, read-model facade, import-linter package boundaries, synthetic-root tests. |
| First downstream proof | Synthetic fixture where `knowledge.effect/risk/context/pathway` mutations change review/dashboard facts but leave schedule slot assignment unchanged; paired with explicit promotion proof through `schedule.*` or `competes`. |

## Relevant Boundary Pattern

| Pattern | Why it matters here | Rule / risk | First proof |
|---|---|---|---|
| stage-specific authority | Source data, read-model evidence, scheduler decisions, generated presentation, and advisory guidance are intentionally distinct. | Collapsing them creates wrong-premise fixes: amount calculators, schedule changes from review tags, or audit hints treated as validation failures. | ACT-001 scheduler/reviewer authority probe. |

## Phase-Scope Gate

| Current-stage proof | Prepared primitive only | Deferred end-to-end behavior | Owner decision before expansion |
|---|---|---|---|
| YAML + CLI + review/audit workflow with strict QA gates and synthetic tests. | MCP position doc, read-model facade, deterministic maintenance, rich command surfaces. | MCP server/tool surface, explicit unassigned-product lifecycle, dose/ratio calculations, recommendation engine. | Whether the product workflow is clearer than YAML + CLI; whether unassigned products need explicit state. |

## Staff Architect Judgments

| id | Judgment | Why it matters | Confidence | Downstream implication |
|---|---|---|---|---|
| LA-001 | The product center of gravity is deterministic reviewable stack reasoning, not supplement dose computation. | Prevents future agents from treating missing amounts as debt when the task is about interactions and ontology. | High | Keep `amount` optional and task-scoped. |
| LA-002 | Scheduler/reviewer split is the main sacred boundary. | Most future ontology work touches traits, relations, dashboards, or warnings. This boundary prevents accidental behavior changes. | High | First proof must target namespace authority. |
| LA-003 | Relation endpoint breadth is a product decision. | Trait/name endpoints automatically affect future cards; narrow endpoints preserve concrete-form behavior. | Medium-high | Future tooling should preview endpoint expansion before apply. |
| LA-004 | Tests are now mostly protected from personal live data, but helper defaults can reintroduce coupling. | The user explicitly wants cloned repos with different personal stacks to keep tests green. | Medium | Keep architecture contract and consider helper hardening as follow-up. |
| LA-005 | `.planning` is not uniformly current truth. | It contains useful history and stale model names. | Medium | Downstream agents should prefer README, SKILL, domain model, schemas, and tests for current behavior. |

## Handoff Implications

| action_id | Boundary / decision | Operation class | Priority | Forbidden shortcut | Acceptance criteria |
|---|---|---|---|---|---|
| ACT-001 | Scheduler/reviewer namespace authority | preserve / contract-test | required_first_pass | Do not add broad code review or amount modeling first. | Synthetic proof shows review-only knowledge does not move products, while explicit scheduling promotion does. |
| ACT-002 | Unassigned product lifecycle | product_decision / docs | follow_up | Do not infer depleted/reference/candidate from product filename or live stack examples. | Current implicit state is documented as accepted, or explicit lifecycle state is designed before tool/MCP work. |
| ACT-003 | Live-data test quarantine | supporting_contract | conditional | Do not write tests against current personal product IDs. | CLI helper cannot be casually used for behavior tests against repo root. |

## Stop / Proceed

- Proceed to downstream handoff when the next agent receives ACT-001 and the anchor manifest.
- Interview owner first when changing unassigned product lifecycle or MCP surface design.
- Stop lower-level implementation when a proposed fix relies on amount arithmetic, medical inference, or recommendation status not represented in current contracts.
