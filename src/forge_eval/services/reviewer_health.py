from __future__ import annotations

from typing import Any

from forge_eval.errors import StageError

_ALLOWED_STATUS = {"ok", "failed", "skipped"}


def build_reviewer_health(
    *,
    reviewers_from_findings: list[dict[str, Any]],
    config_reviewers: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    config_by_id: dict[str, dict[str, Any]] = {}
    for reviewer in config_reviewers:
        reviewer_id = _required_str(reviewer, "reviewer_id", stage="telemetry_matrix")
        if reviewer_id in config_by_id:
            raise StageError(
                "duplicate reviewer_id in config during telemetry build",
                stage="telemetry_matrix",
                details={"reviewer_id": reviewer_id},
            )
        config_by_id[reviewer_id] = reviewer

    artifact_by_id: dict[str, dict[str, Any]] = {}
    for reviewer in reviewers_from_findings:
        if not isinstance(reviewer, dict):
            raise StageError(
                "review_findings reviewer entry must be object",
                stage="telemetry_matrix",
                details={"type": str(type(reviewer))},
            )
        reviewer_id = _required_str(reviewer, "reviewer_id", stage="telemetry_matrix")
        if reviewer_id in artifact_by_id:
            raise StageError(
                "duplicate reviewer_id in review_findings",
                stage="telemetry_matrix",
                details={"reviewer_id": reviewer_id},
            )

        status = _required_str(reviewer, "status", stage="telemetry_matrix")
        if status not in _ALLOWED_STATUS:
            raise StageError(
                "invalid reviewer status",
                stage="telemetry_matrix",
                details={"reviewer_id": reviewer_id, "status": status},
            )

        kind = _required_str(reviewer, "kind", stage="telemetry_matrix")
        slices_seen = _required_int(
            reviewer, "slices_seen", stage="telemetry_matrix", min_value=0
        )
        findings_emitted = _required_int(
            reviewer,
            "findings_emitted",
            stage="telemetry_matrix",
            min_value=0,
        )
        error = reviewer.get("error")
        if error is not None and not isinstance(error, str):
            raise StageError(
                "reviewer error field must be string or null",
                stage="telemetry_matrix",
                details={"reviewer_id": reviewer_id, "error": error},
            )
        if status == "ok" and error is not None:
            raise StageError(
                "reviewer status ok cannot include error text",
                stage="telemetry_matrix",
                details={"reviewer_id": reviewer_id, "error": error},
            )
        if status == "failed" and (error is None or not error.strip()):
            raise StageError(
                "reviewer status failed must include error text",
                stage="telemetry_matrix",
                details={"reviewer_id": reviewer_id},
            )

        artifact_by_id[reviewer_id] = {
            "reviewer_id": reviewer_id,
            "status": status,
            "kind": kind,
            "slices_seen": slices_seen,
            "findings_emitted": findings_emitted,
            "error": error,
        }

    config_ids = set(config_by_id.keys())
    artifact_ids = set(artifact_by_id.keys())
    if config_ids != artifact_ids:
        raise StageError(
            "review_findings reviewer roster does not match configured reviewers",
            stage="telemetry_matrix",
            details={
                "missing_in_artifact": sorted(config_ids - artifact_ids),
                "extra_in_artifact": sorted(artifact_ids - config_ids),
            },
        )

    entries: list[dict[str, Any]] = []
    for reviewer_id in sorted(config_by_id.keys()):
        config_item = config_by_id[reviewer_id]
        artifact_item = artifact_by_id[reviewer_id]
        if str(config_item.get("kind")) != str(artifact_item["kind"]):
            raise StageError(
                "reviewer kind mismatch between config and review_findings",
                stage="telemetry_matrix",
                details={
                    "reviewer_id": reviewer_id,
                    "config_kind": config_item.get("kind"),
                    "artifact_kind": artifact_item["kind"],
                },
            )

        status = str(artifact_item["status"])
        slices_seen = int(artifact_item["slices_seen"])
        failed = status == "failed"
        skipped = status == "skipped"
        eligible = (not skipped) and slices_seen > 0
        usable = status == "ok" and eligible

        entries.append(
            {
                "reviewer_id": reviewer_id,
                "status": status,
                "kind": str(artifact_item["kind"]),
                "eligible": eligible,
                "usable": usable,
                "failed": failed,
                "skipped": skipped,
                "findings_emitted": int(artifact_item["findings_emitted"]),
                "slices_seen": slices_seen,
                "error": artifact_item["error"],
            }
        )

    summary = {
        "k_configured": len(entries),
        "k_executed": sum(1 for item in entries if item["status"] in {"ok", "failed"}),
        "k_failed": sum(1 for item in entries if item["failed"]),
        "k_skipped": sum(1 for item in entries if item["skipped"]),
        "k_usable": sum(1 for item in entries if item["usable"]),
    }
    return entries, summary


def _required_str(obj: dict[str, Any], key: str, *, stage: str) -> str:
    value = obj.get(key)
    if not isinstance(value, str) or not value.strip():
        raise StageError(
            "missing or invalid string field",
            stage=stage,
            details={"field": key, "value": value},
        )
    return value.strip()


def _required_int(obj: dict[str, Any], key: str, *, stage: str, min_value: int) -> int:
    value = obj.get(key)
    if isinstance(value, bool) or not isinstance(value, int):
        raise StageError(
            "missing or invalid integer field",
            stage=stage,
            details={"field": key, "value": value},
        )
    if value < min_value:
        raise StageError(
            "integer field below minimum",
            stage=stage,
            details={"field": key, "value": value, "min": min_value},
        )
    return value
