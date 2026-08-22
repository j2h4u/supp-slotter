# Agent execution rules

- Do not invoke `pytest`, `basedpyright`, or other test subprocesses directly.
  Use the `just` recipes; their canonical commands go through
  `scripts/run_bounded.sh`.
- Only one bounded test/type gate may run per checkout at a time. The runner
  serializes gates with a git-worktree-specific lock.
- The default aggregate `MemoryMax` is 1G (`MemoryHigh` is 900M and swap is
  disabled). Increase limits only with an explicit per-invocation override
  after confirming an out-of-memory failure; for example, use 1200M/1400M for a
  single invocation.
- After an abnormal gate exit, verify that no repository test processes remain
  before starting another gate.
- Orchestrators must pass `fork_turns` explicitly (default `"none"`) and use
  self-contained prompts that state paths, facts, boundaries, and completion
  criteria.

## Canonical-instance V-model

- Before authoring any instance field, ask: **world fact/relation or stored
  answer?** Store only the former. Desired placements, pair preferences,
  weights, actions, semantic UI prose, and inferred results are stored answers.
- Descend the V before implementation: product invariant -> canonical boundary
  -> facts -> universal inference laws -> runtime design. At every level, write
  the paired acceptance evidence before moving lower. No lower implementation
  begins while an upper contract is missing or disputed.
- Ascend after implementation: unit checks -> inference-law checks ->
  architecture conformance -> real-schedule checks -> product-invariant
  acceptance.
- Use Sol-only expert panels for adjudication and model decisions. Luna may
  collect evidence, perform mechanical implementation, and run checks; it must
  not decide the ontology or inference boundary.
- Treat [docs/domain-model.md](docs/domain-model.md) as the living contract and
  [the canonical-instance ADR](docs/decisions/canonical-instance-inference-boundary-20260822.md)
  as the governing decision.
