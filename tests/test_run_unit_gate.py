from __future__ import annotations

import builtins
import subprocess
from pathlib import Path

import pytest
from scripts import run_unit_gate


def _make_modules(tmp_path: Path, names: list[str]) -> Path:
    tests_root = tmp_path / "tests"
    for name in names:
        path = tests_root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("# fixture\n")
    return tests_root


def _collected(*, returncode: int = 0, stdout: str = "", stderr: str = "") -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(args=[], returncode=returncode, stdout=stdout, stderr=stderr)


def test_discovery_matches_both_patterns_recursively_and_sorts(tmp_path: Path) -> None:
    tests_root = _make_modules(
        tmp_path,
        [
            "z_test.py",
            "test_z.py",
            "nested/test_a.py",
            "nested/a_test.py",
            "nested/not_a_test.txt",
            "nested/test_no.pyc",
            "test_z.py",
        ],
    )

    assert run_unit_gate.discover_test_modules(tests_root) == [
        tests_root / "nested/a_test.py",
        tests_root / "nested/test_a.py",
        tests_root / "test_z.py",
        tests_root / "z_test.py",
    ]


def test_planner_failure_is_fail_fast(tmp_path: Path) -> None:
    tests_root = _make_modules(tmp_path, ["test_one.py"])
    calls: list[list[str]] = []

    def runner(command: run_unit_gate.Command) -> int:
        calls.append(list(command))
        return 3

    assert run_unit_gate.run_unit_gate(tests_root, command_runner=runner) == 3
    assert len(calls) == 1
    assert calls[0][1:] == ["-m", "planner", "check"]


@pytest.mark.parametrize("test_root_exists", [False, True])
def test_missing_or_empty_discovery_fails_closed_without_pytest(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    *,
    test_root_exists: bool,
) -> None:
    tests_root = tmp_path / "tests"
    if test_root_exists:
        tests_root.mkdir()
    calls: list[list[str]] = []

    def runner(command: run_unit_gate.Command) -> int:
        calls.append(list(command))
        return 0

    assert run_unit_gate.run_unit_gate(tests_root, command_runner=runner) == 5
    assert calls == [[run_unit_gate.sys.executable, "-m", "planner", "check"]]
    assert capsys.readouterr().err == f"No unit test modules discovered under {tests_root}.\n"


def test_each_module_uses_exact_fresh_process_invocation_without_xdist(tmp_path: Path) -> None:
    tests_root = _make_modules(tmp_path, ["test_two.py", "test_one.py"])
    calls: list[list[str]] = []

    def runner(command: run_unit_gate.Command) -> int:
        calls.append(list(command))
        return 0

    assert run_unit_gate.run_unit_gate(tests_root, command_runner=runner, split_modules=frozenset()) == 0
    assert len(calls) == 3
    assert calls[0][1:] == ["-m", "planner", "check"]
    assert calls[1:] == [
        [
            run_unit_gate.sys.executable,
            "-m",
            "pytest",
            "-q",
            "-m",
            run_unit_gate.PYTEST_MARKERS,
            str(tests_root / "test_one.py"),
        ],
        [
            run_unit_gate.sys.executable,
            "-m",
            "pytest",
            "-q",
            "-m",
            run_unit_gate.PYTEST_MARKERS,
            str(tests_root / "test_two.py"),
        ],
    ]
    assert all("-n" not in command for command in calls)


def test_pytest_exit_one_continues_and_reports_failures(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    tests_root = _make_modules(tmp_path, ["test_two.py", "test_one.py", "test_three.py"])
    calls: list[list[str]] = []

    def runner(command: run_unit_gate.Command) -> int:
        calls.append(list(command))
        return 1 if len(calls) == 2 else 0

    assert run_unit_gate.run_unit_gate(tests_root, command_runner=runner, split_modules=frozenset()) == 1
    assert len(calls) == 4
    output = capsys.readouterr().out
    assert output.index("[1/3]") < output.index("[2/3]") < output.index("[3/3]")
    assert output.endswith(f"- {tests_root / 'test_one.py'}\n")


def test_abnormal_pytest_status_aborts_immediately_and_is_normalized(tmp_path: Path) -> None:
    tests_root = _make_modules(tmp_path, ["test_one.py", "test_two.py"])
    calls: list[list[str]] = []

    def runner(command: run_unit_gate.Command) -> int:
        calls.append(list(command))
        return -9 if len(calls) == 2 else 0

    assert run_unit_gate.run_unit_gate(tests_root, command_runner=runner, split_modules=frozenset()) == 137
    assert len(calls) == 2


def test_ordinary_module_path_and_output_are_unchanged(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    tests_root = _make_modules(tmp_path, ["test_one.py"])
    calls: list[list[str]] = []

    def runner(command: run_unit_gate.Command) -> int:
        calls.append(list(command))
        return 0

    def collector(command: run_unit_gate.Command) -> subprocess.CompletedProcess[str]:
        pytest.fail(f"ordinary module unexpectedly collected: {command}")

    assert (
        run_unit_gate.run_unit_gate(
            tests_root,
            command_runner=runner,
            collection_runner=collector,
            split_modules=frozenset(),
        )
        == 0
    )
    module = tests_root / "test_one.py"
    assert calls == [
        [run_unit_gate.sys.executable, "-m", "planner", "check"],
        [
            run_unit_gate.sys.executable,
            "-m",
            "pytest",
            "-q",
            "-m",
            run_unit_gate.PYTEST_MARKERS,
            str(module),
        ],
    ]
    assert capsys.readouterr().out == f"[1/1] {module.as_posix()}\n"


def test_missing_configured_split_module_fails_before_test_execution(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    tests_root = _make_modules(tmp_path, ["test_one.py"])
    configured = tests_root / "test_missing.py"
    calls: list[list[str]] = []

    def runner(command: run_unit_gate.Command) -> int:
        calls.append(list(command))
        return 0

    assert (
        run_unit_gate.run_unit_gate(
            tests_root,
            command_runner=runner,
            split_modules=frozenset({configured}),
        )
        == 5
    )
    assert calls == [[run_unit_gate.sys.executable, "-m", "planner", "check"]]
    assert capsys.readouterr().err == (
        f"Configured split unit test modules were not discovered:\n- {configured.as_posix()}\n"
    )


def test_split_modules_are_the_exact_controlled_measurement_set() -> None:
    assert (
        frozenset({
            Path("tests/test_enzyme_governance_acceptance.py"),
            Path("tests/test_ontology_artifacts.py"),
            Path("tests/test_ontology_compiler_outputs.py"),
            Path("tests/test_ontology_formal_runtime_assertions.py"),
            Path("tests/test_ontology_repository_contract.py"),
        })
        == run_unit_gate.SPLIT_MODULES
    )


@pytest.mark.parametrize(
    "module_name",
    [
        "test_enzyme_governance_acceptance.py",
        "test_ontology_artifacts.py",
        "test_ontology_compiler_outputs.py",
        "test_ontology_formal_runtime_assertions.py",
        "test_ontology_repository_contract.py",
    ],
)
def test_split_collection_uses_exact_argv_and_preserves_emitted_order(
    tmp_path: Path,
    module_name: str,
) -> None:
    tests_root = _make_modules(tmp_path, [module_name])
    module = tests_root / module_name
    node_ids = [f"{module}::test_second[param]", f"{module}::test_first"]
    collection_calls: list[list[str]] = []
    test_calls: list[list[str]] = []

    def runner(command: run_unit_gate.Command) -> int:
        test_calls.append(list(command))
        return 0

    def collector(command: run_unit_gate.Command) -> subprocess.CompletedProcess[str]:
        collection_calls.append(list(command))
        return _collected(stdout="\n".join([*node_ids, "", "2 tests collected in 0.01s", ""]))

    assert (
        run_unit_gate.run_unit_gate(
            tests_root,
            command_runner=runner,
            collection_runner=collector,
            split_modules=frozenset({module}),
        )
        == 0
    )
    assert collection_calls == [
        [
            run_unit_gate.sys.executable,
            "-m",
            "pytest",
            "-q",
            "-m",
            run_unit_gate.PYTEST_MARKERS,
            "--collect-only",
            str(module),
        ]
    ]
    assert test_calls == [
        [run_unit_gate.sys.executable, "-m", "planner", "check"],
        *[
            [
                run_unit_gate.sys.executable,
                "-m",
                "pytest",
                "-q",
                "-m",
                run_unit_gate.PYTEST_MARKERS,
                node_id,
            ]
            for node_id in node_ids
        ],
    ]


@pytest.mark.parametrize(("returncode", "expected"), [(2, 2), (-9, 137)])
def test_collection_nonzero_or_signal_aborts_and_surfaces_stderr(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    *,
    returncode: int,
    expected: int,
) -> None:
    tests_root = _make_modules(tmp_path, ["test_enzyme_governance_acceptance.py"])
    module = tests_root / "test_enzyme_governance_acceptance.py"
    calls: list[list[str]] = []

    def runner(command: run_unit_gate.Command) -> int:
        calls.append(list(command))
        return 0

    def collector(command: run_unit_gate.Command) -> subprocess.CompletedProcess[str]:
        return _collected(returncode=returncode, stdout=f"{module}::test_ignored\n", stderr="collection failed\n")

    assert (
        run_unit_gate.run_unit_gate(
            tests_root,
            command_runner=runner,
            collection_runner=collector,
            split_modules=frozenset({module}),
        )
        == expected
    )
    assert calls == [[run_unit_gate.sys.executable, "-m", "planner", "check"]]
    assert capsys.readouterr().err == "collection failed\n"


@pytest.mark.parametrize(
    ("stdout", "error_fragment"),
    [
        ("1 test collected in 0.01s\n", "no test node IDs"),
        ("not a node record\n1 test collected in 0.01s\n", "malformed collection record"),
        (
            "{module}::test_one\n{module}::test_one\n2 tests collected in 0.01s\n",
            "duplicate collection record",
        ),
        ("tests/test_other.py::test_one\n1 test collected in 0.01s\n", "foreign collection record"),
    ],
)
def test_invalid_collection_output_fails_closed(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    stdout: str,
    error_fragment: str,
) -> None:
    tests_root = _make_modules(tmp_path, ["test_enzyme_governance_acceptance.py"])
    module = tests_root / "test_enzyme_governance_acceptance.py"
    rendered_stdout = stdout.format(module=module)
    calls: list[list[str]] = []

    def runner(command: run_unit_gate.Command) -> int:
        calls.append(list(command))
        return 0

    def collector(command: run_unit_gate.Command) -> subprocess.CompletedProcess[str]:
        return _collected(stdout=rendered_stdout, stderr=f"{module}::test_stderr_is_not_a_node\n")

    assert (
        run_unit_gate.run_unit_gate(
            tests_root,
            command_runner=runner,
            collection_runner=collector,
            split_modules=frozenset({module}),
        )
        == 5
    )
    assert calls == [[run_unit_gate.sys.executable, "-m", "planner", "check"]]
    assert error_fragment in capsys.readouterr().err


def test_split_leaf_exit_one_continues_and_reports_module_and_leaves(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    tests_root = _make_modules(tmp_path, ["test_enzyme_governance_acceptance.py"])
    module = tests_root / "test_enzyme_governance_acceptance.py"
    node_ids = [f"{module}::test_one", f"{module}::test_two", f"{module}::test_three"]
    leaf_statuses = iter([1, 0, 1])
    test_calls: list[list[str]] = []

    def runner(command: run_unit_gate.Command) -> int:
        test_calls.append(list(command))
        return 0 if len(test_calls) == 1 else next(leaf_statuses)

    def collector(command: run_unit_gate.Command) -> subprocess.CompletedProcess[str]:
        return _collected(stdout="\n".join([*node_ids, "3 tests collected in 0.01s", ""]))

    assert (
        run_unit_gate.run_unit_gate(
            tests_root,
            command_runner=runner,
            collection_runner=collector,
            split_modules=frozenset({module}),
        )
        == 1
    )
    assert [command[-1] for command in test_calls[1:]] == node_ids
    output = capsys.readouterr().out
    assert output == (
        f"[1/1] {module.as_posix()}\n"
        f"  [1/3] {node_ids[0]}\n"
        f"  [2/3] {node_ids[1]}\n"
        f"  [3/3] {node_ids[2]}\n"
        "Failed unit test modules:\n"
        f"- {module.as_posix()}\n"
        "Failed split unit test leaves:\n"
        f"- {node_ids[0]}\n"
        f"- {node_ids[2]}\n"
    )


def test_split_leaf_abnormal_status_aborts_immediately(tmp_path: Path) -> None:
    tests_root = _make_modules(tmp_path, ["test_enzyme_governance_acceptance.py"])
    module = tests_root / "test_enzyme_governance_acceptance.py"
    node_ids = [f"{module}::test_one", f"{module}::test_two", f"{module}::test_three"]
    leaf_statuses = iter([0, -9])
    test_calls: list[list[str]] = []

    def runner(command: run_unit_gate.Command) -> int:
        test_calls.append(list(command))
        return 0 if len(test_calls) == 1 else next(leaf_statuses)

    def collector(command: run_unit_gate.Command) -> subprocess.CompletedProcess[str]:
        return _collected(stdout="\n".join([*node_ids, "3 tests collected in 0.01s", ""]))

    assert (
        run_unit_gate.run_unit_gate(
            tests_root,
            command_runner=runner,
            collection_runner=collector,
            split_modules=frozenset({module}),
        )
        == 137
    )
    assert [command[-1] for command in test_calls[1:]] == node_ids[:2]


def test_module_and_leaf_progress_are_flushed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    tests_root = _make_modules(tmp_path, ["test_enzyme_governance_acceptance.py"])
    module = tests_root / "test_enzyme_governance_acceptance.py"
    node_id = f"{module}::test_one"
    progress: list[tuple[str, object]] = []

    def fake_print(*values: object, **kwargs: object) -> None:
        progress.append((" ".join(str(value) for value in values), kwargs.get("flush")))

    def collector(command: run_unit_gate.Command) -> subprocess.CompletedProcess[str]:
        return _collected(stdout=f"{node_id}\n1 test collected in 0.01s\n")

    def runner(command: run_unit_gate.Command) -> int:
        return 0

    monkeypatch.setattr(builtins, "print", fake_print)
    assert (
        run_unit_gate.run_unit_gate(
            tests_root,
            command_runner=runner,
            collection_runner=collector,
            split_modules=frozenset({module}),
        )
        == 0
    )
    assert progress == [
        (f"[1/1] {module.as_posix()}", True),
        (f"  [1/1] {node_id}", True),
    ]
