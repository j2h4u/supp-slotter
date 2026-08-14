# Deferred from 260509-ka3

## Generate `planner/contracts.py` from JSON Schema

**Source of truth today:** hand-written `planner/contracts.py` + the JSON
schemas under `schema/`. Two artifacts that describe the same on-disk
shape — drift is possible.

**Proposal:** Make JSON Schema the single source of truth. Generate the
dataclass surface from the schemas via `datamodel-code-generator` (or a
~40-LOC ad-hoc generator over `jsonschema.Draft202012Validator`).

**Scope of a follow-up quick task:**

- Add `datamodel-code-generator` to `[dependency-groups.dev]`.
- Configure generator: `output-model-type = "dataclasses.dataclass"`,
  frozen + slots, tuple-not-list for arrays, Literal aliases for
  enum-constrained strings.
- Generate `planner/contracts_generated.py` from `schema/*.schema.json`
  on each schema change. Commit the generated file.
- Replace `planner/contracts.py` with a thin wrapper that re-exports
  generated dataclasses + adds the synthetic-field types that aren't in
  the schemas (`Slot` joined fields `pillbox`/`pillbox_label`/`stack`,
  `FindResult` NamedTuple, `CardLoadError` exception, `SlotNear` /
  `RelationType` Literal aliases if codegen didn't emit them).
- CI gate: `uv run datamodel-codegen --check` to fail when the
  committed generated file is stale relative to the schemas.

**Why deferred (not in 260509-ka3):**

- 260509-ka3 ships hand-written contracts that are type-equivalent to
  what codegen would produce — they're not throwaway. Switching to
  codegen later is a non-destructive replacement.
- Mid-task swap of the contracts surface would break T1 atomicity and
  blur the "dataclass migration + strict pyright" focus.
- Codegen is a separate architectural improvement worth its own task
  with its own CI drift-detection gate.

**Trigger:** When a schema is next modified (new field, changed enum),
or when a hand-written / schema mismatch surfaces a real bug.
