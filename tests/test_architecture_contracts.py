from __future__ import annotations

import ast
from pathlib import Path

COMMANDS_REQUIRING_SYNTHETIC_ROOT = frozenset({
    "cmd_audit",
    "cmd_check",
    "cmd_find",
    "cmd_plan",
    "cmd_review",
    "cmd_review_substance",
})


def _test_files() -> list[Path]:
    return sorted(path for path in Path("tests").glob("test_*.py") if path.name != "test_architecture_contracts.py")


def _call_name(node: ast.Call) -> str | None:
    if isinstance(node.func, ast.Name):
        return node.func.id
    if isinstance(node.func, ast.Attribute):
        return node.func.attr
    return None


def _has_keyword(node: ast.Call, keyword: str) -> bool:
    return any(item.arg == keyword for item in node.keywords)


def test_behavior_tests_do_not_use_live_default_data_root() -> None:
    offenders: list[str] = []
    for path in _test_files():
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            call_name = _call_name(node)
            if call_name in COMMANDS_REQUIRING_SYNTHETIC_ROOT and not _has_keyword(node, "data_root"):
                offenders.append(f"{path}:{node.lineno} calls {call_name} without data_root")
            if call_name == "default" and isinstance(node.func, ast.Attribute) and _call_name_owner(node) == "Paths":
                offenders.append(f"{path}:{node.lineno} calls Paths.default()")

    assert offenders == []


def _call_name_owner(node: ast.Call) -> str | None:
    if isinstance(node.func, ast.Attribute) and isinstance(node.func.value, ast.Name):
        return node.func.value.id
    return None
