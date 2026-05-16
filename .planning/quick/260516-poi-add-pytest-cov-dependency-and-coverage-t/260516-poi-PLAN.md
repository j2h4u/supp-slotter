---
phase: quick-260516-poi
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - pyproject.toml
  - uv.lock
  - justfile
autonomous: true
requirements:
  - "QUICK-260516-POI-01: pytest-cov wired into dev deps and locked"
  - "QUICK-260516-POI-02: coverage config defined in pyproject.toml"
  - "QUICK-260516-POI-03: just coverage recipe runs suite with coverage + fails below threshold"
  - "QUICK-260516-POI-04: threshold set from measured baseline (not arbitrary)"

must_haves:
  truths:
    - "pytest-cov appears in [dependency-groups].dev in pyproject.toml"
    - "pytest-cov is present in uv.lock"
    - "pyproject.toml contains [tool.coverage.run] with source = ['planner']"
    - "pyproject.toml contains [tool.coverage.report] with a numeric fail_under value"
    - "justfile defines a `coverage` recipe"
    - "`just coverage` exits 0 against the current codebase"
    - "`just check` still passes (107/107 tests, ruff clean, pyright 0/0/0)"
    - "fail_under is strictly less than 100 (no 100% anti-pattern)"
    - "fail_under is ≤ the measured baseline (recipe must pass on the unmodified codebase)"
  artifacts:
    - path: "pyproject.toml"
      provides: "pytest-cov dev dep + coverage tool config"
      contains: "pytest-cov"
    - path: "pyproject.toml"
      provides: "coverage source declaration"
      contains: "[tool.coverage.run]"
    - path: "pyproject.toml"
      provides: "coverage threshold declaration"
      contains: "fail_under"
    - path: "uv.lock"
      provides: "Locked pytest-cov version"
      contains: "pytest-cov"
    - path: "justfile"
      provides: "coverage recipe"
      contains: "coverage:"
  key_links:
    - from: "justfile (coverage recipe)"
      to: "[tool.coverage.*] in pyproject.toml"
      via: "pytest --cov reads pyproject config automatically"
      pattern: "--cov=planner"
    - from: "[tool.coverage.run].source"
      to: "planner/ package"
      via: "coverage measures only planner/, not tests/ or scripts/"
      pattern: "source.*planner"
---

<objective>
Wire `pytest-cov` into the project so test coverage on the `planner/` package is
measured and enforced via a single `just coverage` recipe. The threshold is
chosen from the actual measured baseline so the gate is honest from day one.

Purpose: close the "No enforced coverage metric" gap from
`.planning/codebase/CONCERNS.md` — give the project a local drift detector
without writing new tests in this task.

Output:
- `pytest-cov` added to dev deps (lower-bound only, recent stable)
- `[tool.coverage.run]` and `[tool.coverage.report]` config in `pyproject.toml`
- `just coverage` recipe that runs the suite with coverage and enforces threshold
- `uv.lock` regenerated atomically with `pyproject.toml`
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/STATE.md
@pyproject.toml
@justfile

<interfaces>
<!-- Current pyproject.toml shape (line-extract; not a copy-paste target) -->
<!-- [dependency-groups].dev currently lists: pytest>=8, ruff>=0.7, pyright>=1.1.380 -->
<!-- [tool.ruff], [tool.ruff.lint], [tool.pyright] already exist as siblings -->
<!-- requires-python = ">=3.14" -->

<!-- justfile already has: default, test, lint, lint-fix, typecheck, check, fmt -->
<!-- The `test` recipe runs: `uv run python -m planner check` then `uv run pytest tests/` -->
<!-- The `coverage` recipe should be a sibling, NOT replacing `test` -->

<!-- Package layout: -->
<!--   planner/        ← runtime code (coverage target) -->
<!--   tests/          ← omit from coverage source -->
<!--   scripts/        ← one-shot migration scripts, out of scope per task brief -->

<!-- pytest-cov latest stable on PyPI: 7.1.0 (queried 2026-05-16). -->
<!-- Use lower bound `pytest-cov>=7` to match the existing dep style (pytest>=8, ruff>=0.7, pyright>=1.1.380). -->
</interfaces>
</context>

<tasks>

<task type="auto">
  <name>Task 1: Add pytest-cov dep, coverage config, and just coverage recipe (atomic)</name>
  <files>pyproject.toml, uv.lock, justfile</files>
  <action>
    Make the three files cohere as a single change. Order of operations matters
    because the threshold value depends on the measured baseline.

    Step 1 — Add `pytest-cov>=7` to `[dependency-groups].dev` in `pyproject.toml`
    (alongside the existing pytest/ruff/pyright entries). Lower bound only,
    matching project convention. Do NOT pin an exact version. Justification:
    pytest-cov 7.1.0 is the current stable on PyPI as of 2026-05-16; `>=7`
    follows the same lower-bound style used for pytest/ruff/pyright.

    Step 2 — Run `uv sync` to regenerate `uv.lock` with the new dep. This must
    be a real lock update, not a manual edit. Do not pass `--upgrade` (that
    bumps unrelated deps); a plain `uv sync` adds pytest-cov and leaves the
    rest alone.

    Step 3 — Add coverage config to `pyproject.toml` as a new top-level table
    block (sibling to `[tool.ruff]`, `[tool.pyright]`). Use the `[tool.coverage.*]`
    namespace, not `[tool.pytest.ini_options]`, because the project has no other
    pytest config and the coverage namespace is the canonical home for
    source/omit/threshold:
      - `[tool.coverage.run]` with `source = ["planner"]` and
        `omit = ["tests/*", "scripts/*", "planner/__main__.py"]`.
        Rationale: `tests/*` is the test suite (not runtime); `scripts/*` is
        explicitly out of scope per the task brief (one-shot migration scripts);
        `planner/__main__.py` is the CLI entry shim and is exercised end-to-end,
        not via unit tests — including it skews the metric without adding signal.
      - `[tool.coverage.report]` with `show_missing = true`, `skip_covered = false`,
        and `fail_under = <threshold>` (placeholder — set in Step 5). Do NOT
        enable branch coverage (`branch = true`) — out of scope per task brief.

    Step 4 — Measure baseline. Run:
      `uv run pytest tests/ --cov=planner --cov-report=term-missing`
    Read the `TOTAL` line percentage. This is the measured baseline.
    Record this number — it goes into the SUMMARY for traceability.

    Step 5 — Set `fail_under` in `[tool.coverage.report]` to `baseline - 2`
    rounded down to an integer (e.g. baseline 92.4% → fail_under = 90).
    Hard floor: never set above 99 (the 100% anti-pattern is forbidden per
    task brief). If baseline is below 50%, set fail_under = baseline_floor - 2
    anyway and surface the low number in the SUMMARY — the gate is for drift
    detection, not aspirational targets.

    Step 6 — Add a `coverage` recipe to `justfile` as a sibling to the existing
    recipes (insert between `typecheck` and `check`, or after `fmt` — either
    is fine; consistent with file ordering matters more than position).
    The recipe runs:
      `uv run pytest tests/ --cov=planner --cov-report=term-missing`
    pytest-cov reads `fail_under` from `[tool.coverage.report]` automatically,
    so no `--cov-fail-under` flag is needed on the command line. This keeps
    the threshold value single-sourced in `pyproject.toml`.

    Do NOT modify the existing `test` recipe — `just test` stays fast and
    coverage-free. `just check` stays unchanged (lint + typecheck + test).
    `just coverage` is opt-in / pre-commit / drift-check.
  </action>
  <verify>
    <automated>uv sync &amp;&amp; just check &amp;&amp; just coverage &amp;&amp; grep -q 'pytest-cov' pyproject.toml &amp;&amp; grep -q 'pytest-cov' uv.lock &amp;&amp; grep -q '\[tool.coverage.run\]' pyproject.toml &amp;&amp; grep -q 'fail_under' pyproject.toml &amp;&amp; grep -q '^coverage:' justfile</automated>
  </verify>
  <done>
    - `pytest-cov>=7` present in `[dependency-groups].dev` in pyproject.toml
    - `uv.lock` contains a `pytest-cov` entry (regenerated by `uv sync`, not hand-edited)
    - `[tool.coverage.run]` block exists in pyproject.toml with `source = ["planner"]` and `omit` excludes `tests/*`, `scripts/*`, `planner/__main__.py`
    - `[tool.coverage.report]` block exists with `fail_under` set to (measured_baseline - 2), integer, ≤ 99
    - `just coverage` recipe exists, runs `uv run pytest tests/ --cov=planner --cov-report=term-missing`, and exits 0
    - `just check` still passes (107/107 tests, ruff clean, pyright 0/0/0)
    - SUMMARY records: measured baseline %, chosen fail_under value, pytest-cov version locked
  </done>
</task>

</tasks>

<verification>
After the task completes:

1. `just check` exits 0 — invariant preserved.
2. `just coverage` exits 0 — new gate green on the unmodified codebase.
3. `grep -c 'pytest-cov' pyproject.toml uv.lock` both ≥ 1.
4. `grep -E '^(coverage|test|check):' justfile` shows `coverage` as a distinct recipe.
5. `uv run python -c "import coverage; print(coverage.__version__)"` succeeds — confirms the dep is actually installed in the env, not just locked.
6. Threshold sanity: `grep fail_under pyproject.toml` shows a numeric value between 1 and 99.
</verification>

<success_criteria>
- pytest-cov is a declared, locked dev dep (lower-bound only, recent stable)
- Coverage config lives in `pyproject.toml` (single source of truth — no CLI-flag duplication of the threshold)
- `just coverage` recipe exists, exits 0 today, and will fail if coverage drops by &gt;2 points
- Threshold value is honest: derived from a measured baseline, not invented
- `just check` and existing test invariants unchanged
- `pyproject.toml` and `uv.lock` updated atomically in the same commit
</success_criteria>

<output>
Create `.planning/quick/260516-poi-add-pytest-cov-dependency-and-coverage-t/260516-poi-SUMMARY.md` when done.

SUMMARY must record:
- Measured baseline coverage % (the actual `TOTAL` from the first `--cov` run)
- Chosen `fail_under` value and the gap to baseline
- pytest-cov version that landed in uv.lock
- Any omit-list deviations from the plan and why
</output>
