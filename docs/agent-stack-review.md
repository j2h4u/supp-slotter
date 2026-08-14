# Agent Stack Review

This document defines stack review and optimization workflows. It is for
informational analysis and repository guidance, not medical advice.

## Start From Existing Surfaces

Do not build an ad hoc aggregate command or script unless the current surfaces
cannot answer the question. Start with:

```bash
uv run python -m planner review
uv run python -m planner
```

Use `planner review` first. Its `Review brief` is the intake surface: active
concerns, actionable relation count, active relation context, risk-flag count,
and dashboard coverage summary. Use the detailed sections below it for
concerns, relations, risk flags, pathways, and dashboard counts.

Use `schedule.yaml` for generated slot placement, humanized warnings, placement
notes, and explanations. Do not edit it directly.

Use `planner audit --full` only when product source URLs, label notes, forms,
or component amounts matter for the current review. Unknown amounts are
acceptable when the current question does not depend on them.

## Source Completion

In read-only review mode, report source gaps and candidate URLs as proposed
edits. Do not write product cards unless the user has approved data enrichment.

Before treating an amount, form, marker, or standardization as unknown:

- inspect the product card `components`, `notes`, and `urls`;
- open existing manufacturer or retailer label URLs when available;
- if the card has no usable source URL, search for the exact brand + product +
  supplement facts/label;
- prefer official manufacturer labels, then exact retailer label pages/images;
- use secondary listings only when clearly identified;
- report conflicting sources as a data-quality issue.

In approved enrichment mode, add the best reliable source URL to the product
card when evidence is good. Do not create `data_quality` concerns solely because
a label omits per-component amounts; add them only when source conflict or
missing label data blocks a concrete review or product decision.

## Review Lenses

Use this workflow when the user wants a qualitative review of the active stack.
The default is a practical **Stack Review Synthesis**, not a simulated medical
consultation.

Good triggers:

- "evaluate my stack", "what do experts think", "is this protocol good";
- significant stack changes;
- stated symptoms or health goals;
- periodic grooming of a mature stack.

Before reviewing, gather relevant context when available: motivating goals,
active symptoms, current medications, prescription items in the stack and their
intent, training type/frequency, and available labs or wearable markers.

Default lenses:

| Lens | Focus |
|------|-------|
| Practical stack reviewer | Current active products, schedule, warnings, and obvious friction |
| Evidence sanity check | Whether a recommendation claim is stronger than the repository supports |
| Interaction safety | Drug-supplement, additive-load, and monitoring flags surfaced by the repo |
| Biochemistry/form lens | Forms, pathways, cofactors, synergies, and antagonisms |
| Training/use-case lens | Workout timing, ergogenic logic, recovery, and burden |
| Kaizen lens | Smallest useful next change; avoid overfitting and ceremony |

Use clinical specialist roles only when the user explicitly asks for that
format or the question genuinely needs that lens. Even then, frame the output
as informational review, not diagnosis or treatment.

Pass to the review:

- `planner review` brief and relevant detailed sections;
- slot layout from `schedule.yaml`;
- source-completion findings from `planner audit --full` only when relevant;
- user context from `docs/private/`;
- explicit framing that this is informational analysis, not medical advice.

If reviewers formulate questions for the user, surface them clearly and wait
for answers before delivering the final assessment when the answers would
change the recommendation.

## Default Report Form

The default artifact is a **General Narrative Report**. Use this first unless
the user explicitly asks for a technical breakdown. Write it as a plain-language
narrative from the review group.

Start with a short **TL;DR** paragraph that states the overall judgment before
details.

General Narrative Report rules:

- Lead with practical interpretation, not a findings table.
- Explain what the stack appears to be trying to do, what is strong, and where
  it becomes dense, opaque, or hard to manage.
- Use ordinary language and concrete examples.
- Expand non-obvious abbreviations on first mention: "L-Carnitine L-Tartrate
  (LCLT)" before `LCLT`; same for ALCAR, AAKG, PQQ, NR, and similar shorthand.
- Separate repo-confirmed facts from medical inference when it matters.
- Mention safety/lab follow-up as review points, not medical orders.
- Keep technical identifiers, line refs, and exhaustive categories out of the
  main narrative unless needed for clarity.

Only if the user asks for more detail, produce a **Technical Findings Report**
with severity buckets, goal coverage, product-quality findings, model gaps,
source links, and implementation-style follow-up lists.

For either report type, distill consensus into what works, priority gaps,
safety items requiring monitoring or physician discussion, and useful baseline
markers.

Do not encode recommendations into data files without explicit user
instruction. Review output is advisory, not automatic.

## Stack Optimization Session

This is a focused variant of stack review: one session, narrow recommendations,
no full-stack report. Use it when the stack is mature and the user wants
incremental improvement.

Good triggers:

- "what's obviously missing";
- "what should I add next";
- "what's the weakest thing";
- follow-up after a full review;
- periodic lightweight check between full reviews.

Recommendation dimensions:

1. **Add** — one substance or product change with the highest evidence-to-impact
   ratio for this profile.
2. **Remove** — the weakest link: weakest evidence, redundancy, or unfavorable
   risk/benefit given the active stack.
3. **Replace** — optional product-level recommendation, only when clearly
   justified by form, tolerance, safety, evidence, or label ambiguity.

Do not recommend a replacement just because an alternative exists.

Before reviewing, collect:

- `planner review` brief;
- slot layout and dashboard summary;
- source/product blockers only if relevant;
- what changed since the last review;
- symptoms/labs that changed;
- previous recommendations not yet acted on.

Resolve add/remove conflicts using this priority ladder:

1. Safety.
2. Evidence strength.
3. Specificity to user profile.
4. Cluster state: no current members > shelf/knowledge-only candidates > already current.
5. Redundancy signal.

If consensus is impossible, surface the conflict explicitly and ask the user to
resolve it.

Save optimization output to `docs/private/stack-review-YYYY-MM.md`. Include the
user profile snapshot, stack at time of session, review lenses used, add/remove
rationale, justified replacements, and carry-forward agenda.

Same boundary as full review: informational analysis, not medical advice.
Prescription items require physician discussion. Do not modify data files
without explicit user confirmation.
