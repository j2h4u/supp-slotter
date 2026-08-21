# Evidence coverage and card grooming

Grooming is a read-only evidence hand-off. The public command is:

```text
uv run python -m planner groom
```

It accepts no state, limit, queue, or batch arguments and selects at most one
substance card. The executable selection contract is authored in
`ontology/runtime-policy.yaml` and loaded from the generated runtime program:

- work unit: `substance_card`;
- eligibility: active-reachable and at least one unassessed owned item;
- rank: `active_unique_product_count` descending,
  `open_owned_item_count` descending, then `substance_id` ascending;
- selection count: exactly one;
- an open relation belongs to the lowest stable ID among its resolved active
  endpoints, and is counted and shown once.

The result is a complete dossier for the selected card. It includes the card's
identity, source path, aliases, form, notes, active products and component
context, every knowledge assertion with its research state and sources, owned
open relation leads, authored scheduling assertions, and every scheduling
assessment axis and conclusion. Missing assessment axes are explicitly shown as
open. Open knowledge and relation items retain their `unassessed` state.

The command never writes cards, relations, schedules, or research conclusions.
It only prepares a bounded evidence unit for review. The evidence collector may
gather candidate sources; an adjudicator decides whether a claim is admitted.
Only admitted facts are written to the authoritative substance or relation
cards, with their provenance and state preserved. Insufficient, anecdotal, or
mechanistic evidence remains visible rather than being promoted to a scheduler
rule.

Grooming priority is workflow ROI: improving a card used by more active products
improves more current explanations or scheduling context. It is not a medical
importance score and does not change scheduling semantics or product placement.
