from __future__ import annotations

from typing import Any

from forge_eval.errors import StageError
from forge_eval.services.occupancy_model import compute_posterior
from forge_eval.services.occupancy_priors import derive_prior


def build_rows(
    *, telemetry_artifact: dict[str, Any], config: dict[str, Any]
) -> list[dict[str, Any]]:
    reviewers = telemetry_artifact.get("reviewers")
    defects = telemetry_artifact.get("defects")
    matrix = telemetry_artifact.get("matrix")

    if (
        not isinstance(reviewers, list)
        or not isinstance(defects, list)
        or not isinstance(matrix, list)
    ):
        raise StageError(
            "telemetry artifact missing required list sections",
            stage="occupancy_snapshot",
            details={
                "reviewers_type": str(type(reviewers)),
                "defects_type": str(type(defects)),
                "matrix_type": str(type(matrix)),
            },
        )

    reviewer_ids: list[str] = []
    seen_reviewer_ids: set[str] = set()
    for reviewer in reviewers:
        if not isinstance(reviewer, dict):
            raise StageError(
                "telemetry reviewer entry must be an object",
                stage="occupancy_snapshot",
                details={"type": str(type(reviewer))},
            )
        reviewer_id = _required_str(reviewer, "reviewer_id")
        if reviewer_id in seen_reviewer_ids:
            raise StageError(
                "duplicate reviewer_id in telemetry reviewers",
                stage="occupancy_snapshot",
                details={"reviewer_id": reviewer_id},
            )
        seen_reviewer_ids.add(reviewer_id)
        reviewer_ids.append(reviewer_id)

    defect_by_key: dict[str, dict[str, Any]] = {}
    for defect in defects:
        if not isinstance(defect, dict):
            raise StageError(
                "telemetry defect entry must be an object",
                stage="occupancy_snapshot",
                details={"type": str(type(defect))},
            )
        defect_key = _required_str(defect, "defect_key")
        if defect_key in defect_by_key:
            raise StageError(
                "duplicate defect_key in telemetry defects",
                stage="occupancy_snapshot",
                details={"defect_key": defect_key},
            )
        defect_by_key[defect_key] = defect

    matrix_by_key: dict[str, dict[str, Any]] = {}
    for row in matrix:
        if not isinstance(row, dict):
            raise StageError(
                "telemetry matrix row must be an object",
                stage="occupancy_snapshot",
                details={"type": str(type(row))},
            )
        defect_key = _required_str(row, "defect_key")
        if defect_key in matrix_by_key:
            raise StageError(
                "duplicate defect_key in telemetry matrix",
                stage="occupancy_snapshot",
                details={"defect_key": defect_key},
            )
        matrix_by_key[defect_key] = row

    defect_keys = set(defect_by_key.keys())
    matrix_keys = set(matrix_by_key.keys())
    if defect_keys != matrix_keys:
        raise StageError(
            "telemetry defects and matrix rows reference different defect keys",
            stage="occupancy_snapshot",
            details={
                "missing_matrix_rows": sorted(defect_keys - matrix_keys),
                "extra_matrix_rows": sorted(matrix_keys - defect_keys),
            },
        )

    round_digits = _required_round_digits(config)
    reviewer_id_set = set(reviewer_ids)
    reviewer_count = len(reviewer_ids)
    rows: list[dict[str, Any]] = []

    for defect_key in sorted(defect_keys):
        defect = defect_by_key[defect_key]
        row = matrix_by_key[defect_key]

        observations = row.get("observations")
        if not isinstance(observations, dict):
            raise StageError(
                "telemetry matrix observations must be an object",
                stage="occupancy_snapshot",
                details={"defect_key": defect_key, "type": str(type(observations))},
            )

        unknown_reviewers = sorted(set(observations.keys()) - reviewer_id_set)
        missing_reviewers = sorted(reviewer_id_set - set(observations.keys()))
        if unknown_reviewers or missing_reviewers:
            raise StageError(
                "telemetry matrix observations do not match reviewer roster",
                stage="occupancy_snapshot",
                details={
                    "defect_key": defect_key,
                    "unknown_reviewers": unknown_reviewers,
                    "missing_reviewers": missing_reviewers,
                },
            )

        observed_by = 0
        missed_by = 0
        null_by = 0
        for reviewer_id in reviewer_ids:
            cell = observations[reviewer_id]
            if cell == 1:
                observed_by += 1
            elif cell == 0:
                missed_by += 1
            elif cell is None:
                null_by += 1
            else:
                raise StageError(
                    "illegal telemetry matrix cell value",
                    stage="occupancy_snapshot",
                    details={
                        "defect_key": defect_key,
                        "reviewer_id": reviewer_id,
                        "cell": cell,
                    },
                )

        k_eff_defect = _required_non_negative_int(row, "k_eff_defect")
        support_count = _required_non_negative_int(defect, "support_count")
        severity = str(defect.get("severity", "medium"))

        prior = derive_prior(
            support_count=support_count, severity=severity, config=config
        )
        psi_post, terms = compute_posterior(
            prior=prior,
            observed_by=observed_by,
            missed_by=missed_by,
            null_by=null_by,
            k_eff_defect=k_eff_defect,
            reviewer_count=reviewer_count,
            config=config,
        )

        out_row: dict[str, Any] = {
            "defect_key": defect_key,
            "psi_post": _round_float(psi_post, round_digits),
            "observed_by": observed_by,
            "missed_by": missed_by,
            "null_by": null_by,
            "k_eff_defect": k_eff_defect,
            "support_count": support_count,
            "evidence_strength": _strength_band(psi_post),
            "inputs": {
                "prior": _round_float(terms["prior"], round_digits),
                "detection_assumption": _round_float(
                    terms["detection_assumption"], round_digits
                ),
                "coverage_ratio": _round_float(terms["coverage_ratio"], round_digits),
                "miss_penalty": _round_float(terms["miss_penalty"], round_digits),
                "uncertainty_guard": _round_float(
                    terms["uncertainty_guard"], round_digits
                ),
            },
        }

        for key in ("file_path", "category", "severity"):
            value = defect.get(key)
            if isinstance(value, str) and value:
                out_row[key] = value

        rows.append(out_row)

    return rows


def _required_str(obj: dict[str, Any], key: str) -> str:
    value = obj.get(key)
    if not isinstance(value, str) or not value.strip():
        raise StageError(
            "missing required string field",
            stage="occupancy_snapshot",
            details={"field": key, "value": value},
        )
    return value.strip()


def _required_non_negative_int(obj: dict[str, Any], key: str) -> int:
    value = obj.get(key)
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise StageError(
            "missing required non-negative integer field",
            stage="occupancy_snapshot",
            details={"field": key, "value": value},
        )
    return value


def _required_round_digits(config: dict[str, Any]) -> int:
    value = config.get("occupancy_round_digits")
    if isinstance(value, bool) or not isinstance(value, int):
        raise StageError(
            "occupancy_round_digits must be an integer",
            stage="occupancy_snapshot",
            details={"value": value},
        )
    if value < 0 or value > 12:
        raise StageError(
            "occupancy_round_digits must be in [0, 12]",
            stage="occupancy_snapshot",
            details={"value": value},
        )
    return value


def _round_float(value: float, digits: int) -> float:
    return float(round(float(value), digits))


def _strength_band(psi_post: float) -> str:
    if psi_post >= 0.80:
        return "strong"
    if psi_post >= 0.60:
        return "moderate"
    return "weak"
