from __future__ import annotations

from pathlib import Path
from typing import Any

from forge_eval.errors import StageError
from forge_eval.services.k_eff import compute_global_k_eff
from forge_eval.services.reviewer_health import build_reviewer_health
from forge_eval.services.telemetry_builder import (
    build_defect_catalog,
    build_matrix_rows,
)


def run_stage(
    *,
    repo_path: str | Path,
    base_ref: str,
    head_ref: str,
    run_id: str,
    config: dict[str, Any],
    review_findings_artifact: dict[str, Any],
) -> dict[str, Any]:
    _validate_review_findings_artifact(review_findings_artifact)

    run = review_findings_artifact["run"]
    if str(run["run_id"]) != str(run_id):
        raise StageError(
            "run_id mismatch between pipeline and review_findings artifact",
            stage="telemetry_matrix",
            details={
                "pipeline_run_id": run_id,
                "artifact_run_id": run["run_id"],
            },
        )

    reviewers_from_findings = review_findings_artifact["reviewers"]
    findings = review_findings_artifact["findings"]

    config_reviewers = list(config["reviewers"])
    reviewer_entries, reviewer_counts = build_reviewer_health(
        reviewers_from_findings=reviewers_from_findings,
        config_reviewers=config_reviewers,
    )

    reviewer_ids = {str(item["reviewer_id"]) for item in reviewer_entries}
    defects = build_defect_catalog(findings=findings, known_reviewer_ids=reviewer_ids)

    reviewer_config_by_id = {
        str(item["reviewer_id"]): dict(item) for item in config_reviewers
    }
    applicability_mode = str(config["telemetry_applicability_mode"])
    rows, cell_counts = build_matrix_rows(
        defects=defects,
        reviewers=reviewer_entries,
        reviewer_config_by_id=reviewer_config_by_id,
        applicability_mode=applicability_mode,
    )

    k_eff_mode = str(config["telemetry_k_eff_mode"])
    k_eff = compute_global_k_eff(rows=rows, mode=k_eff_mode)

    summary = {
        **reviewer_counts,
        "k_eff": k_eff,
        "defect_count": len(defects),
        "matrix_rows": len(rows),
        "cells_observed": cell_counts["cells_observed"],
        "cells_missed": cell_counts["cells_missed"],
        "cells_null": cell_counts["cells_null"],
    }

    repo = Path(repo_path)
    run_payload = {
        "run_id": run_id,
        "repo_path": str(repo.resolve()),
        "base_ref": base_ref,
        "head_ref": head_ref,
        "base_commit": str(run["base_commit"]),
        "head_commit": str(run["head_commit"]),
        "review_findings_artifact": "review_findings.json",
    }

    return {
        "artifact_version": 1,
        "kind": "telemetry_matrix",
        "run": run_payload,
        "reviewers": reviewer_entries,
        "defects": defects,
        "matrix": rows,
        "summary": summary,
        "provenance": {
            "algorithm": "telemetry_matrix_v1",
            "deterministic": True,
            "inputs": ["review_findings.json"],
            "applicability_mode": applicability_mode,
            "k_eff_mode": k_eff_mode,
        },
    }


def _validate_review_findings_artifact(artifact: dict[str, Any]) -> None:
    if artifact.get("kind") != "review_findings":
        raise StageError(
            "telemetry_matrix requires review_findings artifact",
            stage="telemetry_matrix",
            details={"kind": artifact.get("kind")},
        )

    run = artifact.get("run")
    if not isinstance(run, dict):
        raise StageError(
            "review_findings artifact missing run object",
            stage="telemetry_matrix",
        )

    required_run_fields = {"run_id", "base_commit", "head_commit"}
    missing = sorted(field for field in required_run_fields if field not in run)
    if missing:
        raise StageError(
            "review_findings artifact run object missing required fields",
            stage="telemetry_matrix",
            details={"missing_fields": missing},
        )

    reviewers = artifact.get("reviewers")
    if not isinstance(reviewers, list):
        raise StageError(
            "review_findings artifact has invalid reviewers field",
            stage="telemetry_matrix",
            details={"type": str(type(reviewers))},
        )

    findings = artifact.get("findings")
    if not isinstance(findings, list):
        raise StageError(
            "review_findings artifact has invalid findings field",
            stage="telemetry_matrix",
            details={"type": str(type(findings))},
        )
