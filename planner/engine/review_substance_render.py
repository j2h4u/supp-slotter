"""Text renderer for `review-substance`."""

from __future__ import annotations

from typing import Any

from planner.cards.substance import format_substance_name
from planner.cards.traits import NAMESPACE_ORDER, grouped_trait_defs, print_trait_details
from planner.engine.review_substance_model import SubstanceReviewModel
from planner.paths import display_path


def render_substance_review(model: SubstanceReviewModel) -> None:
    substance = model.substance
    print(f"Substance review: {format_substance_name(substance)}")
    print(f"File: {display_path(model.path)}")
    if substance.id:
        print(f"ID: {substance.id}")
    if substance.aliases:
        print("Aliases: " + ", ".join(substance.aliases))
    _print_central_relation_matches(model)
    print()
    print("Before editing traits, scan this checklist and mark only source-backed facts.")
    print("If a fact matters but no trait fits, add it to concerns with the appropriate kind.")
    print("Put substance-to-substance relations in data/relations.yaml, not in this card.")
    print()
    print("Traits")
    _print_trait_checklist(model)
    _print_substance_concerns(model)


def _print_central_relation_matches(model: SubstanceReviewModel) -> None:
    substance = model.substance
    print("\nCentral relations from data/relations.yaml (read-only)")
    print("Edit these in data/relations.yaml, not in this substance card.")
    if substance.id:
        print(f"Matches this substance by id: {substance.id}")
    if substance.name:
        print(f"Matches this substance by exact name: {substance.name}")

    if not model.relation_matches:
        print("  none matched; add links in data/relations.yaml if needed.")
        return

    print("Note: balance/competes are symmetric; supports/review_with are directional.")
    grouped: dict[str, list[tuple[dict[str, Any], list[str]]]] = {}
    for row, matched_by in model.relation_matches:
        grouped.setdefault(str(row["type"]), []).append((row, matched_by))

    for relation_type in ("balance", "competes", "supports", "review_with"):
        relation_group = grouped.get(relation_type)
        if not relation_group:
            continue
        print(f"\n{relation_type}")
        for row, matched_by in relation_group:
            print(f"  {row['src_display']} -> {row['tgt_display']}")
            print(f"    matched by: {', '.join(matched_by)}")
            reason = row.get("reason")
            if reason:
                print(f"    reason: {reason}")
            action = row.get("action")
            if action:
                print(f"    action: {action}")


def _print_trait_checklist(model: SubstanceReviewModel) -> None:
    registered_by_namespace = grouped_trait_defs(model.trait_defs)
    all_namespaces: list[str] = list(NAMESPACE_ORDER)
    for extra_ns in sorted(ns for ns in registered_by_namespace if ns not in NAMESPACE_ORDER):
        all_namespaces.append(extra_ns)

    for namespace in all_namespaces:
        substance_slugs = model.substance_slugs_by_namespace.get(namespace, set())
        print(f"\n{namespace}")
        if namespace == "context":
            _print_context_namespace(model, substance_slugs)
            continue

        registered_traits = registered_by_namespace.get(namespace, [])
        registered_short_names = {trait.short_name for trait in registered_traits}
        unknown_slugs = sorted(
            (slug for slug in substance_slugs if slug not in registered_short_names),
            key=str.casefold,
        )
        if not registered_traits and not unknown_slugs:
            print("  (empty)")
            continue

        for trait in registered_traits:
            marker = "x" if trait.id in model.current_traits else " "
            label_text = f" - {trait.label}" if trait.label else ""
            print(f"  [{marker}] {trait.short_name}{label_text}")
            print_trait_details(trait)

        if unknown_slugs:
            print("  unknown")
            for slug in unknown_slugs:
                print(f"    [x] {namespace}:{slug}  (not registered in trait registry)")


def _print_context_namespace(
    model: SubstanceReviewModel,
    substance_slugs: set[str],
) -> None:
    if not substance_slugs:
        print("  (empty)")
        return

    for slug in sorted(substance_slugs, key=str.casefold):
        details = model.context_dashboards.get(slug)
        if details is None:
            print(f"  [x] {slug}  (no dashboard yaml — run planner check)")
            continue
        name, description = details
        print(f"  [x] {slug} - {name}")
        if description:
            print(f"      {description}")


def _print_substance_concerns(model: SubstanceReviewModel) -> None:
    print("\nConcerns")
    if not model.substance.concerns:
        print("  none")
        return

    for concern in model.substance.concerns:
        print(f"  [{concern.kind}] {concern.text}")
