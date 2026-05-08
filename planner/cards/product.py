"""Product cards: loading, slugs, search, validation, formatting."""

from __future__ import annotations

import sys
from pathlib import Path

from planner.cards._common import load_card, normalize_filename_part
from planner.cards.search import collect_search_strings, combined_search_score
from planner.io import FIND_MIN_SCORE, PRODUCTS_DIR, schema_errors


def load_product(pf: Path) -> tuple[dict | None, str | None]:
    """Load a product formula card. Returns (data, error_message). Either is None."""
    return load_card(pf, "product")

def product_brand_slug(product: dict) -> str:
    return normalize_filename_part(str(product.get("brand") or "unknown")) or "unknown"

def product_name_slug(product: dict) -> str:
    return normalize_filename_part(str(product.get("name") or "")) or "product"

def canonical_product_filename(product: dict) -> str:
    product_id = str(product.get("id") or "missing_id")
    return f"{product_brand_slug(product)}__{product_name_slug(product)}__{product_id}.yaml"

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

