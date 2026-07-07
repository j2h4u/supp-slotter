from __future__ import annotations

from typing import cast

import pytest
import yaml

_PLACEHOLDER_DESCRIPTION_PREFIX = "Reviewer-only effect axis for"
_PLACEHOLDER_APPLIES_WHEN_PREFIX = "Use when a substance should be surfaced"


def _effect_registry() -> dict[str, dict[str, object]]:
    loaded = cast(
        dict[str, dict[str, dict[str, object]]],
        yaml.safe_load(
            """
            effect:
              fixture_focus_boost:
                label: Fixture focus boost
                description: Improves alertness and focus during work.
                applies_when: Use for cognitive support during long focus blocks.
              fixture_calm:
                label: Fixture calm support
                description: Helps stabilize mood during routine use.
                applies_when: Use when stress and overactivity are present.
            """,
        ),
    )
    assert isinstance(loaded, dict)
    effects_obj = loaded["effect"]
    assert isinstance(effects_obj, dict)
    return cast(dict[str, dict[str, object]], effects_obj)


def _assert_no_placeholders(registry: dict[str, dict[str, object]]) -> None:
    for slug, metadata in registry.items():
        description = cast(str, metadata["description"])
        applies_when = cast(str, metadata["applies_when"])
        assert not description.startswith(_PLACEHOLDER_DESCRIPTION_PREFIX), slug
        assert not applies_when.startswith(_PLACEHOLDER_APPLIES_WHEN_PREFIX), slug


def test_effects_are_not_placeholder_descriptions() -> None:
    registry = _effect_registry()
    _assert_no_placeholders(registry)


def test_effects_reject_placeholder_values() -> None:
    registry = _effect_registry()
    registry["fixture_placeholder"] = {
        "label": "Fixture placeholder",
        "description": f"{_PLACEHOLDER_DESCRIPTION_PREFIX} only.",
        "applies_when": f"{_PLACEHOLDER_APPLIES_WHEN_PREFIX} in edge cases.",
    }

    with pytest.raises(AssertionError):
        _assert_no_placeholders(registry)
