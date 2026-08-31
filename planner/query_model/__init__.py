"""Read-model boundary for graph-style planner queries.

YAML cards remain the source of truth. The query model is rebuilt from plain
domain data for each command.
"""

from __future__ import annotations

from planner.query_model.loaders import stacks_for_read_model
from planner.query_model.read_model import (
    StackReadModel,
    build_stack_read_model,
)

__all__ = [
    "StackReadModel",
    "build_stack_read_model",
    "stacks_for_read_model",
]
