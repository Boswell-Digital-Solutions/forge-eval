from __future__ import annotations

from typing import Any

from forge_eval.errors import StageError
from forge_eval.services.hazard_model import clamp_unit, round_float, severity_weight

ROW_HIGH_RISK_THRESHOLD = 0.75
ROW_HIGH_OCCUPANCY_THRESHOLD = 0.80


def build_hazard_rows(
    *,
    risk_heatmap_artifact: dict[str, Any],
    telemetry_matrix_artifact: dict[str, Any],
    occupancy_snapshot_artifact: dict[str, Any],
    model: dict[str, Any],
) -> list[dict[str, Any]]:
    risk_targets = risk_heatmap_artifact.get("targets")
    telemetry_defects = telemetry_matrix_artifact.get("defects")
    occupancy_rows = occupancy_snapshot_artifact.get("rows")

    if (
        not isinstance(risk_targets, list)
        or not isinstance(telemetry_defects, list)
        or not isinstance(occupancy_rows, list)
    ):
        raise StageError(
            "hazard_map inputs are missing required list sections",
            stage="hazard_map",
            details={
                "risk_targets_type": str(type(risk_targets)),
                "telemetry_defects_type": str(type(telemetry_defects)),
                "occupancy_rows_type": str(type(occupancy_rows)),
            },
        )

    round_digits = _required_round_digits(model)
    params = _required_parameters(model)

    risk_by_file = _map_risk_targets(risk_targets)
    defects_by_key = _map_by_defect_key(telemetry_defects, section="telemetry_defects")
    occupancy_by_key = _map_by_defect_key(occupancy_rows, section="occupancy_rows")

    defect_keys = set(defects_by_key.keys())
    occupancy_keys = set(occupancy_by_key.keys())
    if defect_keys != occupancy_keys:
        raise StageError(
            "telemetry and occupancy defect sets are inconsistent for hazard mapping",
            stage="hazard_map",
            details={
                "missing_in_occupancy": sorted(defect_keys - occupancy_keys),
                "extra_in_occupancy": sorted(occupancy_keys - defect_keys),
            },
        )

    built_rows: list[dict[str, Any]] = []
    for defect_key in sorted(defect_keys):
        defect = defects_by_key[defect_key]
        occupancy = occupancy_by_key[defect_key]

        file_path = _required_str(defect, "file_path")
        if file_path not in risk_by_file:
            raise StageError(
                "hazard_map could not map defect file to risk target",
                stage="hazard_map",
                details={"defect_key": defect_key, "file_path": file_path},
            )
        local_risk_score = risk_by_file[file_path]

        _cross_check_optional_str(
            defect=defect, occupancy=occupancy, key="file_path", defect_key=defect_key
        )
        _cross_check_optional_str(
            defect=defect, occupancy=occupancy, key="category", defect_key=defect_key
        )
        _cross_check_optional_str(
            defect=defect, occupancy=occupancy, key="severity", defect_key=defect_key
        )

        severity = _required_str(defect, "severity")
        category = _required_str(defect, "category")
        reported_by = _required_string_list(defect, "reported_by")
        support_count = _required_non_negative_int(defect, "support_count")
        occupancy_support = _required_non_negative_int(occupancy, "support_count")
        if support_count != occupancy_support:
            raise StageError(
                "hazard_map found support_count mismatch across telemetry and occupancy",
                stage="hazard_map",
                details={
                    "defect_key": defect_key,
                    "telemetry_support_count": support_count,
                    "occupancy_support_count": occupancy_support,
                },
            )

        observed_by = _required_non_negative_int(occupancy, "observed_by")
        missed_by = _required_non_negative_int(occupancy, "missed_by")
        null_by = _required_non_negative_int(occupancy, "null_by")
        k_eff_defect = _required_non_negative_int(occupancy, "k_eff_defect")
        psi_post = _required_unit_float(occupancy, "psi_post")

        severity_base = severity_weight(severity)
        support_signal = 0.0
        if k_eff_defect > 1:
            support_signal = min(
                max(support_count - 1, 0) / float(max(k_eff_defect - 1, 1)), 1.0
            )

        occupancy_uplift = (
            severity_base * float(params["hazard_occupancy_strength"]) * psi_post
        )
        structural_uplift = (
            severity_base
            * float(params["hazard_structural_risk_strength"])
            * local_risk_score
        )
        support_uplift = (
            severity_base
            * float(params["hazard_support_uplift_strength"])
            * support_signal
        )
        hazard_contribution = clamp_unit(
            severity_base + occupancy_uplift + structural_uplift + support_uplift
        )

        hazard_flags = _build_hazard_flags(
            severity=severity,
            local_risk_score=local_risk_score,
            psi_post=psi_post,
            null_by=null_by,
            k_eff_defect=k_eff_defect,
            support_count=support_count,
        )

        built_rows.append(
            {
                "defect_key": defect_key,
                "file_path": file_path,
                "category": category,
                "severity": severity,
                "reported_by": reported_by,
                "support_count": support_count,
                "observed_by": observed_by,
                "missed_by": missed_by,
                "null_by": null_by,
                "k_eff_defect": k_eff_defect,
                "psi_post": round_float(psi_post, round_digits),
                "local_risk_score": round_float(local_risk_score, round_digits),
                "severity_weight": round_float(severity_base, round_digits),
                "occupancy_uplift": round_float(occupancy_uplift, round_digits),
                "structural_risk_uplift": round_float(structural_uplift, round_digits),
                "support_uplift": round_float(support_uplift, round_digits),
                "hazard_contribution": round_float(hazard_contribution, round_digits),
                "hazard_flags": hazard_flags,
            }
        )

    return built_rows


def _map_risk_targets(targets: list[Any]) -> dict[str, float]:
    mapped: dict[str, float] = {}
    for item in targets:
        if not isinstance(item, dict):
            raise StageError(
                "risk target entry must be an object",
                stage="hazard_map",
                details={"type": str(type(item))},
            )
        file_path = _required_str(item, "file_path")
        if file_path in mapped:
            raise StageError(
                "duplicate file_path in risk targets",
                stage="hazard_map",
                details={"file_path": file_path},
            )
        mapped[file_path] = _required_unit_float(item, "risk_score")
    return mapped


def _map_by_defect_key(items: list[Any], *, section: str) -> dict[str, dict[str, Any]]:
    mapped: dict[str, dict[str, Any]] = {}
    for item in items:
        if not isinstance(item, dict):
            raise StageError(
                "artifact section entry must be an object",
                stage="hazard_map",
                details={"section": section, "type": str(type(item))},
            )
        defect_key = _required_str(item, "defect_key")
        if defect_key in mapped:
            raise StageError(
                "duplicate defect_key in hazard input section",
                stage="hazard_map",
                details={"section": section, "defect_key": defect_key},
            )
        mapped[defect_key] = item
    return mapped


def _build_hazard_flags(
    *,
    severity: str,
    local_risk_score: float,
    psi_post: float,
    null_by: int,
    k_eff_defect: int,
    support_count: int,
) -> list[str]:
    flags: list[str] = []
    if severity == "critical":
        flags.append("critical_severity")
    elif severity == "high":
        flags.append("high_severity")
    if local_risk_score >= ROW_HIGH_RISK_THRESHOLD:
        flags.append("high_structural_risk")
    if psi_post >= ROW_HIGH_OCCUPANCY_THRESHOLD:
        flags.append("high_residual_occupancy")
    if null_by > 0:
        flags.append("null_uncertainty")
    if k_eff_defect < 2:
        flags.append("low_effective_coverage")
    if support_count >= 2:
        flags.append("cross_reviewer_support")
    return flags


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


def _required_str(obj: dict[str, Any], key: str) -> str:
    value = obj.get(key)
    if not isinstance(value, str) or not value.strip():
        raise StageError(
            "hazard input is missing required string field",
            stage="hazard_map",
            details={"field": key, "value": value},
        )
    return value.strip()


def _required_string_list(obj: dict[str, Any], key: str) -> list[str]:
    value = obj.get(key)
    if (
        not isinstance(value, list)
        or not value
        or not all(isinstance(item, str) and item for item in value)
    ):
        raise StageError(
            "hazard input requires non-empty list of strings",
            stage="hazard_map",
            details={"field": key, "value": value},
        )
    return list(value)


def _required_non_negative_int(obj: dict[str, Any], key: str) -> int:
    value = obj.get(key)
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise StageError(
            "hazard input requires non-negative integer field",
            stage="hazard_map",
            details={"field": key, "value": value},
        )
    return value


def _required_unit_float(obj: dict[str, Any], key: str) -> float:
    value = obj.get(key)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise StageError(
            "hazard input requires numeric field",
            stage="hazard_map",
            details={"field": key, "value": value},
        )
    number = float(value)
    if number < 0.0 or number > 1.0:
        raise StageError(
            "hazard input numeric field must be in [0, 1]",
            stage="hazard_map",
            details={"field": key, "value": number},
        )
    return number


def _cross_check_optional_str(
    *,
    defect: dict[str, Any],
    occupancy: dict[str, Any],
    key: str,
    defect_key: str,
) -> None:
    defect_value = defect.get(key)
    occupancy_value = occupancy.get(key)
    if defect_value is None or occupancy_value is None:
        return
    if str(defect_value) != str(occupancy_value):
        raise StageError(
            "hazard_map found inconsistent defect metadata across telemetry and occupancy",
            stage="hazard_map",
            details={
                "defect_key": defect_key,
                "field": key,
                "telemetry_value": defect_value,
                "occupancy_value": occupancy_value,
            },
        )
