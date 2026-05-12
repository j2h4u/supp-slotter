#!/usr/bin/env python3
"""One-shot substance card quality audit.

Checks that go beyond planner audit:
  1. Stub cards — name-only (no form) alongside specific-form siblings
  2. Missing is: classification entirely
  3. Missing intake: trait entirely
  4. Intake review candidates — is: classification suggests an intake trait
     worth verifying; NOT automatic violations (correlation, not hard rules)
  5. Relations.yaml integrity — unknown names/IDs

Run: uv run python scripts/card_audit.py
"""

from __future__ import annotations

from collections import defaultdict

from planner.cards.product import load_product_registry
from planner.cards.relations import load_global_relations
from planner.cards.substance import format_substance_name, load_substance_registry

# ── Review hints: is: slug → acceptable intake slugs ─────────────────────────
# These are correlations from traits.yaml applies_when, NOT hard rules.
# A substance missing the acceptable set is worth a human look, not a bug.
#
# mineral:    most minerals benefit from food for GI tolerance; but some forms
#             (organic chelates, low-dose trace minerals) may be genuinely neutral
# fat_soluble: fat-dependent absorption suggests fat_meal_required; food_required
#              is accepted as "at least requires food" (less specific but not wrong)
# enzyme:     systemic enzymes work better on empty stomach; digestive enzymes
#             are intentionally taken with food — this is a prompt, not a verdict
INTAKE_REVIEW_HINTS: dict[str, set[str]] = {
    "mineral": {"food_preferred", "food_required"},
    "fat_soluble": {"fat_meal_required", "food_required"},
    "enzyme": {"empty_preferred"},
}

# ── Load data ─────────────────────────────────────────────────────────────────
substances = load_substance_registry()
products = load_product_registry()
relations = load_global_relations()

product_substance_refs: set[str] = set()
for product in products.values():
    for comp in product.components:
        product_substance_refs.add(comp.substance)

# ── 1. Stub cards ─────────────────────────────────────────────────────────────
by_name: dict[str, list[tuple[str, object]]] = defaultdict(list)
for sid, sub in substances.items():
    by_name[sub.name.strip()].append((sid, sub))  # type: ignore[arg-type]

stubs: list[dict] = []
for name, entries in sorted(by_name.items()):
    no_form = [(sid, s) for sid, s in entries if not s.form]  # type: ignore[attr-defined]
    with_form = [(sid, s) for sid, s in entries if s.form]  # type: ignore[attr-defined]
    if no_form and with_form:
        for sid, _ in no_form:
            stubs.append({
                "name": name,
                "id": sid,
                "used": sid in product_substance_refs,
                "forms": sorted(sf.form for _, sf in with_form),  # type: ignore[attr-defined]
            })

# ── 2. Missing / implied fields ───────────────────────────────────────────────
missing_classification: list[str] = []
missing_intake: list[str] = []
intake_review: list[tuple[str, str, str, str]] = []  # name, id, is_slug, detail

for sid, sub in sorted(substances.items(), key=lambda x: x[1].name.casefold()):  # type: ignore[attr-defined]
    display = format_substance_name(sub)  # type: ignore[arg-type]
    is_set = set(sub.is_)  # type: ignore[attr-defined]
    intake_set = set(sub.intake)  # type: ignore[attr-defined]

    if not is_set:
        missing_classification.append(f"{display} [{sid}]")

    if not intake_set:
        missing_intake.append(f"{display} [{sid}]")
    else:
        for is_slug, acceptable in INTAKE_REVIEW_HINTS.items():
            if is_slug in is_set and not (intake_set & acceptable):
                intake_review.append((
                    display, sid, is_slug,
                    f"is:{is_slug}, intake: {sorted(intake_set)} — none of {sorted(acceptable)} set",
                ))

# ── 3. Relations integrity ────────────────────────────────────────────────────
name_set = {s.name for s in substances.values()}  # type: ignore[attr-defined]
id_set = set(substances.keys())

relation_errors: list[str] = []
for rel in relations:
    if rel.source_name and rel.source_name not in name_set:
        relation_errors.append(f"unknown source_name '{rel.source_name}' in {rel.type}")
    if rel.target_name and rel.target_name not in name_set:
        relation_errors.append(f"unknown target_name '{rel.target_name}' in {rel.type}")
    if rel.source_substance and rel.source_substance not in id_set:
        relation_errors.append(f"unknown source_substance '{rel.source_substance}' in {rel.type}")
    if rel.target_substance and rel.target_substance not in id_set:
        relation_errors.append(f"unknown target_substance '{rel.target_substance}' in {rel.type}")

# ── Print report ──────────────────────────────────────────────────────────────
SEP = "─" * 60

def section(title: str, items: list, indent: int = 2) -> None:
    pad = " " * indent
    print(f"\n{title} ({len(items)})")
    print(SEP)
    if not items:
        print(f"{pad}(none)")
        return
    for item in items:
        print(f"{pad}{item}")


print("=" * 60)
print("SUBSTANCE CARD AUDIT")
print("=" * 60)

section(
    "1. Stub cards — no form while specific forms exist",
    [
        f"{'[USED] ' if s['used'] else '[ORPHAN]'} {s['name']} ({s['id']}) "
        f"→ forms: {', '.join(s['forms'])}"
        for s in stubs
    ],
)

section(
    "2. Missing is: classification",
    missing_classification,
)

section(
    "3. Missing intake: trait entirely",
    missing_intake,
)

section(
    "4. Intake review candidates (is: set but no expected intake variant)",
    [f"{name} [{sid}]: {detail}" for name, sid, _, detail in intake_review],
)

section(
    "5. Relations.yaml integrity errors",
    relation_errors,
)

print(f"\nTotal substances audited: {len(substances)}")
print(f"Total relations audited:  {len(relations)}")
