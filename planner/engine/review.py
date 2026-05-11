"""`review-substance` command: trait checklist for one substance card."""

from __future__ import annotations

import sys
from pathlib import Path

import yaml

from planner.cards.relations import print_central_relation_matches
from planner.cards.substance import (
    format_substance_name,
    load_substance,
    load_substance_registry,
)
from planner.cards.traits import (
    NAMESPACE_ORDER,
    grouped_trait_defs,
    load_traits,
    print_trait_details,
)
from planner.contracts import CardLoadError
from planner.io import (
    DASHBOARDS_DIR,
    DATA_DIR,
    ROOT,
    SUBSTANCES_DIR,
    display_path,
    strip_root_prefix,
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
        print(strip_root_prefix(e.message), file=sys.stderr)
        return 1

    try:
        trait_defs = load_traits(DATA_DIR / "traits.yaml")
    except CardLoadError as e:
        print(strip_root_prefix(e.message), file=sys.stderr)
        return 1
    if not trait_defs:
        print("data/traits.yaml: no traits found", file=sys.stderr)
        return 1

    # Build namespace -> substance slugs map; derive flat set for marker lookups.
    ns_to_substance_slugs: dict[str, set[str]] = {}
    for field, ns in [
        ("is_", "is"),
        ("intake", "intake"),
        ("effect", "effect"),
        ("risk", "risk"),
        ("activity", "activity"),
        ("dashboard", "dashboard"),
    ]:
        ns_to_substance_slugs[ns] = set(getattr(substance, field))
    current_traits: set[str] = {
        f"{ns}:{slug}"
        for ns, slugs in ns_to_substance_slugs.items()
        for slug in slugs
    }

    print(f"Substance review: {format_substance_name(substance)}")
    print(f"File: {display_path(path)}")
    if substance.id:
        print(f"ID: {substance.id}")
    if substance.aliases:
        print("Aliases: " + ", ".join(substance.aliases))
    print_central_relation_matches(substance, load_substance_registry())
    print()
    print("Before editing traits, scan this checklist and mark only source-backed facts.")
    print("If a fact matters but no trait fits, add it to concerns with the appropriate kind.")
    print("Put substance-to-substance relations in data/relations.yaml, not in this card.")
    print()
    print("Traits")

    ns_to_registered = grouped_trait_defs(trait_defs)

    # Iterate all 6 namespaces in stable order; show heading even when empty.
    all_namespaces: list[str] = list(NAMESPACE_ORDER)
    for extra_ns in sorted(ns for ns in ns_to_registered if ns not in NAMESPACE_ORDER):
        all_namespaces.append(extra_ns)

    for namespace in all_namespaces:
        substance_slugs = ns_to_substance_slugs.get(namespace, set())
        print(f"\n{namespace}")

        # dashboard: namespace — labels come from dashboard YAML files, not traits.yaml.
        if namespace == "dashboard":
            if not substance_slugs:
                print("  (empty)")
            else:
                for slug in sorted(substance_slugs, key=str.casefold):
                    yaml_path = DASHBOARDS_DIR / f"{slug}.yaml"
                    if yaml_path.exists():
                        data = yaml.safe_load(yaml_path.read_text())
                        name = data.get("name", slug)
                        print(f"  [x] {slug} - {name}")
                        desc = data.get("description", "")
                        if desc:
                            print(f"      {desc}")
                    else:
                        print(f"  [x] {slug}  (no dashboard yaml — run planner check)")
            continue

        registered_traits = ns_to_registered.get(namespace, [])
        registered_short_names = {t.short_name for t in registered_traits}

        # Determine if the namespace has any content to show.
        unknown_slugs = sorted(
            (slug for slug in substance_slugs if slug not in registered_short_names),
            key=str.casefold,
        )
        has_content = registered_traits or unknown_slugs

        if not has_content:
            print("  (empty)")
            continue

        for trait in registered_traits:
            marker = "x" if trait.id in current_traits else " "
            label_text = f" - {trait.label}" if trait.label else ""
            print(f"  [{marker}] {trait.short_name}{label_text}")
            print_trait_details(trait)

        if unknown_slugs:
            print("  unknown")
            for slug in unknown_slugs:
                print(f"    [x] {namespace}:{slug}  (not registered in traits.yaml)")

    print("\nConcerns")
    if substance.concerns:
        for concern in substance.concerns:
            print(f"  [{concern.kind}] {concern.text}")
    else:
        print("  none")

    return 0
