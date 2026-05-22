from __future__ import annotations

from typing import Any, cast

import yaml

from planner.paths import ROOT


def _effect_registry() -> dict[str, dict[str, Any]]:
    loaded = yaml.safe_load(
        (ROOT / "data/traits/effects.yaml").read_text(encoding="utf-8")
    )
    data = cast(dict[str, Any], loaded)
    assert isinstance(data, dict)
    effects_obj = data["effect"]
    assert isinstance(effects_obj, dict)
    return cast(dict[str, dict[str, Any]], effects_obj)


def test_effects_are_not_placeholder_descriptions() -> None:
    registry = _effect_registry()

    for slug, metadata in registry.items():
        description = metadata["description"]
        applies_when = metadata["applies_when"]
        assert not description.startswith("Reviewer-only effect axis for"), slug
        assert not applies_when.startswith("Use when a substance should be surfaced"), slug
