# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "pyyaml>=6.0",
#     "jsonschema>=4.21",
# ]
# ///
"""Supplement Slot Planner CLI.

Subcommands:
  check    validate slots/traits/substances/products/inventory against schemas and cross-references
  refresh  append missing product formulas to inventory.yaml under stacks.inactive
  plan     build schedule.yaml from non-inactive inventory entries
  orphans  list unused cards and other cleanup candidates

Run via: uv run planner.py <subcommand>
"""

import argparse
import json
import sys
from pathlib import Path

import jsonschema
import yaml

ROOT = Path(__file__).parent
DATA_DIR = ROOT / "data"
SCHEMA_DIR = ROOT / "schema"
SUBSTANCES_DIR = DATA_DIR / "substances"
PRODUCTS_DIR = DATA_DIR / "products"
GOALS_DIR = DATA_DIR / "goals"
INVENTORY_PATH = DATA_DIR / "inventory.yaml"
SCHEDULE_PATH = ROOT / "schedule.yaml"

VALID_LEVELS = {"avoid_strong", "avoid", "prefer", "prefer_strong"}
REGISTERED_NAMESPACES = {
    "intake",
    "effect",
    "class",
    "competition",
    "risk",
    "activity",
    "mechanism",
}
SLOT_META_FIELDS = {"label", "order"}

LEVEL_SCORES = {
    "prefer_strong": 4,
    "prefer": 2,
    "avoid": -2,
    "avoid_strong": -4,
}
BALANCE_WEIGHT = 0.5
PREFER_WITH_BONUS = 3
STAR_SCALE = 5


def load_yaml(path: Path) -> object:
    return yaml.safe_load(path.read_text())


def load_schema(name: str) -> dict:
    return json.loads((SCHEMA_DIR / f"{name}.schema.json").read_text())


def schema_errors(data: object, schema_name: str, file_path: Path) -> list[str]:
    schema = load_schema(schema_name)
    validator = jsonschema.Draft202012Validator(schema)
    out: list[str] = []
    for err in validator.iter_errors(data):
        loc = "/".join(str(p) for p in err.absolute_path) or "<root>"
        out.append(f"{file_path}: {loc}: {err.message}")
    return out


def derive_slot_fields(slots_data: dict) -> set[str]:
    fields: set[str] = set()
    for slot in slots_data.get("slots", {}).values():
        fields.update(k for k in slot if k not in SLOT_META_FIELDS)
    return fields


def check_traits(
    traits_data: dict, traits_path: Path, slot_fields: set[str]
) -> list[str]:
    errors: list[str] = []
    trait_ids = set(traits_data.get("traits", {}).keys())

    for trait_id, trait in traits_data.get("traits", {}).items():
        ns = trait_id.split(":", 1)[0]
        if ns not in REGISTERED_NAMESPACES:
            errors.append(
                f"{traits_path}: trait '{trait_id}' uses unregistered namespace '{ns}' "
                f"(registered: {sorted(REGISTERED_NAMESPACES)})"
            )

        for sep in trait.get("separate_from") or []:
            if sep not in trait_ids:
                errors.append(
                    f"{traits_path}: trait '{trait_id}' separate_from references "
                    f"unknown trait '{sep}'"
                )

        for i, eff in enumerate(trait.get("effects") or []):
            for key in eff.get("match", {}):
                if key not in slot_fields:
                    errors.append(
                        f"{traits_path}: trait '{trait_id}' effect[{i}] match key "
                        f"'{key}' is not a slot field (known: {sorted(slot_fields)})"
                    )

    return errors


def load_card(path: Path, kind: str) -> tuple[dict | None, str | None]:
    """Load a YAML mapping card. Returns (data, error_message). Either is None."""
    if not path.exists():
        return None, f"{path}: file does not exist"
    try:
        card = load_yaml(path)
    except yaml.YAMLError as e:
        return None, f"{path}: yaml parse error: {e}"
    if card is None:
        return None, f"{path}: empty file"
    if not isinstance(card, dict):
        return None, (
            f"{path}: {kind} top-level must be a mapping, "
            f"got {type(card).__name__}"
        )
    return card, None


def load_substance(sf: Path) -> tuple[dict | None, str | None]:
    """Load a substance card. Returns (data, error_message). Either is None."""
    return load_card(sf, "substance")


def load_product(pf: Path) -> tuple[dict | None, str | None]:
    """Load a product formula card. Returns (data, error_message). Either is None."""
    return load_card(pf, "product")


def check_substances(
    substance_files: list[Path],
    trait_ids: set[str],
    *,
    prefer_with_registry: dict[str, Path] | None = None,
) -> tuple[list[str], list[str], dict[str, Path]]:
    """Returns (errors, info, substance_ids_to_path_map)."""
    errors: list[str] = []
    info: list[str] = []
    seen_ids: dict[str, Path] = {}
    prefer_with_refs: list[tuple[Path, str, str]] = []  # (sf, source_id, target_id)

    for sf in substance_files:
        substance, err = load_substance(sf)
        if err:
            errors.append(err)
            continue

        errors.extend(schema_errors(substance, "substance", sf))

        sid = substance.get("id")
        if sid:
            if sid != sf.stem:
                errors.append(
                    f"{sf}: id '{sid}' does not match filename stem '{sf.stem}'"
                )
            if sid in seen_ids:
                errors.append(
                    f"{sf}: duplicate id '{sid}' (also in {seen_ids[sid]})"
                )
            else:
                seen_ids[sid] = sf

        for tid in substance.get("traits", []):
            if tid not in trait_ids:
                errors.append(f"{sf}: trait '{tid}' not defined in traits.yaml")

        for other in substance.get("prefer_with") or []:
            if sid:
                if other == sid:
                    errors.append(
                        f"{sf}: prefer_with references self ('{sid}')"
                    )
                else:
                    prefer_with_refs.append((sf, sid, other))

        for concern in substance.get("unmatched_concerns") or []:
            info.append(f"{sf}: unmatched_concern: {concern}")

    # Second pass: validate prefer_with refs against the full id set.
    target_ids = prefer_with_registry or seen_ids
    for sf, source, target in prefer_with_refs:
        if target not in target_ids:
            errors.append(
                f"{sf}: prefer_with target '{target}' has no matching substance card"
            )

    return errors, info, seen_ids


def check_product_formulas(
    product_files: list[Path], substance_ids: dict[str, Path]
) -> tuple[list[str], list[str], dict[str, Path]]:
    """Returns (errors, info, product_ids_to_path_map)."""
    errors: list[str] = []
    info: list[str] = []
    seen_ids: dict[str, Path] = {}

    for pf in product_files:
        product, err = load_product(pf)
        if err:
            errors.append(err)
            continue

        errors.extend(schema_errors(product, "product", pf))

        pid = product.get("id")
        if pid:
            if pid != pf.stem:
                errors.append(
                    f"{pf}: id '{pid}' does not match filename stem '{pf.stem}'"
                )
            if pid in seen_ids:
                errors.append(
                    f"{pf}: duplicate id '{pid}' (also in {seen_ids[pid]})"
                )
            else:
                seen_ids[pid] = pf

        for i, component in enumerate(product.get("components") or []):
            if not isinstance(component, dict):
                continue
            ref = component.get("substance")
            if ref is None:
                continue
            if ref not in substance_ids:
                errors.append(
                    f"{pf}: components[{i}].substance '{ref}' references unknown "
                    f"substance (expected at data/substances/{ref}.yaml)"
                )

        for concern in product.get("unmatched_concerns") or []:
            info.append(f"{pf}: unmatched_concern: {concern}")

    return errors, info, seen_ids


def check_inventory_alignment(
    inventory_data: dict, product_ids: dict[str, Path]
) -> list[str]:
    """Verify inventory entries reference product formulas and flag refresh candidates."""
    errors: list[str] = []
    referenced_products: set[str] = set()

    for iid, entry in normalize_inventory_entries(inventory_data).items():
        if not isinstance(entry, dict):
            continue
        product_ref = entry.get("product")
        if not product_ref:
            continue
        referenced_products.add(product_ref)
        if product_ref not in product_ids:
            stack = entry.get("stack", "<unknown>")
            errors.append(
                f"{INVENTORY_PATH}: stacks.{stack} contains product '{product_ref}' "
                f"has no matching product card (expected at data/products/{product_ref}.yaml)"
            )

    for pid, pf in product_ids.items():
        if pid not in referenced_products:
            print(
                f"WARN: {INVENTORY_PATH}: product formula '{pid}' has no inventory "
                f"entry (card at {pf}). Run: uv run planner.py refresh"
            )

    return errors


def check_inventory_duplicate_items(inventory_data: dict) -> list[str]:
    errors: list[str] = []
    seen: dict[str, str] = {}
    stacks = inventory_data.get("stacks") or {}
    if not isinstance(stacks, dict):
        return errors

    for stack, items in stacks.items():
        if not isinstance(items, list):
            continue
        for item_id in items:
            if not isinstance(item_id, str):
                continue
            previous_stack = seen.get(item_id)
            if previous_stack is not None:
                errors.append(
                    f"{INVENTORY_PATH}: inventory item '{item_id}' appears in "
                    f"multiple stacks: {previous_stack}, {stack}"
                )
            else:
                seen[item_id] = stack
    return errors


def normalize_inventory_entries(inventory_data: dict) -> dict[str, dict]:
    """Return inventory product ids keyed by item id with stack attached in memory."""
    normalized: dict[str, dict] = {}
    stacks = inventory_data.get("stacks") or {}
    if not isinstance(stacks, dict):
        return normalized

    for stack, items in stacks.items():
        if not isinstance(items, list):
            continue
        for product_id in items:
            if not isinstance(product_id, str):
                continue
            normalized[product_id] = {"product": product_id, "stack": stack}
    return normalized


def collect_goal_substance_refs(goal_files: list[Path]) -> set[str]:
    refs: set[str] = set()
    for gf in goal_files:
        goal, err = load_card(gf, "goal")
        if err:
            continue
        for member in goal.get("members") or []:
            if not isinstance(member, dict):
                continue
            substance_id = member.get("substance")
            if isinstance(substance_id, str):
                refs.add(substance_id)
    return refs


def collect_orphans() -> dict[str, list[str]]:
    substance_files = sorted(SUBSTANCES_DIR.glob("*.yaml"))
    product_files = sorted(PRODUCTS_DIR.glob("*.yaml"))
    goal_files = sorted(GOALS_DIR.glob("*.yaml")) if GOALS_DIR.exists() else []

    substances: dict[str, dict] = {}
    for sf in substance_files:
        substance, err = load_substance(sf)
        if err:
            continue
        substance_id = substance.get("id")
        if isinstance(substance_id, str):
            substances[substance_id] = substance

    products: dict[str, dict] = {}
    product_substance_refs: set[str] = set()
    for pf in product_files:
        product, err = load_product(pf)
        if err:
            continue
        product_id = product.get("id")
        if isinstance(product_id, str):
            products[product_id] = product
        for component in product.get("components") or []:
            if not isinstance(component, dict):
                continue
            substance_id = component.get("substance")
            if isinstance(substance_id, str):
                product_substance_refs.add(substance_id)

    prefer_with_refs: set[str] = set()
    trait_refs: set[str] = set()
    for substance_id, substance in substances.items():
        if substance.get("prefer_with"):
            prefer_with_refs.add(substance_id)
        for target_id in substance.get("prefer_with") or []:
            if isinstance(target_id, str):
                prefer_with_refs.add(target_id)
        for trait_id in substance.get("traits") or []:
            if isinstance(trait_id, str):
                trait_refs.add(trait_id)

    traits_data = load_yaml(DATA_DIR / "traits.yaml")
    traits = traits_data.get("traits", {}) if isinstance(traits_data, dict) else {}
    for trait in traits.values():
        if not isinstance(trait, dict):
            continue
        for target_id in trait.get("separate_from") or []:
            if isinstance(target_id, str):
                trait_refs.add(target_id)

    inventory_data = load_yaml(INVENTORY_PATH)
    inventory_entries = (
        normalize_inventory_entries(inventory_data)
        if isinstance(inventory_data, dict)
        else {}
    )
    inventory_products = {
        entry["product"]
        for entry in inventory_entries.values()
        if isinstance(entry, dict) and isinstance(entry.get("product"), str)
    }
    inventory_stacks = (
        inventory_data.get("stacks", {}) if isinstance(inventory_data, dict) else {}
    )
    if not isinstance(inventory_stacks, dict):
        inventory_stacks = {}

    slots_data = load_yaml(DATA_DIR / "slots.yaml")
    slots = slots_data.get("slots", {}) if isinstance(slots_data, dict) else {}
    slot_stacks = {
        slot.get("stack")
        for slot in slots.values()
        if isinstance(slot, dict) and isinstance(slot.get("stack"), str)
    }

    substance_refs = (
        product_substance_refs
        | collect_goal_substance_refs(goal_files)
        | prefer_with_refs
    )
    unused_substances = sorted(set(substances) - substance_refs)
    products_without_inventory = sorted(set(products) - inventory_products)
    unused_traits = sorted(set(traits) - trait_refs)
    empty_stacks = sorted(
        stack
        for stack, items in inventory_stacks.items()
        if isinstance(items, list) and not items
    )
    stacks_without_slots = sorted(set(inventory_stacks) - slot_stacks - {"inactive"})
    slot_stacks_without_inventory = sorted(slot_stacks - set(inventory_stacks))

    return {
        "substances.unused": unused_substances,
        "products.without_inventory": products_without_inventory,
        "traits.unused": unused_traits,
        "stacks.empty": empty_stacks,
        "stacks.without_slots": stacks_without_slots,
        "slot_stacks.without_inventory": slot_stacks_without_inventory,
    }


def check_goals(goal_files: list[Path], substance_ids: dict[str, Path]) -> list[str]:
    """Validate goal cards against schema and members[].substance refs."""
    errors: list[str] = []
    for gf in goal_files:
        try:
            goal = load_yaml(gf)
        except yaml.YAMLError as e:
            errors.append(f"{gf}: yaml parse error: {e}")
            continue
        if goal is None:
            errors.append(f"{gf}: empty file")
            continue
        if not isinstance(goal, dict):
            errors.append(f"{gf}: top-level must be a mapping")
            continue

        errors.extend(schema_errors(goal, "goal", gf))
        for i, member in enumerate(goal.get("members") or []):
            if not isinstance(member, dict):
                continue
            ref = member.get("substance")
            if ref is None:
                continue
            if ref not in substance_ids:
                errors.append(
                    f"{gf}: members[{i}].substance '{ref}' has no matching substance card "
                    f"(expected at data/substances/{ref}.yaml)"
                )
    return errors


def report(errors: list[str], info: list[str]) -> int:
    for msg in info:
        print(f"INFO: {msg}")
    if errors:
        for e in errors:
            print(f"ERROR: {e}", file=sys.stderr)
        print(f"\n{len(errors)} error(s) found", file=sys.stderr)
        return 1
    print("All checks passed.")
    return 0


def validate_inventory(
    inventory_path: Path,
    product_ids: dict[str, Path],
    trait_ids: set[str],
) -> list[str]:
    if not inventory_path.exists():
        return [f"missing: {inventory_path}"]
    try:
        inventory_data = load_yaml(inventory_path)
    except yaml.YAMLError as e:
        return [f"{inventory_path}: yaml parse error: {e}"]
    if not isinstance(inventory_data, dict):
        return [f"{inventory_path}: top-level must be a mapping"]
    errors = schema_errors(inventory_data, "inventory", inventory_path)
    errors.extend(check_inventory_duplicate_items(inventory_data))
    errors.extend(check_inventory_alignment(inventory_data, product_ids))
    return errors


def validate_goal_file(
    goal_path: Path,
    substance_ids: dict[str, Path],
) -> list[str]:
    return check_goals([goal_path], substance_ids)


def cmd_check(target: Path | None) -> int:
    errors: list[str] = []
    info: list[str] = []

    slots_path = DATA_DIR / "slots.yaml"
    traits_path = DATA_DIR / "traits.yaml"

    for required in (slots_path, traits_path):
        if not required.exists():
            return report([f"missing: {required}"], [])

    slots_data = load_yaml(slots_path)
    traits_data = load_yaml(traits_path)

    if not isinstance(slots_data, dict):
        return report([f"{slots_path}: top-level must be a mapping"], [])
    if not isinstance(traits_data, dict):
        return report([f"{traits_path}: top-level must be a mapping"], [])

    errors.extend(schema_errors(slots_data, "slots", slots_path))
    errors.extend(schema_errors(traits_data, "traits", traits_path))

    if errors:
        return report(errors, info)

    slot_fields = derive_slot_fields(slots_data)
    errors.extend(check_traits(traits_data, traits_path, slot_fields))

    trait_ids = set(traits_data.get("traits", {}).keys())

    if target is not None:
        try:
            relative_target = target.resolve().relative_to(ROOT.resolve())
        except ValueError:
            return report([f"{target}: unsupported check target outside project"], info)

        if relative_target in (Path("data/slots.yaml"), Path("data/traits.yaml")):
            return report(errors, info)
    else:
        relative_target = None

    all_substance_files = sorted(SUBSTANCES_DIR.glob("*.yaml"))
    s_errors, s_info, substance_ids = check_substances(all_substance_files, trait_ids)
    errors.extend(s_errors)
    info.extend(s_info)

    all_product_files = sorted(PRODUCTS_DIR.glob("*.yaml"))
    p_errors, p_info, product_ids = check_product_formulas(
        all_product_files, substance_ids
    )
    errors.extend(p_errors)
    info.extend(p_info)

    if target is not None:
        if relative_target.parts[:2] == ("data", "substances"):
            target_errors, target_info, _ = check_substances(
                [target],
                trait_ids,
                prefer_with_registry=substance_ids,
            )
            errors = target_errors
            info.extend(target_info)
        elif relative_target.parts[:2] == ("data", "products"):
            target_errors, target_info, _ = check_product_formulas(
                [target], substance_ids
            )
            errors = target_errors
            info.extend(target_info)
        elif relative_target == Path("data/inventory.yaml"):
            errors = validate_inventory(INVENTORY_PATH, product_ids, trait_ids)
        elif len(relative_target.parts) == 3 and relative_target.parts[:2] == (
            "data",
            "goals",
        ):
            errors = validate_goal_file(target, substance_ids)
        else:
            return report([f"{target}: unsupported check target"], info)
    else:
        errors.extend(validate_inventory(INVENTORY_PATH, product_ids, trait_ids))
        goal_files = sorted(GOALS_DIR.glob("*.yaml")) if GOALS_DIR.exists() else []
        errors.extend(check_goals(goal_files, substance_ids))

    return report(errors, info)


def cmd_refresh(data_dir: Path = DATA_DIR) -> int:
    inventory_path = data_dir / "inventory.yaml"
    products_dir = data_dir / "products"

    if not inventory_path.exists():
        print(f"missing: {inventory_path}", file=sys.stderr)
        return 1

    inventory_data = load_yaml(inventory_path)
    if not isinstance(inventory_data, dict):
        print(f"{inventory_path}: top-level must be a mapping", file=sys.stderr)
        return 1

    entries = normalize_inventory_entries(inventory_data)
    existing_products = {
        entry.get("product")
        for entry in entries.values()
        if isinstance(entry, dict) and entry.get("product")
    }

    discovered: list[str] = []
    for pf in sorted(products_dir.glob("*.yaml")):
        product, err = load_product(pf)
        if err:
            print(f"WARN: {err}", file=sys.stderr)
            continue
        pid = product.get("id")
        if pid and pid not in existing_products:
            discovered.append(pid)

    if not discovered:
        print("inventory is in sync; no new product formulas found")
        return 0

    stacks = inventory_data.setdefault("stacks", {})
    if not isinstance(stacks, dict):
        print(f"{inventory_path}: stacks must be a mapping", file=sys.stderr)
        return 1
    inactive = stacks.setdefault("inactive", [])
    if not isinstance(inactive, list):
        print(f"{inventory_path}: stacks.inactive must be a list", file=sys.stderr)
        return 1

    for new_id in discovered:
        inactive.append(new_id)

    inventory_path.write_text(
        yaml.safe_dump(
            inventory_data,
            sort_keys=False,
            default_flow_style=False,
            allow_unicode=True,
        )
    )

    print(
        "added "
        f"{len(discovered)} new product formula entries "
        f"under stacks.inactive: {', '.join(discovered)}"
    )
    return 0


def cmd_orphans() -> int:
    sections = collect_orphans()

    print("Orphans / cleanup candidates")
    for section, items in sections.items():
        print(f"\n{section} ({len(items)})")
        if not items:
            print("  none")
            continue
        for item in items:
            print(f"  - {item}")
    return 0


# ============================================================================
# plan: backtracking scheduler
# ============================================================================


def effective_inventory_traits(
    product: dict,
    substances: dict[str, dict],
    traits_data: dict | None = None,
) -> tuple[set[str], dict[str, list[str]], list[dict]]:
    """Aggregate component substance traits for one physical inventory item."""
    effective: set[str] = set()
    trait_sources: dict[str, list[str]] = {}

    for component_id in product_component_substances(product):
        substance = substances.get(component_id)
        if not substance:
            continue
        for trait_id in substance.get("traits") or []:
            effective.add(trait_id)
            trait_sources.setdefault(trait_id, [])
            if component_id not in trait_sources[trait_id]:
                trait_sources[trait_id].append(component_id)

    internal_conflicts: list[dict] = []
    if traits_data is not None:
        seen_conflict_pairs: set[frozenset[str]] = set()
        for left in sorted(effective):
            left_def = traits_data.get("traits", {}).get(left) or {}
            for right in left_def.get("separate_from") or []:
                if right not in effective:
                    continue
                pair_key = frozenset([left, right])
                if pair_key in seen_conflict_pairs:
                    continue
                seen_conflict_pairs.add(pair_key)
                conflict = {
                    "type": "intra_product_trait_conflict",
                    "trait": left,
                    "conflicts_with": right,
                    "substances": list(trait_sources.get(left, [])),
                    "conflicting_substances": list(trait_sources.get(right, [])),
                }
                internal_conflicts.append(conflict)

    return effective, trait_sources, internal_conflicts


def load_substance_registry() -> dict[str, dict]:
    substances: dict[str, dict] = {}
    for sf in sorted(SUBSTANCES_DIR.glob("*.yaml")):
        substance, err = load_substance(sf)
        if err:
            print(f"plan: skipping substance card: {err}", file=sys.stderr)
            continue
        sid = substance.get("id")
        if isinstance(sid, str):
            substances[sid] = substance
    return substances


def load_product_registry() -> dict[str, dict]:
    products: dict[str, dict] = {}
    for pf in sorted(PRODUCTS_DIR.glob("*.yaml")):
        product, err = load_product(pf)
        if err:
            print(f"plan: skipping product card: {err}", file=sys.stderr)
            continue
        pid = product.get("id")
        if isinstance(pid, str):
            products[pid] = product
    return products


def product_component_substances(product: dict) -> list[str]:
    return [
        component["substance"]
        for component in product.get("components", [])
        if isinstance(component, dict) and isinstance(component.get("substance"), str)
    ]


def slot_matches(slot: dict, match_pattern: dict) -> bool:
    """AND-only: slot satisfies match if all listed fields equal."""
    for key, value in match_pattern.items():
        if slot.get(key) != value:
            return False
    return True


def compute_slot_score(
    trait_ids: set[str],
    slot: dict,
    traits_data: dict,
    trait_sources: dict[str, list[str]] | None = None,
) -> tuple[int, bool, list[str]]:
    """Returns (score, blocked, reasons)."""
    score = 0
    blocked = False
    reasons: list[str] = []
    for trait_id in sorted(trait_ids):
        trait = traits_data.get("traits", {}).get(trait_id)
        if not trait:
            continue
        for eff in trait.get("effects") or []:
            match_pattern = eff.get("match", {})
            if not slot_matches(slot, match_pattern):
                continue
            source_text = ""
            if trait_sources is not None:
                sources = trait_sources.get(trait_id) or ["unknown"]
                source_text = f" from {', '.join(sources)}"
            if eff.get("block") is True:
                blocked = True
                reasons.append(f"{trait_id}{source_text} BLOCK on match {match_pattern}")
            elif "level" in eff:
                level = eff["level"]
                delta = LEVEL_SCORES.get(level, 0)
                score += delta
                reasons.append(
                    f"{trait_id}{source_text} match {match_pattern} -> "
                    f"{level} ({delta:+d})"
                )
    return score, blocked, reasons


def score_quality_rating(total: float, max_score: float) -> tuple[float, int, str]:
    """Convert optimizer score to a bounded 0-5 star rating for human display."""
    if max_score <= 0:
        return 0.0, 0, "☆☆☆☆☆"
    ratio = max(0.0, min(1.0, total / max_score))
    stars = 0 if ratio == 0 else min(STAR_SCALE, max(1, round(ratio * STAR_SCALE)))
    return round(ratio, 3), stars, "★" * stars + "☆" * (STAR_SCALE - stars)


def must_separate(t1: set[str], t2: set[str], traits_data: dict) -> bool:
    """Symmetric: t1 and t2 share a slot conflict if either declares separate_from
    referencing a trait in the other."""
    def declares_against(traits_a: set[str], traits_b: set[str]) -> bool:
        for trait_id in traits_a:
            trait = traits_data.get("traits", {}).get(trait_id)
            if not trait:
                continue
            for sep in trait.get("separate_from") or []:
                if sep in traits_b:
                    return True
        return False

    return declares_against(t1, t2) or declares_against(t2, t1)


def cmd_plan() -> int:
    # Implicit check first
    print("=== running check ===", file=sys.stderr)
    check_result = cmd_check(None)
    if check_result != 0:
        print("plan aborted: check failed; fix errors above and retry.", file=sys.stderr)
        return check_result
    print("=== check passed; building schedule ===", file=sys.stderr)

    slots_data = load_yaml(DATA_DIR / "slots.yaml")
    traits_data = load_yaml(DATA_DIR / "traits.yaml")
    inventory_data = load_yaml(INVENTORY_PATH)

    if not (
        isinstance(slots_data, dict)
        and isinstance(traits_data, dict)
        and isinstance(inventory_data, dict)
    ):
        print("plan: data file not a mapping", file=sys.stderr)
        return 1

    slots: dict[str, dict] = dict(
        sorted(
            slots_data.get("slots", {}).items(),
            key=lambda kv: kv[1].get("order", 0),
        )
    )

    substances = load_substance_registry()
    products = load_product_registry()

    # Non-inactive inventory items + effective traits aggregated from product components
    active: dict[str, set[str]] = {}
    item_products: dict[str, str] = {}
    active_components: dict[str, list[str]] = {}
    trait_sources_by_item: dict[str, dict[str, list[str]]] = {}
    intra_product_conflicts_by_item: dict[str, list[dict]] = {}
    item_stacks: dict[str, str] = {}
    for item_id, entry in normalize_inventory_entries(inventory_data).items():
        stack = entry.get("stack")
        if stack == "inactive":
            continue
        product_id = entry.get("product")
        product = products.get(product_id)
        if not product:
            print(
                f"plan: skipping '{item_id}' — product '{product_id}' missing or invalid",
                file=sys.stderr,
            )
            continue
        effective, trait_sources, internal_conflicts = effective_inventory_traits(
            product, substances, traits_data
        )
        active[item_id] = effective
        item_products[item_id] = product_id
        active_components[item_id] = product_component_substances(product)
        trait_sources_by_item[item_id] = trait_sources
        intra_product_conflicts_by_item[item_id] = internal_conflicts
        item_stacks[item_id] = stack

    if not active:
        print("plan: no non-inactive inventory items.", file=sys.stderr)
        return 1

    # Symmetric prefer_with pairs between schedulable product-backed inventory items.
    prefer_pairs: set[frozenset[str]] = set()
    ambiguous_prefer_with_warnings: list[dict] = []
    substance_to_active_items: dict[str, list[str]] = {}
    for item_id, component_ids in active_components.items():
        for component_id in component_ids:
            substance_to_active_items.setdefault(component_id, []).append(item_id)
    for component_id in substance_to_active_items:
        substance_to_active_items[component_id].sort()

    for item_id, component_ids in active_components.items():
        for component_id in component_ids:
            substance = substances.get(component_id) or {}
            for target_substance in substance.get("prefer_with") or []:
                target_items = substance_to_active_items.get(target_substance, [])
                if len(target_items) == 1:
                    other_item = target_items[0]
                    if other_item != item_id:
                        prefer_pairs.add(frozenset([item_id, other_item]))
                elif len(target_items) > 1:
                    ambiguous_prefer_with_warnings.append(
                        {
                            "type": "ambiguous_prefer_with",
                            "item": item_id,
                            "product": item_products[item_id],
                            "source_substance": component_id,
                            "target_substance": target_substance,
                            "candidate_items": target_items,
                            "message": (
                                "prefer_with target maps to multiple active "
                                "inventory items; no bonus awarded"
                            ),
                        }
                    )

    # Candidate slots per substance: list of (slot_name, score, reasons)
    candidates: dict[str, list[tuple[str, int, list[str]]]] = {}
    for sid, traits in active.items():
        valid: list[tuple[str, int, list[str]]] = []
        for slot_name, slot in slots.items():
            if slot.get("stack") != item_stacks[sid]:
                continue
            score, blocked, reasons = compute_slot_score(
                traits, slot, traits_data, trait_sources_by_item[sid]
            )
            if blocked:
                continue
            valid.append((slot_name, score, reasons))
        if not valid:
            print(
                f"plan: inventory item '{sid}' is blocked from every slot.",
                file=sys.stderr,
            )
            return 1
        valid.sort(key=lambda c: -c[1])  # best score first
        candidates[sid] = valid

    # Most-constrained-first ordering
    sorted_subs = sorted(active.keys(), key=lambda s: len(candidates[s]))

    # === Greedy initial assignment: best valid slot for each substance ===
    assignment: dict[str, str] = {}
    slot_traits: dict[str, list[set[str]]] = {sn: [] for sn in slots}

    for sid in sorted_subs:
        traits = active[sid]
        chosen: str | None = None
        for slot_name, _, _ in candidates[sid]:  # already score-desc
            if any(
                must_separate(traits, existing_traits, traits_data)
                for existing_traits in slot_traits[slot_name]
            ):
                continue
            chosen = slot_name
            break
        if chosen is None:
            print(
                f"plan: inventory item '{sid}' has no valid slot under separate_from "
                f"constraints (greedy phase).",
                file=sys.stderr,
            )
            return 1
        assignment[sid] = chosen
        slot_traits[chosen].append(traits)

    def total_score() -> tuple[float, int, int, float]:
        slot_score_total = 0
        for sid, slot_name in assignment.items():
            slot = slots[slot_name]
            score, _, _ = compute_slot_score(
                active[sid], slot, traits_data, trait_sources_by_item[sid]
            )
            slot_score_total += score
        prefer_with_bonus = 0
        for pair in prefer_pairs:
            a, b = tuple(pair)
            if assignment.get(a) == assignment.get(b):
                prefer_with_bonus += PREFER_WITH_BONUS
        slot_loads = [len(slot_traits[sn]) for sn in slots]
        balance_penalty = BALANCE_WEIGHT * sum(load * load for load in slot_loads)
        total = slot_score_total + prefer_with_bonus - balance_penalty
        return total, slot_score_total, prefer_with_bonus, balance_penalty

    # === Local search: first-improvement single-substance moves ===
    current_total, _, _, _ = total_score()
    iterations = 0
    max_iterations = 200
    while iterations < max_iterations:
        improved = False
        for sid in sorted_subs:
            current_slot = assignment[sid]
            traits = active[sid]
            best_target: str | None = None
            best_delta = 0.0
            for slot_name, _, _ in candidates[sid]:
                if slot_name == current_slot:
                    continue
                if any(
                    must_separate(traits, existing_traits, traits_data)
                    for existing_traits in slot_traits[slot_name]
                ):
                    continue
                # Tentative move
                slot_traits[current_slot].remove(traits)
                slot_traits[slot_name].append(traits)
                assignment[sid] = slot_name
                new_total, _, _, _ = total_score()
                delta = new_total - current_total
                # Revert
                slot_traits[slot_name].remove(traits)
                slot_traits[current_slot].append(traits)
                assignment[sid] = current_slot
                if delta > best_delta + 1e-9:
                    best_delta = delta
                    best_target = slot_name
            if best_target is not None:
                slot_traits[current_slot].remove(traits)
                slot_traits[best_target].append(traits)
                assignment[sid] = best_target
                current_total += best_delta
                improved = True
        iterations += 1
        if not improved:
            break

    final_total, slot_score_sum, prefer_bonus, balance_pen = total_score()
    theoretical_max = (
        sum(max(score for _, score, _ in valid) for valid in candidates.values())
        + len(prefer_pairs) * PREFER_WITH_BONUS
    )
    quality_ratio, quality_stars, quality_label = score_quality_rating(
        final_total, theoretical_max
    )

    # Build schedule.yaml
    schedule: dict = {
        "version": 1,
        "total_score": round(final_total, 2),
        "quality_stars": quality_label,
        "quality_rating": quality_stars,
        "quality_scale": STAR_SCALE,
        "quality_ratio": quality_ratio,
        "quality_max_score": theoretical_max,
        "slot_score_total": slot_score_sum,
        "prefer_with_bonus": prefer_bonus,
        "balance_penalty": round(balance_pen, 2),
        "search": {
            "algorithm": "greedy + first-improvement local search",
            "iterations": iterations,
        },
        "slots": {sn: [] for sn in slots},
        "warnings": [],
        "prefer_with_pairs": [
            {
                "pair": sorted(p),
                "co_located": (
                    assignment[sorted(p)[0]] == assignment[sorted(p)[1]]
                ),
                "slot": assignment[sorted(p)[0]]
                if assignment[sorted(p)[0]] == assignment[sorted(p)[1]]
                else None,
            }
            for p in (sorted(prefer_pairs, key=lambda x: sorted(x)))
        ],
        "explanations": {},
    }

    for sid, slot_name in assignment.items():
        schedule["slots"][slot_name].append(sid)

    for sid, slot_name in assignment.items():
        slot = slots[slot_name]
        score, _, reasons = compute_slot_score(
            active[sid], slot, traits_data, trait_sources_by_item[sid]
        )
        schedule["explanations"][sid] = {
            "product": item_products[sid],
            "components": active_components[sid],
            "slot": slot_name,
            "slot_score": score,
            "reasons": reasons,
        }

    for sid, internal_conflicts in intra_product_conflicts_by_item.items():
        for conflict in internal_conflicts:
            schedule["warnings"].append(
                {
                    "type": "intra_product_trait_conflict",
                    "item": sid,
                    "product": item_products[sid],
                    "trait": conflict["trait"],
                    "conflicts_with": conflict["conflicts_with"],
                    "substances": conflict["substances"],
                    "conflicting_substances": conflict["conflicting_substances"],
                    "message": (
                        "Component traits conflict inside one physical product; "
                        "scheduling keeps the product together and emits this warning"
                    ),
                }
            )

    schedule["warnings"].extend(ambiguous_prefer_with_warnings)

    for sid, traits in active.items():
        for trait_id in sorted(traits):
            trait_def = traits_data.get("traits", {}).get(trait_id)
            if trait_def and trait_def.get("warning"):
                for source in trait_sources_by_item[sid].get(trait_id) or ["unknown"]:
                    schedule["warnings"].append(
                        {
                            "item": sid,
                            "product": item_products[sid],
                            "substance": source,
                            "trait": trait_id,
                            "message": trait_def.get(
                                "description", "Manual review required."
                            ),
                        }
                    )

    SCHEDULE_PATH.write_text(
        yaml.safe_dump(
            schedule,
            sort_keys=False,
            default_flow_style=False,
            allow_unicode=True,
        )
    )

    slot_loads = {sn: len(items) for sn, items in schedule["slots"].items()}
    print(f"\nschedule written to {SCHEDULE_PATH}")
    print(
        f"total_score: {schedule['total_score']} = "
        f"slot_scores {schedule['slot_score_total']} + "
        f"prefer_with {schedule['prefer_with_bonus']} − "
        f"balance_penalty {schedule['balance_penalty']}"
    )
    print(
        f"quality: {schedule['quality_stars']} "
        f"({schedule['quality_rating']}/{schedule['quality_scale']})"
    )
    print(f"slot loads: {slot_loads}")
    print(f"prefer_with pairs: {len(prefer_pairs)} declared, "
          f"{schedule['prefer_with_bonus'] // PREFER_WITH_BONUS} co-located")
    print(f"warnings: {len(schedule['warnings'])}")
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description="Supplement Slot Planner")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_check = sub.add_parser("check", help="validate YAML data files")
    p_check.add_argument(
        "target",
        nargs="?",
        type=Path,
        help="single substance/product/inventory/goal file to check (default: scan all)",
    )

    sub.add_parser(
        "refresh",
        help=(
            "append missing product formulas to inventory.yaml under "
            "stacks.inactive"
        ),
        description=(
            "Append missing product formulas to inventory.yaml under "
            "stacks.inactive."
        ),
        formatter_class=argparse.RawTextHelpFormatter,
    )

    sub.add_parser("plan", help="generate schedule.yaml from non-inactive inventory")
    sub.add_parser("orphans", help="list unused cards and cleanup candidates")

    args = parser.parse_args()

    if args.cmd == "check":
        sys.exit(cmd_check(args.target))
    elif args.cmd == "refresh":
        sys.exit(cmd_refresh())
    elif args.cmd == "plan":
        sys.exit(cmd_plan())
    elif args.cmd == "orphans":
        sys.exit(cmd_orphans())


if __name__ == "__main__":
    main()
