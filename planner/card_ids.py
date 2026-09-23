"""Card ID predicates shared by maintenance and validation code."""

from __future__ import annotations


def composition_role_id(product_id: str, substance_id: str) -> str:
    """Return the portable authored identity for one product/substance role."""
    return f"cmp_{product_id}__{substance_id}"
