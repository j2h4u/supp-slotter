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
    """Runtime planner code reads through artifacts.py and never imports the compiler."""
    forbidden_imports: list[str] = []
    for path in sorted(Path("planner").rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                module = node.module or ""
                if module == "planner.ontology.generate" or module.startswith(("linkml", "linkml_runtime", "scripts")):
                    forbidden_imports.append(f"{path}:{module}")
            elif isinstance(node, ast.Import):
                names = [alias.name for alias in node.names]
                forbidden_imports.extend(
                    f"{path}:{name}"
                    for name in names
                    if name == "planner.ontology.generate"
                    or name == "linkml"
                    or name.startswith(("linkml_runtime", "scripts"))
                )
    assert forbidden_imports == []


def test_authoritative_artifact_writer_boundary_is_unique() -> None:
    """Only the generation module may write the ontology generated tree."""
    offenders: list[str] = []
    for path in sorted(Path("planner").rglob("*.py")):
        text = path.read_text(encoding="utf-8")
        if "ontology/generated" in text or "_GENERATED_DIR" in text or "write_artifacts" in text:
            offenders.append(str(path))
    assert offenders == []

    compiler = Path("scripts/ontology_compiler.py")
    assert compiler.is_file()
    compiler_text = compiler.read_text(encoding="utf-8")
    assert "_GENERATED_DIR" in compiler_text
    assert "def write_artifacts" in compiler_text
    writer_defs = [
        str(path)
        for path in sorted([*Path("planner").rglob("*.py"), *Path("scripts").rglob("*.py")])
        if "def write_artifacts" in path.read_text(encoding="utf-8")
    ]
    assert writer_defs == ["scripts/ontology_compiler.py"]


def test_former_planner_compiler_path_is_removed() -> None:
    assert not Path("planner/ontology/generate.py").exists()


def test_runtime_planner_has_no_linkml_compiler_symbols() -> None:
    offenders: list[str] = []
    for path in sorted(Path("planner").rglob("*.py")):
        text = path.read_text(encoding="utf-8")
        if any(token in text for token in ("SchemaView", "JsonSchemaGenerator", "ShaclGenerator", "linkml_runtime")):
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
