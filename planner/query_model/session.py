"""SurrealDB session protocol and value helpers."""

from __future__ import annotations

from typing import Any, Protocol, cast

from surrealdb import RecordID


class SurrealSession(Protocol):
    """Structural type for the subset of surrealdb sync session methods we use.

    The surrealdb 2.x SDK exposes `Surreal` as a factory function and uses
    internal value types that don't conform cleanly to a plain Protocol. We cast
    at the single construction point and use this protocol inside query_model.
    Positional-only params decouple from SDK parameter names.
    """

    def use(self, namespace: str, _database: str, /) -> Any: ...
    def create(self, _table: str, data: dict[str, Any], /) -> Any: ...
    def query(
        self,
        sql: str,
        params: dict[str, Any] | None = None,
        /,
    ) -> list[dict[str, Any]]: ...


def id_str(value: Any) -> str:
    """Coerce a SurrealDB id field to its bare string."""
    if isinstance(value, RecordID):
        return cast(str, value.id)
    return cast(str, value)
