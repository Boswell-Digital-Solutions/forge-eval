from __future__ import annotations

from typing import Any

from forge_eval.errors import StageError


def build_evidence_bundle_summary(
    *,
    artifacts: list[dict[str, Any]],
    merge_decision_artifact: dict[str, Any],
    manifest: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    decision = _build_decision_section(merge_decision_artifact)
    summary = _build_summary_section(
        artifacts=artifacts,
        merge_decision_artifact=merge_decision_artifact,
        manifest=manifest,
    )
    return decision, summary


def _build_decision_section(merge_decision_artifact: dict[str, Any]) -> dict[str, Any]:
    decision = _required_object(merge_decision_artifact, "decision")
    reason_codes = merge_decision_artifact.get("reason_codes")
    if (
        not isinstance(reason_codes, list)
        or not reason_codes
        or not all(isinstance(item, str) and item for item in reason_codes)
    ):
        raise StageError(
            "merge_decision artifact reason_codes must be a non-empty string list",
            stage="evidence_bundle",
            details={"reason_codes": reason_codes},
        )

    result = _required_enum(decision, "result", {"allow", "caution", "block"})
    advisory = _required_bool(decision, "advisory")
    blocking = _required_bool(decision, "blocking_conditions_present")
    caution = _required_bool(decision, "caution_conditions_present")
    return {
        "source_artifact": "merge_decision.json",
        "result": result,
        "advisory": advisory,
        "blocking_conditions_present": blocking,
        "caution_conditions_present": caution,
        "reason_codes": list(reason_codes),
    }


def _build_summary_section(
    *,
    artifacts: list[dict[str, Any]],
    merge_decision_artifact: dict[str, Any],
    manifest: dict[str, Any],
) -> dict[str, Any]:
    decision = _required_object(merge_decision_artifact, "decision")
    merge_summary = _required_object(merge_decision_artifact, "summary")
    reason_codes = merge_decision_artifact.get("reason_codes")
    if not isinstance(reason_codes, list):
        raise StageError(
            "merge_decision artifact reason_codes must be a list",
            stage="evidence_bundle",
            details={"reason_codes": reason_codes},
        )
    included_kinds = [str(entry["kind"]) for entry in artifacts]
    final_chain_hash = _required_string(manifest, "final_chain_hash")

    return {
        "artifact_count": len(artifacts),
        "included_kinds": included_kinds,
        "final_decision": _required_enum(
            decision, "result", {"allow", "caution", "block"}
        ),
        "reason_code_count": len(reason_codes),
        "blocking_conditions_present": _required_bool(
            decision, "blocking_conditions_present"
        ),
        "caution_conditions_present": _required_bool(
            decision, "caution_conditions_present"
        ),
        "dominant_hazard_tier": _required_enum(
            merge_summary,
            "dominant_hazard_tier",
            {"low", "guarded", "elevated", "high", "critical"},
        ),
        "final_chain_hash": final_chain_hash,
    }


def _required_object(obj: dict[str, Any], field: str) -> dict[str, Any]:
    value = obj.get(field)
    if not isinstance(value, dict):
        raise StageError(
            "evidence bundle requires object section",
            stage="evidence_bundle",
            details={"field": field, "value": value},
        )
    return value


def _required_string(obj: dict[str, Any], field: str) -> str:
    value = obj.get(field)
    if not isinstance(value, str) or not value:
        raise StageError(
            "evidence bundle requires non-empty string field",
            stage="evidence_bundle",
            details={"field": field, "value": value},
        )
    return value


def _required_bool(obj: dict[str, Any], field: str) -> bool:
    value = obj.get(field)
    if not isinstance(value, bool):
        raise StageError(
            "evidence bundle requires boolean field",
            stage="evidence_bundle",
            details={"field": field, "value": value},
        )
    return value


def _required_enum(obj: dict[str, Any], field: str, allowed: set[str]) -> str:
    value = obj.get(field)
    if not isinstance(value, str) or value not in allowed:
        raise StageError(
            "evidence bundle requires supported enum field",
            stage="evidence_bundle",
            details={"field": field, "value": value, "allowed": sorted(allowed)},
        )
    return value
