"""Product cards: loading, slugs, search, validation, formatting."""

from __future__ import annotations

from pathlib import Path
from typing import cast

from planner.cards._common import load_card_mapping, normalize_filename_part
from planner.cards.search import collect_search_strings, combined_search_score
from planner.contracts import (
    CardLoadError,
    Concern,
    ConcernKind,
    Product,
    ProductComponent,
)
from planner.domain_constants import FIND_MIN_SCORE
from planner.ontology.artifacts import OntologyBundle
from planner.ontology.schema_enums import schema_enum_values
from planner.paths import Paths
from planner.schema_validation import schema_errors


def load_product(path: Path, bundle: OntologyBundle) -> Product:
    """Load a product card into a Product dataclass.

    Raises CardLoadError on missing file, parse error, schema violation, or
    missing required field.
    """
    data = load_card_mapping(path, "product")
    errors = schema_errors(data, "product", path, bundle)
    if errors:
        raise CardLoadError(path, errors[0])
    try:
        return Product(
            id=cast(str, data["id"]),
            name=cast(str, data["name"]),
            components=tuple(_product_components(data.get("components"))),
            brand=cast(str | None, data.get("brand")),
            urls=tuple(_string_list(data.get("urls"))),
            notes=cast(str | None, data.get("notes")),
            concerns=_concerns(data.get("concerns"), path, bundle),
        )
    except KeyError as e:
        raise CardLoadError(path, f"{path}: missing required field {e}") from e


def _product_components(value: object) -> list[ProductComponent]:
    components: list[ProductComponent] = []
    if not isinstance(value, (list, tuple)):
        return components
    for component in value:
        if not isinstance(component, dict):
            continue
        component_dict = cast(dict[str, object], component)
        substance = component_dict.get("substance")
        if not isinstance(substance, str):
            continue
        components.append(
            ProductComponent(
                substance=substance,
                label=cast(str | None, component_dict.get("label")),
                amount=cast(str | None, component_dict.get("amount")),
                notes=cast(str | None, component_dict.get("notes")),
            )
        )
    return components


def _string_list(value: object) -> list[str]:
    return [item for item in value if isinstance(item, str)] if isinstance(value, (list, tuple)) else []


def _concerns(value: object, path: Path, bundle: OntologyBundle) -> tuple[Concern, ...]:
    if value is None:
        return ()
    if not isinstance(value, (list, tuple)):
        raise CardLoadError(path, f"{path}: concerns must be a list")
    concern_kinds = frozenset(schema_enum_values(bundle, "ConcernKind"))
    concerns: list[Concern] = []
    for index, concern in enumerate(cast(list[object] | tuple[object, ...], value)):
        if not isinstance(concern, dict):
            raise CardLoadError(path, f"{path}: concerns[{index}] must be a mapping")
        concern_dict = cast(dict[str, object], concern)
        kind = concern_dict.get("kind")
        text = concern_dict.get("text")
        if not isinstance(kind, str) or kind not in concern_kinds:
            raise CardLoadError(path, f"{path}: concerns[{index}].kind is not in ontology ConcernKind")
        if not isinstance(text, str) or not text:
            raise CardLoadError(path, f"{path}: concerns[{index}].text must be non-empty")
        concerns.append(Concern(kind=cast(ConcernKind, kind), text=text))
    return tuple(concerns)


def product_brand_slug(product: Product) -> str:
    return normalize_filename_part(product.brand or "unknown") or "unknown"


def product_name_slug(product: Product) -> str:
    return normalize_filename_part(product.name) or "product"


def canonical_product_filename(product: Product) -> str:
    return f"{product_brand_slug(product)}__{product_name_slug(product)}__{product.id}.yaml"


def find_product_results(query: str, paths: Paths, bundle: OntologyBundle) -> list[tuple[float, str, str, Path]]:
    results: list[tuple[float, str, str, Path]] = []
    errors: list[CardLoadError] = []
    for path in sorted(paths.products.glob("*.yaml")):
        try:
            product = load_product(path, bundle)
        except CardLoadError as e:
            errors.append(e)
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
    if errors:
        _raise_product_registry_errors(paths.products, errors)
    return sorted(results, key=lambda item: (-item[0], item[2].casefold(), item[1]))


def collect_product_substance_refs(products: dict[str, Product], product_ids: set[str]) -> set[str]:
    refs: set[str] = set()
    for product_id in product_ids:
        product = products.get(product_id)
        if product is None:
            continue
        refs.update(product_component_substances(product))
    return refs


def load_product_registry(paths: Paths, bundle: OntologyBundle) -> dict[str, Product]:
    products: dict[str, Product] = {}
    product_files = sorted(paths.products.glob("*.yaml"))
    errors: list[CardLoadError] = []
    for pf in product_files:
        try:
            product = load_product(pf, bundle)
        except CardLoadError as e:
            errors.append(e)
            continue
        previous = products.get(product.id)
        if previous is not None:
            errors.append(CardLoadError(pf, f"{pf}: duplicate product id {product.id!r}"))
            continue
        products[product.id] = product
    if errors:
        _raise_product_registry_errors(paths.products, errors)
    return products


def _raise_product_registry_errors(directory: Path, errors: list[CardLoadError]) -> None:
    details = "\n".join(f"- {error.message}" for error in errors)
    raise CardLoadError(directory, f"{directory}: failed to load {len(errors)} product card(s):\n{details}")


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
