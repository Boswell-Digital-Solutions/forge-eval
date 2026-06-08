from __future__ import annotations

from typing import Any

from forge_eval.errors import StageError

BLOCK_REASON_ORDER = (
    "HAZARD_BLOCKING_SIGNAL_PRESENT",
    "HAZARD_TIER_CRITICAL",
    "HAZARD_TIER_HIGH",
    "HAZARD_SCORE_AT_OR_ABOVE_BLOCK_THRESHOLD",
)
CAUTION_REASON_ORDER = (
    "HAZARD_TIER_ELEVATED",
    "HAZARD_TIER_GUARDED",
    "HAZARD_SCORE_AT_OR_ABOVE_CAUTION_THRESHOLD",
    "HAZARD_UNCERTAINTY_PRESENT",
    "HAZARD_HIDDEN_PRESSURE_ELEVATED",
)


def build_merge_decision_reasons(
    *,
    hazard_map_artifact: dict[str, Any],
    model: dict[str, Any],
) -> dict[str, Any]:
    summary = _required_object(hazard_map_artifact, "summary")
    hazard_score = _required_unit_number(summary, "hazard_score")
    hazard_tier = _required_hazard_tier(summary, "hazard_tier")
    blocking_signals_present = _required_bool(summary, "blocking_signals_present")
    hidden_pressure = _required_unit_number(summary, "hidden_pressure")
    uncertainty_flags = _required_string_list(summary, "uncertainty_flags")

    parameters = _required_object(model, "parameters")
    caution_threshold = _required_unit_number(
        parameters, "merge_decision_caution_threshold"
    )
    block_threshold = _required_unit_number(
        parameters, "merge_decision_block_threshold"
    )
    block_on_signals = parameters.get("merge_decision_block_on_hazard_blocking_signals")
    if not isinstance(block_on_signals, bool):
        raise StageError(
            "merge decision model blocking-signal policy must be boolean",
            stage="merge_decision",
            details={
                "merge_decision_block_on_hazard_blocking_signals": block_on_signals
            },
        )

    blocking_reason_codes: list[str] = []
    caution_reason_codes: list[str] = []

    if block_on_signals and blocking_signals_present:
        blocking_reason_codes.append("HAZARD_BLOCKING_SIGNAL_PRESENT")
    if hazard_tier == "critical":
        blocking_reason_codes.append("HAZARD_TIER_CRITICAL")
    elif hazard_tier == "high":
        blocking_reason_codes.append("HAZARD_TIER_HIGH")
    if hazard_score >= block_threshold:
        blocking_reason_codes.append("HAZARD_SCORE_AT_OR_ABOVE_BLOCK_THRESHOLD")

    if hazard_tier == "elevated":
        caution_reason_codes.append("HAZARD_TIER_ELEVATED")
    elif hazard_tier == "guarded":
        caution_reason_codes.append("HAZARD_TIER_GUARDED")
    if hazard_score >= caution_threshold:
        caution_reason_codes.append("HAZARD_SCORE_AT_OR_ABOVE_CAUTION_THRESHOLD")
    if uncertainty_flags:
        caution_reason_codes.append("HAZARD_UNCERTAINTY_PRESENT")
    if hidden_pressure >= 0.25:
        caution_reason_codes.append("HAZARD_HIDDEN_PRESSURE_ELEVATED")

    blocking_reason_codes = _stable_reason_subset(
        BLOCK_REASON_ORDER, blocking_reason_codes
    )
    caution_reason_codes = _stable_reason_subset(
        CAUTION_REASON_ORDER, caution_reason_codes
    )

    if blocking_reason_codes:
        decision = "block"
    elif caution_reason_codes:
        decision = "caution"
    else:
        decision = "allow"

    return {
        "decision": decision,
        "blocking_reason_codes": blocking_reason_codes,
        "caution_reason_codes": caution_reason_codes,
        "reason_codes": [*blocking_reason_codes, *caution_reason_codes],
    }


def _stable_reason_subset(order: tuple[str, ...], candidates: list[str]) -> list[str]:
    candidate_set = set(candidates)
    return [item for item in order if item in candidate_set]


def _required_object(obj: dict[str, Any], key: str) -> dict[str, Any]:
    value = obj.get(key)
    if not isinstance(value, dict):
        raise StageError(
            "merge decision requires object section",
            stage="merge_decision",
            details={"field": key, "value": value},
        )
    return value


def _required_unit_number(obj: dict[str, Any], key: str) -> float:
    value = obj.get(key)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise StageError(
            "merge decision requires numeric field",
            stage="merge_decision",
            details={"field": key, "value": value},
        )
    number = float(value)
    if number < 0.0 or number > 1.0:
        raise StageError(
            "merge decision numeric field must be in [0, 1]",
            stage="merge_decision",
            details={"field": key, "value": number},
        )
    return number


def _required_bool(obj: dict[str, Any], key: str) -> bool:
    value = obj.get(key)
    if not isinstance(value, bool):
        raise StageError(
            "merge decision requires boolean field",
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
            "merge decision requires list of strings",
            stage="merge_decision",
            details={"field": key, "value": value},
        )
    return list(value)


def _required_hazard_tier(obj: dict[str, Any], key: str) -> str:
    value = obj.get(key)
    allowed = {"low", "guarded", "elevated", "high", "critical"}
    if value not in allowed:
        raise StageError(
            "merge decision requires supported hazard tier",
            stage="merge_decision",
            details={"field": key, "value": value},
        )
    return str(value)
