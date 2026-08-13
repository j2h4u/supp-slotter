"""Raw card mapping adapters for auto-maintenance."""

from __future__ import annotations

from planner.contracts import Product, Substance


def substance_from_mapping(data: dict[str, object]) -> Substance:
    name_raw = data.get("name")
    form_raw = data.get("form")
    return Substance(
        id=str(data["id"]),
        name=name_raw if isinstance(name_raw, str) else "",
        form=form_raw if isinstance(form_raw, str) else None,
    )


def product_from_mapping(data: dict[str, object]) -> Product:
    name_raw = data.get("name")
    brand_raw = data.get("brand")
    use_pattern_raw = data.get("use_pattern")
    return Product(
        id=str(data["id"]),
        name=name_raw if isinstance(name_raw, str) else "",
        components=(),
        brand=brand_raw if isinstance(brand_raw, str) else None,
        use_pattern=use_pattern_raw if isinstance(use_pattern_raw, str) else None,
    )
