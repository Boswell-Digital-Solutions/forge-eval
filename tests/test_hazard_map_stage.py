from __future__ import annotations

from pathlib import Path

import pytest

from forge_eval.config import normalize_config
from forge_eval.errors import StageError
from forge_eval.services.hazard_model import map_hazard_tier
from forge_eval.stages.capture_estimate import run_stage as run_capture_estimate_stage
from forge_eval.stages.hazard_map import run_stage


def _telemetry_artifact_repeat_supported() -> dict[str, object]:
    return {
        "artifact_version": 1,
        "kind": "telemetry_matrix",
        "run": {
            "run_id": "run",
            "repo_path": "/tmp/repo",
            "base_ref": "base",
            "head_ref": "head",
            "base_commit": "basec",
            "head_commit": "headc",
            "review_findings_artifact": "review_findings.json",
        },
        "reviewers": [
            {
                "reviewer_id": "r1",
                "status": "ok",
                "kind": "changed_lines",
                "eligible": True,
                "usable": True,
                "failed": False,
                "skipped": False,
                "findings_emitted": 4,
                "slices_seen": 4,
                "error": None,
            },
            {
                "reviewer_id": "r2",
                "status": "ok",
                "kind": "changed_lines",
                "eligible": True,
                "usable": True,
                "failed": False,
                "skipped": False,
                "findings_emitted": 2,
                "slices_seen": 4,
                "error": None,
            },
            {
                "reviewer_id": "r3",
                "status": "ok",
                "kind": "structural_risk",
                "eligible": True,
                "usable": True,
                "failed": False,
                "skipped": False,
                "findings_emitted": 1,
                "slices_seen": 4,
                "error": None,
            },
        ],
        "defects": [
            {
                "defect_key": "dfk_" + ("a" * 64),
                "file_path": "a.py",
                "category": "consistency",
                "severity": "medium",
                "reported_by": ["r1"],
                "support_count": 1,
            },
            {
                "defect_key": "dfk_" + ("b" * 64),
                "file_path": "b.py",
                "category": "correctness",
                "severity": "high",
                "reported_by": ["r1", "r2"],
                "support_count": 2,
            },
            {
                "defect_key": "dfk_" + ("c" * 64),
                "file_path": "c.py",
                "category": "risk",
                "severity": "medium",
                "reported_by": ["r1"],
                "support_count": 1,
            },
            {
                "defect_key": "dfk_" + ("d" * 64),
                "file_path": "d.py",
                "category": "correctness",
                "severity": "critical",
                "reported_by": ["r1", "r2", "r3"],
                "support_count": 3,
            },
        ],
        "matrix": [
            {
                "defect_key": "dfk_" + ("a" * 64),
                "observations": {"r1": 1, "r2": 0, "r3": None},
                "k_eff_defect": 2,
            },
            {
                "defect_key": "dfk_" + ("b" * 64),
                "observations": {"r1": 1, "r2": 1, "r3": 0},
                "k_eff_defect": 3,
            },
            {
                "defect_key": "dfk_" + ("c" * 64),
                "observations": {"r1": 1, "r2": None, "r3": None},
                "k_eff_defect": 1,
            },
            {
                "defect_key": "dfk_" + ("d" * 64),
                "observations": {"r1": 1, "r2": 1, "r3": 1},
                "k_eff_defect": 3,
            },
        ],
        "summary": {
            "k_configured": 3,
            "k_executed": 3,
            "k_failed": 0,
            "k_skipped": 0,
            "k_usable": 3,
            "k_eff": 1,
            "defect_count": 4,
            "matrix_rows": 4,
            "cells_observed": 7,
            "cells_missed": 2,
            "cells_null": 3,
        },
        "provenance": {
            "algorithm": "telemetry_matrix_v1",
            "deterministic": True,
            "inputs": ["review_findings.json"],
            "applicability_mode": "reviewer_kind_scope_v1",
            "k_eff_mode": "global_min_per_defect",
        },
    }


def _occupancy_artifact_repeat_supported() -> dict[str, object]:
    return {
        "artifact_version": 1,
        "kind": "occupancy_snapshot",
        "run": {
            "run_id": "run",
            "repo_path": "/tmp/repo",
            "base_ref": "base",
            "head_ref": "head",
            "base_commit": "basec",
            "head_commit": "headc",
            "telemetry_artifact": "telemetry_matrix.json",
        },
        "rows": [
            {
                "defect_key": "dfk_" + ("a" * 64),
                "psi_post": 0.72,
                "observed_by": 1,
                "missed_by": 1,
                "null_by": 1,
                "k_eff_defect": 2,
                "support_count": 1,
                "evidence_strength": "moderate",
                "file_path": "a.py",
                "category": "consistency",
                "severity": "medium",
                "inputs": {
                    "prior": 0.7,
                    "detection_assumption": 0.7,
                    "coverage_ratio": 0.666667,
                    "miss_penalty": 0.116667,
                    "uncertainty_guard": 0.033333,
                },
            },
            {
                "defect_key": "dfk_" + ("b" * 64),
                "psi_post": 0.83,
                "observed_by": 2,
                "missed_by": 1,
                "null_by": 0,
                "k_eff_defect": 3,
                "support_count": 2,
                "evidence_strength": "strong",
                "file_path": "b.py",
                "category": "correctness",
                "severity": "high",
                "inputs": {
                    "prior": 0.8,
                    "detection_assumption": 0.7,
                    "coverage_ratio": 1.0,
                    "miss_penalty": 0.116667,
                    "uncertainty_guard": 0.0,
                },
            },
            {
                "defect_key": "dfk_" + ("c" * 64),
                "psi_post": 0.68,
                "observed_by": 1,
                "missed_by": 0,
                "null_by": 2,
                "k_eff_defect": 1,
                "support_count": 1,
                "evidence_strength": "moderate",
                "file_path": "c.py",
                "category": "risk",
                "severity": "medium",
                "inputs": {
                    "prior": 0.7,
                    "detection_assumption": 0.7,
                    "coverage_ratio": 0.333333,
                    "miss_penalty": 0.0,
                    "uncertainty_guard": 0.133333,
                },
            },
            {
                "defect_key": "dfk_" + ("d" * 64),
                "psi_post": 0.94,
                "observed_by": 3,
                "missed_by": 0,
                "null_by": 0,
                "k_eff_defect": 3,
                "support_count": 3,
                "evidence_strength": "strong",
                "file_path": "d.py",
                "category": "correctness",
                "severity": "critical",
                "inputs": {
                    "prior": 0.85,
                    "detection_assumption": 0.7,
                    "coverage_ratio": 1.0,
                    "miss_penalty": 0.0,
                    "uncertainty_guard": 0.0,
                },
            },
        ],
        "summary": {
            "defect_rows": 4,
            "rows_with_positive_observation": 4,
            "rows_with_nulls": 2,
            "mean_psi_post": 0.7925,
            "max_psi_post": 0.94,
            "min_psi_post": 0.68,
            "global_k_eff": 1,
        },
        "model": {
            "name": "occupancy_rev1",
            "mode": "deterministic_conservative",
            "prior_policy": "config_locked_v1",
            "null_policy": "null_is_uncertainty",
            "suppression_policy": "usable_misses_only",
            "parameters": {
                "occupancy_prior_base": 0.45,
                "occupancy_support_uplift": 0.2,
                "occupancy_detection_assumption": 0.7,
                "occupancy_miss_penalty_strength": 0.35,
                "occupancy_null_uncertainty_boost": 0.3,
                "occupancy_round_digits": 6,
                "severity_uplift": {
                    "low": 0.0,
                    "medium": 0.05,
                    "high": 0.1,
                    "critical": 0.15,
                },
            },
        },
        "provenance": {
            "algorithm": "occupancy_snapshot_v1",
            "deterministic": True,
            "inputs": ["telemetry_matrix.json"],
            "model_version": "occupancy_rev1",
        },
    }


def _risk_artifact() -> dict[str, object]:
    return {
        "schema_version": "v1",
        "kind": "risk_heatmap",
        "run_id": "run",
        "repo_path": "/tmp/repo",
        "base_ref": "base",
        "head_ref": "head",
        "weights": {"w_change_magnitude": 0.2, "w_centrality": 0.35, "w_churn": 0.45},
        "targets": [
            {
                "target_id": "t:a.py",
                "file_path": "a.py",
                "churn": {"added_lines": 2, "deleted_lines": 0, "normalized": 0.2},
                "centrality": 0.4,
                "change_magnitude": 0.3,
                "risk_raw": 0.37,
                "risk_score": 0.37,
                "reasons": [{"metric": "churn", "value": 0.2}],
            },
            {
                "target_id": "t:b.py",
                "file_path": "b.py",
                "churn": {"added_lines": 6, "deleted_lines": 1, "normalized": 0.7},
                "centrality": 0.6,
                "change_magnitude": 0.5,
                "risk_raw": 0.68,
                "risk_score": 0.68,
                "reasons": [{"metric": "churn", "value": 0.7}],
            },
            {
                "target_id": "t:c.py",
                "file_path": "c.py",
                "churn": {"added_lines": 4, "deleted_lines": 2, "normalized": 0.5},
                "centrality": 0.5,
                "change_magnitude": 0.45,
                "risk_raw": 0.55,
                "risk_score": 0.55,
                "reasons": [{"metric": "churn", "value": 0.5}],
            },
            {
                "target_id": "t:d.py",
                "file_path": "d.py",
                "churn": {"added_lines": 8, "deleted_lines": 2, "normalized": 0.9},
                "centrality": 0.8,
                "change_magnitude": 0.7,
                "risk_raw": 0.86,
                "risk_score": 0.86,
                "reasons": [{"metric": "churn", "value": 0.9}],
            },
        ],
        "summary": {"target_count": 4, "min_risk_score": 0.37, "max_risk_score": 0.86},
        "provenance": {"algorithm": "structural_risk_v1", "deterministic": True},
    }


def _capture_artifact(cfg: dict[str, object]) -> dict[str, object]:
    return run_capture_estimate_stage(
        repo_path=Path("/tmp/repo"),
        base_ref="base",
        head_ref="head",
        run_id="run",
        config=cfg,
        telemetry_matrix_artifact=_telemetry_artifact_repeat_supported(),
        occupancy_snapshot_artifact=_occupancy_artifact_repeat_supported(),
    )


def _telemetry_artifact_no_defects() -> dict[str, object]:
    return {
        "artifact_version": 1,
        "kind": "telemetry_matrix",
        "run": {
            "run_id": "run",
            "repo_path": "/tmp/repo",
            "base_ref": "base",
            "head_ref": "head",
            "base_commit": "basec",
            "head_commit": "headc",
            "review_findings_artifact": "review_findings.json",
        },
        "reviewers": [],
        "defects": [],
        "matrix": [],
        "summary": {
            "k_configured": 0,
            "k_executed": 0,
            "k_failed": 0,
            "k_skipped": 0,
            "k_usable": 0,
            "k_eff": 0,
            "defect_count": 0,
            "matrix_rows": 0,
            "cells_observed": 0,
            "cells_missed": 0,
            "cells_null": 0,
        },
        "provenance": {
            "algorithm": "telemetry_matrix_v1",
            "deterministic": True,
            "inputs": ["review_findings.json"],
            "applicability_mode": "reviewer_kind_scope_v1",
            "k_eff_mode": "global_min_per_defect",
        },
    }


def _occupancy_artifact_no_defects() -> dict[str, object]:
    return {
        "artifact_version": 1,
        "kind": "occupancy_snapshot",
        "run": {
            "run_id": "run",
            "repo_path": "/tmp/repo",
            "base_ref": "base",
            "head_ref": "head",
            "base_commit": "basec",
            "head_commit": "headc",
            "telemetry_artifact": "telemetry_matrix.json",
        },
        "rows": [],
        "summary": {
            "defect_rows": 0,
            "rows_with_positive_observation": 0,
            "rows_with_nulls": 0,
            "mean_psi_post": 0.0,
            "max_psi_post": 0.0,
            "min_psi_post": 0.0,
            "global_k_eff": 0,
        },
        "model": {
            "name": "occupancy_rev1",
            "mode": "deterministic_conservative",
            "prior_policy": "config_locked_v1",
            "null_policy": "null_is_uncertainty",
            "suppression_policy": "usable_misses_only",
            "parameters": {
                "occupancy_prior_base": 0.45,
                "occupancy_support_uplift": 0.2,
                "occupancy_detection_assumption": 0.7,
                "occupancy_miss_penalty_strength": 0.35,
                "occupancy_null_uncertainty_boost": 0.3,
                "occupancy_round_digits": 6,
                "severity_uplift": {
                    "low": 0.0,
                    "medium": 0.05,
                    "high": 0.1,
                    "critical": 0.15,
                },
            },
        },
        "provenance": {
            "algorithm": "occupancy_snapshot_v1",
            "deterministic": True,
            "inputs": ["telemetry_matrix.json"],
            "model_version": "occupancy_rev1",
        },
    }


def _capture_artifact_no_defects() -> dict[str, object]:
    return {
        "artifact_version": 1,
        "kind": "capture_estimate",
        "run": {
            "run_id": "run",
            "repo_path": "/tmp/repo",
            "base_ref": "base",
            "head_ref": "head",
            "base_commit": "basec",
            "head_commit": "headc",
            "telemetry_artifact": "telemetry_matrix.json",
            "occupancy_artifact": "occupancy_snapshot.json",
        },
        "inputs": {
            "mode": "deterministic_conservative",
            "occupancy_inclusion_policy": "include_all",
            "chao1_variant": "bias_corrected",
            "ice_rare_threshold": 10,
            "selection_policy": "max_hidden",
            "sparse_guard_policy": "enabled",
            "round_digits": 6,
        },
        "counts": {
            "defect_rows": 0,
            "included_rows": 0,
            "excluded_rows": 0,
            "k_eff_global": 0,
            "f1": 0,
            "f2": 0,
            "incidence_histogram": {},
            "ice": {
                "rare_threshold": 10,
                "rare_count": 0,
                "frequent_count": 0,
                "q1": 0,
                "q2": 0,
                "sample_coverage": 1.0,
            },
        },
        "estimators": {
            "chao1": {
                "observed": 0,
                "hidden": 0.0,
                "total": 0.0,
                "formula_variant": "bias_corrected",
                "guard_applied": True,
                "inputs": {"f1": 0, "f2": 0},
            },
            "ice": {
                "observed": 0,
                "hidden": 0.0,
                "total": 0.0,
                "rare_threshold": 10,
                "sample_coverage": 1.0,
                "formula_variant": "no_rare_rows",
                "guard_applied": True,
                "inputs": {
                    "rare_count": 0,
                    "frequent_count": 0,
                    "q1": 0,
                    "q2": 0,
                    "gamma_sq": 0.0,
                },
            },
            "selected_method": "max_hidden",
            "selected_source": "tie",
            "selected_hidden": 0.0,
            "selected_total": 0.0,
        },
        "summary": {
            "observed_defects": 0,
            "selected_hidden": 0.0,
            "selected_total": 0.0,
            "selected_method": "max_hidden",
            "sparse_data": True,
            "low_doubleton_support": True,
            "ice_low_coverage": False,
            "estimator_guard_applied": True,
            "global_k_eff": 0,
            "mean_psi_post": 0.0,
        },
        "provenance": {
            "algorithm": "capture_estimate_v1",
            "deterministic": True,
            "inputs": ["telemetry_matrix.json", "occupancy_snapshot.json"],
            "inclusion_policy": "include_all",
            "selection_policy": "max_hidden",
        },
    }


def test_hazard_map_stage_emits_rows_summary_and_tier() -> None:
    cfg = normalize_config({})
    out = run_stage(
        repo_path=Path("/tmp/repo"),
        base_ref="base",
        head_ref="head",
        run_id="run",
        config=cfg,
        risk_heatmap_artifact=_risk_artifact(),
        telemetry_matrix_artifact=_telemetry_artifact_repeat_supported(),
        occupancy_snapshot_artifact=_occupancy_artifact_repeat_supported(),
        capture_estimate_artifact=_capture_artifact(cfg),
    )

    assert out["kind"] == "hazard_map"
    assert out["artifact_version"] == 1
    assert len(out["rows"]) == 4
    assert 0.0 <= out["summary"]["hazard_score"] <= 1.0
    assert out["summary"]["hazard_tier"] in {
        "low",
        "guarded",
        "elevated",
        "high",
        "critical",
    }
    assert out["inputs"]["hidden_selection_policy"] == "max_hidden"

    rows = {row["defect_key"]: row for row in out["rows"]}
    critical_row = rows["dfk_" + ("d" * 64)]
    medium_row = rows["dfk_" + ("a" * 64)]
    assert critical_row["hazard_contribution"] > medium_row["hazard_contribution"]
    assert "critical_severity" in critical_row["hazard_flags"]
    assert out["summary"]["defect_count"] == 4
    assert (
        out["summary"]["selected_hidden"]
        == _capture_artifact(cfg)["summary"]["selected_hidden"]
    )


def test_hazard_map_allows_zero_defect_rows_and_preserves_uncertainty() -> None:
    cfg = normalize_config({})
    out = run_stage(
        repo_path=Path("/tmp/repo"),
        base_ref="base",
        head_ref="head",
        run_id="run",
        config=cfg,
        risk_heatmap_artifact=_risk_artifact(),
        telemetry_matrix_artifact=_telemetry_artifact_no_defects(),
        occupancy_snapshot_artifact=_occupancy_artifact_no_defects(),
        capture_estimate_artifact=_capture_artifact_no_defects(),
    )

    assert out["rows"] == []
    assert out["summary"]["defect_count"] == 0
    assert out["summary"]["base_hazard_score"] == 0.0
    assert out["summary"]["uncertainty_flags"] == [
        "sparse_capture_data",
        "low_doubleton_support",
        "estimator_guard_applied",
        "low_global_k_eff",
    ]


@pytest.mark.parametrize(
    ("score", "expected"),
    [
        (0.00, "low"),
        (0.19, "low"),
        (0.20, "guarded"),
        (0.40, "elevated"),
        (0.60, "high"),
        (0.80, "critical"),
        (1.00, "critical"),
    ],
)
def test_hazard_map_tier_mapping_thresholds(score: float, expected: str) -> None:
    assert map_hazard_tier(score) == expected


def test_hazard_map_missing_risk_mapping_fails_closed() -> None:
    cfg = normalize_config({})
    risk = _risk_artifact()
    risk["targets"] = [
        target for target in risk["targets"] if target["file_path"] != "d.py"
    ]

    with pytest.raises(StageError):
        run_stage(
            repo_path=Path("/tmp/repo"),
            base_ref="base",
            head_ref="head",
            run_id="run",
            config=cfg,
            risk_heatmap_artifact=risk,
            telemetry_matrix_artifact=_telemetry_artifact_repeat_supported(),
            occupancy_snapshot_artifact=_occupancy_artifact_repeat_supported(),
            capture_estimate_artifact=_capture_artifact(cfg),
        )


def test_hazard_map_run_id_mismatch_fails_closed() -> None:
    cfg = normalize_config({})
    capture = _capture_artifact(cfg)
    capture["run"]["run_id"] = "other-run"

    with pytest.raises(StageError):
        run_stage(
            repo_path=Path("/tmp/repo"),
            base_ref="base",
            head_ref="head",
            run_id="run",
            config=cfg,
            risk_heatmap_artifact=_risk_artifact(),
            telemetry_matrix_artifact=_telemetry_artifact_repeat_supported(),
            occupancy_snapshot_artifact=_occupancy_artifact_repeat_supported(),
            capture_estimate_artifact=capture,
        )


def test_hazard_map_commit_mismatch_fails_closed() -> None:
    cfg = normalize_config({})
    occupancy = _occupancy_artifact_repeat_supported()
    occupancy["run"]["head_commit"] = "other-head"

    with pytest.raises(StageError):
        run_stage(
            repo_path=Path("/tmp/repo"),
            base_ref="base",
            head_ref="head",
            run_id="run",
            config=cfg,
            risk_heatmap_artifact=_risk_artifact(),
            telemetry_matrix_artifact=_telemetry_artifact_repeat_supported(),
            occupancy_snapshot_artifact=occupancy,
            capture_estimate_artifact=_capture_artifact(cfg),
        )


def test_hazard_map_inconsistent_defect_sets_fail_closed() -> None:
    cfg = normalize_config({})
    occupancy = _occupancy_artifact_repeat_supported()
    occupancy["rows"] = occupancy["rows"][:-1]

    with pytest.raises(StageError):
        run_stage(
            repo_path=Path("/tmp/repo"),
            base_ref="base",
            head_ref="head",
            run_id="run",
            config=cfg,
            risk_heatmap_artifact=_risk_artifact(),
            telemetry_matrix_artifact=_telemetry_artifact_repeat_supported(),
            occupancy_snapshot_artifact=occupancy,
            capture_estimate_artifact=_capture_artifact(cfg),
        )


def test_hazard_map_invalid_model_version_fails_closed() -> None:
    cfg = normalize_config({})
    cfg["hazard_model_version"] = "hazard_revX"

    with pytest.raises(StageError):
        run_stage(
            repo_path=Path("/tmp/repo"),
            base_ref="base",
            head_ref="head",
            run_id="run",
            config=cfg,
            risk_heatmap_artifact=_risk_artifact(),
            telemetry_matrix_artifact=_telemetry_artifact_repeat_supported(),
            occupancy_snapshot_artifact=_occupancy_artifact_repeat_supported(),
            capture_estimate_artifact=_capture_artifact(normalize_config({})),
        )
