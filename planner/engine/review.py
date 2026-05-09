"""`review-substance` command: trait checklist for one substance card."""

from __future__ import annotations

import sys
from pathlib import Path

from planner.cards.relations import print_central_relation_matches
from planner.cards.substance import (
    format_substance_name,
    load_substance,
    load_substance_registry,
)
from planner.cards.traits import (
    grouped_trait_defs,
    load_traits,
    print_trait_details,
)
from planner.contracts import CardLoadError
from planner.io import (
    DATA_DIR,
    ROOT,
    SUBSTANCES_DIR,
    display_message,
    display_path,
    validate_schemas,
)


def cmd_review_substance(target: str) -> int:
    path = Path(target)
    if not path.is_absolute():
        path = ROOT / path

    try:
        resolved = path.resolve(strict=True)
    except FileNotFoundError:
        print(f"{display_path(path)}: file not found", file=sys.stderr)
        return 1

    substances_root = SUBSTANCES_DIR.resolve()
    try:
        resolved.relative_to(substances_root)
    except ValueError:
        print(
            f"{display_path(path)}: review-substance only accepts paths "
            f"inside {display_path(SUBSTANCES_DIR)}/",
            file=sys.stderr,
        )
        return 1

    if resolved.suffix != ".yaml":
        print(
            f"{display_path(path)}: review-substance only accepts .yaml files",
            file=sys.stderr,
        )
        return 1

    schema_result = validate_schemas()
    if schema_result != 0:
        return schema_result

    path = resolved
    try:
        substance = load_substance(path)
    except CardLoadError as e:
        print(display_message(e.message), file=sys.stderr)
        return 1

    try:
        trait_defs = load_traits(DATA_DIR / "traits.yaml")
    except CardLoadError as e:
        print(display_message(e.message), file=sys.stderr)
        return 1
    if not trait_defs:
        print("data/traits.yaml: no traits found", file=sys.stderr)
        return 1

    current_traits = set(substance.traits)

    print(f"Substance review: {format_substance_name(substance)}")
    print(f"File: {display_path(path)}")
    if substance.id:
        print(f"ID: {substance.id}")
    if substance.aliases:
        print("Aliases: " + ", ".join(substance.aliases))
    print_central_relation_matches(substance, load_substance_registry())
    print()
    print("Before editing traits, scan this checklist and mark only source-backed facts.")
    print("If a fact matters but no trait fits, use unmatched_concerns.")
    print("Put substance-to-substance relations in data/relations.yaml, not in this card.")
    print()
    print("Traits")
    for namespace, traits in grouped_trait_defs(trait_defs).items():
        print(f"\n{namespace}")
        for trait in traits:
            marker = "x" if trait.id in current_traits else " "
            label_text = f" - {trait.label}" if trait.label else ""
            print(f"  [{marker}] {trait.short_name}{label_text}")
            print_trait_details(trait)

    unknown_traits = sorted(current_traits - set(trait_defs), key=str.casefold)
    if unknown_traits:
        print("\nunknown")
        for trait_id in unknown_traits:
            print(f"  [x] {trait_id}")

    print("\nUnmatched concerns")
    if substance.unmatched_concerns:
        for concern in substance.unmatched_concerns:
            print(f"  - {concern}")
    else:
        print("  none")

    return 0
