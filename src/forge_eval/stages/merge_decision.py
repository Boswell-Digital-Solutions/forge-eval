from __future__ import annotations

from pathlib import Path
from typing import Any

from forge_eval.errors import StageError
from forge_eval.services.merge_decision_model import load_merge_decision_model
from forge_eval.services.merge_decision_reasons import build_merge_decision_reasons
from forge_eval.services.merge_decision_summary import build_merge_decision_summary


def run_stage(
    *,
    repo_path: str | Path,
    base_ref: str,
    head_ref: str,
    run_id: str,
    config: dict[str, Any],
    hazard_map_artifact: dict[str, Any],
) -> dict[str, Any]:
    _validate_hazard_map_artifact(hazard_map_artifact)
    model = load_merge_decision_model(config)
    hazard_run = hazard_map_artifact["run"]
    _validate_run_alignment(
        run_id=run_id,
        repo_path=repo_path,
        base_ref=base_ref,
        head_ref=head_ref,
        hazard_run=hazard_run,
    )

    reasoning = build_merge_decision_reasons(
        hazard_map_artifact=hazard_map_artifact,
        model=model,
    )
    decision, summary = build_merge_decision_summary(
        hazard_map_artifact=hazard_map_artifact,
        reasoning=reasoning,
    )

    repo = Path(repo_path)
    return {
        "artifact_version": 1,
        "kind": "merge_decision",
        "run": {
            "run_id": run_id,
            "repo_path": str(repo.resolve()),
            "base_ref": base_ref,
            "head_ref": head_ref,
            "base_commit": str(hazard_run["base_commit"]),
            "head_commit": str(hazard_run["head_commit"]),
            "hazard_artifact": "hazard_map.json",
        },
        "inputs": {
            "mode": "deterministic_advisory",
            "hazard_artifact": "hazard_map.json",
        },
        "decision": decision,
        "summary": summary,
        "reason_codes": list(reasoning["reason_codes"]),
        "model": model,
        "provenance": {
            "algorithm": "merge_decision_v1",
            "deterministic": True,
            "inputs": ["hazard_map.json"],
            "model_version": str(model["name"]),
        },
    }


def _validate_hazard_map_artifact(artifact: dict[str, Any]) -> None:
    if artifact.get("kind") != "hazard_map":
        raise StageError(
            "merge_decision requires hazard_map artifact",
            stage="merge_decision",
            details={"kind": artifact.get("kind")},
        )
    run = artifact.get("run")
    if not isinstance(run, dict):
        raise StageError(
            "hazard_map artifact missing run object",
            stage="merge_decision",
            details={"run": run},
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
                "hazard_map artifact run object missing required fields",
                stage="merge_decision",
                details={"field": field, "value": value},
            )

    summary = artifact.get("summary")
    if not isinstance(summary, dict):
        raise StageError(
            "hazard_map artifact missing summary object",
            stage="merge_decision",
            details={"summary": summary},
        )
    for field in (
        "hazard_score",
        "hazard_tier",
        "blocking_signals_present",
        "hidden_pressure",
        "uncertainty_flags",
    ):
        if field not in summary:
            raise StageError(
                "hazard_map artifact summary missing required field",
                stage="merge_decision",
                details={"field": field},
            )


def _validate_run_alignment(
    *,
    run_id: str,
    repo_path: str | Path,
    base_ref: str,
    head_ref: str,
    hazard_run: dict[str, Any],
) -> None:
    repo_resolved = str(Path(repo_path).resolve())
    if str(hazard_run["run_id"]) != str(run_id):
        raise StageError(
            "run_id mismatch between pipeline and hazard_map artifact",
            stage="merge_decision",
            details={"pipeline_run_id": run_id, "hazard_run_id": hazard_run["run_id"]},
        )
    if str(hazard_run["repo_path"]) != repo_resolved:
        raise StageError(
            "hazard_map artifact repo_path does not match pipeline repo",
            stage="merge_decision",
            details={
                "pipeline_repo_path": repo_resolved,
                "hazard_repo_path": hazard_run["repo_path"],
            },
        )
    for field, expected in (("base_ref", base_ref), ("head_ref", head_ref)):
        if str(hazard_run[field]) != str(expected):
            raise StageError(
                "hazard_map artifact ref does not match pipeline refs",
                stage="merge_decision",
                details={
                    "field": field,
                    "expected": expected,
                    "actual": hazard_run[field],
                },
            )
