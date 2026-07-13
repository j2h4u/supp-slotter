"""Deterministic, typed normalization for migration evidence.

The migration baseline must distinguish YAML values that look alike after a
lossy conversion (for example ``"1"`` and ``1``).  This module deliberately
returns JSON-only structures so the resulting fixture is stable and safe to
compare in CI.
"""

from __future__ import annotations

import unicodedata
from collections.abc import Mapping, Sequence
from decimal import Decimal
from typing import cast

type NormalizedValue = dict[str, object]

NORMALIZER_VERSION = "1"


def normalize(value: object) -> NormalizedValue:
    """Return a recursively typed, deterministic representation of *value*."""
    if value is None:
        normalized: NormalizedValue = {"type": "null"}
    elif isinstance(value, bool):
        normalized = {"type": "boolean", "value": value}
    elif isinstance(value, int):
        normalized = {"type": "integer", "value": str(value)}
    elif isinstance(value, float):
        normalized = {"type": "float", "value": repr(value)}
    elif isinstance(value, Decimal):
        normalized = {"type": "decimal", "value": str(value)}
    elif isinstance(value, str):
        normalized = {"type": "string", "value": _normalise_string(value)}
    elif isinstance(value, Mapping):
        mapping = cast(Mapping[object, object], value)
        pairs = [
            [_normalise_string(str(key)), normalize(item)]
            for key, item in sorted(mapping.items(), key=lambda pair: str(pair[0]))
        ]
        normalized = {"type": "mapping", "value": pairs}
    elif isinstance(value, Sequence) and not isinstance(value, (bytes, bytearray, str)):
        sequence = cast(Sequence[object], value)
        normalized = {"type": "sequence", "value": [normalize(item) for item in sequence]}
    else:
        raise TypeError(f"Unsupported YAML value for migration normalization: {type(value).__name__}")
    return normalized


def flatten_facts(value: NormalizedValue, *, entity_id: str | None, path: str = "$") -> list[dict[str, object]]:
    """Emit leaf facts with the full source path and typed normalized value."""
    value_type = value["type"]
    if value_type == "mapping":
        facts: list[dict[str, object]] = []
        pairs = cast(list[list[object]], value["value"])
        for key, child in pairs:
            facts.extend(flatten_facts(cast(NormalizedValue, child), entity_id=entity_id, path=f"{path}.{key}"))
        return facts
    if value_type == "sequence":
        facts = []
        items = cast(list[object], value["value"])
        for index, child in enumerate(items):
            facts.extend(flatten_facts(cast(NormalizedValue, child), entity_id=entity_id, path=f"{path}[{index}]"))
        return facts
    return [{"entity_id": entity_id, "path": path, "value": value}]


def _normalise_string(value: str) -> str:
    return unicodedata.normalize("NFC", value.replace("\r\n", "\n").replace("\r", "\n"))
