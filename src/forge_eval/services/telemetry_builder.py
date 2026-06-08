from __future__ import annotations

from typing import Any

from forge_eval.errors import StageError
from forge_eval.services.applicability import reviewer_applicable_to_defect
from forge_eval.services.k_eff import k_eff_for_row


def build_defect_catalog(
    *,
    findings: list[dict[str, Any]],
    known_reviewer_ids: set[str],
) -> list[dict[str, Any]]:
    defects_by_key: dict[str, dict[str, Any]] = {}

    for finding in findings:
        if not isinstance(finding, dict):
            raise StageError(
                "review finding must be object",
                stage="telemetry_matrix",
                details={"type": str(type(finding))},
            )

        defect_key = _required_str(finding, "defect_key")
        reviewer_id = _required_str(finding, "reviewer_id")
        if reviewer_id not in known_reviewer_ids:
            raise StageError(
                "finding references unknown reviewer_id",
                stage="telemetry_matrix",
                details={"defect_key": defect_key, "reviewer_id": reviewer_id},
            )

        file_path = _required_str(finding, "file_path")
        category = _required_str(finding, "category")
        severity = _required_str(finding, "severity")

        existing = defects_by_key.get(defect_key)
        if existing is None:
            defects_by_key[defect_key] = {
                "defect_key": defect_key,
                "file_path": file_path,
                "category": category,
                "severity": severity,
                "reported_by": [reviewer_id],
                "support_count": 1,
            }
            continue

        _validate_defect_compatibility(
            defect_key=defect_key,
            existing=existing,
            file_path=file_path,
            category=category,
            severity=severity,
        )

        reported_by = set(existing.get("reported_by", []))
        if reviewer_id in reported_by:
            raise StageError(
                "duplicate defect_key for same reviewer in review findings",
                stage="telemetry_matrix",
                details={"defect_key": defect_key, "reviewer_id": reviewer_id},
            )

        reported_by.add(reviewer_id)
        existing["reported_by"] = sorted(reported_by)
        existing["support_count"] = len(reported_by)

    defects = sorted(defects_by_key.values(), key=lambda item: str(item["defect_key"]))
    return defects


def build_matrix_rows(
    *,
    defects: list[dict[str, Any]],
    reviewers: list[dict[str, Any]],
    reviewer_config_by_id: dict[str, dict[str, Any]],
    applicability_mode: str,
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    rows: list[dict[str, Any]] = []
    cells_observed = 0
    cells_missed = 0
    cells_null = 0

    reviewer_ids = [str(item["reviewer_id"]) for item in reviewers]
    reviewer_id_set = set(reviewer_ids)

    for defect in defects:
        defect_key = str(defect["defect_key"])
        reported_by = set(defect.get("reported_by", []))
        if not reported_by:
            raise StageError(
                "defect reported_by cannot be empty",
                stage="telemetry_matrix",
                details={"defect_key": defect_key},
            )
        unknown_reporters = sorted(reported_by - reviewer_id_set)
        if unknown_reporters:
            raise StageError(
                "defect references reviewers not present in reviewer roster",
                stage="telemetry_matrix",
                details={
                    "defect_key": defect_key,
                    "unknown_reporters": unknown_reporters,
                },
            )

        support_count = defect.get("support_count")
        if not isinstance(support_count, int) or support_count < 1:
            raise StageError(
                "defect support_count must be positive integer",
                stage="telemetry_matrix",
                details={"defect_key": defect_key, "support_count": support_count},
            )
        if support_count != len(reported_by):
            raise StageError(
                "defect support_count does not match reported_by cardinality",
                stage="telemetry_matrix",
                details={
                    "defect_key": defect_key,
                    "support_count": support_count,
                    "reported_by_count": len(reported_by),
                },
            )

        observations: dict[str, int | None] = {}
        for reviewer in reviewers:
            reviewer_id = str(reviewer["reviewer_id"])
            reviewer_config = reviewer_config_by_id.get(reviewer_id)
            if reviewer_config is None:
                raise StageError(
                    "cannot determine reviewer applicability due to missing config mapping",
                    stage="telemetry_matrix",
                    details={"reviewer_id": reviewer_id},
                )

            if not bool(reviewer["usable"]):
                cell: int | None = None
            else:
                applicable = reviewer_applicable_to_defect(
                    reviewer=reviewer,
                    reviewer_config=reviewer_config,
                    defect=defect,
                    applicability_mode=applicability_mode,
                )
                if not applicable:
                    cell = None
                else:
                    cell = 1 if reviewer_id in reported_by else 0

            _validate_cell_value(
                cell=cell, reviewer_id=reviewer_id, defect_key=defect_key
            )
            observations[reviewer_id] = cell
            if cell is None:
                cells_null += 1
            elif cell == 1:
                cells_observed += 1
            elif cell == 0:
                cells_missed += 1

        rows.append(
            {
                "defect_key": defect_key,
                "observations": observations,
                "k_eff_defect": k_eff_for_row(observations),
            }
        )

    rows.sort(key=lambda row: str(row["defect_key"]))
    return rows, {
        "cells_observed": cells_observed,
        "cells_missed": cells_missed,
        "cells_null": cells_null,
    }


def _required_str(obj: dict[str, Any], key: str) -> str:
    value = obj.get(key)
    if not isinstance(value, str) or not value.strip():
        raise StageError(
            "missing required finding field",
            stage="telemetry_matrix",
            details={"field": key, "value": value},
        )
    return value.strip()


def _validate_defect_compatibility(
    *,
    defect_key: str,
    existing: dict[str, Any],
    file_path: str,
    category: str,
    severity: str,
) -> None:
    mismatches: dict[str, dict[str, str]] = {}

    existing_file_path = str(existing.get("file_path", "")).strip()
    existing_category = str(existing.get("category", "")).strip()
    existing_severity = str(existing.get("severity", "")).strip()

    if existing_file_path != file_path:
        mismatches["file_path"] = {
            "existing": existing_file_path,
            "incoming": file_path,
        }
    if existing_category != category:
        mismatches["category"] = {"existing": existing_category, "incoming": category}
    if existing_severity != severity:
        mismatches["severity"] = {"existing": existing_severity, "incoming": severity}

    if mismatches:
        raise StageError(
            "incompatible duplicate defect_key in review findings",
            stage="telemetry_matrix",
            details={"defect_key": defect_key, "mismatches": mismatches},
        )


def _validate_cell_value(
    *, cell: int | None, reviewer_id: str, defect_key: str
) -> None:
    if cell in {0, 1, None}:
        return
    raise StageError(
        "illegal telemetry matrix cell value",
        stage="telemetry_matrix",
        details={"defect_key": defect_key, "reviewer_id": reviewer_id, "cell": cell},
    )
