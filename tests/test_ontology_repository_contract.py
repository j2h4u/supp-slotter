"""Wave C2 closed repository projection contract."""

from __future__ import annotations

import base64
import binascii
import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Never, cast

import pytest
import yaml
from planner.ontology.errors import OntologyInfrastructureError
from scripts.ontology_compiler import compile_ontology, generate_ontology

ROOT = Path(__file__).resolve().parents[1]
ONTOLOGY = ROOT / "ontology"

_COMPILE_FRAME_VERSION = "supp-slotter.test-compile-artifacts/v1"
_ONTOLOGY_COMPILE_TIMEOUT_SECONDS = 60.0
_COMPILE_DIAGNOSTIC_LIMIT_BYTES = 8_192
_COMPILE_RUNTIME_WORKER = """
import base64
import hashlib
import json
import sys
from pathlib import Path

from planner.ontology.errors import OntologyInfrastructureError
from scripts.ontology_compiler import compile_ontology

version = "supp-slotter.test-compile-artifacts/v1"
try:
    compiled = compile_ontology(Path(sys.argv[1]))
    artifacts = {}
    for path, payload in compiled.items():
        if not isinstance(path, Path) or not isinstance(payload, bytes):
            raise TypeError("compile_ontology returned a non-path or non-bytes artifact")
        encoded_path = path.as_posix()
        if encoded_path in artifacts:
            raise TypeError(f"compile_ontology returned duplicate artifact path: {encoded_path}")
        artifacts[encoded_path] = {
            "payload_base64": base64.b64encode(payload).decode("ascii"),
            "byte_length": len(payload),
            "sha256": hashlib.sha256(payload).hexdigest(),
        }
    frame = {
        "version": version,
        "kind": "ok",
        "artifact_count": len(artifacts),
        "artifacts": artifacts,
    }
except OntologyInfrastructureError as error:
    frame = {
        "version": version,
        "kind": "error",
        "error": {
            "message": str(error),
            "code": error.code,
            "violation_code": error.violation_code,
            "path": None if error.path is None else str(error.path),
        },
    }
except Exception as error:
    frame = {
        "version": version,
        "kind": "unexpected",
        "error": {"type": type(error).__name__, "message": str(error)},
    }
sys.stdout.write(json.dumps(frame, separators=(",", ":"), sort_keys=True))
sys.stdout.write("\\n")
"""


def _fixture(tmp_path: Path) -> Path:
    repository = tmp_path / "repo"
    shutil.copytree(ONTOLOGY, repository / "ontology")
    shutil.copytree(ROOT / "data", repository / "data")
    return repository / "ontology"


def _manifest(path: Path) -> dict[str, object]:
    return cast(dict[str, object], yaml.safe_load(path.read_text(encoding="utf-8")))


def _write_manifest(path: Path, manifest: dict[str, object]) -> None:
    path.write_text(yaml.safe_dump(manifest, sort_keys=False), encoding="utf-8")


def _bounded_compile_diagnostic(value: bytes | str | None) -> str:
    if value is None:
        return "<empty>"
    raw = value.encode("utf-8", errors="replace") if isinstance(value, str) else value
    if not raw:
        return "<empty>"
    if len(raw) <= _COMPILE_DIAGNOSTIC_LIMIT_BYTES:
        return raw.decode("utf-8", errors="replace")
    omitted = len(raw) - _COMPILE_DIAGNOSTIC_LIMIT_BYTES
    tail = raw[-_COMPILE_DIAGNOSTIC_LIMIT_BYTES:].decode("utf-8", errors="replace")
    return f"<truncated {omitted} leading bytes>\n{tail}"


def _fail_compile_child(
    operation: str,
    reason: str,
    *,
    stderr: bytes | str | None,
    stdout: bytes | str | None = None,
) -> Never:
    message = f"ontology compile child failed for {operation}: {reason}\nstderr:\n{_bounded_compile_diagnostic(stderr)}"
    if stdout is not None:
        message += f"\nstdout:\n{_bounded_compile_diagnostic(stdout)}"
    pytest.fail(message, pytrace=False)


def _decode_compile_error(frame: dict[object, object], *, operation: str) -> OntologyInfrastructureError:
    if set(frame) != {"version", "kind", "error"}:
        _fail_compile_child(operation, "malformed error frame", stderr=None)
    raw_error = frame["error"]
    if not isinstance(raw_error, dict) or set(raw_error) != {"message", "code", "violation_code", "path"}:
        _fail_compile_child(operation, "malformed error payload", stderr=None)
    error = cast(dict[object, object], raw_error)
    message = error["message"]
    code = error["code"]
    violation_code = error["violation_code"]
    path = error["path"]
    if not isinstance(message, str) or not isinstance(code, str) or not isinstance(violation_code, str):
        _fail_compile_child(operation, "malformed error metadata", stderr=None)
    if path is not None and not isinstance(path, str):
        _fail_compile_child(operation, "malformed error path", stderr=None)
    reconstructed = OntologyInfrastructureError(message, code=code, path=path)
    reconstructed.violation_code = violation_code
    return reconstructed


def _compile_in_fresh_child(  # noqa: C901, PLR0912, PLR0915
    ontology_root: Path,
    *,
    operation: str,
) -> dict[Path, bytes]:
    try:
        command = [sys.executable, "-c", _COMPILE_RUNTIME_WORKER, str(ontology_root.resolve())]
        result = subprocess.run(
            command,
            cwd=ROOT,
            capture_output=True,
            check=False,
            shell=False,
            timeout=_ONTOLOGY_COMPILE_TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired as error:
        _fail_compile_child(
            operation,
            f"timed out after {_ONTOLOGY_COMPILE_TIMEOUT_SECONDS:.0f}s",
            stderr=error.stderr,
            stdout=error.stdout,
        )
    except (OSError, subprocess.SubprocessError) as error:
        _fail_compile_child(operation, f"could not start or collect child: {error}", stderr=None)
    if result.returncode != 0:
        reason = (
            f"terminated by signal {-result.returncode}"
            if result.returncode < 0
            else f"exited with status {result.returncode}"
        )
        _fail_compile_child(operation, reason, stderr=result.stderr, stdout=result.stdout)
    lines = result.stdout.splitlines()
    if len(lines) != 1 or result.stdout != lines[0] + b"\n" or lines[0].strip() != lines[0]:
        _fail_compile_child(
            operation,
            f"expected exactly one LF-terminated {_COMPILE_FRAME_VERSION} frame",
            stderr=result.stderr,
            stdout=result.stdout,
        )
    try:
        decoded = json.loads(lines[0].decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        _fail_compile_child(operation, f"malformed JSON frame: {error}", stderr=result.stderr, stdout=result.stdout)
    if not isinstance(decoded, dict):
        _fail_compile_child(operation, "JSON frame is not an object", stderr=result.stderr, stdout=result.stdout)
    frame = cast(dict[object, object], decoded)
    if frame.get("version") != _COMPILE_FRAME_VERSION:
        _fail_compile_child(operation, "unexpected compile frame version", stderr=result.stderr, stdout=result.stdout)
    kind = frame.get("kind")
    if kind == "error":
        raise _decode_compile_error(frame, operation=operation)
    if kind == "unexpected":
        _fail_compile_child(
            operation,
            "unexpected exception in compile child",
            stderr=result.stderr,
            stdout=result.stdout,
        )
    expected_fields = {"version", "kind", "artifact_count", "artifacts"}
    if kind != "ok" or set(frame) != expected_fields:
        _fail_compile_child(operation, "malformed successful compile frame", stderr=result.stderr, stdout=result.stdout)
    count = frame["artifact_count"]
    raw_artifacts = frame["artifacts"]
    if not isinstance(count, int) or isinstance(count, bool) or not isinstance(raw_artifacts, dict):
        _fail_compile_child(operation, "malformed artifact map metadata", stderr=result.stderr, stdout=result.stdout)
    if count <= 0 or count != len(raw_artifacts):
        _fail_compile_child(operation, "incomplete artifact map", stderr=result.stderr, stdout=result.stdout)
    artifacts: dict[Path, bytes] = {}
    for raw_path, raw_payload in raw_artifacts.items():
        if not isinstance(raw_path, str) or not raw_path:
            _fail_compile_child(operation, "malformed artifact path", stderr=result.stderr, stdout=result.stdout)
        path = Path(raw_path)
        if path.is_absolute() or path.as_posix() != raw_path or ".." in path.parts or path in artifacts:
            _fail_compile_child(
                operation,
                f"unsafe or duplicate artifact path: {raw_path!r}",
                stderr=result.stderr,
                stdout=result.stdout,
            )
        if not isinstance(raw_payload, dict) or set(raw_payload) != {"payload_base64", "byte_length", "sha256"}:
            _fail_compile_child(
                operation,
                f"malformed artifact payload: {raw_path!r}",
                stderr=result.stderr,
                stdout=result.stdout,
            )
        payload = cast(dict[object, object], raw_payload)
        encoded = payload["payload_base64"]
        byte_length = payload["byte_length"]
        digest = payload["sha256"]
        if not isinstance(encoded, str) or not isinstance(byte_length, int) or isinstance(byte_length, bool):
            _fail_compile_child(
                operation,
                f"invalid artifact metadata: {raw_path!r}",
                stderr=result.stderr,
                stdout=result.stdout,
            )
        if not isinstance(digest, str):
            _fail_compile_child(
                operation,
                f"invalid artifact digest: {raw_path!r}",
                stderr=result.stderr,
                stdout=result.stdout,
            )
        try:
            content = base64.b64decode(encoded, validate=True)
        except binascii.Error as error:
            _fail_compile_child(
                operation,
                f"invalid artifact base64 for {raw_path!r}: {error}",
                stderr=result.stderr,
                stdout=result.stdout,
            )
        if byte_length < 0 or len(content) != byte_length:
            _fail_compile_child(
                operation,
                f"artifact byte length mismatch: {raw_path!r}",
                stderr=result.stderr,
                stdout=result.stdout,
            )
        if hashlib.sha256(content).hexdigest() != digest:
            _fail_compile_child(
                operation,
                f"artifact SHA-256 mismatch: {raw_path!r}",
                stderr=result.stderr,
                stdout=result.stdout,
            )
        artifacts[path] = content
    return artifacts


def test_projection_sources_are_closed_and_catalog_ref_is_not_a_live_path() -> None:
    manifest = _manifest(ONTOLOGY / "manifest.yaml")
    projection = cast(dict[str, object], manifest["repository_projection"])
    assert projection["format_version"] == "repository-projection-v1"
    sources = cast(list[dict[str, object]], projection["sources"])
    assert [item["id"] for item in sources] == [
        "substances",
        "products",
        "dashboards",
        "stacks",
        "pillboxes",
        "assertions",
    ]
    assertions = sources[-1]
    assert assertions["locator"] == {"kind": "catalog_ref", "catalog_id": "assertions"}
    assert all("path" not in cast(dict[str, object], assertions["locator"]) for _ in [0])


def test_card_content_and_same_shape_addition_do_not_change_projection(tmp_path: Path) -> None:
    ontology = _fixture(tmp_path)
    baseline = _compile_in_fresh_child(ontology, operation="baseline")
    card = next((ontology.parent / "data/substances").glob("*.yaml"))
    authored = cast(dict[str, object], cast(object, yaml.safe_load(card.read_text(encoding="utf-8"))))
    assert isinstance(authored, dict)
    authored["name"] = str(authored["name"]) + " changed"
    card.write_text(yaml.safe_dump(authored, sort_keys=False), encoding="utf-8")
    assert _compile_in_fresh_child(ontology, operation="card-content") == baseline
    extra = ontology.parent / "data/substances/fixture_unique__sub_fixtureunique.yaml"
    authored["id"] = "sub_fixtureunique"
    extra.write_text(yaml.safe_dump(authored, sort_keys=False), encoding="utf-8")
    assert _compile_in_fresh_child(ontology, operation="same-shape-addition") == baseline
    renamed = card.with_name(card.stem + "__renamed.yaml")
    card.rename(renamed)
    assert _compile_in_fresh_child(ontology, operation="same-shape-rename") == baseline
    renamed.unlink()
    assert _compile_in_fresh_child(ontology, operation="same-shape-removal") == baseline


@pytest.mark.parametrize("container", ["mapping", "list"])
def test_unknown_empty_container_fails_coverage(tmp_path: Path, container: str) -> None:
    ontology = _fixture(tmp_path)
    card = next((ontology.parent / "data/substances").glob("*.yaml"))
    authored = cast(dict[str, object], cast(object, yaml.safe_load(card.read_text(encoding="utf-8"))))
    assert isinstance(authored, dict)
    authored["unknown_field"] = {} if container == "mapping" else []
    card.write_text(yaml.safe_dump(authored, sort_keys=False), encoding="utf-8")
    with pytest.raises(OntologyInfrastructureError, match="unknown_field"):
        compile_ontology(ontology)


def test_projection_manifest_change_requires_schema_and_changes_projection(tmp_path: Path) -> None:
    ontology = _fixture(tmp_path)
    baseline = _compile_in_fresh_child(ontology, operation="baseline")
    manifest_path = ontology / "manifest.yaml"
    manifest = _manifest(manifest_path)
    projection = cast(dict[str, object], manifest["repository_projection"])
    sources = cast(list[dict[str, object]], projection["sources"])
    cast(dict[str, object], sources[0]["locator"])["path"] = "data/products"
    _write_manifest(manifest_path, manifest)
    with pytest.raises(OntologyInfrastructureError):
        _compile_in_fresh_child(ontology, operation="projection-path")
    cast(dict[str, object], sources[0]["locator"])["path"] = "data/substances"
    cast(dict[str, object], sources[0])["root_class"] = "Product"
    _write_manifest(manifest_path, manifest)
    with pytest.raises(OntologyInfrastructureError):
        _compile_in_fresh_child(ontology, operation="projection-root-class")
    cast(dict[str, object], sources[0])["root_class"] = "Substance"
    cast(dict[str, object], sources[0]["locator"])["kind"] = "explicit_paths"
    cast(dict[str, object], sources[0]["locator"]).pop("path")
    cast(dict[str, object], sources[0]["locator"])["paths"] = [
        "data/substances/" + path.name for path in sorted((ontology.parent / "data/substances").glob("*.yaml"))
    ]
    _write_manifest(manifest_path, manifest)
    assert _compile_in_fresh_child(ontology, operation="projection-explicit-paths") != baseline


@pytest.mark.parametrize("mutation", ["wildcard", "dotdot", "absolute", "unknown_locator", "unknown_root"])
def test_locator_attack_matrix_fails_closed(tmp_path: Path, mutation: str) -> None:
    ontology = _fixture(tmp_path)
    manifest_path = ontology / "manifest.yaml"
    manifest = _manifest(manifest_path)
    source = cast(list[dict[str, object]], cast(dict[str, object], manifest["repository_projection"])["sources"])[0]
    locator = cast(dict[str, object], source["locator"])
    if mutation == "wildcard":
        locator["path"] = "data/*"
    elif mutation == "dotdot":
        locator["path"] = "data/../data/substances"
    elif mutation == "absolute":
        locator["path"] = str((ontology.parent / "data/substances").resolve())
    elif mutation == "unknown_locator":
        locator["kind"] = "glob"
    else:
        source["root_class"] = "Unknown"
    _write_manifest(manifest_path, manifest)
    with pytest.raises(OntologyInfrastructureError):
        compile_ontology(ontology)


def test_assertion_catalog_ref_cannot_switch_catalog_role(tmp_path: Path) -> None:
    ontology = _fixture(tmp_path)
    manifest_path = ontology / "manifest.yaml"
    manifest = _manifest(manifest_path)
    projection = cast(dict[str, object], manifest["repository_projection"])
    sources = cast(list[dict[str, object]], projection["sources"])
    assertion = next(item for item in sources if item["id"] == "assertions")
    cast(dict[str, object], assertion["locator"])["catalog_id"] = "policies"
    _write_manifest(manifest_path, manifest)
    with pytest.raises(OntologyInfrastructureError):
        compile_ontology(ontology)


def test_symlink_and_unexpected_flat_root_entry_fail_closed(tmp_path: Path) -> None:
    ontology = _fixture(tmp_path)
    root = ontology.parent / "data/substances"
    unexpected = root / "unexpected.txt"
    unexpected.write_text("x", encoding="utf-8")
    with pytest.raises(OntologyInfrastructureError):
        compile_ontology(ontology)
    unexpected.unlink()
    link = root / "linked.yaml"
    try:
        link.symlink_to(next(root.glob("*.yaml")))
    except (OSError, NotImplementedError):
        pytest.skip("symlinks unavailable")
    with pytest.raises(OntologyInfrastructureError):
        compile_ontology(ontology)


def test_generated_projection_is_deterministic_and_checkable() -> None:
    first = compile_ontology(ONTOLOGY)
    second = compile_ontology(ONTOLOGY)
    assert first == second
    projection = cast(dict[str, object], json.loads(first[Path("projection-map.json")]))
    repository_projection = cast(dict[str, object], projection["repository_projection"])
    assert repository_projection["format_version"] == "repository-projection-v1"
    generate_ontology(ONTOLOGY, check=True)
