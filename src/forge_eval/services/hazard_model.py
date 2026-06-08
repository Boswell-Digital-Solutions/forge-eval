from __future__ import annotations

from typing import Any

from forge_eval.errors import StageError

HAZARD_MODEL_VERSION = "hazard_rev1"
SEVERITY_BASE_WEIGHTS = {
    "low": 0.08,
    "medium": 0.18,
    "high": 0.35,
    "critical": 0.55,
}
TIER_FLOORS = {
    "low": 0.0,
    "guarded": 0.20,
    "elevated": 0.40,
    "high": 0.60,
    "critical": 0.80,
}


def load_hazard_model(config: dict[str, Any]) -> dict[str, Any]:
    model_version = str(config.get("hazard_model_version", ""))
    if model_version != HAZARD_MODEL_VERSION:
        raise StageError(
            "unsupported hazard model version",
            stage="hazard_map",
            details={"hazard_model_version": model_version},
        )

    round_digits = _required_int_in_range(
        config, "hazard_round_digits", minimum=0, maximum=12
    )
    hidden_strength = _required_unit_float(config, "hazard_hidden_uplift_strength")
    structural_strength = _required_unit_float(
        config, "hazard_structural_risk_strength"
    )
    occupancy_strength = _required_unit_float(config, "hazard_occupancy_strength")
    support_strength = _required_unit_float(config, "hazard_support_uplift_strength")
    uncertainty_boost = _required_unit_float(config, "hazard_uncertainty_boost")
    blocking_threshold = _required_unit_float(config, "hazard_blocking_threshold")

    return {
        "name": model_version,
        "mode": "deterministic_conservative",
        "row_policy": "severity_plus_uplifts_v1",
        "summary_policy": "bounded_union_hidden_uncertainty_v1",
        "parameters": {
            "hazard_round_digits": round_digits,
            "hazard_hidden_uplift_strength": hidden_strength,
            "hazard_structural_risk_strength": structural_strength,
            "hazard_occupancy_strength": occupancy_strength,
            "hazard_support_uplift_strength": support_strength,
            "hazard_uncertainty_boost": uncertainty_boost,
            "hazard_blocking_threshold": blocking_threshold,
            "severity_weights": dict(SEVERITY_BASE_WEIGHTS),
        },
        "thresholds": {
            "tier_floors": dict(TIER_FLOORS),
        },
    }


def severity_weight(severity: str) -> float:
    if severity not in SEVERITY_BASE_WEIGHTS:
        raise StageError(
            "unsupported severity for hazard calculation",
            stage="hazard_map",
            details={"severity": severity},
        )
    return float(SEVERITY_BASE_WEIGHTS[severity])


def map_hazard_tier(score: float) -> str:
    if score < 0.0 or score > 1.0:
        raise StageError(
            "hazard score must be in [0, 1]",
            stage="hazard_map",
            details={"hazard_score": score},
        )
    if score >= TIER_FLOORS["critical"]:
        return "critical"
    if score >= TIER_FLOORS["high"]:
        return "high"
    if score >= TIER_FLOORS["elevated"]:
        return "elevated"
    if score >= TIER_FLOORS["guarded"]:
        return "guarded"
    return "low"


def clamp_unit(value: float) -> float:
    return min(1.0, max(0.0, float(value)))


def round_float(value: float, digits: int) -> float:
    return float(round(float(value), digits))


def _required_unit_float(config: dict[str, Any], key: str) -> float:
    value = config.get(key)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise StageError(
            "hazard config value must be numeric",
            stage="hazard_map",
            details={"key": key, "value": value},
        )
    number = float(value)
    if number < 0.0 or number > 1.0:
        raise StageError(
            "hazard config value must be in [0, 1]",
            stage="hazard_map",
            details={"key": key, "value": number},
        )
    return number


def _required_int_in_range(
    config: dict[str, Any], key: str, *, minimum: int, maximum: int
) -> int:
    value = config.get(key)
    if isinstance(value, bool) or not isinstance(value, int):
        raise StageError(
            "hazard config value must be an integer",
            stage="hazard_map",
            details={"key": key, "value": value},
        )
    if value < minimum or value > maximum:
        raise StageError(
            "hazard config integer is out of allowed range",
            stage="hazard_map",
            details={
                "key": key,
                "value": value,
                "minimum": minimum,
                "maximum": maximum,
            },
        )
    return value
