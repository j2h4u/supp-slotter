"""Product cards: loading, slugs, search, validation, formatting."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, cast

from planner.cards._common import load_card_mapping, normalize_filename_part
from planner.cards.search import collect_search_strings, combined_search_score
from planner.contracts import CardLoadError, Concern, Product, ProductComponent
from planner.io import FIND_MIN_SCORE, Paths, schema_errors


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
        components_raw: Any = data.get("components") or ()
        components_list = cast(tuple[Any, ...] | list[Any], components_raw)
        components = tuple(
            ProductComponent(
                substance=cast(dict[str, Any], c)["substance"],
                label=cast(dict[str, Any], c).get("label"),
                amount=cast(dict[str, Any], c).get("amount"),
                notes=cast(dict[str, Any], c).get("notes"),
                primary=cast(dict[str, Any], c).get("primary"),
            )
            for c in components_list
            if isinstance(c, dict) and isinstance(cast(dict[str, Any], c).get("substance"), str)
        )
        return Product(
            id=data["id"],
            name=data["name"],
            components=components,
            brand=data.get("brand"),
            urls=tuple(data.get("urls") or ()),
            notes=data.get("notes"),
            concerns=tuple(
                Concern(kind=cast(dict[str, Any], c)["kind"], text=cast(dict[str, Any], c)["text"])
                for c in cast(list[Any], data.get("concerns") or [])
                if isinstance(c, dict)
            ),
        )
    except KeyError as e:
        raise CardLoadError(path, f"{path}: missing required field {e}") from e


def product_brand_slug(product: Product) -> str:
    return normalize_filename_part(product.brand or "unknown") or "unknown"


def product_name_slug(product: Product) -> str:
    return normalize_filename_part(product.name) or "product"


def canonical_product_filename(product: Product) -> str:
    return f"{product_brand_slug(product)}__{product_name_slug(product)}__{product.id}.yaml"


def find_product_results(query: str, paths: Paths) -> list[tuple[float, str, str, Path]]:
    results: list[tuple[float, str, str, Path]] = []
    for path in sorted(paths.products.glob("*.yaml")):
        try:
            product = load_product(path)
        except CardLoadError as e:
            print(f"warning: skipping product card: {e.message}", file=sys.stderr)
            continue
        identity_values = [
            product.id,
            product.brand or "",
            product.name,
            path.name,
        ]
        identity_values.extend(product.urls)
        full_values = collect_search_strings(product)
        full_values.append(path.name)
        score = combined_search_score(query, identity_values, full_values)
        if score >= FIND_MIN_SCORE:
            results.append((score, product.id, format_product_name(product), path))
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

        pid_raw = product.get("id")
        if isinstance(pid_raw, str):
            pid: str = pid_raw
            name_raw = product.get("name")
            brand_raw = product.get("brand")
            expected_filename = canonical_product_filename(
                Product(
                    id=pid,
                    name=name_raw if isinstance(name_raw, str) else "",
                    components=(),
                    brand=brand_raw if isinstance(brand_raw, str) else None,
                )
            )
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
            component = cast(dict[str, Any], component)
            ref = component.get("substance")
            if ref is None:
                continue
            if ref not in substance_ids:
                errors.append(
                    f"{pf}: components[{i}].substance '{ref}' references unknown "
                    f"substance (expected at data/substances/{ref}.yaml)"
                )

    return errors, info, seen_ids


def collect_product_substance_refs(
    products: dict[str, Product], product_ids: set[str]
) -> set[str]:
    refs: set[str] = set()
    for product_id in product_ids:
        product = products.get(product_id)
        if product is None:
            continue
        refs.update(product_component_substances(product))
    return refs


def load_product_registry(paths: Paths) -> dict[str, Product]:
    products: dict[str, Product] = {}
    product_files = sorted(paths.products.glob("*.yaml"))
    skipped = 0
    for pf in product_files:
        try:
            product = load_product(pf)
        except CardLoadError as e:
            print(f"warning: skipping product card: {e.message}", file=sys.stderr)
            skipped += 1
            continue
        products[product.id] = product
    if skipped:
        print(
            f"warning: loaded {len(products)}/{len(product_files)} product cards; {skipped} skipped",
            file=sys.stderr,
        )
    return products


def product_component_substances(product: Product) -> list[str]:
    return [c.substance for c in product.components]


def format_product_name(product: Product) -> str:
    name = product.name or product.id or "unknown product"
    if product.brand and product.brand != "unknown":
        return f"{product.brand} - {name}"
    return name


def format_item_product_name(
    item_id: str,
    item_products: dict[str, str],
    products: dict[str, Product],
) -> str:
    product_id = item_products[item_id]
    product = products.get(product_id)
    if product is None:
        return product_id
    return format_product_name(product)
