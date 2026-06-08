from __future__ import annotations

import logging
from typing import Any

from forge_eval.errors import StageError

logger = logging.getLogger(__name__)


_REQUIRED_UPSTREAM = {
    "risk_heatmap": "risk_heatmap",
    "context_slices": "context_slices",
    "review_findings": "review_findings",
    "telemetry_matrix": "telemetry_matrix",
    "hazard_map": "hazard_map",
}


def _validate_upstream(
    *,
    run_id: str,
    risk_heatmap_artifact: dict[str, Any],
    context_slices_artifact: dict[str, Any],
    review_findings_artifact: dict[str, Any],
    telemetry_matrix_artifact: dict[str, Any],
    hazard_map_artifact: dict[str, Any],
) -> None:
    artifacts = {
        "risk_heatmap": risk_heatmap_artifact,
        "context_slices": context_slices_artifact,
        "review_findings": review_findings_artifact,
        "telemetry_matrix": telemetry_matrix_artifact,
        "hazard_map": hazard_map_artifact,
    }
    for name, artifact in artifacts.items():
        expected_kind = _REQUIRED_UPSTREAM[name]
        if artifact.get("kind") != expected_kind:
            raise StageError(
                f"localization_pack upstream artifact kind mismatch for {name}",
                stage="localization_pack",
                details={
                    "expected_kind": expected_kind,
                    "actual_kind": artifact.get("kind"),
                },
            )


def _build_source_artifacts_refs(
    *,
    occupancy_snapshot_artifact: dict[str, Any] | None,
) -> dict[str, Any]:
    return {
        "risk_heatmap_ref": "risk_heatmap.json",
        "context_slices_ref": "context_slices.json",
        "review_findings_ref": "review_findings.json",
        "telemetry_matrix_ref": "telemetry_matrix.json",
        "occupancy_snapshot_ref": "occupancy_snapshot.json"
        if occupancy_snapshot_artifact is not None
        else None,
        "hazard_map_ref": "hazard_map.json",
        "patch_targets_ref": None,
        "concernspans_ref": None,
    }


def run_stage(
    *,
    run_id: str,
    config: dict[str, Any],
    risk_heatmap_artifact: dict[str, Any],
    context_slices_artifact: dict[str, Any],
    review_findings_artifact: dict[str, Any],
    telemetry_matrix_artifact: dict[str, Any],
    hazard_map_artifact: dict[str, Any],
    occupancy_snapshot_artifact: dict[str, Any] | None = None,
) -> dict[str, Any]:
    _validate_upstream(
        run_id=run_id,
        risk_heatmap_artifact=risk_heatmap_artifact,
        context_slices_artifact=context_slices_artifact,
        review_findings_artifact=review_findings_artifact,
        telemetry_matrix_artifact=telemetry_matrix_artifact,
        hazard_map_artifact=hazard_map_artifact,
    )

    from forge_eval.services.construct_extractor import enrich_block_candidates
    from forge_eval.services.localization_ranker import rank_candidates
    from forge_eval.services.patch_scope_builder import build_patch_scope
    from forge_eval.services.review_scope_compiler import compile_review_scope

    source_refs = _build_source_artifacts_refs(
        occupancy_snapshot_artifact=occupancy_snapshot_artifact,
    )

    file_candidates, block_candidates = rank_candidates(
        config=config,
        context_slices_artifact=context_slices_artifact,
        review_findings_artifact=review_findings_artifact,
        telemetry_matrix_artifact=telemetry_matrix_artifact,
        hazard_map_artifact=hazard_map_artifact,
    )

    block_candidates = enrich_block_candidates(block_candidates, config=config)

    review_scope = compile_review_scope(
        block_candidates=block_candidates,
        config=config,
    )

    patch_scope = build_patch_scope(config=config)

    round_digits = config.get("localization_round_digits", 6)

    block_confidences = [b["confidence"] for b in block_candidates]
    summary_confidence = (
        round(min(block_confidences), round_digits) if block_confidences else 0.0
    )
    evidence_densities = [b["evidence_density"] for b in block_candidates]
    evidence_density_mean = (
        round(sum(evidence_densities) / len(evidence_densities), round_digits)
        if evidence_densities
        else 0.0
    )

    hazard_summary = hazard_map_artifact.get("summary", {})
    hazard_tier = hazard_summary.get("hazard_tier", "low")

    review_scope_line_count = sum(
        entry["end_line"] - entry["start_line"] + 1 for entry in review_scope
    )

    logger.info(
        "localization_pack telemetry: "
        "run_id=%s model_version=%s file_candidates=%d block_candidates=%d "
        "review_scope_lines=%d patch_scope_present=%s "
        "summary_confidence=%.6f hazard_tier=%s",
        run_id,
        config.get("localization_model_version", "localization_pack_rev1"),
        len(file_candidates),
        len(block_candidates),
        review_scope_line_count,
        len(patch_scope) > 0,
        summary_confidence,
        hazard_tier,
    )

    pack = {
        "artifact_version": "localization_pack.v1",
        "kind": "localization_pack",
        "run_id": run_id,
        "source_artifacts": source_refs,
        "file_candidates": file_candidates,
        "function_candidates": [],
        "block_candidates": block_candidates,
        "review_scope": review_scope,
        "patch_scope": patch_scope,
        "summary": {
            "summary_confidence": summary_confidence,
            "evidence_density_mean": evidence_density_mean,
            "hazard_tier": hazard_tier,
            "file_candidate_count": len(file_candidates),
            "block_candidate_count": len(block_candidates),
            "review_scope_line_count": review_scope_line_count,
            "patch_scope_present": len(patch_scope) > 0,
        },
        "model": {
            "ranking_policy": "heuristic_v1",
            "scope_merge_policy": "deterministic_merge_v1",
            "construct_extraction_policy": "ast_heuristic_v1",
        },
        "provenance": {
            "algorithm": "localization_pack_v1",
            "deterministic": True,
        },
    }

    return pack
