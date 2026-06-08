from __future__ import annotations

from typing import Any

from forge_eval.errors import StageError


def build_merge_decision_summary(
    *,
    hazard_map_artifact: dict[str, Any],
    reasoning: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    summary = hazard_map_artifact.get("summary")
    if not isinstance(summary, dict):
        raise StageError(
            "merge decision requires hazard summary",
            stage="merge_decision",
            details={"summary": summary},
        )

    decision_value = str(reasoning.get("decision"))
    if decision_value not in {"allow", "caution", "block"}:
        raise StageError(
            "merge decision helper returned unsupported decision",
            stage="merge_decision",
            details={"decision": decision_value},
        )

    blocking_reason_codes = _required_string_list(reasoning, "blocking_reason_codes")
    caution_reason_codes = _required_string_list(reasoning, "caution_reason_codes")
    all_reason_codes = _required_string_list(reasoning, "reason_codes")

    decision_payload = {
        "result": decision_value,
        "advisory": True,
        "blocking_conditions_present": bool(blocking_reason_codes),
        "caution_conditions_present": bool(caution_reason_codes),
    }
    summary_payload = {
        "decision_label": decision_value.upper(),
        "hazard_score": _required_unit_number(summary, "hazard_score"),
        "dominant_hazard_tier": _required_hazard_tier(summary, "hazard_tier"),
        "blocking_signals_present": _required_bool(summary, "blocking_signals_present"),
        "blocking_reason_count": len(blocking_reason_codes),
        "caution_reason_count": len(caution_reason_codes),
        "reason_code_count": len(all_reason_codes),
        "uncertainty_flag_count": len(
            _required_string_list(summary, "uncertainty_flags")
        ),
    }
    return decision_payload, summary_payload


def _required_unit_number(obj: dict[str, Any], key: str) -> float:
    value = obj.get(key)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise StageError(
            "merge decision summary requires numeric field",
            stage="merge_decision",
            details={"field": key, "value": value},
        )
    number = float(value)
    if number < 0.0 or number > 1.0:
        raise StageError(
            "merge decision summary numeric field must be in [0, 1]",
            stage="merge_decision",
            details={"field": key, "value": number},
        )
    return number


def _required_bool(obj: dict[str, Any], key: str) -> bool:
    value = obj.get(key)
    if not isinstance(value, bool):
        raise StageError(
            "merge decision summary requires boolean field",
            stage="merge_decision",
            details={"field": key, "value": value},
        )
    return value


def _required_string_list(obj: dict[str, Any], key: str) -> list[str]:
    value = obj.get(key)
    if not isinstance(value, list) or not all(
        isinstance(item, str) and item for item in value
    ):
        raise StageError(
            "merge decision summary requires list of strings",
            stage="merge_decision",
            details={"field": key, "value": value},
        )
    return list(value)


def _required_hazard_tier(obj: dict[str, Any], key: str) -> str:
    value = obj.get(key)
    allowed = {"low", "guarded", "elevated", "high", "critical"}
    if value not in allowed:
        raise StageError(
            "merge decision summary requires supported hazard tier",
            stage="merge_decision",
            details={"field": key, "value": value},
        )
    return str(value)
