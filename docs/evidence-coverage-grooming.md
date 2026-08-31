# Evidence coverage grooming

Grooming is a read-only queue for canonical evidence coverage:

```text
uv run python -m planner groom
```

The queue validates the closed `data/scheduling-candidates.yaml` catalog and
the global `data/coverage-closure.yaml` receipt. The receipt binds the 354
legacy-note spans/1073 atoms, 191 passive structured memberships, 34 passive
relations, and the active role universe to exact hashes. A role with no matching
candidate is complete when that global closure is valid; grooming never creates
a fake per-role candidate. A candidate is closed only by exactly one of
`pressure`, `neutral`, `unresolved_without_direction`, or `outside_model`.
The last disposition is explicitly research-open but coverage-closed; it is
not silently converted to neutral. Missing, malformed, or stale catalog and
closure records are surfaced as a stale/unclosed source class and planning
fails closed after disposing of any stale schedule output.

Grooming identifies evidence or applicability gaps only. It does not write
cards, relations, schedules, or conclusions. Evidence collection may produce
candidate sources; only adjudication can admit a canonical fact with provenance.
