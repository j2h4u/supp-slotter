"""Card ID predicates shared by maintenance and validation code."""

from __future__ import annotations

import re

SUBSTANCE_ID_PATTERN = re.compile(r"^sub_[a-z0-9]{10}$")


def is_substance_id(value: str) -> bool:
    return SUBSTANCE_ID_PATTERN.fullmatch(value) is not None


def composition_role_id(product_id: str, substance_id: str) -> str:
    """Return the portable authored identity for one product/substance role."""
    return f"cmp_{product_id}__{substance_id}"
