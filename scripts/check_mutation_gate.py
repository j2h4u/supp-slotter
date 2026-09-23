from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import cast

BLOCKING_FIELDS = (
    "survived",
    "no_tests",
    "suspicious",
    "timeout",
    "check_was_interrupted_by_user",
    "segfault",
    "not_checked",
)
REQUIRED_FIELDS = (
    "total",
    "killed",
    "survived",
    "no_tests",
    "suspicious",
    "timeout",
    "check_was_interrupted_by_user",
    "segfault",
)
OPTIONAL_RESULT_FIELDS = ("skipped",)
SURVIVOR_LINE = re.compile(r"^\s*(\S+): survived\s*$")


def _read_stats(path: Path) -> dict[str, int]:
    raw_data = cast("object", json.loads(path.read_text(encoding="utf-8")))
    if not isinstance(raw_data, dict):
        raise SystemExit(f"mutation stats must be a JSON object: {path}")

    stats: dict[str, int] = {}
    for key, value in raw_data.items():
        if not isinstance(key, str):
            raise SystemExit(f"mutation stats contains a non-string key: {path}")
        if not isinstance(value, int):
            raise SystemExit(f"mutation stats field {key!r} must be an integer")
        if value < 0:
            raise SystemExit(f"mutation stats field {key!r} must be non-negative")
        stats[key] = value
    missing = [field for field in REQUIRED_FIELDS if field not in stats]
    if missing:
        raise SystemExit(f"mutation stats missing required field(s): {', '.join(missing)}")
    return stats


def _validate_totals(stats: dict[str, int]) -> None:
    total = stats["total"]
    if total <= 0:
        raise SystemExit("mutation stats total must be greater than zero")
    classified = sum(stats[field] for field in ("killed", *BLOCKING_FIELDS, *OPTIONAL_RESULT_FIELDS) if field in stats)
    if classified != total:
        raise SystemExit(f"mutation stats total={total} does not match classified mutants={classified}")


def _read_survivors(path: Path) -> set[str]:
    return {
        match.group(1) for line in path.read_text(encoding="utf-8").splitlines() if (match := SURVIVOR_LINE.match(line))
    }


def _read_baseline(path: Path) -> set[str]:
    return {line.strip() for line in path.read_text(encoding="utf-8").splitlines() if line.strip()}


def check_mutation_gate(path: Path, *, results_path: Path | None = None, baseline_path: Path | None = None) -> int:
    stats = _read_stats(path)
    _validate_totals(stats)
    if results_path is None or baseline_path is None:
        blockers = [f"{field}={stats.get(field, 0)}" for field in BLOCKING_FIELDS if stats.get(field, 0) > 0]
        if blockers:
            print(f"mutation gate failed: {', '.join(blockers)}", file=sys.stderr)
            return 1
        print(f"mutation gate passed: total={stats['total']}, killed={stats['killed']}")
        return 0

    survivors = _read_survivors(results_path)
    if len(survivors) != stats["survived"]:
        raise SystemExit(
            f"mutation results survived={len(survivors)} does not match stats survived={stats['survived']}"
        )
    baseline = _read_baseline(baseline_path)
    new_survivors = sorted(survivors - baseline)
    blockers = [
        f"{field}={stats.get(field, 0)}" for field in BLOCKING_FIELDS if field != "survived" and stats.get(field, 0) > 0
    ]
    if new_survivors:
        blockers.append(f"new_survivors={','.join(new_survivors)}")
    if blockers:
        print(f"mutation gate failed: {', '.join(blockers)}", file=sys.stderr)
        return 1

    print(
        f"mutation gate passed: total={stats['total']}, killed={stats['killed']}, "
        f"survivors={len(survivors)}, baseline={len(baseline)}"
    )
    return 0


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    if not args or len(args) not in (1, 5):
        print(
            "usage: python scripts/check_mutation_gate.py <stats.json> "
            "[--results <mutmut-results.txt> --baseline <survivors.txt>]",
            file=sys.stderr,
        )
        return 2
    if len(args) == 1:
        return check_mutation_gate(Path(args[0]))
    if args[1] != "--results" or args[3] != "--baseline":
        print("--results and --baseline must be supplied together", file=sys.stderr)
        return 2
    return check_mutation_gate(Path(args[0]), results_path=Path(args[2]), baseline_path=Path(args[4]))


if __name__ == "__main__":
    raise SystemExit(main())
