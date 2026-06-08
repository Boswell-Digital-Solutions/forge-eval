from __future__ import annotations

from typing import Any

from forge_eval.errors import StageError


def estimate_ice(
    *,
    observed: int,
    incidence_histogram: dict[str, int],
    rare_threshold: int,
    fallback_hidden: float,
    round_digits: int,
) -> dict[str, Any]:
    _validate_inputs(
        observed=observed,
        incidence_histogram=incidence_histogram,
        rare_threshold=rare_threshold,
        fallback_hidden=fallback_hidden,
        round_digits=round_digits,
    )

    histogram = {int(freq): count for freq, count in incidence_histogram.items()}
    rare_histogram = {
        freq: count for freq, count in histogram.items() if freq <= rare_threshold
    }
    frequent_count = sum(
        count for freq, count in histogram.items() if freq > rare_threshold
    )
    rare_count = sum(rare_histogram.values())
    rare_incidence_total = sum(freq * count for freq, count in rare_histogram.items())
    q1 = rare_histogram.get(1, 0)
    q2 = rare_histogram.get(2, 0)

    if rare_count == 0:
        return {
            "observed": observed,
            "hidden": 0.0,
            "total": float(observed),
            "rare_threshold": rare_threshold,
            "sample_coverage": 1.0,
            "formula_variant": "no_rare_rows",
            "guard_applied": True,
            "inputs": {
                "rare_count": 0,
                "frequent_count": frequent_count,
                "q1": 0,
                "q2": 0,
                "gamma_sq": 0.0,
            },
        }

    if rare_incidence_total <= 0:
        raise StageError(
            "ICE rare incidence total must be positive when rare rows exist",
            stage="capture_estimate",
            details={"rare_incidence_total": rare_incidence_total},
        )

    sample_coverage = 1.0 - (q1 / rare_incidence_total)
    if sample_coverage < 0.0:
        sample_coverage = 0.0

    denominator = rare_incidence_total * (rare_incidence_total - 1)
    if sample_coverage <= 0.0 or denominator <= 0:
        hidden = float(fallback_hidden)
        total = observed + hidden
        return {
            "observed": observed,
            "hidden": _round_float(hidden, round_digits),
            "total": _round_float(total, round_digits),
            "rare_threshold": rare_threshold,
            "sample_coverage": _round_float(sample_coverage, round_digits),
            "formula_variant": "fallback_chao1_bias_corrected",
            "guard_applied": True,
            "inputs": {
                "rare_count": rare_count,
                "frequent_count": frequent_count,
                "q1": q1,
                "q2": q2,
                "gamma_sq": 0.0,
            },
        }

    sum_i_i_minus_1_qi = sum(
        freq * (freq - 1) * count for freq, count in rare_histogram.items()
    )
    gamma_sq = (
        (rare_count / sample_coverage) * (sum_i_i_minus_1_qi / denominator)
    ) - 1.0
    if gamma_sq < 0.0:
        gamma_sq = 0.0

    total = (
        frequent_count
        + (rare_count / sample_coverage)
        + ((q1 / sample_coverage) * gamma_sq)
    )
    hidden = max(total - observed, 0.0)
    _validate_number(hidden=hidden, total=total)

    return {
        "observed": observed,
        "hidden": _round_float(hidden, round_digits),
        "total": _round_float(total, round_digits),
        "rare_threshold": rare_threshold,
        "sample_coverage": _round_float(sample_coverage, round_digits),
        "formula_variant": "ice",
        "guard_applied": False,
        "inputs": {
            "rare_count": rare_count,
            "frequent_count": frequent_count,
            "q1": q1,
            "q2": q2,
            "gamma_sq": _round_float(gamma_sq, round_digits),
        },
    }


def _validate_inputs(
    *,
    observed: int,
    incidence_histogram: dict[str, int],
    rare_threshold: int,
    fallback_hidden: float,
    round_digits: int,
) -> None:
    if isinstance(observed, bool) or not isinstance(observed, int) or observed < 0:
        raise StageError(
            "ICE observed count must be a non-negative integer",
            stage="capture_estimate",
            details={"observed": observed},
        )
    if not isinstance(incidence_histogram, dict):
        raise StageError(
            "ICE incidence_histogram must be an object",
            stage="capture_estimate",
            details={"type": str(type(incidence_histogram))},
        )
    for key, value in incidence_histogram.items():
        if not isinstance(key, str) or not key.isdigit():
            raise StageError(
                "ICE histogram keys must be decimal strings",
                stage="capture_estimate",
                details={"key": key},
            )
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            raise StageError(
                "ICE histogram counts must be non-negative integers",
                stage="capture_estimate",
                details={"key": key, "value": value},
            )
    if (
        isinstance(rare_threshold, bool)
        or not isinstance(rare_threshold, int)
        or rare_threshold < 1
    ):
        raise StageError(
            "ICE rare_threshold must be an integer >= 1",
            stage="capture_estimate",
            details={"rare_threshold": rare_threshold},
        )
    if (
        isinstance(fallback_hidden, bool)
        or not isinstance(fallback_hidden, (int, float))
        or fallback_hidden < 0.0
    ):
        raise StageError(
            "ICE fallback_hidden must be a non-negative number",
            stage="capture_estimate",
            details={"fallback_hidden": fallback_hidden},
        )
    if (
        isinstance(round_digits, bool)
        or not isinstance(round_digits, int)
        or round_digits < 0
        or round_digits > 12
    ):
        raise StageError(
            "ICE round_digits must be an integer in [0, 12]",
            stage="capture_estimate",
            details={"round_digits": round_digits},
        )


def _validate_number(*, hidden: float, total: float) -> None:
    for key, value in (("hidden", hidden), ("total", total)):
        if value < 0.0 or value != value or value == float("inf"):
            raise StageError(
                "ICE produced invalid numeric output",
                stage="capture_estimate",
                details={"field": key, "value": value},
            )


def _round_float(value: float, digits: int) -> float:
    return float(round(float(value), digits))
