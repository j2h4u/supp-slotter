# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "pyyaml>=6.0",
#     "jsonschema>=4.21",
# ]
# ///
"""Supplement Slot Planner CLI.

Subcommands:
  check    validate slots/traits/products/inventory against schemas and cross-references
  refresh  add missing product entries to inventory.yaml as {stack: inactive}
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
PRODUCTS_DIR = DATA_DIR / "products"
GOALS_DIR = DATA_DIR / "goals"
INVENTORY_PATH = DATA_DIR / "inventory.yaml"
SCHEDULE_PATH = ROOT / "schedule.yaml"

VALID_LEVELS = {"avoid_strong", "avoid", "prefer", "prefer_strong"}
REGISTERED_NAMESPACES = {"intake", "effect", "class", "family", "risk", "activity"}
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


def load_product(pf: Path) -> tuple[dict | None, str | None]:
    """Load a product card. Returns (data, error_message). Either is None."""
    if not pf.exists():
        return None, f"{pf}: file does not exist"
    try:
        product = load_yaml(pf)
    except yaml.YAMLError as e:
        return None, f"{pf}: yaml parse error: {e}"
    if product is None:
        return None, f"{pf}: empty file"
    if not isinstance(product, dict):
        return None, f"{pf}: top-level must be a mapping, got {type(product).__name__}"
    return product, None


def check_products(
    product_files: list[Path], trait_ids: set[str]
) -> tuple[list[str], list[str], dict[str, Path]]:
    """Returns (errors, info, card_ids_to_path_map)."""
    errors: list[str] = []
    info: list[str] = []
    seen_ids: dict[str, Path] = {}
    prefer_with_refs: list[tuple[Path, str, str]] = []  # (pf, source_id, target_id)

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

        for tid in product.get("traits", []):
            if tid not in trait_ids:
                errors.append(f"{pf}: trait '{tid}' not defined in traits.yaml")

        for other in product.get("prefer_with") or []:
            if pid:
                if other == pid:
                    errors.append(
                        f"{pf}: prefer_with references self ('{pid}')"
                    )
                else:
                    prefer_with_refs.append((pf, pid, other))

        for concern in product.get("unmatched_concerns") or []:
            info.append(f"{pf}: unmatched_concern: {concern}")

    # Second pass: validate prefer_with refs against the full id set
    for pf, source, target in prefer_with_refs:
        if target not in seen_ids:
            errors.append(
                f"{pf}: prefer_with target '{target}' has no matching product card"
            )

    return errors, info, seen_ids


def check_inventory_alignment(
    inventory_data: dict, card_ids: dict[str, Path]
) -> list[str]:
    """Verify every product card has an inventory entry and vice versa."""
    errors: list[str] = []
    inventory_ids = set((inventory_data.get("supplements") or {}).keys())

    for pid, pf in card_ids.items():
        if pid not in inventory_ids:
            errors.append(
                f"{INVENTORY_PATH}: missing entry for '{pid}' "
                f"(card at {pf}). Run: uv run planner.py refresh"
            )

    for iid in sorted(inventory_ids):
        if iid not in card_ids:
            errors.append(
                f"{INVENTORY_PATH}: entry '{iid}' has no matching product card "
                f"(expected at data/products/{iid}.yaml)"
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


def check_goals(goal_files: list[Path], card_ids: dict[str, Path]) -> list[str]:
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
            if ref not in card_ids:
                errors.append(
                    f"{gf}: members[{i}].substance '{ref}' has no matching product card "
                    f"(expected at data/products/{ref}.yaml)"
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
        product_files = [target]
    else:
        product_files = sorted(PRODUCTS_DIR.glob("*.yaml"))

    p_errors, p_info, card_ids = check_products(product_files, trait_ids)
    errors.extend(p_errors)
    info.extend(p_info)

    # Inventory cross-check: only on full scan, not single-file mode
    if target is None:
        if not INVENTORY_PATH.exists():
            errors.append(f"missing: {INVENTORY_PATH}")
        else:
            inventory_data = load_yaml(INVENTORY_PATH)
            if not isinstance(inventory_data, dict):
                errors.append(f"{INVENTORY_PATH}: top-level must be a mapping")
            else:
                errors.extend(schema_errors(inventory_data, "inventory", INVENTORY_PATH))
                errors.extend(check_inventory_alignment(inventory_data, card_ids))
                errors.extend(check_inventory_overrides(inventory_data, trait_ids))
        goal_files = sorted(GOALS_DIR.glob("*.yaml")) if GOALS_DIR.exists() else []
        errors.extend(check_goals(goal_files, card_ids))

    return report(errors, info)


def cmd_refresh() -> int:
    if not INVENTORY_PATH.exists():
        print(f"missing: {INVENTORY_PATH}", file=sys.stderr)
        return 1

    inventory_data = load_yaml(INVENTORY_PATH)
    if not isinstance(inventory_data, dict):
        print(f"{INVENTORY_PATH}: top-level must be a mapping", file=sys.stderr)
        return 1

    supplements = inventory_data.get("supplements") or {}
    existing_ids = set(supplements.keys())

    discovered: list[str] = []
    for pf in sorted(PRODUCTS_DIR.glob("*.yaml")):
        product, err = load_product(pf)
        if err:
            print(f"WARN: {err}", file=sys.stderr)
            continue
        pid = product.get("id")
        if pid and pid not in existing_ids:
            discovered.append(pid)

    if not discovered:
        print("inventory is in sync; no new supplements found")
        return 0

    for new_id in discovered:
        supplements[new_id] = {"stack": "inactive"}

    inventory_data["supplements"] = supplements

    INVENTORY_PATH.write_text(
        yaml.safe_dump(
            inventory_data,
            sort_keys=False,
            default_flow_style=False,
            allow_unicode=True,
        )
    )

    print(f"added {len(discovered)} new entries (stack: inactive): {', '.join(discovered)}")
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

    # Non-inactive substances + effective traits + prefer_with pairs
    active: dict[str, set[str]] = {}
    cards: dict[str, dict] = {}
    sub_stacks: dict[str, str] = {}
    for sid, entry in (inventory_data.get("supplements") or {}).items():
        stack = entry.get("stack")
        if stack == "inactive":
            continue
        card_path = PRODUCTS_DIR / f"{sid}.yaml"
        card = load_yaml(card_path) if card_path.exists() else None
        if not isinstance(card, dict):
            print(f"plan: skipping '{sid}' — card missing or invalid", file=sys.stderr)
            continue
        active[sid] = effective_traits(card, entry)
        cards[sid] = card
        sub_stacks[sid] = stack

    if not active:
        print("plan: no non-inactive substances in inventory.", file=sys.stderr)
        return 1

    # Symmetric prefer_with pairs (only between active substances)
    prefer_pairs: set[frozenset[str]] = set()
    for sid, card in cards.items():
        for other in card.get("prefer_with") or []:
            if other in active and other != sid:
                prefer_pairs.add(frozenset([sid, other]))

    # Candidate slots per substance: list of (slot_name, score, reasons)
    candidates: dict[str, list[tuple[str, int, list[str]]]] = {}
    for sid, traits in active.items():
        valid: list[tuple[str, int, list[str]]] = []
        for slot_name, slot in slots.items():
            if slot.get("stack") != sub_stacks[sid]:
                continue
            score, blocked, reasons = compute_slot_score(traits, slot, traits_data)
            if blocked:
                continue
            valid.append((slot_name, score, reasons))
        if not valid:
            print(
                f"plan: substance '{sid}' is blocked from every slot.",
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
                f"plan: substance '{sid}' has no valid slot under separate_from "
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
        help="single product file to check (default: scan all)",
    )

    sub.add_parser(
        "refresh",
        help="append missing product cards to inventory.yaml as {stack: inactive}",
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
