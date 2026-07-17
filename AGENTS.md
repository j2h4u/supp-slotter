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
