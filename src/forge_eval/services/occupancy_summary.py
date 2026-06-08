from __future__ import annotations

from typing import Any

from forge_eval.errors import StageError


def build_summary(
    *, rows: list[dict[str, Any]], global_k_eff: int, round_digits: int
) -> dict[str, Any]:
    if (
        isinstance(global_k_eff, bool)
        or not isinstance(global_k_eff, int)
        or global_k_eff < 0
    ):
        raise StageError(
            "telemetry global k_eff must be a non-negative integer",
            stage="occupancy_snapshot",
            details={"global_k_eff": global_k_eff},
        )
    if (
        isinstance(round_digits, bool)
        or not isinstance(round_digits, int)
        or round_digits < 0
        or round_digits > 12
    ):
        raise StageError(
            "round_digits must be an integer in [0, 12]",
            stage="occupancy_snapshot",
            details={"round_digits": round_digits},
        )

    defect_rows = len(rows)
    if defect_rows == 0:
        return {
            "defect_rows": 0,
            "rows_with_positive_observation": 0,
            "rows_with_nulls": 0,
            "mean_psi_post": 0.0,
            "max_psi_post": 0.0,
            "min_psi_post": 0.0,
            "global_k_eff": global_k_eff,
        }

    psi_values: list[float] = []
    rows_with_positive_observation = 0
    rows_with_nulls = 0

    for row in rows:
        psi = row.get("psi_post")
        observed_by = row.get("observed_by")
        null_by = row.get("null_by")

        if isinstance(psi, bool) or not isinstance(psi, (int, float)):
            raise StageError(
                "occupancy row has invalid psi_post",
                stage="occupancy_snapshot",
                details={"row": row},
            )
        psi_float = float(psi)
        if psi_float < 0.0 or psi_float > 1.0:
            raise StageError(
                "occupancy row psi_post is out of range",
                stage="occupancy_snapshot",
                details={"psi_post": psi_float, "row": row},
            )

        if (
            isinstance(observed_by, bool)
            or not isinstance(observed_by, int)
            or observed_by < 0
        ):
            raise StageError(
                "occupancy row has invalid observed_by",
                stage="occupancy_snapshot",
                details={"row": row},
            )
        if isinstance(null_by, bool) or not isinstance(null_by, int) or null_by < 0:
            raise StageError(
                "occupancy row has invalid null_by",
                stage="occupancy_snapshot",
                details={"row": row},
            )

        psi_values.append(psi_float)
        if observed_by > 0:
            rows_with_positive_observation += 1
        if null_by > 0:
            rows_with_nulls += 1

    mean_psi = sum(psi_values) / defect_rows
    return {
        "defect_rows": defect_rows,
        "rows_with_positive_observation": rows_with_positive_observation,
        "rows_with_nulls": rows_with_nulls,
        "mean_psi_post": _round_float(mean_psi, round_digits),
        "max_psi_post": _round_float(max(psi_values), round_digits),
        "min_psi_post": _round_float(min(psi_values), round_digits),
        "global_k_eff": global_k_eff,
    }


def _round_float(value: float, digits: int) -> float:
    return float(round(float(value), digits))
