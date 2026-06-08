from __future__ import annotations

from typing import Any

from forge_eval.errors import StageError

SEVERITY_UPLIFT = {
    "low": 0.00,
    "medium": 0.05,
    "high": 0.10,
    "critical": 0.15,
}


def derive_prior(
    *,
    support_count: int,
    severity: str,
    config: dict[str, Any],
) -> float:
    if (
        isinstance(support_count, bool)
        or not isinstance(support_count, int)
        or support_count < 0
    ):
        raise StageError(
            "support_count must be a non-negative integer",
            stage="occupancy_snapshot",
            details={"support_count": support_count},
        )

    if severity not in SEVERITY_UPLIFT:
        raise StageError(
            "unsupported severity for occupancy prior derivation",
            stage="occupancy_snapshot",
            details={"severity": severity},
        )

    prior_base = _required_unit_float(config, "occupancy_prior_base")
    support_uplift = _required_unit_float(config, "occupancy_support_uplift")

    prior = (
        prior_base
        + (support_uplift if support_count > 0 else 0.0)
        + SEVERITY_UPLIFT[severity]
    )
    return _clamp(prior, 0.01, 0.99)


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
