"""SurrealDB session protocol and value helpers."""

from __future__ import annotations

from typing import Protocol

from surrealdb import RecordID


class SurrealSession(Protocol):
    """Structural type for the subset of surrealdb sync session methods we use.

    The surrealdb 2.x SDK exposes `Surreal` as a factory function and uses
    internal value types that don't conform cleanly to a plain Protocol. We cast
    at the single construction point and use this protocol inside query_model.
    Positional-only params decouple from SDK parameter names.
    """

    def use(self, namespace: str, _database: str, /) -> object: ...
    def create(self, _table: str, data: dict[str, object], /) -> object: ...
    def query(
        self,
        sql: str,
        params: dict[str, object] | None = None,
        /,
    ) -> list[dict[str, object]]: ...


def id_str(value: object) -> str:
    """Coerce a SurrealDB id field to its bare string."""
    if isinstance(value, RecordID):
        return str(value.id)
    return str(value)


def string_list(value: object) -> list[str]:
    """Return only string members from a SurrealDB array-like value."""
    return [item for item in value if isinstance(item, str)] if isinstance(value, list) else []
