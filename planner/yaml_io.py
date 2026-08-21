"""YAML loading helpers with planner-specific error wrapping."""

# PyYAML's runtime constructors are intentionally dynamic and its stubs expose
# mapping/sequence nodes as ``Any``.  Keep that untyped boundary local; all
# callers receive the narrow, validated ``YamlValue`` shape below.
# pyright: reportAny=false, reportUnknownArgumentType=false, reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnannotatedClassAttribute=false, reportArgumentType=false, reportReturnType=false

from __future__ import annotations

import functools
from collections.abc import Iterator
from pathlib import Path
from typing import cast

import yaml
from yaml.constructor import ConstructorError
from yaml.nodes import MappingNode, SequenceNode

from planner.contracts import CardLoadError

type YamlScalar = None | bool | int | float | str
type YamlValue = YamlScalar | list[YamlValue] | dict[str, YamlValue]


class DuplicateYamlKeyError(ConstructorError):
    """Raised when a YAML mapping repeats a key at any nesting level."""

    def __init__(self, *, source: str, key: object, line: int, column: int, mapping_path: tuple[str, ...]) -> None:
        self.source: str = source
        self.key: object = key
        self.line: int = line
        self.column: int = column
        self.mapping_path: tuple[str, ...] = mapping_path
        location = f"{source}:{line}:{column}"
        path = _format_mapping_path(mapping_path)
        super().__init__(
            "while constructing a mapping",
            None,
            f"{location}: duplicate YAML key {key!r} in mapping {path!r}",
            None,
        )


class StrictSafeLoader(yaml.SafeLoader):
    """Safe YAML loader that rejects duplicate mapping keys."""

    def __init__(self, stream: str | bytes) -> None:
        super().__init__(stream)
        self.source_name: str = "<string>"
        self.mapping_path: list[str] = []


def _yaml_key_path(key: object) -> str:
    return key if isinstance(key, str) else repr(key)


def _format_mapping_path(path: tuple[str, ...]) -> str:
    if not path:
        return "<root>"
    result = path[0]
    for part in path[1:]:
        result += part if part.startswith("[") else f".{part}"
    return result


def _strict_construct_mapping(loader: StrictSafeLoader, node: MappingNode, deep: bool = False) -> dict[object, object]:
    loader.flatten_mapping(node)
    mapping: dict[object, object] = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=deep)
        if key in mapping:
            raise DuplicateYamlKeyError(
                source=loader.source_name,
                key=key,
                line=key_node.start_mark.line + 1,
                column=key_node.start_mark.column + 1,
                mapping_path=tuple(loader.mapping_path),
            )
        loader.mapping_path.append(_yaml_key_path(key))
        try:
            mapping[key] = loader.construct_object(value_node, deep=deep)
        finally:
            loader.mapping_path.pop()
    return mapping


def _strict_construct_sequence(
    loader: StrictSafeLoader, node: SequenceNode, deep: bool = False
) -> Iterator[list[object]]:
    result: list[object] = []
    base_path = tuple(loader.mapping_path)
    yield result
    for index, child in enumerate(node.value):
        loader.mapping_path[:] = [*base_path, f"[{index}]"]
        try:
            result.append(loader.construct_object(child, deep=deep))
        finally:
            loader.mapping_path[:] = list(base_path)


StrictSafeLoader.add_constructor(
    yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG,
    _strict_construct_mapping,
)
StrictSafeLoader.add_constructor(
    yaml.resolver.BaseResolver.DEFAULT_SEQUENCE_TAG,
    _strict_construct_sequence,
)


def safe_load_yaml(source: str | bytes, *, path: Path | str = "<string>") -> object:
    """Parse one YAML document with safe tags and duplicate-key rejection."""
    loader = StrictSafeLoader(source)
    loader.source_name = str(path)
    try:
        return loader.get_single_data()
    finally:
        loader.dispose()


@functools.lru_cache(maxsize=512)
def _parse_yaml_cached(path: Path, _fingerprint: tuple[int, int, int]) -> YamlValue:
    try:
        return cast(YamlValue, safe_load_yaml(path.read_text(encoding="utf-8"), path=path))
    except OSError as e:
        raise CardLoadError(path, f"{path}: {e}") from e
    except yaml.YAMLError as e:
        raise CardLoadError(path, f"{path}: invalid YAML: {e}") from e


def load_yaml(path: Path) -> YamlValue:
    """Read and parse YAML; callers must validate the returned top-level type."""
    try:
        stat = path.stat()
    except OSError as e:
        raise CardLoadError(path, f"{path}: {e}") from e
    return _parse_yaml_cached(path, (stat.st_mtime_ns, stat.st_ctime_ns, stat.st_size))


def load_yaml_mapping(path: Path) -> dict[str, YamlValue]:
    data = load_yaml(path)
    if not isinstance(data, dict):
        raise CardLoadError(path, f"{path}: expected mapping, got {type(data).__name__}")
    return cast(dict[str, YamlValue], data)
