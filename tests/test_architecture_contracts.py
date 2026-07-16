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


def test_ontology_compiler_has_one_runtime_importer() -> None:
    """Runtime planner code reads through artifacts.py, never imports the compiler directly."""
    importers: list[str] = []
    for path in sorted(Path("planner").rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if (
                (isinstance(node, ast.ImportFrom) and node.module == "planner.ontology.generate")
                or (isinstance(node, ast.Import) and any(alias.name == "planner.ontology.generate" for alias in node.names))
            ):
                importers.append(str(path))
    assert importers == ["planner/ontology/artifacts.py"]


def test_authoritative_artifact_writer_boundary_is_unique() -> None:
    """Only the generation module may write the ontology generated tree."""
    offenders: list[str] = []
    for path in sorted(Path("planner").rglob("*.py")):
        if path.name == "generate.py" or path.name == "__init__.py":
            continue
        text = path.read_text(encoding="utf-8")
        if "ontology/generated" in text or "_GENERATED_DIR" in text:
            offenders.append(str(path))
    assert offenders == []


def test_linkml_spike_cannot_bypass_authoritative_compiler() -> None:
    source = Path("scripts/ontology_stack_spike.py").read_text(encoding="utf-8")
    assert "ontology/generated" not in source
    assert "JsonSchemaGenerator" not in source
    assert "OwlSchemaGenerator" not in source
    assert "ShaclGenerator" not in source
    assert "write_artifacts" not in source


def test_generator_cli_compiles_once_then_dispatches_exactly_one_mode() -> None:
    tree = ast.parse(Path("scripts/generate_ontology.py").read_text(encoding="utf-8"))
    calls = [node for node in ast.walk(tree) if isinstance(node, ast.Call)]
    assert sum(_call_name(node) == "compile_ontology" for node in calls) == 1
    assert sum(_call_name(node) == "check_artifacts" for node in calls) == 1
    assert sum(_call_name(node) == "write_artifacts" for node in calls) == 1
