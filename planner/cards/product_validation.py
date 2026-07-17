"""Product-card validation for `planner check`."""

from __future__ import annotations

from pathlib import Path
from typing import cast

from planner.cards._common import load_card_mapping
from planner.cards.product import canonical_product_filename
from planner.contracts import CardLoadError, Product
from planner.schema_validation import schema_errors
from planner.ontology.artifacts import OntologyBundle
from planner.yaml_io import YamlValue


def check_product_formulas(
    product_files: list[Path], substance_ids: dict[str, Path], bundle: OntologyBundle
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

        errors.extend(schema_errors(product, "product", pf, bundle))
        _validate_product_identity(pf, product, seen_ids, errors)
        _validate_component_refs(pf, product, substance_ids, errors)

    return errors, info, seen_ids


def _validate_product_identity(
    path: Path,
    product: dict[str, YamlValue],
    seen_ids: dict[str, Path],
    errors: list[str],
) -> None:
    pid_raw = product.get("id")
    if not isinstance(pid_raw, str):
        return

    name_raw = product.get("name")
    brand_raw = product.get("brand")
    expected_filename = canonical_product_filename(
        Product(
            id=pid_raw,
            name=name_raw if isinstance(name_raw, str) else "",
            components=(),
            brand=brand_raw if isinstance(brand_raw, str) else None,
        )
    )
    if path.name != expected_filename:
        errors.append(f"{path}: product filename must be '{expected_filename}'")
    if pid_raw in seen_ids:
        errors.append(f"{path}: duplicate id '{pid_raw}' (also in {seen_ids[pid_raw]})")
    else:
        seen_ids[pid_raw] = path


def _validate_component_refs(
    path: Path,
    product: dict[str, YamlValue],
    substance_ids: dict[str, Path],
    errors: list[str],
) -> None:
    components_raw = product.get("components") or ()
    if not isinstance(components_raw, (list, tuple)):
        return
    for index, component in enumerate(components_raw):
        if not isinstance(component, dict):
            continue
        component_dict = cast(dict[str, object], component)
        ref = component_dict.get("substance")
        if ref is None:
            continue
        if isinstance(ref, str) and ref not in substance_ids:
            errors.append(
                f"{path}: components[{index}].substance '{ref}' references unknown "
                f"substance (expected at data/substances/{ref}.yaml)"
            )
