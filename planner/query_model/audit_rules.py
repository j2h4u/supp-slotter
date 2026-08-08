"""Generated audit relation-exemption projection."""

from __future__ import annotations

from typing import cast

from planner.ontology.artifacts import OntologyBundle
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
