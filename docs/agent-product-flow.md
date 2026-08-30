# Agent Product Flow

This is the active workflow for adding products and maintaining the canonical
planning inputs. It is not medical advice. [Domain Model](domain-model.md)
owns field meaning; historical decision records remain historical evidence,
not authoring instructions.

## The planning boundary

The runtime has one causal path:

```text
world facts -> universal laws -> normalized pressures -> exact optimizer -> Optimal publisher
```

Store only world facts and relations. Product identity, ingredient/form
identity, components, stack membership, slot anchors, evidence provenance, and
admitted canonical facts are world facts. Desired placement, pair preference,
weights, actions, presentation prose, and inferred layouts are stored answers;
do not write them into a product or substance card.

Canonical facts belong in `ontology/canonical-facts.yaml`, scoped to the
appropriate stable entity or composition role. Universal laws belong in
`ontology/canonical-laws.yaml`; a law maps a closed fact family to one pressure
dimension/value and must never encode a particular product's preferred slot.

The optimizer maximizes unique pressure identities, then minimizes integer
squared load independently in each unbounded logical domain, then applies the
stable assignment tie-break. It publishes only a globally proved `Optimal`
layout. A same-dimension conflict or any unproved optimization result is
layout-free `Indeterminate`.

## Author a new product or substance

1. Capture the physical label losslessly: bottle-facing name, manufacturer,
   label components/forms, source URL, and relevant notes. Keep a product name
   commercial and concise; route amounts and formulation details to their
   dedicated fields.
2. Search for the exact product and concrete substance/form identity with
   `uv run python -m planner find "<name form alias>"`. Reuse the existing
   identity when it matches; do not create spelling variants or generic parent
   cards.
3. Add or update the product and substance cards with only their own facts.
   Select stack membership deliberately. Slots are unbounded logical groups,
   not physical compartments or biological claims.
4. For an active item, collect evidence separately from semantic adjudication.
   Preserve source/provenance and admit a canonical fact only when it is true
   for the fact's declared subject and scope. Record uncertainty without
   inventing a fact.
5. Add a universal law only after establishing its closed family and pressure
   mapping. Do not turn a desired schedule, a pairing, a policy annotation, or
   a reviewer conclusion into a law.
6. Run `uv run python -m planner check`, then `uv run python -m planner`.
   Inspect either the proof-bearing `Optimal` output or the `Indeterminate`
   diagnostics before making another source change.

## Fact-admission rules

- A fact is scoped either to a reusable substance/form or to a stable
  composition role when it is product/formulation specific.
- Evidence witnesses and repeated components may explain a pressure, but they
  never multiply its objective weight. Pressure identity is exactly
  `(item_id, dimension, value)`.
- Independent `meal_context`, `circadian_anchor`, and `exercise_anchor` facts
  may coexist. Labels such as breakfast or sleep have no implicit biological
  meaning beyond their typed anchors.
- A conflicting value in one item/dimension is a failure to infer, not a
  request to choose a compromise placement.
- Review facts and concerns can guide human review but cannot add, remove, or
  rank a placement unless admitted through the canonical fact-and-law path.

## Review and private context

Keep user-specific health history, symptoms, medicines, goals, and proposal
notes in gitignored `docs/private/`. Do not convert them into tracked ontology
facts or active stack changes without explicit approval.

Review output is for inspection of authored relations, concerns, provenance,
and inferred pressure proofs. It is not an instruction to treat an inferred
layout as medical advice.

## Completion checklist

- [ ] Label and concrete identities are accurate and reused where possible.
- [ ] Every edited card contains only its own world facts.
- [ ] New canonical facts have a stable subject/scope and provenance.
- [ ] A proposed law is universal and maps only facts to pressures.
- [ ] No desired placement, pair preference, weight, or policy answer was
      authored as a fact.
- [ ] `planner check` passes and the planner result is inspected as `Optimal`
      or layout-free `Indeterminate`.
- [ ] The targeted runtime or formal `just` recipe matches the edited boundary.
