# Agent Stack Review

This document defines the expert-panel and optimization workflows for the active stack. It is for informational analysis and repository guidance, not medical advice.

## Start From Existing Surfaces

Do not build an ad hoc aggregate command or script unless the current surfaces cannot answer the question. Start with:

```bash
uv run python -m planner review
uv run python -m planner audit --full
uv run python -m planner
```

Use `planner review` first. Its `Review brief` is the panel intake surface: active concerns, actionable relation count, active relation context, risk-flag count, and dashboard coverage summary. Use the detailed sections below it for concerns, relations, risk flags, pathways, and dashboard counts.

Use `planner audit --full` for data-quality drilldown, especially active product source URLs, product notes, component amounts, generic/form-specific card issues, and intake/classification review.

Use `schedule.yaml` for generated slot placement, humanized warnings, placement notes, and explanations. Do not edit it directly.

## Source Completion Before Reporting Unknowns

Before treating an amount, form, marker, or standardization as unknown:

- inspect the product card `components`, `notes`, and `urls`;
- open existing manufacturer or retailer label URLs when available;
- if the card has no usable source URL, search for the exact brand + product + supplement facts/label;
- add the best reliable source URL to the product card when evidence is good;
- prefer official manufacturer labels, then exact retailer label pages/images;
- use secondary listings only when clearly identified;
- add a `data_quality` concern if sources conflict.

Only report "amount unknown" after this source pass fails or sources conflict in a way that cannot be resolved safely.

## Full Stack Expert Panel

Use this workflow when the user wants a structured qualitative review of the active stack.

Good triggers:

- "evaluate my stack", "what do experts think", "is this protocol good";
- significant stack changes;
- stated symptoms or health goals;
- periodic grooming of a mature stack.

Before convening, gather relevant user context: motivating health history, active symptoms, current medications, prescription items in the stack and their dose/intent, training type/frequency, and available labs or wearable markers.

Standard panel composition:

| Role | Focus |
|------|-------|
| Evidence-Based Medicine physician | Evidence strength and clinical plausibility |
| Clinical Pharmacologist | Drug-supplement interactions, PK/PD, safety flags |
| Cardiologist / Vascular Medicine | Vascular, cardiovascular, and blood-pressure goals |
| Biochemist | Metabolic pathways, nutrient forms, synergies, antagonisms |
| Exercise Physiologist | Training-adjacent components, timing, ergogenic logic |
| Translational Medicine physician | Mechanistic plausibility and gap analysis |

Add or replace roles based on the user's context, such as Hepatologist for liver markers or Endocrinologist for thyroid/hormonal context.

Pass to the panel:

- `planner review` brief and relevant detailed sections;
- `planner audit --full` active product source gaps and product-quality blockers;
- slot layout from `schedule.yaml`;
- user health context and symptoms from `docs/private/`;
- explicit framing that this is informational analysis, not medical advice.

If panel members formulate questions for the user, surface them clearly and wait for answers before delivering the final assessment.

## Default Report Form

The default artifact is a **General Narrative Report**. Use this first unless the user explicitly asks for a technical breakdown. Write it as a plain-language narrative from the expert group, typically in the voice of a sports physician working with a supplement-focused clinician.

Start with a short **TL;DR** paragraph that states the overall judgment before details.

General Narrative Report rules:

- Lead with practical interpretation, not a findings table.
- Explain what the stack appears to be trying to do, what is strong, and where it becomes dense, opaque, or hard to manage.
- Use ordinary language and concrete examples.
- Expand non-obvious abbreviations on first mention: "L-Carnitine L-Tartrate (LCLT)" before `LCLT`; same for ALCAR, AAKG, PQQ, NR, and similar shorthand.
- Separate repo-confirmed facts from medical inference when it matters.
- Mention safety/lab follow-up as review points, not medical orders.
- Keep technical identifiers, line refs, and exhaustive categories out of the main narrative unless needed for clarity.

Only if the user asks for more detail, produce a **Technical Findings Report** with severity buckets, goal coverage, product-quality findings, model gaps, source links, and implementation-style follow-up lists.

For either report type, distill panel consensus into what works, priority gaps, safety items requiring monitoring or physician discussion, and useful baseline lab markers.

Do not encode panel recommendations into data files without explicit user instruction. Panel output is advisory, not automatic.

## Stack Optimization Ceremony

This is a focused variant of the expert panel: one session, narrow recommendations, no full-stack review. Use it when the stack is mature and the user wants incremental improvement.

Good triggers:

- "what's obviously missing";
- "what should I add next";
- "what's the weakest thing";
- follow-up after a full panel session;
- periodic lightweight check between full reviews.

Recommendation dimensions:

1. **Add** — one substance with the highest evidence-to-impact ratio for this specific user profile.
2. **Remove** — the weakest link: weakest evidence, redundancy, or unfavorable risk/benefit given the active stack.
3. **Replace** — optional product-level recommendation, only when clearly justified by form, dose, tolerance, safety, evidence, or label ambiguity.

Do not recommend a replacement just because an alternative exists.

Before convening, collect:

- `planner review` brief;
- `planner audit --full` source/product blockers;
- slot layout and dashboard summary;
- what changed since the last panel;
- symptoms/labs that changed;
- previous panel recommendations not yet acted on.

The panel resolves add/remove conflicts using this priority ladder:

1. Safety.
2. Evidence strength.
3. Specificity to user profile.
4. Cluster state: no current members > shelf/knowledge-only candidates > already current.
5. Redundancy signal.

If consensus is impossible, surface the conflict explicitly and ask the user to resolve it.

Save optimization output to `docs/private/expert-panel-YYYY-MM.md`. Include the user health profile snapshot, stack at time of session, panel composition, add/remove rationale, justified replacements, and carry-forward agenda.

Same boundary as full panel: informational analysis, not medical advice. Prescription items require physician discussion. Do not modify data files without explicit user confirmation.
