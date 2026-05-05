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
  refresh  append missing product formulas to inventory.yaml as {product: <id>, stack: inactive}
  plan     build schedule.yaml from non-inactive inventory entries

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
    "family",
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
    substance_files: list[Path], trait_ids: set[str]
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

    # Second pass: validate prefer_with refs against the full id set
    for sf, source, target in prefer_with_refs:
        if target not in seen_ids:
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
    supplements = inventory_data.get("supplements") or {}
    referenced_products: set[str] = set()

    for iid, entry in supplements.items():
        product_ref = entry.get("product")
        if not product_ref:
            continue
        referenced_products.add(product_ref)
        if product_ref not in product_ids:
            errors.append(
                f"{INVENTORY_PATH}: supplements.{iid}.product '{product_ref}' "
                f"has no matching product card (expected at data/products/{product_ref}.yaml)"
            )

    for pid, pf in product_ids.items():
        if pid not in referenced_products:
            print(
                f"WARN: {INVENTORY_PATH}: product formula '{pid}' has no inventory "
                f"entry (card at {pf}). Run: uv run planner.py refresh"
            )

    return errors


def check_inventory_overrides(
    inventory_data: dict, trait_ids: set[str]
) -> list[str]:
    errors: list[str] = []
    for sid, entry in (inventory_data.get("supplements") or {}).items():
        override = entry.get("traits_override")
        if not override:
            continue
        for action in ("add", "remove"):
            for tid in override.get(action) or []:
                if tid not in trait_ids:
                    errors.append(
                        f"{INVENTORY_PATH}: supplements.{sid}.traits_override.{action} "
                        f"references unknown trait '{tid}'"
                    )
    return errors


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
    errors.extend(check_inventory_alignment(inventory_data, product_ids))
    errors.extend(check_inventory_overrides(inventory_data, trait_ids))
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
            target_errors, target_info, _ = check_substances([target], trait_ids)
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

    supplements = inventory_data.get("supplements") or {}
    existing_products = {
        entry.get("product")
        for entry in supplements.values()
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
        print("inventory is in sync; no new supplements found")
        return 0

    for new_id in discovered:
        supplements[new_id] = {"product": new_id, "stack": "inactive"}

    inventory_data["supplements"] = supplements

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
        f"({{product: <id>, stack: inactive}}): {', '.join(discovered)}"
    )
    return 0


# ============================================================================
# plan: backtracking scheduler
# ============================================================================


def effective_traits(card: dict, inventory_entry: dict) -> set[str]:
    """Apply inventory traits_override to the card's trait set."""
    traits = set(card.get("traits", []) or [])
    override = inventory_entry.get("traits_override") or {}
    traits.update(override.get("add") or [])
    traits.difference_update(override.get("remove") or [])
    return traits


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


def product_traits(
    product: dict,
    inventory_entry: dict,
    substances: dict[str, dict],
) -> set[str]:
    traits: set[str] = set()
    for substance_id in product_component_substances(product):
        substance = substances.get(substance_id)
        if substance:
            traits.update(substance.get("traits") or [])
    override = inventory_entry.get("traits_override") or {}
    traits.update(override.get("add") or [])
    traits.difference_update(override.get("remove") or [])
    return traits


def slot_matches(slot: dict, match_pattern: dict) -> bool:
    """AND-only: slot satisfies match if all listed fields equal."""
    for key, value in match_pattern.items():
        if slot.get(key) != value:
            return False
    return True


def compute_slot_score(
    trait_ids: set[str], slot: dict, traits_data: dict
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
            if eff.get("block") is True:
                blocked = True
                reasons.append(f"{trait_id} BLOCK on match {match_pattern}")
            elif "level" in eff:
                level = eff["level"]
                delta = LEVEL_SCORES.get(level, 0)
                score += delta
                reasons.append(f"{trait_id} match {match_pattern} → {level} ({delta:+d})")
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
    active_products: dict[str, dict] = {}
    active_components: dict[str, set[str]] = {}
    item_stacks: dict[str, str] = {}
    for item_id, entry in (inventory_data.get("supplements") or {}).items():
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
        active[item_id] = product_traits(product, entry, substances)
        active_products[item_id] = product
        active_components[item_id] = set(product_component_substances(product))
        item_stacks[item_id] = stack

    if not active:
        print("plan: no non-inactive inventory items.", file=sys.stderr)
        return 1

    # Symmetric prefer_with pairs between schedulable product-backed inventory items.
    prefer_pairs: set[frozenset[str]] = set()
    component_to_items: dict[str, set[str]] = {}
    for item_id, component_ids in active_components.items():
        for component_id in component_ids:
            component_to_items.setdefault(component_id, set()).add(item_id)
    for item_id, component_ids in active_components.items():
        for component_id in component_ids:
            substance = substances.get(component_id) or {}
            for other in substance.get("prefer_with") or []:
                for other_item in component_to_items.get(other, set()):
                    if other_item != item_id:
                        prefer_pairs.add(frozenset([item_id, other_item]))

    # Candidate slots per substance: list of (slot_name, score, reasons)
    candidates: dict[str, list[tuple[str, int, list[str]]]] = {}
    for sid, traits in active.items():
        valid: list[tuple[str, int, list[str]]] = []
        for slot_name, slot in slots.items():
            if slot.get("stack") != item_stacks[sid]:
                continue
            score, blocked, reasons = compute_slot_score(traits, slot, traits_data)
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
            if any(must_separate(traits, e, traits_data) for e in slot_traits[slot_name]):
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
            score, _, _ = compute_slot_score(active[sid], slot, traits_data)
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
                if any(must_separate(traits, e, traits_data) for e in slot_traits[slot_name]):
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
                    assignment[next(iter(p))]
                    == assignment[next(reversed(list(p)))]
                ),
                "slot": assignment[next(iter(p))]
                if assignment[next(iter(p))] == assignment[next(reversed(list(p)))]
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
        score, _, reasons = compute_slot_score(active[sid], slot, traits_data)
        schedule["explanations"][sid] = {
            "slot": slot_name,
            "slot_score": score,
            "reasons": reasons,
        }

    for sid, traits in active.items():
        for trait_id in sorted(traits):
            trait_def = traits_data.get("traits", {}).get(trait_id)
            if trait_def and trait_def.get("warning"):
                schedule["warnings"].append(
                    {
                        "substance": sid,
                        "trait": trait_id,
                        "message": trait_def.get("description", "Manual review required."),
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
            "append missing product formulas to inventory.yaml as "
            "{product: <id>, stack: inactive}"
        ),
        description=(
            "Append missing product formulas to inventory.yaml as "
            "{product: <id>, stack: inactive}."
        ),
        formatter_class=argparse.RawTextHelpFormatter,
    )

    sub.add_parser("plan", help="generate schedule.yaml from non-inactive inventory")

    args = parser.parse_args()

    if args.cmd == "check":
        sys.exit(cmd_check(args.target))
    elif args.cmd == "refresh":
        sys.exit(cmd_refresh())
    elif args.cmd == "plan":
        sys.exit(cmd_plan())


if __name__ == "__main__":
    main()
