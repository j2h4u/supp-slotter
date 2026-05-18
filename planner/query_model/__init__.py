"""Read-model boundary for graph-style planner queries.

YAML cards remain the source of truth. The query model is rebuilt in memory for
each command and owns SurrealDB/SurrealQL details.
"""

from __future__ import annotations

from planner.query_model.loaders import (
    dashboards_for_read_model,
    pillbox_stack_names,
    stacks_for_read_model,
)
from planner.query_model.read_model import (
    StackReadModel,
    build_stack_read_model,
)

__all__ = [
    "StackReadModel",
    "build_stack_read_model",
    "dashboards_for_read_model",
    "pillbox_stack_names",
    "stacks_for_read_model",
]
