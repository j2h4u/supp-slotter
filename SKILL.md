---
name: supp-slotter
description: "Use when editing or reviewing Supp Slotter's domain model, ontology, data, inference, optimizer, generated schedules, or supplement-stack workflow. This is repository maintenance and structured guidance, not medical advice."
metadata:
  short-description: "Maintain the Supp Slotter model and workflow"
---

# Supp Slotter

## Working Rule

Before changing domain semantics or instance data, read:

- [docs/domain-model.md](docs/domain-model.md) for the living contract;
- [the canonical-instance ADR](docs/decisions/canonical-instance-inference-boundary-20260822.md)
  for the governing decision and migration status; and
- [AGENTS.md](AGENTS.md) for the V-model and verification rules.

Apply the canonical gate from those documents to every field and behavior. Do
not treat the current schema, runtime, generated ontology, or passing tests as
proof that the migration is complete.

Use [docs/agent-product-flow.md](docs/agent-product-flow.md) for product/card
workflow and [docs/agent-stack-review.md](docs/agent-stack-review.md) for stack
review. Treat [schema/templates/](schema/templates/) and
[ontology/generated/](ontology/generated/) as current implementation aids, not
independent semantic authority.

Use only the bounded `just` recipes allowed by [AGENTS.md](AGENTS.md). Inspect
`git status --short` and `git diff` after any command that may rewrite source or
generated output. Do not edit `schedule.yaml` directly, change personal stack
data without explicit approval, or present planner output as medical advice.
