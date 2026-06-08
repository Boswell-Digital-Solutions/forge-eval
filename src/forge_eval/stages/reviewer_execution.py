from __future__ import annotations

from pathlib import Path
from typing import Any

from forge_eval.errors import StageError
from forge_eval.reviewers import reviewer_specs_from_config
from forge_eval.reviewers.adapters import execute_reviewer
from forge_eval.services.finding_normalizer import normalize_findings

_CODE_EXTENSIONS = (".py", ".rs", ".ts", ".tsx", ".js", ".jsx", ".json")


def run_stage(
    *,
    repo_path: str | Path,
    base_ref: str,
    head_ref: str,
    run_id: str,
    config: dict[str, Any],
    context_slices_artifact: dict[str, Any],
    risk_heatmap_artifact: dict[str, Any] | None = None,
    base_commit: str | None = None,
    head_commit: str | None = None,
) -> dict[str, Any]:
    repo = Path(repo_path)
    slices = _extract_slices(context_slices_artifact)
    reviewer_specs = reviewer_specs_from_config(list(config["reviewers"]))

    reviewer_ids = [spec.reviewer_id for spec in reviewer_specs]
    if len(reviewer_ids) != len(set(reviewer_ids)):
        raise StageError(
            "duplicate reviewer_id detected at stage runtime",
            stage="review_findings",
            details={"reviewer_ids": reviewer_ids},
        )

    context = _build_reviewer_context(
        slices=slices,
        risk_heatmap_artifact=risk_heatmap_artifact,
    )

    reviewer_failure_policy = str(config["reviewer_failure_policy"])
    reviewer_summaries: list[dict[str, Any]] = []
    raw_findings: list[dict[str, Any]] = []
    for spec in reviewer_specs:
        run_result = execute_reviewer(
            spec=spec,
            slices=slices,
            context=context,
            stage_failure_policy=reviewer_failure_policy,
        )
        reviewer_summaries.append(
            {
                "reviewer_id": spec.reviewer_id,
                "kind": spec.kind,
                "status": run_result.status,
                "slices_seen": run_result.slices_seen,
                "findings_emitted": run_result.findings_emitted,
                "error": run_result.error,
            }
        )
        raw_findings.extend(run_result.raw_findings)

    findings = normalize_findings(
        raw_findings=raw_findings,
        reviewer_specs=reviewer_specs,
    )

    summary = _build_summary(reviewer_summaries=reviewer_summaries, findings=findings)
    provenance_inputs = ["context_slices.json"]
    if risk_heatmap_artifact is not None:
        provenance_inputs.append("risk_heatmap.json")
    provenance_inputs.sort()

    run = {
        "run_id": run_id,
        "repo_path": str(repo.resolve()),
        "base_ref": base_ref,
        "head_ref": head_ref,
        "base_commit": base_commit or base_ref,
        "head_commit": head_commit or head_ref,
        "slice_artifact": "context_slices.json",
        "risk_artifact": "risk_heatmap.json"
        if risk_heatmap_artifact is not None
        else None,
    }

    return {
        "artifact_version": 1,
        "kind": "review_findings",
        "run": run,
        "reviewers": reviewer_summaries,
        "findings": findings,
        "summary": summary,
        "provenance": {
            "algorithm": "reviewer_execution_v1",
            "deterministic": True,
            "reviewer_failure_policy": reviewer_failure_policy,
            "inputs": provenance_inputs,
        },
    }


def _extract_slices(context_slices_artifact: dict[str, Any]) -> list[dict[str, Any]]:
    if context_slices_artifact.get("kind") != "context_slices":
        raise StageError(
            "review_findings requires context_slices artifact",
            stage="review_findings",
            details={"kind": context_slices_artifact.get("kind")},
        )
    slices = context_slices_artifact.get("slices")
    if not isinstance(slices, list):
        raise StageError(
            "context_slices artifact has invalid slices field",
            stage="review_findings",
            details={"type": str(type(slices))},
        )
    sorted_slices = sorted(
        slices,
        key=lambda s: (str(s["file_path"]), int(s["start_line"]), int(s["end_line"])),
    )
    return [dict(item) for item in sorted_slices]


def _build_reviewer_context(
    *,
    slices: list[dict[str, Any]],
    risk_heatmap_artifact: dict[str, Any] | None,
) -> dict[str, Any]:
    paths = sorted({str(slc["file_path"]).replace("\\", "/") for slc in slices})
    has_docs_changes = any(path.lower().endswith(".md") for path in paths)
    has_code_changes = any(
        path.lower().endswith(_CODE_EXTENSIONS) and not path.lower().endswith(".md")
        for path in paths
    )
    has_schema_like_change = any("schema" in path.lower() for path in paths)

    risk_by_path: dict[str, float] = {}
    if risk_heatmap_artifact is not None:
        if risk_heatmap_artifact.get("kind") != "risk_heatmap":
            raise StageError(
                "risk artifact has invalid kind",
                stage="review_findings",
                details={"kind": risk_heatmap_artifact.get("kind")},
            )
        targets = risk_heatmap_artifact.get("targets", [])
        if not isinstance(targets, list):
            raise StageError(
                "risk artifact has invalid targets field",
                stage="review_findings",
                details={"type": str(type(targets))},
            )
        for target in targets:
            if not isinstance(target, dict):
                raise StageError(
                    "risk artifact target entry is invalid",
                    stage="review_findings",
                    details={"target": target},
                )
            file_path = str(target.get("file_path", ""))
            if not file_path:
                continue
            risk_score = target.get("risk_score", 0.0)
            if isinstance(risk_score, bool) or not isinstance(risk_score, (int, float)):
                raise StageError(
                    "risk artifact target has invalid risk_score",
                    stage="review_findings",
                    details={"file_path": file_path, "risk_score": risk_score},
                )
            risk_by_path[file_path] = float(risk_score)

    return {
        "changed_file_paths": paths,
        "has_docs_changes": has_docs_changes,
        "has_code_changes": has_code_changes,
        "has_schema_like_change": has_schema_like_change,
        "risk_by_path": risk_by_path,
    }


def _build_summary(
    *,
    reviewer_summaries: list[dict[str, Any]],
    findings: list[dict[str, Any]],
) -> dict[str, Any]:
    status_counts = {"ok": 0, "failed": 0, "skipped": 0}
    for reviewer in reviewer_summaries:
        status = str(reviewer["status"])
        status_counts[status] += 1

    severity_counts = {"low": 0, "medium": 0, "high": 0, "critical": 0}
    for finding in findings:
        severity_counts[str(finding["severity"])] += 1

    return {
        "reviewer_count": len(reviewer_summaries),
        "reviewer_ok_count": status_counts["ok"],
        "reviewer_failed_count": status_counts["failed"],
        "reviewer_skipped_count": status_counts["skipped"],
        "finding_count": len(findings),
        "finding_count_by_severity": severity_counts,
    }
