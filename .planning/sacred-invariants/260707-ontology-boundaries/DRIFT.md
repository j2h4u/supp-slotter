# Drift Notes: supp-slotter sacred-invariants run

Date: 2026-07-07
Overall confidence: Medium

## Drift Findings

| drift_id | Drift | Classification | Evidence | Recommended handling |
|---|---|---|---|---|
| DR-001 | Older `.planning` files still describe `data/inventory.yaml`, `data/slots.yaml`, and single-file `data/traits.yaml`. Current repo uses `data/stacks.yaml`, `data/pillboxes.yaml`, and `data/traits/`. | stale docs / historical planning state | .planning/PROJECT.md:14-27; README.md:162-170; docs/domain-model.md:47-49 | Mark historical or refresh the planning summary. Do not let it drive implementation. |
| DR-002 | Prior planning language emphasized product component amounts; current product intent says amounts are optional and not central. | resolved product evolution | .planning/PROJECT.md:50-55; docs/domain-model.md:324-333; SKILL.md:164-168 | Preserve optional amount fields, but keep audits advisory and task-scoped. |
| DR-003 | MCP was discussed but product surface remains unclear. | explicit deferral | docs/mcp-position.md:1-57 | Keep MCP out of scope until workflows are deterministic and product-clear. |
| DR-004 | CLI subprocess helper still defaults to repo root for help-only tests and can be misused later. | latent test-surface drift | tests/test_architecture_contracts.py:32-45; tests/helpers.py:23-24 per test lane | Treat as follow-up guardrail, not current blocker. |

## Owner Questions

No interactive questions were asked; the following owner questions remain open.

| Priority | Question | Default assumption | Risk |
|---|---|---|---|
| P1 | Should stale `.planning` status docs be updated now or left as archival history? | Leave history, but prefer current README/SKILL/domain model. | Agents may read stale paths as current. |
| P1 | Should product lifecycle outside stacks stay implicit, or become explicit before future tool/MCP work? | Stay implicit for current CLI/YAML workflow. | Tooling may need a clearer state machine later. |
| P2 | Should helper-default live-root use be removed even for `--help` tests? | Keep as low-priority follow-up unless new coupling appears. | New tests could bypass the architecture guard. |

## Non-Drift Clarifications

- Unknown component amounts are not a current drift problem by themselves.
- Knowledge-only substance cards are not deletion candidates by default.
- Tracked-unassigned products can represent depleted, reference, candidate, or not-owned states today.
- Dashboard membership is intentionally flat and neutral today.
