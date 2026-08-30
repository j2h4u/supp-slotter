# Evidence coverage grooming

Grooming is a read-only queue for canonical evidence coverage:

```text
uv run python -m planner groom
```

The queue considers active composition roles that have neither dynamically
applicable canonical evidence nor a completed negative receipt in
`data/grooming-receipts.yaml`, orders them by stable composition-role ID, and
shows at most one role. Each receipt contains exactly a composition role,
assessment date, and the one operational outcome:

- `no_supported_fact` when assessment found no supported canonical fact.

Canonical facts close roles dynamically: a substance target closes every
product component whose exact canonical substance matches, while a
composition-role target closes only that role. Receipt validation rejects
duplicates, unknown roles, and negative receipts newly covered by a fact. A
negative receipt closes its role; removing it reopens the role.

Grooming identifies evidence or applicability gaps only. It does not write
cards, relations, schedules, or conclusions. Evidence collection may produce
candidate sources; only adjudication can admit a canonical fact with provenance.
