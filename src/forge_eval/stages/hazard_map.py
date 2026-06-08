from __future__ import annotations

from pathlib import Path
from typing import Any

from forge_eval.errors import StageError
from forge_eval.services.hazard_model import load_hazard_model
from forge_eval.services.hazard_rows import build_hazard_rows
from forge_eval.services.hazard_summary import build_hazard_summary


def run_stage(
    *,
    repo_path: str | Path,
    base_ref: str,
    head_ref: str,
    run_id: str,
    config: dict[str, Any],
    risk_heatmap_artifact: dict[str, Any],
    telemetry_matrix_artifact: dict[str, Any],
    occupancy_snapshot_artifact: dict[str, Any],
    capture_estimate_artifact: dict[str, Any],
) -> dict[str, Any]:
    _validate_risk_heatmap_artifact(risk_heatmap_artifact)
    _validate_telemetry_artifact(telemetry_matrix_artifact)
    _validate_occupancy_artifact(occupancy_snapshot_artifact)
    _validate_capture_artifact(capture_estimate_artifact)

    model = load_hazard_model(config)

    telemetry_run = telemetry_matrix_artifact["run"]
    occupancy_run = occupancy_snapshot_artifact["run"]
    capture_run = capture_estimate_artifact["run"]
    _validate_run_alignment(
        run_id=run_id,
        repo_path=repo_path,
        base_ref=base_ref,
        head_ref=head_ref,
        risk_heatmap_artifact=risk_heatmap_artifact,
        telemetry_run=telemetry_run,
        occupancy_run=occupancy_run,
        capture_run=capture_run,
    )

    rows = build_hazard_rows(
        risk_heatmap_artifact=risk_heatmap_artifact,
        telemetry_matrix_artifact=telemetry_matrix_artifact,
        occupancy_snapshot_artifact=occupancy_snapshot_artifact,
        model=model,
    )
    summary = build_hazard_summary(
        rows=rows,
        risk_heatmap_artifact=risk_heatmap_artifact,
        telemetry_matrix_artifact=telemetry_matrix_artifact,
        occupancy_snapshot_artifact=occupancy_snapshot_artifact,
        capture_estimate_artifact=capture_estimate_artifact,
        model=model,
    )

    repo = Path(repo_path)
    round_digits = int(model["parameters"]["hazard_round_digits"])
    selected_method = str(capture_estimate_artifact["estimators"]["selected_method"])
    run_payload = {
        "run_id": run_id,
        "repo_path": str(repo.resolve()),
        "base_ref": base_ref,
        "head_ref": head_ref,
        "base_commit": str(telemetry_run["base_commit"]),
        "head_commit": str(telemetry_run["head_commit"]),
        "risk_artifact": "risk_heatmap.json",
        "telemetry_artifact": "telemetry_matrix.json",
        "occupancy_artifact": "occupancy_snapshot.json",
        "capture_artifact": "capture_estimate.json",
    }

    return {
        "artifact_version": 1,
        "kind": "hazard_map",
        "run": run_payload,
        "inputs": {
            "mode": "deterministic_conservative",
            "risk_artifact": "risk_heatmap.json",
            "telemetry_artifact": "telemetry_matrix.json",
            "occupancy_artifact": "occupancy_snapshot.json",
            "capture_artifact": "capture_estimate.json",
            "hidden_selection_policy": selected_method,
            "round_digits": round_digits,
        },
        "summary": summary,
        "rows": rows,
        "model": model,
        "provenance": {
            "algorithm": "hazard_map_v1",
            "deterministic": True,
            "inputs": [
                "risk_heatmap.json",
                "telemetry_matrix.json",
                "occupancy_snapshot.json",
                "capture_estimate.json",
            ],
            "model_version": str(model["name"]),
        },
    }


def _validate_risk_heatmap_artifact(artifact: dict[str, Any]) -> None:
    if artifact.get("kind") != "risk_heatmap":
        raise StageError(
            "hazard_map requires risk_heatmap artifact",
            stage="hazard_map",
            details={"kind": artifact.get("kind")},
        )
    for field in ("run_id", "repo_path", "base_ref", "head_ref"):
        value = artifact.get(field)
        if not isinstance(value, str) or not value:
            raise StageError(
                "risk_heatmap artifact missing required field",
                stage="hazard_map",
                details={"field": field, "value": value},
            )
    targets = artifact.get("targets")
    if not isinstance(targets, list):
        raise StageError(
            "risk_heatmap artifact missing targets list",
            stage="hazard_map",
            details={"type": str(type(targets))},
        )


def _validate_telemetry_artifact(artifact: dict[str, Any]) -> None:
    if artifact.get("kind") != "telemetry_matrix":
        raise StageError(
            "hazard_map requires telemetry_matrix artifact",
            stage="hazard_map",
            details={"kind": artifact.get("kind")},
        )
    _validate_run_object(artifact.get("run"), context="telemetry_matrix")


def _validate_occupancy_artifact(artifact: dict[str, Any]) -> None:
    if artifact.get("kind") != "occupancy_snapshot":
        raise StageError(
            "hazard_map requires occupancy_snapshot artifact",
            stage="hazard_map",
            details={"kind": artifact.get("kind")},
        )
    _validate_run_object(artifact.get("run"), context="occupancy_snapshot")


def _validate_capture_artifact(artifact: dict[str, Any]) -> None:
    if artifact.get("kind") != "capture_estimate":
        raise StageError(
            "hazard_map requires capture_estimate artifact",
            stage="hazard_map",
            details={"kind": artifact.get("kind")},
        )
    _validate_run_object(artifact.get("run"), context="capture_estimate")
    estimators = artifact.get("estimators")
    if not isinstance(estimators, dict):
        raise StageError(
            "capture_estimate artifact missing estimators object",
            stage="hazard_map",
        )
    selected_method = estimators.get("selected_method")
    if selected_method != "max_hidden":
        raise StageError(
            "hazard_map only supports max_hidden capture selection",
            stage="hazard_map",
            details={"selected_method": selected_method},
        )


def _validate_run_object(run: Any, *, context: str) -> None:
    if not isinstance(run, dict):
        raise StageError(
            "artifact missing run object",
            stage="hazard_map",
            details={"context": context},
        )
    for field in (
        "run_id",
        "repo_path",
        "base_ref",
        "head_ref",
        "base_commit",
        "head_commit",
    ):
        value = run.get(field)
        if not isinstance(value, str) or not value:
            raise StageError(
                "artifact run object missing required fields",
                stage="hazard_map",
                details={"context": context, "field": field, "value": value},
            )


def _validate_run_alignment(
    *,
    run_id: str,
    repo_path: str | Path,
    base_ref: str,
    head_ref: str,
    risk_heatmap_artifact: dict[str, Any],
    telemetry_run: dict[str, Any],
    occupancy_run: dict[str, Any],
    capture_run: dict[str, Any],
) -> None:
    repo_resolved = str(Path(repo_path).resolve())

    if str(risk_heatmap_artifact["run_id"]) != str(run_id):
        raise StageError(
            "run_id mismatch between pipeline and risk_heatmap artifact",
            stage="hazard_map",
            details={
                "pipeline_run_id": run_id,
                "risk_run_id": risk_heatmap_artifact["run_id"],
            },
        )

    if str(risk_heatmap_artifact["repo_path"]) != repo_resolved:
        raise StageError(
            "risk_heatmap artifact repo_path does not match pipeline repo",
            stage="hazard_map",
            details={
                "pipeline_repo_path": repo_resolved,
                "risk_repo_path": risk_heatmap_artifact["repo_path"],
            },
        )

    for field, expected in (("base_ref", base_ref), ("head_ref", head_ref)):
        if str(risk_heatmap_artifact[field]) != str(expected):
            raise StageError(
                "risk_heatmap artifact ref does not match pipeline refs",
                stage="hazard_map",
                details={
                    "field": field,
                    "expected": expected,
                    "actual": risk_heatmap_artifact[field],
                },
            )

    for context, run in (
        ("telemetry_matrix", telemetry_run),
        ("occupancy_snapshot", occupancy_run),
        ("capture_estimate", capture_run),
    ):
        if str(run["run_id"]) != str(run_id):
            raise StageError(
                "run_id mismatch across hazard inputs",
                stage="hazard_map",
                details={
                    "context": context,
                    "pipeline_run_id": run_id,
                    "artifact_run_id": run["run_id"],
                },
            )
        if str(run["repo_path"]) != repo_resolved:
            raise StageError(
                "artifact repo_path mismatch across hazard inputs",
                stage="hazard_map",
                details={
                    "context": context,
                    "pipeline_repo_path": repo_resolved,
                    "artifact_repo_path": run["repo_path"],
                },
            )
        for field, expected in (("base_ref", base_ref), ("head_ref", head_ref)):
            if str(run[field]) != str(expected):
                raise StageError(
                    "artifact refs mismatch across hazard inputs",
                    stage="hazard_map",
                    details={
                        "context": context,
                        "field": field,
                        "expected": expected,
                        "actual": run[field],
                    },
                )

    for field in ("base_commit", "head_commit"):
        telemetry_value = str(telemetry_run[field])
        occupancy_value = str(occupancy_run[field])
        capture_value = str(capture_run[field])
        if telemetry_value != occupancy_value or telemetry_value != capture_value:
            raise StageError(
                "hazard inputs disagree on run commits",
                stage="hazard_map",
                details={
                    "field": field,
                    "telemetry_value": telemetry_value,
                    "occupancy_value": occupancy_value,
                    "capture_value": capture_value,
                },
            )
