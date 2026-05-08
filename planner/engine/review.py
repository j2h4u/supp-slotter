"""`review-substance` command: trait checklist for one substance card."""

from __future__ import annotations

import sys
from pathlib import Path

from planner.cards import (
    flatten_trait_defs,
    format_substance_name,
    grouped_trait_defs,
    load_substance,
    load_substance_registry,
    print_central_relation_matches,
    print_trait_details,
)
from planner.io import (
    DATA_DIR,
    ROOT,
    SUBSTANCES_DIR,
    display_message,
    display_path,
    load_yaml,
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
            f"{display_path(path)}: review-substance only accepts paths inside {display_path(SUBSTANCES_DIR)}/",
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
    substance, err = load_substance(path)
    if err is not None:
        print(display_message(err), file=sys.stderr)
        return 1
    if substance is None:
        print(f"{display_path(path)}: substance could not be loaded", file=sys.stderr)
        return 1

    traits_data = load_yaml(DATA_DIR / "traits.yaml")
    if not isinstance(traits_data, dict):
        print("data/traits.yaml: top-level must be a mapping", file=sys.stderr)
        return 1
    trait_defs = flatten_trait_defs(traits_data)
    if not trait_defs:
        print("data/traits.yaml: no traits found", file=sys.stderr)
        return 1

    current_traits = {
        trait
        for trait in substance.get("traits") or []
        if isinstance(trait, str)
    }
    aliases = substance.get("aliases") or []
    concerns = substance.get("unmatched_concerns") or []

    print(f"Substance review: {format_substance_name(substance)}")
    print(f"File: {display_path(path)}")
    if substance.get("id"):
        print(f"ID: {substance['id']}")
    if aliases:
        print("Aliases: " + ", ".join(str(alias) for alias in aliases))
    print_central_relation_matches(substance, load_substance_registry())
    print()
    print("Before editing traits, scan this checklist and mark only source-backed facts.")
    print("If a fact matters but no trait fits, use unmatched_concerns.")
    print("Put substance-to-substance relations in data/relations.yaml, not in this card.")
    print()
    print("Traits")
    for namespace, entries in grouped_trait_defs(trait_defs).items():
        print(f"\n{namespace}")
        for short_name, trait_id, trait in entries:
            marker = "x" if trait_id in current_traits else " "
            label = trait.get("label")
            label_text = f" - {label}" if label else ""
            print(f"  [{marker}] {short_name}{label_text}")
            print_trait_details(trait)

    unknown_traits = sorted(current_traits - set(trait_defs), key=str.casefold)
    if unknown_traits:
        print("\nunknown")
        for trait_id in unknown_traits:
            print(f"  [x] {trait_id}")

    print("\nUnmatched concerns")
    if concerns:
        for concern in concerns:
            print(f"  - {concern}")
    else:
        print("  none")

    return 0

