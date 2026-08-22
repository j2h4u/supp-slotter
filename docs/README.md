# Documentation

Use this page as the map. The README is the product front door; these docs are the operating manuals.

## New Users

- [README.md](../README.md) — what Supp Slotter does, why it exists, and how to run it.
- [Agent Product Flow](agent-product-flow.md) — how to onboard a new stack, add products, and keep private user context separate.
- [Agent Stack Review](agent-stack-review.md) — how to review a stack and produce the default narrative report.

## Agents And Operators

- [SKILL.md](../SKILL.md) — quick operating guide for agents.
- [Domain Model](domain-model.md) — living contract for canonical facts,
  universal inference laws, runtime ownership, and V-model acceptance.
- [Templates](../schema/templates/) — copy-ready product and substance card skeletons.

## Maintainers

- [Canonical Instance and Inference Boundary](decisions/canonical-instance-inference-boundary-20260822.md) — governing target, migration boundary, and V-model acceptance matrix.
- [Ontology Cutover Decision And Completion Plan](decisions/ontology-cutover-decision-20260821.md) — historical evidence for the previous cutover; its ownership clauses are superseded.
- [Execution-Engine Boundary Audit](decisions/execution-engine-boundary-audit-20260821.md) — historical audit of the pre-migration runtime boundary.
- [Ontology Facts](ontology-facts.md) — current unresolved ontology pressure points only.
- [Evidence Coverage Grooming](evidence-coverage-grooming.md) — current card-level grooming contract and evidence-state boundaries.
- [MCP Position](mcp-position.md) — why an MCP server is deferred until the product surface is clearer.
- [planner/](../planner/) — CLI/runtime package.
- [tests/](../tests/) — regression tests for validation, review, scheduling, and maintenance behavior.

## Private Notes

User-specific intake, goals, health context, proposals, and stack-review notes belong under `docs/private/`. That directory is intentionally gitignored and should not be used for reusable product or substance facts.
