# Subagent Brief — Substance Card Authoring

You are filling **one substance card** in YAML for the supp-slotter project. Read this brief in full before starting.

## Substance vs Product (terminology)

You are describing a **substance** — a chemical compound or extract with its form and traits. Examples: cholecalciferol, magnesium glycinate, methylcobalamin, Lion's Mane (Hericium erinaceus) extract.

You are NOT describing a **product** — a "bottle on the shelf" with a brand name and dose (e.g., "NOW Foods Magnesium Glycinate 400mg"). Brand and dose live in `data/inventory.yaml`, not in your card. The operator handles them.

**Legacy note:** these substance cards currently live under `data/products/` and validate against schema `product`. This is a known terminology lag — see §13 and §24 of `idea.md`. The cards are substance cards regardless of folder name.

## Your task

Given a supplement name (passed as argument from dispatcher), produce one file at `data/products/<id>.yaml` that:
- describes the **substance** (not the branded bottle);
- assigns trait references from a closed taxonomy;
- self-validates via `uv run planner.py check data/products/<id>.yaml`.

Return: only the file path you wrote and a short structured summary (which traits + why, sources, self-check result). Don't paste the file content — the dispatcher will read it.

## Read first (in this order)

1. `idea.md` — system design. Skim §11 (namespaces), §12 (traits format), §13 (substance card format), §22 (this brief in summary).
2. `data/traits.yaml` — the **closed list** of allowed traits with `description` and `applies_when` (with anti-examples).
3. `data/slots.yaml` — slot definitions (you don't write to this, but it tells you which slot properties exist).
4. `data/products/vitamin_d3_k2.yaml` and `data/products/magnesium_glycinate.yaml` — reference cards. Mirror their style.

## Hard rules

- **Use only existing traits from `data/traits.yaml`.** Do not invent new trait identifiers.
- **Do not invent new namespaces.** Registered: `intake:`, `effect:`, `class:`, `family:`, `risk:`. (The `product:` namespace was previously registered but is currently empty and unregistered after the only trait — `product:multicomponent` — was removed; multicomponent products are now signalled by the presence of a `components:` block in the card.)
- **Do not include `dose:` or `brand:` in the card.** Those are operator-managed in inventory.yaml. Schema rejects them.
- **Do not worry about personal sensitivity overrides.** The operator can override the universal taxonomy per-substance via `traits_override: {add: [...], remove: [...]}` in inventory.yaml. Your job is to encode the universal/typical case. If a trait genuinely doesn't apply universally, do not add it — operator handles personal additions.
- **Do not specify slots, weights, or levels in the card.** Those live in `traits.yaml`.
- **Anti-examples are binding.** Each trait's `applies_when` lists what it does NOT apply to ("НЕ применять к..."). If your supplement matches an anti-example, you do NOT use that trait — period. There is no override.
- **When in doubt, omit.** A card with 2 confident traits beats a card with 4 speculative ones.
- **Use `unmatched_concerns` for taxonomy gaps.** If you wanted to express something but no existing trait fits, write a one-line concern instead. Example:

  ```yaml
  unmatched_concerns:
    - "Nootropic / cognitive enhancement — no trait covers this category"
    - "Has neuroprotective effects — separate from sleep_support"
  ```

  These are not errors — they are signals that grow the taxonomy organically.

- **Do not flag allergen concerns.** The operator has confirmed no allergies; allergen-related `unmatched_concerns` are noise for this project.
- **Cite sources in `notes`.** At least one of: NIH ODS, examine.com, peer-reviewed paper, manufacturer label. A few words is enough.

## Soft rules

- Keep `notes` to 1-3 sentences. Form, typical dose range, source, key practical note. Even though `dose` isn't a card field, mentioning a typical range in prose is fine.
- Use snake_case for `id`. Strip vendor names (`lions_mane`, not `nootropics_depot_lions_mane`).
- If the supplement is a single substance, don't include `components`.
- If the supplement is a multicomponent (B-complex, multivitamin), include `components` as a flat dict of `name: "amount unit"` strings. **This is a legacy workaround pending Substance↔Product split (idea.md §24).**

## Self-check (mandatory)

Before finishing, run:

```bash
uv run planner.py check data/products/<id>.yaml
```

- **Exit code 0** → done. Report success.
- **Non-zero exit** → read the errors, fix the file, run again. Repeat until clean.
- **`INFO:` lines about `unmatched_concerns`** are NOT errors. They are correct signals. Pass them through.

## Common mistakes to avoid

1. **Picking `effect:energy_like` for nootropics that aren't stimulants** (Lion's Mane, alpha-GPC, citicoline). Read the `applies_when` carefully — Lion's Mane is in the explicit anti-example list. Also: B-complex and B12 are NOT `effect:energy_like` — folklore connection is not pharmacologically supported.
2. **Picking `intake:requires_food` for things that just *prefer* food.** `requires_food` is reserved for cases where without food the substance is wasted, harmful, or significantly weakened. Use `intake:prefers_food` for "better tolerated with food".
3. **Combining `intake:requires_food` with `intake:prefers_food`** — they are mutually exclusive. Pick the stronger one that fits.
4. **Omitting `risk:manual_review`** for products with real interactions (anything affecting blood clotting, hormones, thyroid, blood sugar, or with narrow therapeutic windows).
5. **Picking `class:fat_soluble` for water-soluble vitamins** (B, C). Anti-examples are explicit in the trait.
6. **Picking `family:magnesium_like` for products where Mg is a trace co-factor.** The trait is for products *primarily* delivering magnesium.
7. **Inventing `product:*` traits.** The `product:` namespace is currently empty (the previous `product:multicomponent` marker was removed — multicomponent products are signalled by the presence of a `components:` block in the card). Do not add new `product:*` traits.

## Output format expected

A single YAML file matching this shape:

```yaml
id: <snake_case_id>
name: "<Human-readable name>"

traits:
  - "<namespace>:<identifier>"
  - "<namespace>:<identifier>"

notes: "Form, typical dose range, key practical note. Source: <NIH/examine/etc>."

# optional
unmatched_concerns:
  - "<one-line concern>"

# optional, only for legacy multicomponent (B-complex, multivitamins)
components:
  ingredient_name: "amount unit"

# optional — soft synergy: scheduler bonuses co-location with these substances
prefer_with:
  - other_substance_id
```

That's it. No `dose`, no `brand`, no additional fields. Schema enforces this strictly.

**`prefer_with` guidance:** use only when there's a real reason to co-locate (operator stacks them in one cup of water, synergistic mechanism, etc). Do NOT speculate ("vitamin C might enhance iron — let's prefer_with"). Symmetric: declare in one direction, planner enforces both. Cross-references are validated — referenced substance must have its own card.
