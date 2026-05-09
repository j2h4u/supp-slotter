"""Product cards: loading, slugs, search, validation, formatting."""

from __future__ import annotations

import dataclasses
import sys
from pathlib import Path

from planner.cards._common import load_card_mapping, normalize_filename_part
from planner.cards.search import collect_search_strings, combined_search_score
from planner.contracts import CardLoadError, Product, ProductComponent
from planner.io import FIND_MIN_SCORE, PRODUCTS_DIR, schema_errors


def load_product(path: Path) -> Product:
    """Load a product card into a Product dataclass.

    Raises CardLoadError on missing file, parse error, schema violation, or
    missing required field.
    """
    data = load_card_mapping(path, "product")
    errors = schema_errors(data, "product", path)
    if errors:
        raise CardLoadError(path, errors[0])
    try:
        components = tuple(
            ProductComponent(
                substance=c["substance"],
                label=c.get("label"),
                amount=c.get("amount"),
                notes=c.get("notes"),
            )
            for c in data.get("components") or ()
            if isinstance(c, dict) and isinstance(c.get("substance"), str)
        )
        return Product(
            id=data["id"],
            name=data["name"],
            components=components,
            brand=data.get("brand"),
            urls=tuple(data.get("urls") or ()),
            notes=data.get("notes"),
            unmatched_concerns=tuple(data.get("unmatched_concerns") or ()),
        )
    except KeyError as e:
        raise CardLoadError(path, f"{path}: missing required field {e}") from e

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
        try:
            product_dc = load_product(path)
        except CardLoadError:
            continue
        product = dataclasses.asdict(product_dc)
        product_id = product_dc.id
        identity_values = [
            product_id,
            product_dc.brand or "",
            product_dc.name,
            path.name,
        ]
        identity_values.extend(product_dc.urls)
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
        try:
            product = load_card_mapping(pf, "product")
        except CardLoadError as e:
            errors.append(e.message)
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
    """Load all product cards into an id-keyed registry of plain dicts.

    Internally builds Product dataclasses (raises on bad data) and converts
    back to dict via asdict so the existing dict-based callers keep working.
    Task 2: change return type to dict[str, Product] and migrate callers.
    """
    products: dict[str, dict] = {}
    for pf in sorted(PRODUCTS_DIR.glob("*.yaml")):
        try:
            product_dc = load_product(pf)
        except CardLoadError as e:
            print(f"plan: skipping product card: {e.message}", file=sys.stderr)
            continue
        products[product_dc.id] = dataclasses.asdict(product_dc)
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
