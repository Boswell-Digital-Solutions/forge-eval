from __future__ import annotations

from typing import Any

from forge_eval.errors import StageError


def compute_posterior(
    *,
    prior: float,
    observed_by: int,
    missed_by: int,
    null_by: int,
    k_eff_defect: int,
    reviewer_count: int,
    config: dict[str, Any],
) -> tuple[float, dict[str, float]]:
    _validate_counts(
        observed_by=observed_by,
        missed_by=missed_by,
        null_by=null_by,
        k_eff_defect=k_eff_defect,
        reviewer_count=reviewer_count,
    )

    detection_assumption = _required_unit_float(
        config, "occupancy_detection_assumption"
    )
    miss_penalty_strength = _required_unit_float(
        config, "occupancy_miss_penalty_strength"
    )
    null_uncertainty_boost = _required_unit_float(
        config, "occupancy_null_uncertainty_boost"
    )

    coverage_ratio = k_eff_defect / reviewer_count
    miss_ratio_usable = (missed_by / k_eff_defect) if k_eff_defect > 0 else 0.0
    null_ratio = null_by / reviewer_count

    observed_retention = 1.0 - ((1.0 - detection_assumption) ** observed_by)
    psi_after_observation = prior + ((1.0 - prior) * observed_retention)

    miss_penalty = miss_penalty_strength * miss_ratio_usable * coverage_ratio
    uncertainty_guard = null_uncertainty_boost * null_ratio * (1.0 - coverage_ratio)

    psi_post = _clamp(
        psi_after_observation - miss_penalty + uncertainty_guard, 0.02, 0.995
    )
    if psi_post < 0.0 or psi_post > 1.0:
        raise StageError(
            "psi_post is out of range after occupancy computation",
            stage="occupancy_snapshot",
            details={"psi_post": psi_post},
        )

    return psi_post, {
        "prior": prior,
        "detection_assumption": detection_assumption,
        "observed_retention": observed_retention,
        "coverage_ratio": coverage_ratio,
        "miss_ratio_usable": miss_ratio_usable,
        "miss_penalty": miss_penalty,
        "null_ratio": null_ratio,
        "uncertainty_guard": uncertainty_guard,
    }


def _validate_counts(
    *,
    observed_by: int,
    missed_by: int,
    null_by: int,
    k_eff_defect: int,
    reviewer_count: int,
) -> None:
    for key, value in (
        ("observed_by", observed_by),
        ("missed_by", missed_by),
        ("null_by", null_by),
        ("k_eff_defect", k_eff_defect),
        ("reviewer_count", reviewer_count),
    ):
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            raise StageError(
                "occupancy counts must be non-negative integers",
                stage="occupancy_snapshot",
                details={"field": key, "value": value},
            )

    total = observed_by + missed_by + null_by
    if total != reviewer_count:
        raise StageError(
            "observation counts do not match reviewer count",
            stage="occupancy_snapshot",
            details={
                "observed_by": observed_by,
                "missed_by": missed_by,
                "null_by": null_by,
                "reviewer_count": reviewer_count,
            },
        )

    if observed_by + missed_by != k_eff_defect:
        raise StageError(
            "k_eff_defect must equal observed_by + missed_by",
            stage="occupancy_snapshot",
            details={
                "observed_by": observed_by,
                "missed_by": missed_by,
                "k_eff_defect": k_eff_defect,
            },
        )

    if reviewer_count == 0:
        raise StageError(
            "telemetry reviewer roster cannot be empty",
            stage="occupancy_snapshot",
        )


def _required_unit_float(config: dict[str, Any], key: str) -> float:
    value = config.get(key)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise StageError(
            "occupancy config value must be numeric",
            stage="occupancy_snapshot",
            details={"key": key, "value": value},
        )
    number = float(value)
    if number < 0.0 or number > 1.0:
        raise StageError(
            "occupancy config value must be in [0,1]",
            stage="occupancy_snapshot",
            details={"key": key, "value": number},
        )
    return number


def _clamp(value: float, low: float, high: float) -> float:
    return min(high, max(low, value))
