# MCP Position

Status: deferred

This repository is not currently designed as an MCP server.

We have discussed an MCP-shaped surface where agents would not edit YAML files
directly, but would instead use deterministic tools for product intake, ontology
edits, stack membership, review, audit, and schedule regeneration. That idea is
not rejected, but it is not product-clear enough to implement yet.

## Current Decision

Do not build an MCP server for Supp Slotter until the product workflow is
clearer.

The current working surface remains:

- YAML source files under `data/`;
- `uv run python -m planner check` for validation and deterministic maintenance;
- `uv run python -m planner` for schedule generation;
- `uv run python -m planner review` and `audit` for review surfaces;
- agent-assisted edits through the repository, followed by the normal validation
  gate.

## Why MCP Is Deferred

The useful product shape is not "CRUD over YAML entities." A raw CRUD surface
over products, substances, traits, relations, dashboards, and stacks would make
the agent reconstruct too much workflow logic and would likely be worse than the
current repo-based editing loop.

A better MCP surface would need a clear product model for guided deterministic
workflows, for example:

- product intake from a physical label;
- discovery of available ontology axes;
- preview of relation endpoints and dashboard membership;
- validation of a proposed stack edit before apply;
- review/audit summaries that do not expose raw files.

We do not yet know whether that surface would be simpler, safer, or more useful
than the current YAML + CLI workflow.

## Boundaries If This Is Revisited

If MCP work resumes later, keep these constraints:

- no AI or LLM calls inside the MCP server;
- no raw `read_file` / `write_file` tools over `data/*.yaml`;
- no direct edits to `schedule.yaml`;
- every write must be deterministic and validation-gated;
- `planner check` remains the shared source of validation truth;
- amounts stay optional label facts, not a hidden dose-calculation model.

Until those constraints can be turned into a clear product workflow, MCP stays
out of scope.
