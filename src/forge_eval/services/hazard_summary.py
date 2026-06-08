from __future__ import annotations

from typing import Any

from forge_eval.errors import StageError
from forge_eval.services.hazard_model import clamp_unit, map_hazard_tier, round_float

UNCERTAINTY_FLAG_KEYS = (
    "sparse_capture_data",
    "low_doubleton_support",
    "ice_low_coverage",
    "estimator_guard_applied",
    "null_heavy_occupancy",
    "low_global_k_eff",
)


def build_hazard_summary(
    *,
    rows: list[dict[str, Any]],
    risk_heatmap_artifact: dict[str, Any],
    telemetry_matrix_artifact: dict[str, Any],
    occupancy_snapshot_artifact: dict[str, Any],
    capture_estimate_artifact: dict[str, Any],
    model: dict[str, Any],
) -> dict[str, Any]:
    if not isinstance(rows, list):
        raise StageError(
            "hazard_map rows must be a list",
            stage="hazard_map",
            details={"row_count": 0 if not isinstance(rows, list) else len(rows)},
        )

    round_digits = _required_round_digits(model)
    parameters = _required_parameters(model)

    risk_summary = _required_object(
        risk_heatmap_artifact, "summary", context="risk_heatmap"
    )
    telemetry_summary = _required_object(
        telemetry_matrix_artifact, "summary", context="telemetry_matrix"
    )
    occupancy_summary = _required_object(
        occupancy_snapshot_artifact, "summary", context="occupancy_snapshot"
    )
    capture_summary = _required_object(
        capture_estimate_artifact, "summary", context="capture_estimate"
    )

    defect_count = _required_non_negative_int(telemetry_summary, "defect_count")
    occupancy_defect_rows = _required_non_negative_int(occupancy_summary, "defect_rows")
    if defect_count != len(rows) or occupancy_defect_rows != len(rows):
        raise StageError(
            "hazard_map summary counts do not match row count",
            stage="hazard_map",
            details={
                "telemetry_defect_count": defect_count,
                "occupancy_defect_rows": occupancy_defect_rows,
                "row_count": len(rows),
            },
        )

    base_hazard_score = _bounded_union_score(rows)
    observed_defects = _required_non_negative_int(capture_summary, "observed_defects")
    selected_hidden = _required_non_negative_number(capture_summary, "selected_hidden")
    selected_total = _required_non_negative_number(capture_summary, "selected_total")
    if selected_total > 0.0 and selected_hidden > selected_total:
        raise StageError(
            "capture_estimate selected_hidden cannot exceed selected_total",
            stage="hazard_map",
            details={
                "selected_hidden": selected_hidden,
                "selected_total": selected_total,
            },
        )

    hidden_pressure = (
        0.0 if selected_total <= 0.0 else clamp_unit(selected_hidden / selected_total)
    )
    hidden_uplift = clamp_unit(
        float(parameters["hazard_hidden_uplift_strength"]) * hidden_pressure
    )

    uncertainty_flags = _build_uncertainty_flags(
        telemetry_summary=telemetry_summary,
        occupancy_summary=occupancy_summary,
        capture_summary=capture_summary,
    )
    uncertainty_ratio = len(uncertainty_flags) / float(len(UNCERTAINTY_FLAG_KEYS))
    uncertainty_uplift = clamp_unit(
        float(parameters["hazard_uncertainty_boost"]) * uncertainty_ratio
    )

    hazard_score = clamp_unit(
        1.0
        - (
            (1.0 - base_hazard_score)
            * (1.0 - hidden_uplift)
            * (1.0 - uncertainty_uplift)
        )
    )
    hazard_tier = map_hazard_tier(hazard_score)

    mean_psi_post = _required_unit_number(occupancy_summary, "mean_psi_post")
    max_risk_score = _required_unit_number(risk_summary, "max_risk_score")
    max_hazard_contribution = 0.0
    if rows:
        max_hazard_contribution = max(
            _required_unit_number(row, "hazard_contribution") for row in rows
        )
    blocking_threshold = _required_unit_number(parameters, "hazard_blocking_threshold")

    blocking_reason_flags = _build_blocking_reason_flags(
        rows=rows,
        hazard_score=hazard_score,
        blocking_threshold=blocking_threshold,
        hidden_pressure=hidden_pressure,
        max_risk_score=max_risk_score,
    )

    return {
        "hazard_score": round_float(hazard_score, round_digits),
        "hazard_tier": hazard_tier,
        "defect_count": defect_count,
        "observed_defects": observed_defects,
        "selected_hidden": round_float(selected_hidden, round_digits),
        "selected_total": round_float(selected_total, round_digits),
        "mean_psi_post": round_float(mean_psi_post, round_digits),
        "max_risk_score": round_float(max_risk_score, round_digits),
        "max_hazard_contribution": round_float(max_hazard_contribution, round_digits),
        "hidden_pressure": round_float(hidden_pressure, round_digits),
        "base_hazard_score": round_float(base_hazard_score, round_digits),
        "hidden_uplift": round_float(hidden_uplift, round_digits),
        "uncertainty_uplift": round_float(uncertainty_uplift, round_digits),
        "blocking_signals_present": bool(blocking_reason_flags),
        "blocking_reason_flags": blocking_reason_flags,
        "uncertainty_flags": uncertainty_flags,
    }


def _bounded_union_score(rows: list[dict[str, Any]]) -> float:
    remainder = 1.0
    for row in rows:
        contribution = _required_unit_number(row, "hazard_contribution")
        remainder *= 1.0 - contribution
    return clamp_unit(1.0 - remainder)


def _build_uncertainty_flags(
    *,
    telemetry_summary: dict[str, Any],
    occupancy_summary: dict[str, Any],
    capture_summary: dict[str, Any],
) -> list[str]:
    flags: list[str] = []
    if _required_bool(capture_summary, "sparse_data"):
        flags.append("sparse_capture_data")
    if _required_bool(capture_summary, "low_doubleton_support"):
        flags.append("low_doubleton_support")
    if _required_bool(capture_summary, "ice_low_coverage"):
        flags.append("ice_low_coverage")
    if _required_bool(capture_summary, "estimator_guard_applied"):
        flags.append("estimator_guard_applied")
    if _required_non_negative_int(occupancy_summary, "rows_with_nulls") > 0:
        flags.append("null_heavy_occupancy")
    if _required_non_negative_int(telemetry_summary, "k_eff") < 2:
        flags.append("low_global_k_eff")
    return flags


def _build_blocking_reason_flags(
    *,
    rows: list[dict[str, Any]],
    hazard_score: float,
    blocking_threshold: float,
    hidden_pressure: float,
    max_risk_score: float,
) -> list[str]:
    flags: list[str] = []
    if hazard_score >= blocking_threshold:
        flags.append("hazard_score_threshold")
    if any(
        str(row.get("severity")) == "critical"
        and _required_unit_number(row, "local_risk_score") >= 0.60
        for row in rows
    ):
        flags.append("critical_defect_on_risky_file")
    if hidden_pressure >= 0.25 and max_risk_score >= 0.75:
        flags.append("hidden_pressure_on_high_risk_surface")
    return flags


def _required_object(obj: dict[str, Any], key: str, *, context: str) -> dict[str, Any]:
    value = obj.get(key)
    if not isinstance(value, dict):
        raise StageError(
            "hazard_map requires object section",
            stage="hazard_map",
            details={"context": context, "field": key, "value": value},
        )
    return value


def _required_parameters(model: dict[str, Any]) -> dict[str, Any]:
    parameters = model.get("parameters")
    if not isinstance(parameters, dict):
        raise StageError(
            "hazard model parameters must be an object",
            stage="hazard_map",
            details={"parameters": parameters},
        )
    return parameters


def _required_round_digits(model: dict[str, Any]) -> int:
    parameters = _required_parameters(model)
    value = parameters.get("hazard_round_digits")
    if isinstance(value, bool) or not isinstance(value, int) or value < 0 or value > 12:
        raise StageError(
            "hazard_round_digits must be an integer in [0, 12]",
            stage="hazard_map",
            details={"hazard_round_digits": value},
        )
    return value


def _required_non_negative_int(obj: dict[str, Any], key: str) -> int:
    value = obj.get(key)
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise StageError(
            "hazard_map requires non-negative integer field",
            stage="hazard_map",
            details={"field": key, "value": value},
        )
    return value


def _required_non_negative_number(obj: dict[str, Any], key: str) -> float:
    value = obj.get(key)
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or float(value) < 0.0
    ):
        raise StageError(
            "hazard_map requires non-negative numeric field",
            stage="hazard_map",
            details={"field": key, "value": value},
        )
    return float(value)


def _required_unit_number(obj: dict[str, Any], key: str) -> float:
    number = _required_non_negative_number(obj, key)
    if number > 1.0:
        raise StageError(
            "hazard_map requires unit-interval numeric field",
            stage="hazard_map",
            details={"field": key, "value": number},
        )
    return number


def _required_bool(obj: dict[str, Any], key: str) -> bool:
    value = obj.get(key)
    if not isinstance(value, bool):
        raise StageError(
            "hazard_map requires boolean field",
            stage="hazard_map",
            details={"field": key, "value": value},
        )
    return value
