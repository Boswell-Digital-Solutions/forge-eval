from __future__ import annotations

from pathlib import Path
from typing import Any

from forge_eval.errors import StageError
from forge_eval.evidence_cli import EvidenceCli
from forge_eval.services.evidence_bundle_manifest import (
    build_evidence_manifest,
    required_bundle_artifacts,
)
from forge_eval.services.evidence_bundle_model import load_evidence_bundle_model
from forge_eval.services.evidence_bundle_summary import build_evidence_bundle_summary

_REQUIRED_KINDS = {
    "risk_heatmap": "risk_heatmap",
    "context_slices": "context_slices",
    "review_findings": "review_findings",
    "telemetry_matrix": "telemetry_matrix",
    "occupancy_snapshot": "occupancy_snapshot",
    "capture_estimate": "capture_estimate",
    "hazard_map": "hazard_map",
    "merge_decision": "merge_decision",
}


def run_stage(
    *,
    repo_path: str | Path,
    artifacts_dir: str | Path,
    base_ref: str,
    head_ref: str,
    run_id: str,
    config: dict[str, Any],
    resolved_config_artifact: dict[str, Any],
    risk_heatmap_artifact: dict[str, Any],
    context_slices_artifact: dict[str, Any],
    review_findings_artifact: dict[str, Any],
    telemetry_matrix_artifact: dict[str, Any],
    occupancy_snapshot_artifact: dict[str, Any],
    capture_estimate_artifact: dict[str, Any],
    hazard_map_artifact: dict[str, Any],
    merge_decision_artifact: dict[str, Any],
) -> dict[str, Any]:
    repo = Path(repo_path)
    out_dir = Path(artifacts_dir)
    model = load_evidence_bundle_model(config)
    _validate_resolved_config(
        resolved_config_artifact=resolved_config_artifact,
        run_id=run_id,
        repo_path=repo,
        base_ref=base_ref,
        head_ref=head_ref,
    )
    _validate_required_artifact_kinds(
        risk_heatmap_artifact=risk_heatmap_artifact,
        context_slices_artifact=context_slices_artifact,
        review_findings_artifact=review_findings_artifact,
        telemetry_matrix_artifact=telemetry_matrix_artifact,
        occupancy_snapshot_artifact=occupancy_snapshot_artifact,
        capture_estimate_artifact=capture_estimate_artifact,
        hazard_map_artifact=hazard_map_artifact,
        merge_decision_artifact=merge_decision_artifact,
    )
    merge_run = _extract_run_section(merge_decision_artifact)
    _validate_run_alignment(
        run_id=run_id,
        repo_path=repo,
        base_ref=base_ref,
        head_ref=head_ref,
        merge_run=merge_run,
    )

    evidence_cli = EvidenceCli()
    artifacts, manifest = build_evidence_manifest(
        artifacts_dir=out_dir, evidence_cli=evidence_cli
    )
    decision, summary = build_evidence_bundle_summary(
        artifacts=artifacts,
        merge_decision_artifact=merge_decision_artifact,
        manifest=manifest,
    )
    input_files = [path for _, path in required_bundle_artifacts()]

    return {
        "artifact_version": 1,
        "kind": "evidence_bundle",
        "run": {
            "run_id": run_id,
            "repo_path": str(repo.resolve()),
            "base_ref": base_ref,
            "head_ref": head_ref,
            "base_commit": str(merge_run["base_commit"]),
            "head_commit": str(merge_run["head_commit"]),
            "merge_decision_artifact": "merge_decision.json",
        },
        "inputs": {
            "mode": "deterministic_evidence_assembly",
            "evidence_runtime": "forge_evidence_cli",
            "artifacts": input_files,
            "merge_decision_artifact": "merge_decision.json",
        },
        "artifacts": artifacts,
        "decision": decision,
        "manifest": manifest,
        "summary": summary,
        "model": model,
        "provenance": {
            "algorithm": "evidence_bundle_v1",
            "deterministic": True,
            "inputs": input_files,
            "model_version": str(model["name"]),
            "runtime_evidence_integration": "forge_evidence_cli",
        },
    }


def _validate_resolved_config(
    *,
    resolved_config_artifact: dict[str, Any],
    run_id: str,
    repo_path: Path,
    base_ref: str,
    head_ref: str,
) -> None:
    if resolved_config_artifact.get("kind") != "config_resolved":
        raise StageError(
            "evidence_bundle requires config_resolved artifact",
            stage="evidence_bundle",
            details={"kind": resolved_config_artifact.get("kind")},
        )
    if str(resolved_config_artifact.get("run_id")) != str(run_id):
        raise StageError(
            "run_id mismatch between pipeline and config.resolved artifact",
            stage="evidence_bundle",
            details={
                "pipeline_run_id": run_id,
                "config_run_id": resolved_config_artifact.get("run_id"),
            },
        )
    if str(resolved_config_artifact.get("repo_path")) != str(repo_path.resolve()):
        raise StageError(
            "config.resolved repo_path does not match pipeline repo",
            stage="evidence_bundle",
            details={
                "pipeline_repo_path": str(repo_path.resolve()),
                "config_repo_path": resolved_config_artifact.get("repo_path"),
            },
        )
    for field, expected in (("base_ref", base_ref), ("head_ref", head_ref)):
        if str(resolved_config_artifact.get(field)) != str(expected):
            raise StageError(
                "config.resolved ref does not match pipeline refs",
                stage="evidence_bundle",
                details={
                    "field": field,
                    "expected": expected,
                    "actual": resolved_config_artifact.get(field),
                },
            )


def _validate_required_artifact_kinds(**artifacts: dict[str, dict[str, Any]]) -> None:
    for name, artifact in artifacts.items():
        expected = _REQUIRED_KINDS[name.replace("_artifact", "")]
        if artifact.get("kind") != expected:
            raise StageError(
                "evidence_bundle upstream artifact kind mismatch",
                stage="evidence_bundle",
                details={
                    "expected_kind": expected,
                    "actual_kind": artifact.get("kind"),
                },
            )


def _extract_run_section(merge_decision_artifact: dict[str, Any]) -> dict[str, Any]:
    run = merge_decision_artifact.get("run")
    if not isinstance(run, dict):
        raise StageError(
            "merge_decision artifact missing run object",
            stage="evidence_bundle",
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
                "merge_decision artifact run object missing required field",
                stage="evidence_bundle",
                details={"field": field, "value": value},
            )
    return run


def _validate_run_alignment(
    *,
    run_id: str,
    repo_path: Path,
    base_ref: str,
    head_ref: str,
    merge_run: dict[str, Any],
) -> None:
    if str(merge_run["run_id"]) != str(run_id):
        raise StageError(
            "run_id mismatch between pipeline and merge_decision artifact",
            stage="evidence_bundle",
            details={"pipeline_run_id": run_id, "merge_run_id": merge_run["run_id"]},
        )
    if str(merge_run["repo_path"]) != str(repo_path.resolve()):
        raise StageError(
            "merge_decision artifact repo_path does not match pipeline repo",
            stage="evidence_bundle",
            details={
                "pipeline_repo_path": str(repo_path.resolve()),
                "merge_repo_path": merge_run["repo_path"],
            },
        )
    for field, expected in (("base_ref", base_ref), ("head_ref", head_ref)):
        if str(merge_run[field]) != str(expected):
            raise StageError(
                "merge_decision artifact ref does not match pipeline refs",
                stage="evidence_bundle",
                details={
                    "field": field,
                    "expected": expected,
                    "actual": merge_run[field],
                },
            )
