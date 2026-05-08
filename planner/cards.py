"""Card domain: loaders, slugs, similarity/search, validators, formatters."""

from __future__ import annotations

import json
from difflib import SequenceMatcher
from pathlib import Path

import yaml

from planner.io import (
    DASHBOARDS_DIR,
    DATA_DIR,
    FIND_MIN_SCORE,
    FIND_MIN_WORD_SCORE,
    LEVEL_SCORES,
    NANOID_ALPHABET,
    PRODUCTS_DIR,
    REGISTERED_NAMESPACES,
    RELATIONS_PATH,
    REVIEW_CONTEXTS,
    ROOT,
    SCHEMA_DIR,
    SIMILAR_SUBSTANCE_THRESHOLD,
    SLOT_META_FIELDS,
    STABLE_ID_SIZE,
    STACKS_PATH,
    SUBSTANCES_DIR,
    VALID_LEVELS,
    WARNING_CATEGORY_LABELS,
    display_message,
    display_path,
    load_schema,
    load_yaml,
    schema_errors,
)

import secrets


def flatten_trait_defs(traits_data: dict) -> dict[str, dict]:
    traits: dict[str, dict] = {}
    for namespace, entries in traits_data.items():
        if not isinstance(namespace, str) or not isinstance(entries, dict):
            continue
        for short_name, trait in entries.items():
            if isinstance(short_name, str):
                traits[f"{namespace}:{short_name}"] = trait if isinstance(trait, dict) else {}
    return traits

def derive_slot_fields(slots_data: dict) -> set[str]:
    fields: set[str] = set()
    for slot in flatten_pillbox_slots(slots_data).values():
        fields.update(k for k in slot if k not in SLOT_META_FIELDS)
    return fields

def flatten_pillbox_slots(slots_data: dict) -> dict[str, dict]:
    slots: dict[str, dict] = {}
    if not isinstance(slots_data, dict):
        return slots

    for pillbox_name, pillbox in sorted(slots_data.items()):
        if not isinstance(pillbox, dict):
            continue
        pillbox_slots = pillbox.get("slots", {})
        if not isinstance(pillbox_slots, dict):
            continue
        for slot_name, slot in sorted(
            pillbox_slots.items(),
            key=lambda kv: kv[1].get("order", 0) if isinstance(kv[1], dict) else 0,
        ):
            if not isinstance(slot, dict):
                continue
            slots[slot_name] = {
                **slot,
                "pillbox": pillbox_name,
                "pillbox_label": pillbox.get("label", pillbox_name),
                "stack": pillbox_name,
            }
    return slots

def build_empty_schedule_pillboxes(slots_data: dict) -> dict[str, dict]:
    out: dict[str, dict] = {}
    if not isinstance(slots_data, dict):
        return out

    for pillbox_name, pillbox in slots_data.items():
        if not isinstance(pillbox, dict):
            continue
        out[pillbox_name] = {
            "label": pillbox.get("label", pillbox_name),
            "slots": {},
        }
        pillbox_slots = pillbox.get("slots", {})
        if not isinstance(pillbox_slots, dict):
            continue
        for slot_name, slot in sorted(
            pillbox_slots.items(),
            key=lambda kv: kv[1].get("order", 0) if isinstance(kv[1], dict) else 0,
        ):
            if not isinstance(slot, dict):
                continue
            out[pillbox_name]["slots"][slot_name] = {
                "label": slot.get("label", slot_name),
                "products": [],
                "substances": [],
            }
    return out

def check_pillbox_slot_ids(slots_data: dict, slots_path: Path) -> list[str]:
    errors: list[str] = []
    seen: dict[str, str] = {}
    if not isinstance(slots_data, dict):
        return errors
    for pillbox_name, pillbox in slots_data.items():
        if not isinstance(pillbox, dict):
            continue
        pillbox_slots = pillbox.get("slots", {})
        if not isinstance(pillbox_slots, dict):
            continue
        for slot_name in pillbox_slots:
            previous_pillbox = seen.get(slot_name)
            if previous_pillbox is not None:
                errors.append(
                    f"{slots_path}: slot id '{slot_name}' is used in both "
                    f"'{previous_pillbox}' and '{pillbox_name}'; slot ids must be "
                    "unique across pillboxes"
                )
            else:
                seen[slot_name] = pillbox_name
    return errors

def check_traits(
    traits_data: dict, traits_path: Path, slot_fields: set[str]
) -> list[str]:
    errors: list[str] = []
    trait_defs = flatten_trait_defs(traits_data)
    trait_ids = set(trait_defs)

    for trait_id, trait in trait_defs.items():
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

def normalize_filename_part(value: str) -> str:
    normalized = value.lower().replace("&", " and ").replace("'", "").replace("’", "")
    chars = [char if char.isascii() and char.isalnum() else "_" for char in normalized]
    return "_".join(part for part in "".join(chars).split("_") if part)

def normalize_similarity_text(value: str) -> str:
    normalized = value.lower().replace("&", " and ").replace("'", "").replace("’", "")
    chars = [char if char.isascii() and char.isalnum() else " " for char in normalized]
    return " ".join("".join(chars).split())

def product_brand_slug(product: dict) -> str:
    return normalize_filename_part(str(product.get("brand") or "unknown")) or "unknown"

def product_name_slug(product: dict) -> str:
    return normalize_filename_part(str(product.get("name") or "")) or "product"

def generate_stable_id(prefix: str) -> str:
    token = "".join(secrets.choice(NANOID_ALPHABET) for _ in range(STABLE_ID_SIZE))
    return f"{prefix}_{token}"

def canonical_product_filename(product: dict) -> str:
    product_id = str(product.get("id") or "missing_id")
    return f"{product_brand_slug(product)}__{product_name_slug(product)}__{product_id}.yaml"

def substance_slug(substance: dict) -> str:
    name = str(substance.get("name") or "")
    form = substance.get("form")
    if isinstance(form, str) and form:
        return normalize_filename_part(f"{name} {form}")
    return normalize_filename_part(name)

def canonical_substance_filename(substance: dict) -> str:
    substance_id = str(substance.get("id") or "missing_id")
    return f"{substance_slug(substance)}__{substance_id}.yaml"

def format_substance_candidate(substance_id: str, substance: dict) -> str:
    label = format_substance_name(substance)
    return f"{substance_id} {label}"

def substance_similarity_terms(substance: dict) -> list[tuple[str, bool]]:
    terms: list[tuple[str, bool]] = []

    name = substance.get("name")
    form = substance.get("form")
    if isinstance(name, str):
        if isinstance(form, str):
            terms.append((f"{name} {form}", True))
        else:
            terms.append((name, True))

    for alias in substance.get("aliases") or []:
        if isinstance(alias, str):
            terms.append((alias, False))

    normalized_terms: list[tuple[str, bool]] = []
    for term, is_primary in terms:
        normalized = normalize_similarity_text(term)
        normalized_entry = (normalized, is_primary)
        if normalized and normalized_entry not in normalized_terms:
            normalized_terms.append(normalized_entry)
    return normalized_terms

def similarity_score(
    left_terms: list[tuple[str, bool]],
    right_terms: list[tuple[str, bool]],
) -> float:
    scores: list[float] = []
    for left, left_primary in left_terms:
        for right, right_primary in right_terms:
            if left == right:
                if left_primary or right_primary:
                    return 1.0
                continue
            if left_primary and right_primary:
                scores.append(SequenceMatcher(None, left, right).ratio())
    return max(scores) if scores else 0.0

def substance_name_key(substance: dict) -> str:
    name = substance.get("name")
    if not isinstance(name, str):
        return ""
    return normalize_similarity_text(name)

def substance_display_name(substance: dict) -> str:
    name = substance.get("name")
    if isinstance(name, str) and name:
        return name
    return str(substance.get("id") or "Unknown substance")

def collect_search_strings(value: object) -> list[str]:
    strings: list[str] = []
    if isinstance(value, str):
        strings.append(value)
    elif isinstance(value, dict):
        for child in value.values():
            strings.extend(collect_search_strings(child))
    elif isinstance(value, list):
        for child in value:
            strings.extend(collect_search_strings(child))
    return strings

def search_words(values: list[str]) -> set[str]:
    words: set[str] = set()
    for value in values:
        words.update(normalize_similarity_text(value).split())
    return words

def word_match_score(query_word: str, candidate_words: set[str]) -> float:
    if query_word in candidate_words:
        return 1.0

    scores: list[float] = []
    for candidate_word in candidate_words:
        shorter = min(len(query_word), len(candidate_word))
        longer = max(len(query_word), len(candidate_word))
        length_ratio = shorter / longer if longer else 0
        if (
            length_ratio >= 0.65
            and (query_word in candidate_word or candidate_word in query_word)
        ):
            scores.append(0.9)
        else:
            scores.append(SequenceMatcher(None, query_word, candidate_word).ratio())
    return max(scores) if scores else 0.0

def search_score(query: str, values: list[str]) -> float:
    query_text = normalize_similarity_text(query)
    query_words = query_text.split()
    if not query_words:
        return 0.0

    candidate_text = normalize_similarity_text(" ".join(values))
    candidate_words = search_words(values)
    word_scores = [
        word_match_score(query_word, candidate_words)
        for query_word in query_words
    ]
    if min(word_scores) < FIND_MIN_WORD_SCORE:
        return 0.0
    score = sum(word_scores) / len(word_scores)
    if query_text and query_text in candidate_text:
        score = max(score, 0.98)
    return score

def combined_search_score(
    query: str,
    identity_values: list[str],
    full_values: list[str],
) -> float:
    identity_score = search_score(query, identity_values)
    full_score = search_score(query, full_values)
    if identity_score > 0:
        return max(identity_score, full_score)
    return full_score * 0.75

def format_find_result(score: float, card_id: str, label: str, path: Path) -> str:
    return f"  {score:.2f}  {card_id}  {label}\n        {display_path(path)}"

def find_substance_results(query: str) -> list[tuple[float, str, str, Path]]:
    results: list[tuple[float, str, str, Path]] = []
    for path in sorted(SUBSTANCES_DIR.glob("*.yaml")):
        substance, err = load_substance(path)
        if err is not None or substance is None:
            continue
        substance_id = substance.get("id")
        if not isinstance(substance_id, str):
            continue
        identity_values = [
            substance_id,
            str(substance.get("name") or ""),
            str(substance.get("form") or ""),
            path.name,
        ]
        identity_values.extend(
            alias for alias in substance.get("aliases") or [] if isinstance(alias, str)
        )
        full_values = collect_search_strings(substance)
        full_values.append(path.name)
        score = combined_search_score(query, identity_values, full_values)
        if score >= FIND_MIN_SCORE:
            results.append((score, substance_id, format_substance_name(substance), path))
    return sorted(results, key=lambda item: (-item[0], item[2].casefold(), item[1]))

def find_product_results(query: str) -> list[tuple[float, str, str, Path]]:
    results: list[tuple[float, str, str, Path]] = []
    for path in sorted(PRODUCTS_DIR.glob("*.yaml")):
        product, err = load_product(path)
        if err is not None or product is None:
            continue
        product_id = product.get("id")
        if not isinstance(product_id, str):
            continue
        identity_values = [
            product_id,
            str(product.get("brand") or ""),
            str(product.get("name") or ""),
            path.name,
        ]
        identity_values.extend(
            url for url in product.get("urls") or [] if isinstance(url, str)
        )
        full_values = collect_search_strings(product)
        full_values.append(path.name)
        score = combined_search_score(query, identity_values, full_values)
        if score >= FIND_MIN_SCORE:
            results.append((score, product_id, format_product_name(product), path))
    return sorted(results, key=lambda item: (-item[0], item[2].casefold(), item[1]))

def connected_components(edges: dict[str, set[str]]) -> list[list[str]]:
    seen: set[str] = set()
    components: list[list[str]] = []

    for node in sorted(edges):
        if node in seen:
            continue
        stack = [node]
        component: list[str] = []
        seen.add(node)
        while stack:
            current = stack.pop()
            component.append(current)
            for next_node in sorted(edges[current]):
                if next_node in seen:
                    continue
                seen.add(next_node)
                stack.append(next_node)
        if len(component) > 1:
            components.append(sorted(component))
    return components

def substance_cluster_label(substances: dict[str, dict], component: list[str]) -> str:
    name_counts: dict[str, int] = {}
    display_names: dict[str, str] = {}
    for substance_id in component:
        substance = substances[substance_id]
        name_key = substance_name_key(substance)
        if not name_key:
            continue
        name_counts[name_key] = name_counts.get(name_key, 0) + 1
        display_names.setdefault(name_key, substance_display_name(substance))

    if name_counts:
        best_key = sorted(
            name_counts,
            key=lambda key: (-name_counts[key], display_names[key].casefold()),
        )[0]
        return display_names[best_key]

    first_substance = substances[component[0]]
    return substance_display_name(first_substance)

def collect_similar_substances(substances: dict[str, dict]) -> list[str]:
    clusters: list[str] = []
    substance_items = sorted(substances.items())
    terms_by_id = {
        substance_id: substance_similarity_terms(substance)
        for substance_id, substance in substance_items
    }
    edges: dict[str, set[str]] = {substance_id: set() for substance_id in substances}

    for index, (left_id, left_substance) in enumerate(substance_items):
        for right_id, right_substance in substance_items[index + 1 :]:
            same_name = (
                substance_name_key(left_substance)
                and substance_name_key(left_substance) == substance_name_key(right_substance)
            )
            score = similarity_score(terms_by_id[left_id], terms_by_id[right_id])
            if not same_name and score < SIMILAR_SUBSTANCE_THRESHOLD:
                continue
            edges[left_id].add(right_id)
            edges[right_id].add(left_id)

    for component in connected_components(edges):
        label = substance_cluster_label(substances, component)
        entries = [
            format_substance_candidate(substance_id, substances[substance_id])
            for substance_id in component
        ]
        cluster_lines = [label]
        cluster_lines.extend(f"    - {entry}" for entry in sorted(entries, key=str.casefold))
        clusters.append("\n".join(cluster_lines))

    return sorted(clusters, key=lambda cluster: cluster.splitlines()[0].casefold())

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
    seen_substances: dict[str, dict] = {}
    prefer_with_refs: list[tuple[Path, str, str]] = []  # (sf, source_id, target_id)

    for sf in substance_files:
        substance, err = load_substance(sf)
        if err:
            errors.append(err)
            continue

        errors.extend(schema_errors(substance, "substance", sf))

        sid = substance.get("id")
        if sid:
            expected_filename = canonical_substance_filename(substance)
            if sf.name != expected_filename:
                errors.append(
                    f"{sf}: substance filename must be '{expected_filename}'"
                )
            if sid in seen_ids:
                errors.append(
                    f"{sf}: duplicate id '{sid}' (also in {seen_ids[sid]})"
                )
            else:
                seen_ids[sid] = sf
                substance["_path"] = str(sf)
                seen_substances[sid] = substance

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

    # Second pass: validate substance refs against the full id set.
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
            expected_filename = canonical_product_filename(product)
            if pf.name != expected_filename:
                errors.append(
                    f"{pf}: product filename must be '{expected_filename}'"
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

def check_stack_alignment(
    stacks_data: dict, product_ids: dict[str, Path]
) -> list[str]:
    """Verify stack entries reference product cards and flag shelf candidates."""
    errors: list[str] = []
    referenced_products: set[str] = set()

    for _item_id, entry in normalize_stack_entries(stacks_data).items():
        if not isinstance(entry, dict):
            continue
        product_ref = entry.get("product")
        if not product_ref:
            continue
        referenced_products.add(product_ref)
        if product_ref not in product_ids:
            stack = entry.get("stack", "<unknown>")
            errors.append(
                f"{STACKS_PATH}: {stack} contains product '{product_ref}' "
                "has no matching product card id under data/products/"
            )

    for pid, pf in product_ids.items():
        if pid not in referenced_products:
            print(
                f"WARN: {STACKS_PATH}: product '{pid}' has no stack "
                f"entry (card at {pf}). Add it to a stack if it is on the shelf."
            )

    return errors

def check_stack_duplicate_items(stacks_data: dict) -> list[str]:
    errors: list[str] = []
    seen: dict[str, str] = {}

    for stack, items in stacks_data.items():
        if not isinstance(items, list):
            continue
        for item_id in items:
            if not isinstance(item_id, str):
                continue
            previous_stack = seen.get(item_id)
            if previous_stack is not None:
                errors.append(
                    f"{STACKS_PATH}: stack item '{item_id}' appears in "
                    f"multiple stacks: {previous_stack}, {stack}"
                )
            else:
                seen[item_id] = stack
    return errors

def normalize_stack_entries(stacks_data: dict) -> dict[str, dict]:
    """Return product ids keyed by item id with stack attached in memory."""
    normalized: dict[str, dict] = {}

    for stack, items in stacks_data.items():
        if not isinstance(items, list):
            continue
        for product_id in items:
            if not isinstance(product_id, str):
                continue
            normalized[product_id] = {"product": product_id, "stack": stack}
    return normalized

def collect_product_substance_refs(
    products: dict[str, dict], product_ids: set[str]
) -> set[str]:
    refs: set[str] = set()
    for product_id in product_ids:
        product = products.get(product_id)
        if not isinstance(product, dict):
            continue
        refs.update(product_component_substances(product))
    return refs

def load_global_relations() -> list[dict]:
    if not RELATIONS_PATH.exists():
        return []
    data = load_yaml(RELATIONS_PATH)
    if not isinstance(data, dict):
        return []
    relations: list[dict] = []
    for relation_type in ("balance", "supports", "competes", "antagonizes"):
        relation_items = data.get(relation_type)
        if not isinstance(relation_items, list):
            continue
        for relation in relation_items:
            if isinstance(relation, dict):
                relations.append({"type": relation_type, **relation})
    return relations

def substance_names(substances: dict[str, dict]) -> set[str]:
    return {
        name
        for substance in substances.values()
        if isinstance((name := substance.get("name")), str)
    }

def global_relation_refs(
    substances: dict[str, dict],
    global_relations: list[dict],
) -> set[str]:
    refs = {
        value
        for relation in global_relations
        for key in ("source_substance", "target_substance")
        if isinstance((value := relation.get(key)), str)
    }
    names = {
        value
        for relation in global_relations
        for key in ("source_name", "target_name")
        if isinstance((value := relation.get(key)), str)
    }
    refs.update({
        substance_id
        for substance_id, substance in substances.items()
        if isinstance(substance.get("name"), str) and substance["name"] in names
    })
    return refs

def relation_endpoint_value(relation: dict, side: str) -> str | None:
    for suffix in ("substance", "name"):
        value = relation.get(f"{side}_{suffix}")
        if isinstance(value, str):
            return value
    return None

def substance_matches_relation_endpoint(
    substance_id: str,
    substance: dict,
    relation: dict,
    side: str,
) -> bool:
    exact_id = relation.get(f"{side}_substance")
    if isinstance(exact_id, str):
        return substance_id == exact_id
    expected_name = relation.get(f"{side}_name")
    return isinstance(expected_name, str) and substance.get("name") == expected_name

def relation_endpoint_is_active(
    relation: dict,
    side: str,
    substances: dict[str, dict],
    active_substances: set[str],
) -> bool:
    for substance_id in active_substances:
        substance = substances.get(substance_id)
        if isinstance(substance, dict) and substance_matches_relation_endpoint(
            substance_id,
            substance,
            relation,
            side,
        ):
            return True
    return False

def relation_endpoint_display(
    relation: dict,
    side: str,
    substances: dict[str, dict],
) -> tuple[str, str]:
    exact_id = relation.get(f"{side}_substance")
    if isinstance(exact_id, str):
        return exact_id, format_substance_name(substances.get(exact_id) or {"id": exact_id})
    name = relation.get(f"{side}_name")
    if isinstance(name, str):
        return name, name
    return "<unknown>", "<unknown>"

def relation_endpoint_match_label(
    relation: dict,
    side: str,
    substance_id: str | None,
    substance: dict,
) -> str | None:
    exact_id = relation.get(f"{side}_substance")
    if isinstance(exact_id, str) and substance_id == exact_id:
        return f"{side} exact id"
    expected_name = relation.get(f"{side}_name")
    if isinstance(expected_name, str) and substance.get("name") == expected_name:
        return f"{side} exact name"
    return None

def collect_substance_relation_matches(
    substance: dict,
    global_relations: list[dict],
) -> list[tuple[dict, list[str]]]:
    substance_id = substance.get("id")
    if not isinstance(substance_id, str):
        substance_id = None

    matches: list[tuple[dict, list[str]]] = []
    for relation in global_relations:
        matched_by = [
            label
            for side in ("source", "target")
            if (
                label := relation_endpoint_match_label(
                    relation,
                    side,
                    substance_id,
                    substance,
                )
            )
        ]
        if matched_by:
            matches.append((relation, matched_by))
    return matches

def print_central_relation_matches(
    substance: dict,
    substances: dict[str, dict],
) -> None:
    print("\nCentral relations from data/relations.yaml (read-only)")
    print("Edit these in data/relations.yaml, not in this substance card.")
    substance_id = substance.get("id")
    if isinstance(substance_id, str):
        print(f"Matches this substance by id: {substance_id}")
    name = substance.get("name")
    if isinstance(name, str):
        print(f"Matches this substance by exact name: {name}")

    matches = collect_substance_relation_matches(substance, load_global_relations())
    if not matches:
        print("  none matched; add links in data/relations.yaml if needed.")
        return

    print("Note: balance/competes are symmetric; supports/antagonizes are directional.")
    grouped: dict[str, list[tuple[dict, list[str]]]] = {}
    for relation, matched_by in matches:
        relation_type = str(relation.get("type") or "unknown")
        grouped.setdefault(relation_type, []).append((relation, matched_by))

    for relation_type in ("balance", "competes", "supports", "antagonizes"):
        relation_group = grouped.get(relation_type)
        if not relation_group:
            continue
        print(f"\n{relation_type}")
        for relation, matched_by in relation_group:
            _source_key, source_name = relation_endpoint_display(
                relation,
                "source",
                substances,
            )
            _target_key, target_name = relation_endpoint_display(
                relation,
                "target",
                substances,
            )
            print(f"  {source_name} -> {target_name}")
            print(f"    matched by: {', '.join(matched_by)}")
            reason = relation.get("reason")
            if isinstance(reason, str) and reason:
                print(f"    reason: {reason}")
            action = relation.get("action")
            if isinstance(action, str) and action:
                print(f"    action: {action}")

def check_global_relations(
    relations_data: object,
    substances: dict[str, dict],
) -> list[str]:
    errors: list[str] = []
    errors.extend(schema_errors(relations_data, "relations", RELATIONS_PATH))
    if errors or not isinstance(relations_data, dict):
        return errors

    names = substance_names(substances)
    relation_items = [
        (relation_type, index, relation)
        for relation_type in ("balance", "supports", "competes", "antagonizes")
        for index, relation in enumerate(relations_data.get(relation_type) or [])
    ]
    for relation_type, index, relation in relation_items:
        if not isinstance(relation, dict):
            continue
        path = f"{RELATIONS_PATH}: {relation_type}[{index}]"
        source_name = relation.get("source_name")
        target_name = relation.get("target_name")
        source_substance = relation.get("source_substance")
        target_substance = relation.get("target_substance")
        if isinstance(source_name, str) and source_name not in names:
            errors.append(
                f"{path}.source_name '{source_name}' has no matching substance name"
            )
        if isinstance(target_name, str) and target_name not in names:
            errors.append(
                f"{path}.target_name '{target_name}' has no matching substance name"
            )
        if isinstance(source_substance, str) and source_substance not in substances:
            errors.append(
                f"{path}.source_substance '{source_substance}' has no matching substance card"
            )
        if isinstance(target_substance, str) and target_substance not in substances:
            errors.append(
                f"{path}.target_substance '{target_substance}' has no matching substance card"
            )
        source = relation_endpoint_value(relation, "source")
        target = relation_endpoint_value(relation, "target")
        if source is not None and source == target:
            errors.append(f"{path} references the same source and target")
    return errors

def collect_missing_balance_relations(
    substances: dict[str, dict],
    active_substances: set[str],
    global_relations: list[dict] | None = None,
) -> list[dict]:
    warnings: list[dict] = []
    active_names = collect_active_substance_names(substances, active_substances)
    seen: set[tuple[str, str, str]] = set()
    for relation in global_relations or []:
        if relation.get("type") != "balance":
            continue
        pairs = (("source", "target"), ("target", "source"))
        for active_side, missing_side in pairs:
            if not relation_endpoint_is_active(
                relation,
                active_side,
                substances,
                active_substances,
            ) or relation_endpoint_is_active(
                relation,
                missing_side,
                substances,
                active_substances,
            ):
                continue
            source_key, source_name = relation_endpoint_display(
                relation,
                active_side,
                substances,
            )
            target_key, target_name = relation_endpoint_display(
                relation,
                missing_side,
                substances,
            )
            warning_key = (source_key, "balance", target_key)
            if warning_key in seen:
                continue
            seen.add(warning_key)
            reason = relation.get("reason")
            action = relation.get("action")
            warnings.append(
                {
                    "type": "missing_balance_substance",
                    "source_substance": source_key,
                    "source_name": source_name,
                    "target_substance": target_key,
                    "target_name": target_name,
                    "reason": reason if isinstance(reason, str) else "",
                    "action": action if isinstance(action, str) else "",
                }
            )
    return warnings

def collect_active_substance_names(
    substances: dict[str, dict],
    active_substances: set[str],
) -> set[str]:
    return {
        substance.get("name")
        for substance_id in active_substances
        if isinstance((substance := substances.get(substance_id)), dict)
        and isinstance(substance.get("name"), str)
    }

def substance_is_covered_by_active_name(
    substance_id: str,
    substances: dict[str, dict],
    active_names: set[str],
) -> bool:
    substance = substances.get(substance_id)
    if not isinstance(substance, dict):
        return False
    name = substance.get("name")
    return isinstance(name, str) and name in active_names

def collect_missing_support_relations(
    substances: dict[str, dict],
    active_substances: set[str],
    global_relations: list[dict] | None = None,
) -> list[dict]:
    warnings: list[dict] = []
    active_names = collect_active_substance_names(substances, active_substances)
    seen: set[tuple[str, str, str]] = set()
    for relation in global_relations or []:
        if relation.get("type") != "supports":
            continue
        if not relation_endpoint_is_active(
            relation,
            "target",
            substances,
            active_substances,
        ) or relation_endpoint_is_active(
            relation,
            "source",
            substances,
            active_substances,
        ):
            continue
        source_key, source_name = relation_endpoint_display(
            relation,
            "source",
            substances,
        )
        target_key, target_name = relation_endpoint_display(
            relation,
            "target",
            substances,
        )
        warning_key = (source_key, "supports", target_key)
        if warning_key in seen:
            continue
        seen.add(warning_key)
        reason = relation.get("reason")
        action = relation.get("action")
        warnings.append(
            {
                "type": "missing_support_substance",
                "source_substance": source_key,
                "source_name": source_name,
                "target_substance": target_key,
                "target_name": target_name,
                "reason": reason if isinstance(reason, str) else "",
                "action": action if isinstance(action, str) else "",
            }
        )
    return warnings

def global_relation_matches(
    left_id: str,
    right_id: str,
    substances: dict[str, dict],
    relation: dict,
    relation_type: str,
) -> bool:
    if relation.get("type") != relation_type:
        return False
    left = substances.get(left_id)
    right = substances.get(right_id)
    if not isinstance(left, dict) or not isinstance(right, dict):
        return False
    if relation_type in {"balance", "competes"}:
        return (
            substance_matches_relation_endpoint(left_id, left, relation, "source")
            and substance_matches_relation_endpoint(right_id, right, relation, "target")
        ) or (
            substance_matches_relation_endpoint(left_id, left, relation, "target")
            and substance_matches_relation_endpoint(right_id, right, relation, "source")
        )
    return substance_matches_relation_endpoint(
        left_id,
        left,
        relation,
        "source",
    ) and substance_matches_relation_endpoint(right_id, right, relation, "target")

def components_have_global_relation(
    left_id: str,
    right_id: str,
    substances: dict[str, dict],
    relation_type: str,
    global_relations: list[dict] | None,
) -> bool:
    for relation in global_relations or []:
        if global_relation_matches(left_id, right_id, substances, relation, relation_type):
            return True
        if global_relation_matches(right_id, left_id, substances, relation, relation_type):
            return True
    return False

def component_sets_have_relation(
    left_components: list[str],
    right_components: list[str],
    substances: dict[str, dict],
    relation_type: str,
    global_relations: list[dict] | None = None,
) -> bool:
    for left_id in left_components:
        for right_id in right_components:
            if left_id == right_id:
                continue
            if components_have_global_relation(
                left_id,
                right_id,
                substances,
                relation_type,
                global_relations,
            ):
                return True
    return False

def collect_intra_product_relation_conflicts(
    *,
    item_id: str,
    product_id: str,
    component_ids: list[str],
    substances: dict[str, dict],
    relation_type: str,
    global_relations: list[dict] | None = None,
) -> list[dict]:
    conflicts: list[dict] = []
    component_set = set(component_ids)
    seen_pairs: set[frozenset[str]] = set()
    for index, source_id in enumerate(component_ids):
        for target_id in component_ids[index + 1 :]:
            if source_id == target_id:
                continue
            pair_key = frozenset([source_id, target_id])
            if pair_key in seen_pairs:
                continue
            relation = next(
                (
                    candidate
                    for candidate in global_relations or []
                    if components_have_global_relation(
                        source_id,
                        target_id,
                        substances,
                        relation_type,
                        [candidate],
                    )
                ),
                None,
            )
            if relation is None:
                continue
            seen_pairs.add(pair_key)
            conflicts.append(
                {
                    "type": "intra_product_relation_conflict",
                    "item": item_id,
                    "product": product_id,
                    "relation": relation_type,
                    "source_substance": source_id,
                    "target_substance": target_id,
                    "message": (
                        "Component relation conflicts inside one physical product; "
                        "scheduling keeps the product together and emits this warning"
                    ),
                    "action": relation.get("action", ""),
                }
            )
    return conflicts

def format_relation_warning(warning: dict) -> str:
    def endpoint(key: str, name: str) -> str:
        return name if key == name else f"{key} ({name})"

    reason = warning.get("reason")
    suffix = f": {reason}" if reason else ""
    return (
        f"{endpoint(warning['source_substance'], warning['source_name'])} -> "
        f"{endpoint(warning['target_substance'], warning['target_name'])}{suffix}"
    )

def warning_action(warning_type: str, trait: str, relation: str) -> str:
    if warning_type == "unmatched_concern":
        return "Review unresolved active concerns before treating the schedule as final."
    if warning_type == "intra_product_relation_conflict":
        return "Review this product manually; competing components are inside one physical product and cannot be separated by scheduling."
    if warning_type == "intra_product_trait_conflict":
        return "Review this product manually; its components have conflicting timing preferences."
    if warning_type == "ambiguous_prefer_with":
        return "Choose the intended companion product before relying on co-location."
    if warning_type == "missing_balance_substance":
        return "Review whether the paired balancing substance should be present in the active stack."
    if warning_type == "missing_support_substance":
        return "Review whether adding the supporting substance would improve this target in the active stack."
    if warning_type == "risk_cluster_load":
        return "Review this clustered risk load before treating the schedule as final."
    if trait == "risk:manual_review":
        return "Review this substance/product context manually before treating the schedule as final."
    if trait == "risk:narrow_therapeutic_window":
        return "Review total daily amount across products and avoid accidental stacking."
    if trait == "risk:hyperkalemia_med_interaction":
        return "Review potassium-related medication context before using this stack."
    if relation == "competes":
        return "Keep these substances away from the same slot when they are in separate products."
    return "Review this warning before treating the schedule as final."

def review_context_key(warning: dict) -> str | None:
    concern = str(warning.get("concern") or "")
    category = str(warning.get("category") or "")
    action = str(warning.get("action") or "")
    text = " ".join([concern, category, action]).lower()

    if "bleeding" in text or "fibrinolytic" in text or "antiplatelet" in text:
        return "bleeding_context"
    if "cholinergic" in text:
        return "cholinergic_load"
    if "blood-pressure" in text or "blood pressure" in text or "hypotension" in text:
        return "blood_pressure"
    if "inside one product" in text or "intra-product" in text:
        return "intra_product_conflicts"
    if "missing balance" in text or "missing support" in text or "paired" in text:
        return "missing_pairings"
    if "narrow therapeutic window" in text or "narrow-window" in text:
        return "narrow_window_minerals"
    if "potassium" in text or "hyperkalemia" in text:
        return "potassium_medication"
    if "timing conflict" in text:
        return "timing_conflicts"
    if "unmatched" in text or "unresolved active concern" in text:
        return "unmatched_concerns"
    return None

def warning_subject(warning: dict) -> str:
    risk = warning.get("risk")
    if isinstance(risk, str) and risk:
        return risk
    for key in ("product", "substance", "source", "target"):
        value = warning.get(key)
        if isinstance(value, str) and value:
            return value
    return "Stack"

def build_review_contexts(warnings: list[dict]) -> list[dict]:
    grouped: dict[str, dict[str, set[str]]] = {}
    for warning in warnings:
        key = review_context_key(warning)
        if key is None:
            continue
        context = grouped.setdefault(key, {"items": set(), "actions": set()})
        context["items"].add(warning_subject(warning))
        action = warning.get("action")
        if isinstance(action, str) and action:
            context["actions"].add(action)

    return [
        {
            "context": REVIEW_CONTEXTS.get(key, key.replace("_", " ").title()),
            "items": sorted(value["items"], key=str.casefold),
            "actions": sorted(value["actions"], key=str.casefold),
        }
        for key, value in sorted(grouped.items())
    ]

def humanize_warning(
    warning: dict,
    *,
    products: dict[str, dict],
    substances: dict[str, dict],
) -> dict:
    warning_type = str(warning.get("type") or "review")
    trait = str(warning.get("trait") or "")
    relation = str(warning.get("relation") or "")
    product_id = warning.get("product")
    product = (
        format_product_name(products.get(product_id) or {"id": product_id})
        if isinstance(product_id, str)
        else None
    )
    out: dict = {
        "category": WARNING_CATEGORY_LABELS.get(
            warning_type,
            "Review",
        )
    }
    if warning_type == "risk_cluster_load":
        cluster = warning.get("cluster")
        if isinstance(cluster, str) and cluster:
            out["risk"] = cluster
            out["concern"] = cluster
        active_members = warning.get("active")
        if isinstance(active_members, list):
            out["active"] = [
                format_substance_name(substances.get(sid) or {"id": sid})
                for sid in active_members
                if isinstance(sid, str)
            ]
    if product:
        out["product"] = product

    substance_id = warning.get("substance")
    if isinstance(substance_id, str):
        out["substance"] = format_substance_name(
            substances.get(substance_id) or {"id": substance_id}
        )

    source_id = warning.get("source_substance")
    target_id = warning.get("target_substance")
    if isinstance(source_id, str):
        out["source"] = (
            format_substance_name(substances[source_id])
            if source_id in substances
            else str(warning.get("source_name") or source_id)
        )
    if isinstance(target_id, str):
        out["target"] = (
            format_substance_name(substances[target_id])
            if target_id in substances
            else str(warning.get("target_name") or target_id)
        )

    if warning_type == "risk_cluster_load":
        pass
    elif trait:
        out["concern"] = trait.split(":", 1)[1].replace("_", " ")
    elif relation:
        out["concern"] = relation.replace("_", " ")
    elif warning_type.startswith("missing_"):
        out["concern"] = warning_type.replace("_", " ")
    else:
        out["concern"] = warning_type.replace("_", " ")

    message = warning.get("message") or warning.get("reason")
    if isinstance(message, str) and message:
        if "operator attention" not in message:
            out["note"] = message
    action = warning.get("action")
    out["action"] = (
        action if isinstance(action, str) and action else warning_action(warning_type, trait, relation)
    )
    return out

def is_generic_manual_review_warning(warning: dict) -> bool:
    return warning.get("trait") == "risk:manual_review"

def build_action_points(warnings: list[dict]) -> list[str]:
    subjects_by_action: dict[str, set[str]] = {}
    for warning in warnings:
        concern = warning.get("concern")
        if concern == "manual review":
            continue
        product = warning.get("product")
        substance = warning.get("substance") or warning.get("source")
        action = warning.get("action")
        if not isinstance(action, str):
            continue
        if warning.get("category") == "Unresolved active concern":
            subject = "Unresolved active concerns"
        else:
            subject = product or substance or "Stack"
        subjects_by_action.setdefault(action, set()).add(str(subject))

    points: list[str] = []
    for action, subjects in subjects_by_action.items():
        subject_list = sorted(subjects, key=str.casefold)
        if len(subject_list) == 1:
            points.append(f"{subject_list[0]}: {action}")
        else:
            points.append(f"{'; '.join(subject_list)}: {action}")
    return points[:8]

def collect_active_unmatched_concerns(
    *,
    active_order: list[str],
    active_components: dict[str, list[str]],
    item_products: dict[str, str],
    products: dict[str, dict],
    substances: dict[str, dict],
) -> list[dict]:
    warnings: list[dict] = []
    seen: set[tuple[str, str, str]] = set()
    for item_id in active_order:
        product_id = item_products[item_id]
        product = products.get(product_id) or {}
        for concern in product.get("unmatched_concerns") or []:
            if not isinstance(concern, str):
                continue
            key = ("product", product_id, concern)
            if key in seen:
                continue
            seen.add(key)
            warnings.append(
                {
                    "type": "unmatched_concern",
                    "item": item_id,
                    "product": product_id,
                    "message": concern,
                }
            )
        for substance_id in active_components[item_id]:
            substance = substances.get(substance_id) or {}
            for concern in substance.get("unmatched_concerns") or []:
                if not isinstance(concern, str):
                    continue
                key = ("substance", substance_id, concern)
                if key in seen:
                    continue
                seen.add(key)
                warnings.append(
                    {
                        "type": "unmatched_concern",
                        "item": item_id,
                        "product": product_id,
                        "substance": substance_id,
                        "message": concern,
                    }
                )
    return warnings

def build_placement_notes(schedule: dict) -> list[dict]:
    notes: list[dict] = []
    for product_name, explanation in schedule.get("explanations", {}).items():
        why_here = [
            note
            for note in explanation.get("why_here", [])
            if isinstance(note, str) and "tradeoff" in note.lower()
        ]
        if not why_here:
            continue
        notes.append(
            {
                "product": product_name,
                "pillbox": explanation.get("pillbox"),
                "slot": explanation.get("slot"),
                "notes": why_here,
            }
        )
    return sorted(notes, key=lambda entry: str(entry["product"]).casefold())

def build_schedule_summary(schedule: dict) -> dict:
    take: dict[str, list[str]] = {}
    for pillbox_name, pillbox in schedule.get("pillboxes", {}).items():
        lines: list[str] = []
        for slot in pillbox.get("slots", {}).values():
            if not slot.get("products"):
                continue
            lines.append(f"{slot['label']}: {', '.join(slot['products'])}")
        if lines:
            take[pillbox_name] = lines
    return {"take": take}

def collect_dashboard_substance_refs(dashboard_files: list[Path]) -> set[str]:
    refs: set[str] = set()
    for gf in dashboard_files:
        dashboard, err = load_card(gf, "dashboard")
        if err:
            continue
        for member_list_name in ("taking", "candidates", "declined"):
            for member in dashboard.get(member_list_name) or []:
                if not isinstance(member, dict):
                    continue
                substance_id = member.get("substance")
                if isinstance(substance_id, str):
                    refs.add(substance_id)
    return refs

def build_dashboard_review(
    *,
    dashboard_files: list[Path],
    active_substances: set[str],
    inactive_substances: set[str],
    substances: dict[str, dict],
) -> dict[str, list[dict]]:
    benefits: list[dict] = []
    risks: list[dict] = []
    warnings: list[dict] = []
    for dashboard_file in dashboard_files:
        dashboard, err = load_card(dashboard_file, "dashboard")
        if err:
            continue
        benefit = dashboard.get("benefit")
        risk = dashboard.get("risk")
        benefit_text = (
            benefit.get("description")
            if isinstance(benefit, dict)
            and isinstance(benefit.get("description"), str)
            else None
        )
        risk_text = (
            risk.get("description")
            if isinstance(risk, dict)
            and isinstance(risk.get("description"), str)
            else None
        )
        taking_total = 0
        active_count = 0
        covered: list[str] = []
        active_ids: list[str] = []
        inactive: list[str] = []
        missing: list[str] = []

        for member in dashboard.get("taking") or []:
            if not isinstance(member, dict):
                continue
            substance_id = member.get("substance")
            if not isinstance(substance_id, str):
                continue
            taking_total += 1
            if substance_id in active_substances:
                active_count += 1
                active_ids.append(substance_id)
                covered.append(
                    format_substance_name(substances.get(substance_id) or {"id": substance_id})
                )
            elif substance_id in inactive_substances:
                inactive.append(
                    format_substance_name(substances.get(substance_id) or {"id": substance_id})
                )
            else:
                missing.append(
                    format_substance_name(substances.get(substance_id) or {"id": substance_id})
                )

        coverage_ratio = active_count / taking_total if taking_total else 0.0
        if benefit_text:
            benefit_entry: dict = {
                "name": dashboard.get("name"),
                "coverage_percent": round(coverage_ratio * 100),
                "covered": sorted(covered, key=str.casefold),
            }
            if inactive:
                benefit_entry["inactive"] = sorted(inactive, key=str.casefold)
            if missing:
                benefit_entry["missing"] = sorted(missing, key=str.casefold)
            benefits.append(benefit_entry)

        if risk_text:
            risk_entry: dict = {
                "name": dashboard.get("name"),
                "active_count": active_count,
                "tracked_count": taking_total,
                "active": sorted(covered, key=str.casefold),
            }
            if inactive:
                risk_entry["inactive"] = sorted(inactive, key=str.casefold)
            if missing:
                risk_entry["missing"] = sorted(missing, key=str.casefold)
            risks.append(risk_entry)
            threshold = risk.get("warning_threshold") if isinstance(risk, dict) else None
            if isinstance(threshold, int) and active_count >= threshold:
                warnings.append(
                    {
                        "type": "risk_cluster_load",
                        "cluster": str(dashboard.get("name") or dashboard_file.stem),
                        "active": sorted(active_ids, key=lambda sid: format_substance_name(substances.get(sid) or {"id": sid}).casefold()),
                        "message": risk_text,
                        "action": risk.get("action", "") if isinstance(risk, dict) else "",
                    }
                )

    return {"benefits": benefits, "risks": risks, "warnings": warnings}

def check_dashboards(dashboard_files: list[Path], substance_ids: dict[str, Path]) -> list[str]:
    """Validate dashboard cards against schema and dashboard substance refs."""
    errors: list[str] = []
    substance_names: dict[str, str] = {}
    for substance_id, path in substance_ids.items():
        try:
            substance = load_yaml(path)
        except yaml.YAMLError:
            continue
        if isinstance(substance, dict):
            substance_names[substance_id] = format_substance_name(substance)

    def member_label(member: dict) -> str:
        ref = member.get("substance")
        if isinstance(ref, str):
            return substance_names.get(ref, ref)
        name = member.get("name")
        return str(name or "")

    for gf in dashboard_files:
        try:
            dashboard = load_yaml(gf)
        except yaml.YAMLError as e:
            errors.append(f"{gf}: yaml parse error: {e}")
            continue
        if dashboard is None:
            errors.append(f"{gf}: empty file")
            continue
        if not isinstance(dashboard, dict):
            errors.append(f"{gf}: top-level must be a mapping")
            continue

        errors.extend(schema_errors(dashboard, "dashboard", gf))
        for list_name in ("taking", "candidates", "declined"):
            members = dashboard.get(list_name) or []
            if not isinstance(members, list):
                continue
            labels = [member_label(member) for member in members if isinstance(member, dict)]
            if labels != sorted(labels, key=str.casefold):
                errors.append(f"{gf}: {list_name} must be sorted alphabetically")
            for i, member in enumerate(members):
                if not isinstance(member, dict):
                    continue
                ref = member.get("substance")
                if ref is None:
                    continue
                if ref not in substance_ids:
                    errors.append(
                        f"{gf}: {list_name}[{i}].substance '{ref}' has no matching substance card "
                        f"(expected at data/substances/{ref}.yaml)"
                    )
    return errors

def validate_stacks(
    stacks_path: Path,
    product_ids: dict[str, Path],
    trait_ids: set[str],
) -> list[str]:
    if not stacks_path.exists():
        return [f"missing: {stacks_path}"]
    try:
        stacks_data = load_yaml(stacks_path)
    except yaml.YAMLError as e:
        return [f"{stacks_path}: yaml parse error: {e}"]
    if not isinstance(stacks_data, dict):
        return [f"{stacks_path}: top-level must be a mapping"]
    errors = schema_errors(stacks_data, "stacks", stacks_path)
    errors.extend(check_stack_duplicate_items(stacks_data))
    errors.extend(check_stack_alignment(stacks_data, product_ids))
    return errors

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

def grouped_trait_defs(trait_defs: dict) -> dict[str, list[tuple[str, str, dict]]]:
    groups: dict[str, list[tuple[str, str, dict]]] = {}
    for trait_id, trait in sorted(trait_defs.items(), key=lambda item: str(item[0])):
        namespace, _, short_name = str(trait_id).partition(":")
        if not isinstance(trait, dict):
            trait = {}
        groups.setdefault(namespace, []).append(
            (short_name or str(trait_id), str(trait_id), trait)
        )
    return {
        namespace: groups[namespace]
        for namespace in sorted(groups, key=str.casefold)
    }

def format_trait_effect(effect: dict) -> str:
    match = effect.get("match")
    match_text = ""
    if isinstance(match, dict) and match:
        match_text = " when " + ", ".join(
            f"{key}={value}" for key, value in sorted(match.items())
        )
    if effect.get("block") is True:
        return f"blocks slot{match_text}"
    level = effect.get("level")
    if isinstance(level, str):
        return f"{level}{match_text}"
    return ""

def print_trait_details(trait: dict) -> None:
    description = trait.get("description")
    if description:
        print(f"      {description}")
    applies_when = trait.get("applies_when")
    if applies_when:
        print(f"      Applies when: {applies_when}")
    if trait.get("warning") is True:
        print("      Output: schedule warning")
    effects = [
        format_trait_effect(effect)
        for effect in trait.get("effects") or []
        if isinstance(effect, dict)
    ]
    effects = [effect for effect in effects if effect]
    if effects:
        print("      Slot effects: " + "; ".join(effects))

def format_substance_name(substance: dict) -> str:
    name = str(substance.get("name") or substance.get("id") or "unknown")
    form = substance.get("form")
    if isinstance(form, str) and form:
        return f"{name} ({form})"
    return name

def format_product_name(product: dict) -> str:
    name = str(product.get("name") or product.get("id") or "unknown product")
    brand = product.get("brand")
    if isinstance(brand, str) and brand and brand != "unknown":
        return f"{brand} - {name}"
    return name

def format_item_product_name(
    item_id: str,
    item_products: dict[str, str],
    products: dict[str, dict],
) -> str:
    product_id = item_products[item_id]
    return format_product_name(products.get(product_id) or {"id": product_id})

def readable_traits(trait_ids: set[str], traits_data: dict) -> list[str]:
    labels: list[str] = []
    trait_defs = flatten_trait_defs(traits_data) if isinstance(traits_data, dict) else {}
    for trait_id in sorted(trait_ids):
        if trait_id == "risk:manual_review":
            continue
        if trait_id.startswith("class:"):
            continue
        trait = trait_defs.get(trait_id) or {}
        label = trait.get("label") if isinstance(trait, dict) else None
        labels.append(str(label or trait_id))
    return sorted(labels, key=str.casefold)
