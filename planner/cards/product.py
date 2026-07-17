"""Product cards: loading, slugs, search, validation, formatting."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import cast

from planner.cards._common import load_card_mapping, normalize_filename_part
from planner.cards.search import collect_search_strings, combined_search_score
from planner.contracts import (
    CardLoadError,
    Concern,
    ConcernKind,
    EnforcementCap,
    GovernanceStatus,
    Product,
    ProductComponent,
    ScheduleGovernance,
    SlotPolicyEvidence,
)
from planner.domain_constants import FIND_MIN_SCORE
from planner.paths import Paths
from planner.ontology.artifacts import OntologyBundle
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
            concerns=tuple(_concerns(data.get("concerns"))),
            intake=_string_tuple(cast(dict[str, object], data.get("schedule") or {}).get("intake")),
            timing=_string_tuple(cast(dict[str, object], data.get("schedule") or {}).get("timing")),
            activity=_string_tuple(cast(dict[str, object], data.get("schedule") or {}).get("activity")),
            schedule_governance=_governance(data.get("schedule_governance"), path),
        )
    except KeyError as e:
        raise CardLoadError(path, f"{path}: missing required field {e}") from e


def _governance(value: object, path: Path) -> dict[str, ScheduleGovernance]:
    if not isinstance(value, dict):
        return {}
    records = cast(dict[str, object], value)
    out: dict[str, ScheduleGovernance] = {}
    for key in sorted(records):
        raw_value = records[key]
        if not isinstance(raw_value, dict):
            raise CardLoadError(path, f"{path}: invalid schedule_governance[{key}]")
        raw = cast(dict[str, object], raw_value)
        raw_scope = raw.get("scope")
        scope = (
            tuple(sorted((str(k), str(v)) for k, v in cast(dict[str, object], raw_scope).items()))
            if isinstance(raw_scope, dict)
            else ()
        )
        evidence: list[SlotPolicyEvidence] = []
        raw_evidence = raw.get("evidence")
        if isinstance(raw_evidence, list):
            for item_value in cast(list[object], raw_evidence):
                if isinstance(item_value, dict):
                    item = cast(dict[str, object], item_value)
                    evidence.append(
                        SlotPolicyEvidence(
                            str(item.get("source", "")), str(item.get("supports", "")), str(item.get("limitations", ""))
                        )
                    )
        out[key] = ScheduleGovernance(
            status=cast(GovernanceStatus, raw.get("status", "approved")),
            enforcement_cap=cast(EnforcementCap, raw.get("enforcement_cap", "none")),
            scope=scope,
            evidence=tuple(evidence),
            owner=str(raw.get("owner", "")),
            review_by=str(raw.get("review_by", "")),
            evidence_gap=cast(str | None, raw.get("evidence_gap")),
            retirement_reason=cast(str | None, raw.get("retirement_reason")),
        )
    return out


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
                primary=cast(bool | None, component_dict.get("primary")),
            )
        )
    return components


def _string_list(value: object) -> list[str]:
    return [item for item in value if isinstance(item, str)] if isinstance(value, (list, tuple)) else []


def _string_tuple(value: object) -> tuple[str, ...]:
    return tuple(item for item in value if isinstance(item, str)) if isinstance(value, (list, tuple)) else ()


def _concerns(value: object) -> list[Concern]:
    concerns: list[Concern] = []
    if not isinstance(value, (list, tuple)):
        return concerns
    for concern in value:
        if not isinstance(concern, dict):
            continue
        concern_dict = cast(dict[str, object], concern)
        kind = concern_dict.get("kind")
        text = concern_dict.get("text")
        if isinstance(kind, str) and isinstance(text, str) and kind in {"safety", "model_gap", "data_quality"}:
            concerns.append(Concern(kind=cast(ConcernKind, kind), text=text))
    return concerns


def product_brand_slug(product: Product) -> str:
    return normalize_filename_part(product.brand or "unknown") or "unknown"


def product_name_slug(product: Product) -> str:
    return normalize_filename_part(product.name) or "product"


def canonical_product_filename(product: Product) -> str:
    return f"{product_brand_slug(product)}__{product_name_slug(product)}__{product.id}.yaml"


def find_product_results(query: str, paths: Paths, bundle: OntologyBundle) -> list[tuple[float, str, str, Path]]:
    results: list[tuple[float, str, str, Path]] = []
    for path in sorted(paths.products.glob("*.yaml")):
        try:
            product = load_product(path, bundle)
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
    skipped = 0
    for pf in product_files:
        try:
            product = load_product(pf, bundle)
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
