from __future__ import annotations

from pathlib import Path
from typing import Any

from forge_eval.errors import StageError
from forge_eval.services.occupancy_priors import SEVERITY_UPLIFT
from forge_eval.services.occupancy_rows import build_rows
from forge_eval.services.occupancy_summary import build_summary


def run_stage(
    *,
    repo_path: str | Path,
    base_ref: str,
    head_ref: str,
    run_id: str,
    config: dict[str, Any],
    telemetry_matrix_artifact: dict[str, Any],
) -> dict[str, Any]:
    _validate_telemetry_artifact(telemetry_matrix_artifact)

    run = telemetry_matrix_artifact["run"]
    if str(run["run_id"]) != str(run_id):
        raise StageError(
            "run_id mismatch between pipeline and telemetry artifact",
            stage="occupancy_snapshot",
            details={
                "pipeline_run_id": run_id,
                "artifact_run_id": run["run_id"],
            },
        )

    model_version = str(config.get("occupancy_model_version", ""))
    if model_version != "occupancy_rev1":
        raise StageError(
            "unsupported occupancy model version",
            stage="occupancy_snapshot",
            details={"model_version": model_version},
        )

    rows = build_rows(telemetry_artifact=telemetry_matrix_artifact, config=config)

    telemetry_summary = telemetry_matrix_artifact["summary"]
    global_k_eff = telemetry_summary.get("k_eff")
    round_digits = config.get("occupancy_round_digits")
    if isinstance(round_digits, bool) or not isinstance(round_digits, int):
        raise StageError(
            "occupancy_round_digits must be an integer",
            stage="occupancy_snapshot",
            details={"occupancy_round_digits": round_digits},
        )

    summary = build_summary(
        rows=rows, global_k_eff=global_k_eff, round_digits=round_digits
    )

    repo = Path(repo_path)
    run_payload = {
        "run_id": run_id,
        "repo_path": str(repo.resolve()),
        "base_ref": base_ref,
        "head_ref": head_ref,
        "base_commit": str(run["base_commit"]),
        "head_commit": str(run["head_commit"]),
        "telemetry_artifact": "telemetry_matrix.json",
    }

    return {
        "artifact_version": 1,
        "kind": "occupancy_snapshot",
        "run": run_payload,
        "rows": rows,
        "summary": summary,
        "model": {
            "name": model_version,
            "mode": "deterministic_conservative",
            "prior_policy": "config_locked_v1",
            "null_policy": "null_is_uncertainty",
            "suppression_policy": "usable_misses_only",
            "parameters": {
                "occupancy_prior_base": config["occupancy_prior_base"],
                "occupancy_support_uplift": config["occupancy_support_uplift"],
                "occupancy_detection_assumption": config[
                    "occupancy_detection_assumption"
                ],
                "occupancy_miss_penalty_strength": config[
                    "occupancy_miss_penalty_strength"
                ],
                "occupancy_null_uncertainty_boost": config[
                    "occupancy_null_uncertainty_boost"
                ],
                "occupancy_round_digits": config["occupancy_round_digits"],
                "severity_uplift": dict(SEVERITY_UPLIFT),
            },
        },
        "provenance": {
            "algorithm": "occupancy_snapshot_v1",
            "deterministic": True,
            "inputs": ["telemetry_matrix.json"],
            "model_version": model_version,
        },
    }


def _validate_telemetry_artifact(artifact: dict[str, Any]) -> None:
    if artifact.get("kind") != "telemetry_matrix":
        raise StageError(
            "occupancy_snapshot requires telemetry_matrix artifact",
            stage="occupancy_snapshot",
            details={"kind": artifact.get("kind")},
        )

    run = artifact.get("run")
    if not isinstance(run, dict):
        raise StageError(
            "telemetry_matrix artifact missing run object",
            stage="occupancy_snapshot",
        )

    required_run_fields = {"run_id", "base_commit", "head_commit"}
    missing = sorted(field for field in required_run_fields if field not in run)
    if missing:
        raise StageError(
            "telemetry_matrix run object missing required fields",
            stage="occupancy_snapshot",
            details={"missing_fields": missing},
        )

    summary = artifact.get("summary")
    if not isinstance(summary, dict):
        raise StageError(
            "telemetry_matrix artifact missing summary object",
            stage="occupancy_snapshot",
        )
    k_eff = summary.get("k_eff")
    if isinstance(k_eff, bool) or not isinstance(k_eff, int) or k_eff < 0:
        raise StageError(
            "telemetry_matrix summary has invalid k_eff",
            stage="occupancy_snapshot",
            details={"k_eff": k_eff},
        )

    for key in ("reviewers", "defects", "matrix"):
        value = artifact.get(key)
        if not isinstance(value, list):
            raise StageError(
                "telemetry_matrix artifact missing list section",
                stage="occupancy_snapshot",
                details={"field": key, "type": str(type(value))},
            )
