from __future__ import annotations

from typing import Any

from forge_eval.errors import StageError


def build_capture_counts(
    *,
    telemetry_matrix_artifact: dict[str, Any],
    occupancy_snapshot_artifact: dict[str, Any],
    config: dict[str, Any],
) -> dict[str, Any]:
    inclusion_policy = str(config.get("capture_inclusion_policy", ""))
    if inclusion_policy != "include_all":
        raise StageError(
            "unsupported capture inclusion policy",
            stage="capture_estimate",
            details={"capture_inclusion_policy": inclusion_policy},
        )

    round_digits = _required_round_digits(config)
    rare_threshold = _required_positive_int(config, "ice_rare_threshold")

    telemetry_defects = telemetry_matrix_artifact.get("defects")
    telemetry_matrix = telemetry_matrix_artifact.get("matrix")
    telemetry_summary = telemetry_matrix_artifact.get("summary")
    occupancy_rows = occupancy_snapshot_artifact.get("rows")

    if (
        not isinstance(telemetry_defects, list)
        or not isinstance(telemetry_matrix, list)
        or not isinstance(telemetry_summary, dict)
        or not isinstance(occupancy_rows, list)
    ):
        raise StageError(
            "capture_estimate inputs are missing required list/object sections",
            stage="capture_estimate",
            details={
                "telemetry_defects_type": str(type(telemetry_defects)),
                "telemetry_matrix_type": str(type(telemetry_matrix)),
                "telemetry_summary_type": str(type(telemetry_summary)),
                "occupancy_rows_type": str(type(occupancy_rows)),
            },
        )

    defects_by_key = _map_by_defect_key(telemetry_defects, section="telemetry_defects")
    matrix_by_key = _map_by_defect_key(telemetry_matrix, section="telemetry_matrix")
    occupancy_by_key = _map_by_defect_key(occupancy_rows, section="occupancy_rows")

    defect_keys = set(defects_by_key.keys())
    matrix_keys = set(matrix_by_key.keys())
    occupancy_keys = set(occupancy_by_key.keys())
    if defect_keys != matrix_keys or defect_keys != occupancy_keys:
        raise StageError(
            "telemetry and occupancy defect sets are inconsistent",
            stage="capture_estimate",
            details={
                "missing_in_matrix": sorted(defect_keys - matrix_keys),
                "extra_in_matrix": sorted(matrix_keys - defect_keys),
                "missing_in_occupancy": sorted(defect_keys - occupancy_keys),
                "extra_in_occupancy": sorted(occupancy_keys - defect_keys),
            },
        )

    global_k_eff = telemetry_summary.get("k_eff")
    if (
        isinstance(global_k_eff, bool)
        or not isinstance(global_k_eff, int)
        or global_k_eff < 0
    ):
        raise StageError(
            "telemetry summary has invalid global k_eff",
            stage="capture_estimate",
            details={"k_eff": global_k_eff},
        )

    included_rows: list[dict[str, Any]] = []
    incidence_histogram: dict[int, int] = {}

    for defect_key in sorted(defect_keys):
        matrix_row = matrix_by_key[defect_key]
        occupancy_row = occupancy_by_key[defect_key]

        observations = matrix_row.get("observations")
        if not isinstance(observations, dict):
            raise StageError(
                "telemetry observations must be an object",
                stage="capture_estimate",
                details={"defect_key": defect_key, "type": str(type(observations))},
            )

        observed_by, missed_by, null_by = _count_observations(
            observations, defect_key=defect_key
        )
        k_eff_defect = _required_non_negative_int(matrix_row, "k_eff_defect")
        if observed_by + missed_by != k_eff_defect:
            raise StageError(
                "telemetry matrix row has inconsistent k_eff_defect",
                stage="capture_estimate",
                details={
                    "defect_key": defect_key,
                    "observed_by": observed_by,
                    "missed_by": missed_by,
                    "k_eff_defect": k_eff_defect,
                },
            )

        _cross_check_occupancy_row(
            occupancy_row=occupancy_row,
            defect_key=defect_key,
            observed_by=observed_by,
            missed_by=missed_by,
            null_by=null_by,
            k_eff_defect=k_eff_defect,
        )

        if observed_by <= 0:
            raise StageError(
                "included defect row must have at least one positive usable observation",
                stage="capture_estimate",
                details={"defect_key": defect_key},
            )

        psi_post = occupancy_row.get("psi_post")
        if isinstance(psi_post, bool) or not isinstance(psi_post, (int, float)):
            raise StageError(
                "occupancy row has invalid psi_post",
                stage="capture_estimate",
                details={"defect_key": defect_key, "psi_post": psi_post},
            )
        psi_post_float = float(psi_post)
        if psi_post_float < 0.0 or psi_post_float > 1.0:
            raise StageError(
                "occupancy row psi_post is out of range",
                stage="capture_estimate",
                details={"defect_key": defect_key, "psi_post": psi_post_float},
            )

        incidence_histogram[observed_by] = incidence_histogram.get(observed_by, 0) + 1
        included_rows.append(
            {
                "defect_key": defect_key,
                "incidence": observed_by,
                "psi_post": _round_float(psi_post_float, round_digits),
            }
        )

    defect_rows = len(occupancy_rows)
    included_count = len(included_rows)
    excluded_count = defect_rows - included_count
    histogram_payload = {
        str(freq): count for freq, count in sorted(incidence_histogram.items())
    }
    f1 = incidence_histogram.get(1, 0)
    f2 = incidence_histogram.get(2, 0)

    rare_count = sum(
        count for freq, count in incidence_histogram.items() if freq <= rare_threshold
    )
    frequent_count = sum(
        count for freq, count in incidence_histogram.items() if freq > rare_threshold
    )
    rare_incidence_total = sum(
        freq * count
        for freq, count in incidence_histogram.items()
        if freq <= rare_threshold
    )
    q1 = f1
    q2 = f2
    sample_coverage = 1.0
    if rare_count > 0:
        if rare_incidence_total <= 0:
            raise StageError(
                "rare incidence total must be positive when rare rows exist",
                stage="capture_estimate",
                details={"rare_incidence_total": rare_incidence_total},
            )
        sample_coverage = 1.0 - (q1 / rare_incidence_total)
        if sample_coverage < 0.0:
            sample_coverage = 0.0

    counts = {
        "defect_rows": defect_rows,
        "included_rows": included_count,
        "excluded_rows": excluded_count,
        "k_eff_global": int(global_k_eff),
        "f1": f1,
        "f2": f2,
        "incidence_histogram": histogram_payload,
        "ice": {
            "rare_threshold": rare_threshold,
            "rare_count": rare_count,
            "frequent_count": frequent_count,
            "q1": q1,
            "q2": q2,
            "sample_coverage": _round_float(sample_coverage, round_digits),
        },
    }

    return {
        "counts": counts,
        "included_rows": included_rows,
    }


def _map_by_defect_key(items: list[Any], *, section: str) -> dict[str, dict[str, Any]]:
    mapped: dict[str, dict[str, Any]] = {}
    for item in items:
        if not isinstance(item, dict):
            raise StageError(
                "artifact section entry must be an object",
                stage="capture_estimate",
                details={"section": section, "type": str(type(item))},
            )
        defect_key = item.get("defect_key")
        if not isinstance(defect_key, str) or not defect_key:
            raise StageError(
                "artifact section entry is missing defect_key",
                stage="capture_estimate",
                details={"section": section, "entry": item},
            )
        if defect_key in mapped:
            raise StageError(
                "duplicate defect_key in capture input section",
                stage="capture_estimate",
                details={"section": section, "defect_key": defect_key},
            )
        mapped[defect_key] = item
    return mapped


def _count_observations(
    observations: dict[str, Any], *, defect_key: str
) -> tuple[int, int, int]:
    observed_by = 0
    missed_by = 0
    null_by = 0
    for reviewer_id in sorted(observations.keys()):
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
                stage="capture_estimate",
                details={
                    "defect_key": defect_key,
                    "reviewer_id": reviewer_id,
                    "cell": cell,
                },
            )
    return observed_by, missed_by, null_by


def _cross_check_occupancy_row(
    *,
    occupancy_row: dict[str, Any],
    defect_key: str,
    observed_by: int,
    missed_by: int,
    null_by: int,
    k_eff_defect: int,
) -> None:
    for key, expected in (
        ("observed_by", observed_by),
        ("missed_by", missed_by),
        ("null_by", null_by),
        ("k_eff_defect", k_eff_defect),
    ):
        value = occupancy_row.get(key)
        if isinstance(value, bool) or not isinstance(value, int):
            raise StageError(
                "occupancy row is missing integer count field",
                stage="capture_estimate",
                details={"defect_key": defect_key, "field": key, "value": value},
            )
        if value != expected:
            raise StageError(
                "occupancy row counts do not match telemetry row",
                stage="capture_estimate",
                details={
                    "defect_key": defect_key,
                    "field": key,
                    "occupancy_value": value,
                    "telemetry_value": expected,
                },
            )


def _required_non_negative_int(obj: dict[str, Any], key: str) -> int:
    value = obj.get(key)
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise StageError(
            "required integer field is missing or invalid",
            stage="capture_estimate",
            details={"field": key, "value": value},
        )
    return value


def _required_positive_int(config: dict[str, Any], key: str) -> int:
    value = config.get(key)
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise StageError(
            "capture config integer must be >= 1",
            stage="capture_estimate",
            details={"key": key, "value": value},
        )
    return value


def _required_round_digits(config: dict[str, Any]) -> int:
    value = config.get("capture_round_digits")
    if isinstance(value, bool) or not isinstance(value, int) or value < 0 or value > 12:
        raise StageError(
            "capture_round_digits must be an integer in [0, 12]",
            stage="capture_estimate",
            details={"value": value},
        )
    return value


def _round_float(value: float, digits: int) -> float:
    return float(round(float(value), digits))
