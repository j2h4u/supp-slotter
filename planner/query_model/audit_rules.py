"""Generated canonical intake-review rule projection."""

from __future__ import annotations

from typing import cast

from planner.ontology.artifacts import OntologyBundle


def load_audit_review_rules(
    ontology_bundle: OntologyBundle,
    *,
    include_retired: bool = False,
) -> list[dict[str, object]]:  # noqa: C901, PLR0912
    raw = ontology_bundle.runtime_vocabulary.get("audit_review_rules")
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
        if rule.get("axis") not in {"intake", "timing", "activity"}:
            raise RuntimeError("generated audit review rule axis must be valid")
        if rule.get("predicate") != "reviewed_disposition_present":
            raise RuntimeError("generated audit review rule predicate must be reviewed_disposition_present")
        subjects = rule.get("subjects")
        if not isinstance(subjects, dict):
            raise RuntimeError("generated audit review rule subjects must be a sorted mapping")
        subject_mapping = cast(dict[str, object], subjects)
        if list(subject_mapping) != sorted(subject_mapping):
            raise RuntimeError("generated audit review rule subjects must be a sorted mapping")
        rules.append(rule)
    return rules


def load_audit_relation_exemptions(ontology_bundle: OntologyBundle) -> list[dict[str, object]]:
    raw = ontology_bundle.runtime_vocabulary.get("audit_relation_exemptions")
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
