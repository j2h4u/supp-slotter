"""`doctor` command: orphan/cleanup candidate report."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, cast

from planner.cards.dashboards import (
    _from_traits_pairs,
    _substance_carries,
    collect_dashboard_substance_refs,
    load_dashboard,
)
from planner.cards.product import (
    collect_product_substance_refs,
    load_product_registry,
)
from planner.cards.relations import (
    collect_missing_balance_relations,
    collect_missing_support_relations,
    format_relation_warning,
    global_relation_refs,
    load_global_relations,
)
from planner.cards.stacks import normalize_stack_entries
from planner.cards.substance import (
    collect_similar_substances,
    load_substance_registry,
)
from planner.cards.traits import load_traits
from planner.contracts import CardLoadError, Substance, TraitDef
from planner.io import (
    DASHBOARDS_DIR,
    DATA_DIR,
    STACKS_PATH,
    load_yaml,
    validate_schemas,
)
from planner.maintenance import run_auto_maintenance


def check_dashboard_lifecycle(
    trait_defs: dict[str, TraitDef],
    substances: dict[str, Substance],
    dashboard_files: list[Path],
) -> dict[str, list[str]]:
    """Advisory lifecycle warnings for dashboard tag/yaml/trait state. These complement
    (do not replace) the hard reference-integrity errors in planner check:
      - planner check fails on slugs not registered in traits.yaml (hard FK constraint)
      - planner doctor warns on valid-but-suspicious lifecycle states (this function)

    check-vs-doctor boundary:
      planner check = hard reference-integrity errors on data that cannot be loaded or
        that violates the file-based FK constraint (exit non-zero).
      planner doctor = advisory warnings on valid-but-suspicious lifecycle states
        (orphan trait registrations, unused tags, dashboard/trait slug pairing
        inconsistency, empty clusters). Exit 0.
    """
    # --- Collect registered dashboard trait slugs ---
    dashboard_trait_slugs: set[str] = {
        trait.short_name
        for trait in trait_defs.values()
        if trait.namespace == "dashboard"
    }

    # --- Collect slugs actually carried by substance cards ---
    carried_slugs: set[str] = set()
    for substance in substances.values():
        for slug in substance.dashboard:
            carried_slugs.add(slug)

    # --- Collect dashboard yaml stems ---
    yaml_stems: set[str] = {p.stem for p in dashboard_files}

    # --- dashboard.slug_mismatch ---
    # yaml exists without matching trait OR trait exists without yaml
    slug_mismatch_messages: list[str] = []
    yaml_without_trait = yaml_stems - dashboard_trait_slugs
    trait_without_yaml = dashboard_trait_slugs - yaml_stems
    for slug in sorted(yaml_without_trait):
        slug_mismatch_messages.append(
            f"Slug mismatch: data/dashboards/{slug}.yaml exists but dashboard:{slug} "
            f"is not registered in data/traits.yaml. Fix: add dashboard:{slug} entry "
            f"to data/traits.yaml (with label and description)."
        )
    for slug in sorted(trait_without_yaml):
        slug_mismatch_messages.append(
            f"Slug mismatch: dashboard:{slug} is registered in data/traits.yaml but "
            f"data/dashboards/{slug}.yaml does not exist. Fix: create "
            f"data/dashboards/{slug}.yaml referencing from_traits: {{ dashboard: [{slug}] }}, "
            f"or remove the trait entry from data/traits.yaml."
        )

    # Precedence rule: slugs with trait_without_yaml are suppressed from
    # orphan_registration (yaml creation is the prerequisite step).
    # orphan_registration only fires when the yaml exists.
    orphan_registration_excluded = trait_without_yaml

    # --- dashboard.orphan_registration ---
    # Trait registered but no substance carries it (and yaml exists — i.e. not
    # in trait_without_yaml, handled by slug_mismatch instead).
    orphan_registration_messages: list[str] = []
    registered_with_yaml = dashboard_trait_slugs & yaml_stems  # yaml exists for this trait
    for slug in sorted(registered_with_yaml - carried_slugs - orphan_registration_excluded):
        orphan_registration_messages.append(
            f"Orphan registration: dashboard:{slug} defined in data/traits.yaml but "
            f"no substance card has it under its dashboard: group. Likely cause: trait "
            f"registered for a planned cluster but substance tagging not yet done. "
            f"Resolution: tag relevant substance cards under dashboard:, OR remove the "
            f"trait entry from data/traits.yaml if the cluster is abandoned."
        )

    # --- dashboard.unused_trait ---
    # Substances carry a slug but no dashboard yaml references it via from_traits.
    # Collect all dashboard slugs referenced by any dashboard yaml from_traits (dashboard namespace only).
    referenced_in_yaml: set[str] = set()
    for dashboard_file in dashboard_files:
        try:
            dashboard = load_dashboard(dashboard_file)
        except CardLoadError as e:
            print(f"warning: skipping dashboard card in lifecycle check: {e.message}", file=sys.stderr)
            continue
        for ns, slug in _from_traits_pairs(dashboard.from_traits):
            if ns == "dashboard":
                referenced_in_yaml.add(slug)

    unused_trait_messages: list[str] = []
    for slug in sorted(carried_slugs - referenced_in_yaml):
        count = sum(1 for s in substances.values() if slug in s.dashboard)
        unused_trait_messages.append(
            f"Unused trait: dashboard:{slug} is carried by {count} substance card(s) "
            f"but no dashboard yaml references it via from_traits. Likely cause: "
            f"dashboard yaml deleted while tags remained, OR yaml not yet created. "
            f"Resolution: create data/dashboards/{slug}.yaml referencing it via "
            f"from_traits: {{ dashboard: [{slug}] }}, OR remove the tag from substance "
            f"cards and the entry from data/traits.yaml."
        )

    # --- dashboard.empty_cluster ---
    # from_traits resolves to zero member substances using canonical OR-across-namespaces.
    empty_cluster_messages: list[str] = []
    for dashboard_file in dashboard_files:
        try:
            dashboard = load_dashboard(dashboard_file)
        except CardLoadError as e:
            # Already warned above; skip silently here.
            continue
        pairs = list(_from_traits_pairs(dashboard.from_traits))
        if not pairs:
            # No from_traits at all — trivially empty; report it.
            member_count = 0
        else:
            member_count = sum(
                1
                for substance in substances.values()
                if any(_substance_carries(substance, ns, slug) for ns, slug in pairs)
            )
        if member_count == 0:
            slug = dashboard_file.stem
            empty_cluster_messages.append(
                f"Empty cluster: data/dashboards/{slug}.yaml from_traits resolves to "
                f"zero member substances (using union resolution: OR across all listed "
                f"(namespace, slug) pairs). Resolution: tag substances under dashboard: "
                f"{slug}, OR remove the dashboard yaml if abandoned. (If this is an "
                f"intentional placeholder, add a notes: field explaining the intent.)"
            )

    return {
        "dashboard.orphan_registration": orphan_registration_messages,
        "dashboard.unused_trait": unused_trait_messages,
        "dashboard.slug_mismatch": slug_mismatch_messages,
        "dashboard.empty_cluster": empty_cluster_messages,
    }


def collect_orphans() -> dict[str, list[str]]:
    """Collect cleanup candidates across all card types; returned keys are stable section names used by cmd_doctor for display."""
    dashboard_files = sorted(DASHBOARDS_DIR.glob("*.yaml")) if DASHBOARDS_DIR.exists() else []

    substances = load_substance_registry()
    products = load_product_registry()

    product_substance_refs: set[str] = set()
    for product in products.values():
        for component in product.components:
            product_substance_refs.add(component.substance)

    prefer_with_refs: set[str] = set()
    relation_refs: set[str] = set()
    trait_refs: set[str] = set()
    for substance_id, substance in substances.items():
        if substance.prefer_with:
            prefer_with_refs.add(substance_id)
        for target_id in substance.prefer_with:
            prefer_with_refs.add(target_id)
        for field, ns in [
            ("is_", "is"),
            ("intake", "intake"),
            ("effect", "effect"),
            ("risk", "risk"),
            ("activity", "activity"),
            ("dashboard", "dashboard"),
        ]:
            for slug in getattr(substance, field):
                trait_refs.add(f"{ns}:{slug}")
    relation_refs.update(global_relation_refs(substances, load_global_relations()))

    trait_defs = load_traits(DATA_DIR / "traits.yaml")
    for trait in trait_defs.values():
        for target_id in trait.separate_from:
            trait_refs.add(target_id)

    stacks_data = load_yaml(STACKS_PATH)
    stack_entries = (
        normalize_stack_entries(cast(dict[str, Any], stacks_data))
        if isinstance(stacks_data, dict)
        else {}
    )
    stack_products = {
        cast(str, entry.get("product"))
        for entry in stack_entries.values()
        if isinstance(entry.get("product"), str)
    }
    active_stack_products = {
        cast(str, entry.get("product"))
        for entry in stack_entries.values()
        if entry.get("stack") != "inactive" and isinstance(entry.get("product"), str)
    }
    active_substances = collect_product_substance_refs(
        products, active_stack_products
    )
    stacks_by_name: dict[str, Any] = cast(dict[str, Any], stacks_data) if isinstance(stacks_data, dict) else {}

    slots_data = load_yaml(DATA_DIR / "pillboxes.yaml")
    slots_dict = cast(dict[str, Any], slots_data) if isinstance(slots_data, dict) else {}
    pillbox_stacks: set[str] = set(slots_dict.keys()) if slots_dict else set()

    substance_refs = (
        product_substance_refs
        | collect_dashboard_substance_refs(dashboard_files)
        | prefer_with_refs
        | relation_refs
    )
    unused_substances = sorted(set(substances) - substance_refs)
    products_without_stack = sorted(set(products) - stack_products)
    unused_traits = sorted(set(trait_defs) - trait_refs)
    empty_stacks = sorted(
        stack
        for stack, items in stacks_by_name.items()
        if isinstance(items, list) and not items
    )
    stacks_without_pillboxes = sorted(
        set(stacks_by_name) - pillbox_stacks - {"inactive"}
    )
    pillboxes_without_stack = sorted(pillbox_stacks - set(stacks_by_name))

    dashboard_lifecycle = check_dashboard_lifecycle(trait_defs, substances, dashboard_files)

    return {
        "substances.unused": unused_substances,
        "products.without_stack": products_without_stack,
        "traits.unused": unused_traits,
        "stacks.empty": empty_stacks,
        "stacks.without_pillboxes": stacks_without_pillboxes,
        "pillboxes.without_stack": pillboxes_without_stack,
        "substances.similar_names": collect_similar_substances(substances),
        "relations.balance_missing": [
            format_relation_warning(warning)
            for warning in collect_missing_balance_relations(
                substances, active_substances, load_global_relations()
            )
        ],
        "relations.supports_missing": [
            format_relation_warning(warning)
            for warning in collect_missing_support_relations(
                substances, active_substances, load_global_relations()
            )
        ],
        **dashboard_lifecycle,
    }


def cmd_doctor() -> int:
    schema_result = validate_schemas()
    if schema_result != 0:
        return schema_result

    maintenance_result = run_auto_maintenance(suppress_output=True)
    if maintenance_result != 0:
        return maintenance_result

    sections = collect_orphans()

    print("Doctor / cleanup candidates")
    for section, items in sections.items():
        print(f"\n{section} ({len(items)})")
        if not items:
            print("  none")
            continue
        for item in items:
            print(f"  - {item}")
    return 0
