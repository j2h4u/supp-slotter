"""Check and benchmark ontology repository projection plus SHACL validation."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path
from typing import cast

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from planner.ontology.artifacts import load_ontology  # noqa: E402
from planner.ontology.projection import project_repository  # noqa: E402
from planner.ontology.validation import validate_graph  # noqa: E402
from scripts.ontology_compiler import compile_ontology  # noqa: E402

DEFAULT_COLD_LIMIT_SECONDS = 10.0
DEFAULT_WARM_LIMIT_SECONDS = 10.0
DEFAULT_WARM_RUNS = 3


def _path(repository_root: Path, *, include_compile: bool) -> tuple[float, bool]:
    start = time.perf_counter()
    ontology_root = repository_root / "ontology"
    if include_compile:
        compile_ontology(ontology_root)
    bundle = load_ontology(ontology_root)
    projection = project_repository(repository_root, bundle)
    conforms, _report_graph, report_text = validate_graph(projection.graph, ontology_root)
    if not isinstance(report_text, str):
        raise RuntimeError("SHACL validation returned an invalid report")
    return time.perf_counter() - start, conforms


def _single_run(repository_root: Path, *, include_compile: bool) -> int:
    duration, conforms = _path(repository_root, include_compile=include_compile)
    print(json.dumps({"conforms": conforms, "seconds": duration}, sort_keys=True))
    return 0 if conforms else 1


def _cold_run(repository_root: Path, *, include_compile: bool) -> float:
    command = [sys.executable, str(Path(__file__).resolve()), "--single-run", "--repo-root", str(repository_root)]
    if include_compile:
        command.append("--include-compile")
    completed = subprocess.run(
        command,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        raise RuntimeError(
            "Cold benchmark child failed"
            f"\nstdout:\n{completed.stdout}"
            f"\nstderr:\n{completed.stderr}"
        )
    payload = cast(dict[str, object], json.loads(completed.stdout))
    seconds = payload.get("seconds")
    conforms = payload.get("conforms")
    if not isinstance(seconds, int | float) or not isinstance(conforms, bool):
        raise RuntimeError("Cold benchmark child returned an invalid payload")
    if not conforms:
        raise RuntimeError("Cold benchmark child returned non-conforming projection")
    return float(seconds)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=REPOSITORY_ROOT)
    parser.add_argument("--single-run", action="store_true")
    parser.add_argument("--include-compile", action="store_true", help="include ontology artifact compilation")
    parser.add_argument("--check-only", action="store_true", help="check conformance once without enforcing timings")
    parser.add_argument("--warm-runs", type=int, default=DEFAULT_WARM_RUNS)
    parser.add_argument("--cold-limit-seconds", type=float, default=DEFAULT_COLD_LIMIT_SECONDS)
    parser.add_argument("--warm-limit-seconds", type=float, default=DEFAULT_WARM_LIMIT_SECONDS)
    args = parser.parse_args()

    repository_root = args.repo_root.resolve()
    if args.single_run:
        return _single_run(repository_root, include_compile=args.include_compile)
    if args.check_only:
        duration, conforms = _path(repository_root, include_compile=args.include_compile)
        result = {
            "conforms": conforms,
            "include_compile": args.include_compile,
            "seconds": round(duration, 6),
        }
        print(json.dumps(result, sort_keys=True, indent=2))
        return 0 if conforms else 1
    if args.warm_runs < 1:
        parser.error("--warm-runs must be positive")
    cold = _cold_run(repository_root, include_compile=args.include_compile)
    warm_results = [_path(repository_root, include_compile=args.include_compile) for _ in range(args.warm_runs)]
    warm = [duration for duration, _conforms in warm_results]
    slowest_warm = max(warm)
    result = {
        "cold_seconds": round(cold, 6),
        "conforms": [conforms for _duration, conforms in warm_results],
        "include_compile": args.include_compile,
        "warm_seconds": [round(value, 6) for value in warm],
        "slowest_warm_seconds": round(slowest_warm, 6),
        "cold_limit_seconds": args.cold_limit_seconds,
        "warm_limit_seconds": args.warm_limit_seconds,
    }
    print(json.dumps(result, sort_keys=True, indent=2))
    if not all(conforms for _duration, conforms in warm_results):
        raise SystemExit("Ontology repository projection does not conform to generated SHACL shapes")
    if cold > args.cold_limit_seconds:
        raise SystemExit(f"Cold ontology check benchmark exceeded {args.cold_limit_seconds}s: {cold:.3f}s")
    if slowest_warm > args.warm_limit_seconds:
        raise SystemExit(
            f"Warm ontology check benchmark exceeded {args.warm_limit_seconds}s: {slowest_warm:.3f}s"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
