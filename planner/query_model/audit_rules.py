"""Generated canonical intake-review rule projection."""

from __future__ import annotations

from pathlib import Path
from typing import cast

from planner.ontology.artifacts import load_runtime_vocabulary


def load_audit_review_rules(*, include_retired: bool = False) -> list[dict[str, object]]:
    raw = load_runtime_vocabulary(Path(__file__).parents[2] / "ontology").get("audit_review_rules")
    if not isinstance(raw, list):
        raise RuntimeError("generated ontology has no audit_review_rules")
    rules: list[dict[str, object]] = []
    for item in raw:
        if not isinstance(item, dict):
            raise RuntimeError("generated audit_review_rules entries must be mappings")
        rule = cast(dict[str, object], item)
        status = rule.get("status")
        if status not in {"approved", "review_pending", "retired"}:
            raise RuntimeError("generated audit review rule status must be a valid lifecycle")
        if status == "retired" and not include_retired:
            continue
        priority = rule.get("priority")
        if not isinstance(priority, int) or isinstance(priority, bool) or priority < 0:
            raise RuntimeError("generated audit review rule priority must be a non-negative integer")
        if not isinstance(rule.get("message"), str) or not isinstance(rule.get("action"), str):
            raise RuntimeError("generated audit review rule message/action must be strings")
        if not isinstance(rule.get("enforcement"), str) or not isinstance(rule.get("scope"), dict):
            raise RuntimeError("generated audit review rule governance is incomplete")
        rules.append(rule)
    return rules


def load_audit_relation_exemptions() -> list[dict[str, object]]:
    raw = load_runtime_vocabulary(Path(__file__).parents[2] / "ontology").get("audit_relation_exemptions")
    if not isinstance(raw, list):
        raise RuntimeError("generated ontology has no audit_relation_exemptions")
    exemptions: list[dict[str, object]] = []
    for item in raw:
        if not isinstance(item, dict):
            raise RuntimeError("generated audit relation exemption entries must be mappings")
        exemption = cast(dict[str, object], item)
        for key in ("id", "relation_type", "source_selector_key", "target_selector_key"):
            if not isinstance(exemption.get(key), str) or not exemption[key]:
                raise RuntimeError(f"generated audit relation exemption {key} must be a non-empty string")
        exemptions.append(exemption)
    return exemptions
