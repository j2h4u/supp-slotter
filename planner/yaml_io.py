"""YAML loading helpers with planner-specific error wrapping."""

from __future__ import annotations

import functools
from pathlib import Path
from typing import cast

import yaml

from planner.contracts import CardLoadError

type YamlScalar = None | bool | int | float | str
type YamlValue = YamlScalar | list[YamlValue] | dict[str, YamlValue]


@functools.lru_cache(maxsize=512)
def _parse_yaml_cached(path: Path, mtime_ns: int) -> YamlValue:
    try:
        return cast(YamlValue, yaml.safe_load(path.read_text(encoding="utf-8")))
    except OSError as e:
        raise CardLoadError(path, f"{path}: {e}") from e
    except yaml.YAMLError as e:
        raise CardLoadError(path, f"{path}: invalid YAML: {e}") from e


def load_yaml(path: Path) -> YamlValue:
    """Read and parse YAML; callers must validate the returned top-level type."""
    try:
        mtime_ns = path.stat().st_mtime_ns
    except OSError as e:
        raise CardLoadError(path, f"{path}: {e}") from e
    return _parse_yaml_cached(path, mtime_ns)


def load_yaml_mapping(path: Path) -> dict[str, YamlValue]:
    data = load_yaml(path)
    if not isinstance(data, dict):
        raise CardLoadError(path, f"{path}: expected mapping, got {type(data).__name__}")
    return cast(dict[str, YamlValue], data)
