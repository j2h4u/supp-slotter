"""Raw card mapping adapters for auto-maintenance."""

from __future__ import annotations

from typing import Any

from planner.contracts import Product, Substance


def substance_from_mapping(data: dict[str, Any]) -> Substance:
    name_raw = data.get("name")
    form_raw = data.get("form")
    return Substance(
        id=str(data["id"]),
        name=name_raw if isinstance(name_raw, str) else "",
        form=form_raw if isinstance(form_raw, str) else None,
    )


def product_from_mapping(data: dict[str, Any]) -> Product:
    name_raw = data.get("name")
    brand_raw = data.get("brand")
    return Product(
        id=str(data["id"]),
        name=name_raw if isinstance(name_raw, str) else "",
        components=(),
        brand=brand_raw if isinstance(brand_raw, str) else None,
    )
