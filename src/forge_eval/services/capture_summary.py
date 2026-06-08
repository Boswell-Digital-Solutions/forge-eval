from __future__ import annotations

from typing import Any

from forge_eval.errors import StageError


def build_capture_summary(
    *,
    counts: dict[str, Any],
    selection: dict[str, Any],
    chao1: dict[str, Any],
    chao2: dict[str, Any],
    ice: dict[str, Any],
    included_rows: list[dict[str, Any]],
    round_digits: int,
) -> dict[str, Any]:
    if (
        isinstance(round_digits, bool)
        or not isinstance(round_digits, int)
        or round_digits < 0
        or round_digits > 12
    ):
        raise StageError(
            "capture summary round_digits must be an integer in [0, 12]",
            stage="capture_estimate",
            details={"round_digits": round_digits},
        )

    included_count = _required_non_negative_int(counts, "included_rows")
    f1 = _required_non_negative_int(counts, "f1")
    f2 = _required_non_negative_int(counts, "f2")
    global_k_eff = _required_non_negative_int(counts, "k_eff_global")

    ice_counts = counts.get("ice")
    if not isinstance(ice_counts, dict):
        raise StageError(
            "capture counts missing ice section",
            stage="capture_estimate",
            details={"ice": ice_counts},
        )
    sample_coverage = _required_unit_number(ice_counts, "sample_coverage")

    psi_values: list[float] = []
    for row in included_rows:
        psi_post = row.get("psi_post")
        if isinstance(psi_post, bool) or not isinstance(psi_post, (int, float)):
            raise StageError(
                "included capture row has invalid psi_post",
                stage="capture_estimate",
                details={"row": row},
            )
        psi_float = float(psi_post)
        if psi_float < 0.0 or psi_float > 1.0:
            raise StageError(
                "included capture row psi_post is out of range",
                stage="capture_estimate",
                details={"row": row},
            )
        psi_values.append(psi_float)

    mean_psi_post = 0.0 if not psi_values else sum(psi_values) / len(psi_values)
    sparse_data = included_count < 5 or global_k_eff < 2 or f1 > f2
    low_doubleton_support = f2 == 0
    ice_low_coverage = sample_coverage < 0.5
    chao2_guard = (
        any(chao2.get("guard_flags", {}).values()) if chao2.get("available") else False
    )
    estimator_guard_applied = (
        bool(chao1.get("guard_applied"))
        or chao2_guard
        or bool(ice.get("guard_applied"))
    )

    unavailable_estimators = selection.get("unavailable_estimators", [])

    return {
        "observed_defects": included_count,
        "selection_policy": _required_string(selection, "selection_policy"),
        "selected_method": _required_string(selection, "selected_source"),
        "selected_hidden": _required_non_negative_number(selection, "selected_hidden"),
        "selected_total": _required_non_negative_number(selection, "selected_total"),
        "unavailable_estimators": list(unavailable_estimators),
        "sparse_data": sparse_data,
        "low_doubleton_support": low_doubleton_support,
        "ice_low_coverage": ice_low_coverage,
        "estimator_guard_applied": estimator_guard_applied,
        "global_k_eff": global_k_eff,
        "mean_psi_post": _round_float(mean_psi_post, round_digits),
    }


def _required_non_negative_int(obj: dict[str, Any], key: str) -> int:
    value = obj.get(key)
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise StageError(
            "capture summary requires non-negative integer field",
            stage="capture_estimate",
            details={"field": key, "value": value},
        )
    return value


def _required_unit_number(obj: dict[str, Any], key: str) -> float:
    value = obj.get(key)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise StageError(
            "capture summary requires numeric field",
            stage="capture_estimate",
            details={"field": key, "value": value},
        )
    number = float(value)
    if number < 0.0 or number > 1.0:
        raise StageError(
            "capture summary numeric field must be in [0, 1]",
            stage="capture_estimate",
            details={"field": key, "value": number},
        )
    return number


def _required_non_negative_number(obj: dict[str, Any], key: str) -> float:
    value = obj.get(key)
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or float(value) < 0.0
    ):
        raise StageError(
            "capture summary requires non-negative numeric field",
            stage="capture_estimate",
            details={"field": key, "value": value},
        )
    return float(value)


def _required_string(obj: dict[str, Any], key: str) -> str:
    value = obj.get(key)
    if not isinstance(value, str) or not value:
        raise StageError(
            "capture summary requires non-empty string field",
            stage="capture_estimate",
            details={"field": key, "value": value},
        )
    return value


def _round_float(value: float, digits: int) -> float:
    return float(round(float(value), digits))
