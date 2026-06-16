from __future__ import annotations

from typing import cast

import yaml

from planner.paths import ROOT


def _effect_registry() -> dict[str, dict[str, object]]:
    loaded = cast(object, yaml.safe_load((ROOT / "data/traits/effects.yaml").read_text(encoding="utf-8")))
    assert isinstance(loaded, dict)
    data = cast(dict[str, object], loaded)
    assert isinstance(data, dict)
    effects_obj = data["effect"]
    assert isinstance(effects_obj, dict)
    return cast(dict[str, dict[str, object]], effects_obj)


def test_effects_are_not_placeholder_descriptions() -> None:
    registry = _effect_registry()

    for slug, metadata in registry.items():
        description = cast(str, metadata["description"])
        applies_when = cast(str, metadata["applies_when"])
        assert not description.startswith("Reviewer-only effect axis for"), slug
        assert not applies_when.startswith("Use when a substance should be surfaced"), slug
