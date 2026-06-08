from __future__ import annotations

from pathlib import Path

import pytest

from forge_eval.config import normalize_config
from forge_eval.errors import StageError
from forge_eval.stages.merge_decision import run_stage


def _hazard_artifact(
    *,
    hazard_score: float = 0.55,
    hazard_tier: str = "elevated",
    blocking_signals_present: bool = False,
    hidden_pressure: float = 0.20,
    uncertainty_flags: list[str] | None = None,
) -> dict[str, object]:
    return {
        "artifact_version": 1,
        "kind": "hazard_map",
        "run": {
            "run_id": "run",
            "repo_path": "/tmp/repo",
            "base_ref": "base",
            "head_ref": "head",
            "base_commit": "basec",
            "head_commit": "headc",
            "risk_artifact": "risk_heatmap.json",
            "telemetry_artifact": "telemetry_matrix.json",
            "occupancy_artifact": "occupancy_snapshot.json",
            "capture_artifact": "capture_estimate.json",
        },
        "inputs": {
            "mode": "deterministic_conservative",
            "risk_artifact": "risk_heatmap.json",
            "telemetry_artifact": "telemetry_matrix.json",
            "occupancy_artifact": "occupancy_snapshot.json",
            "capture_artifact": "capture_estimate.json",
            "hidden_selection_policy": "max_hidden",
            "round_digits": 6,
        },
        "summary": {
            "hazard_score": hazard_score,
            "hazard_tier": hazard_tier,
            "defect_count": 2,
            "observed_defects": 2,
            "selected_hidden": 1.0,
            "selected_total": 3.0,
            "mean_psi_post": 0.78,
            "max_risk_score": 0.81,
            "max_hazard_contribution": 0.62,
            "hidden_pressure": hidden_pressure,
            "base_hazard_score": 0.51,
            "hidden_uplift": 0.06,
            "uncertainty_uplift": 0.04,
            "blocking_signals_present": blocking_signals_present,
            "blocking_reason_flags": ["hidden_pressure_on_high_risk_surface"]
            if blocking_signals_present
            else [],
            "uncertainty_flags": list(uncertainty_flags or []),
        },
        "rows": [
            {
                "defect_key": "dfk_" + ("a" * 64),
                "file_path": "a.py",
                "category": "correctness",
                "severity": "high",
                "reported_by": ["r1"],
                "support_count": 1,
                "observed_by": 1,
                "missed_by": 0,
                "null_by": 0,
                "k_eff_defect": 1,
                "psi_post": 0.72,
                "local_risk_score": 0.81,
                "severity_weight": 0.35,
                "occupancy_uplift": 0.09,
                "structural_risk_uplift": 0.08,
                "support_uplift": 0.0,
                "hazard_contribution": 0.52,
                "hazard_flags": ["high_severity", "high_structural_risk"],
            }
        ],
        "model": {
            "name": "hazard_rev1",
            "mode": "deterministic_conservative",
            "row_policy": "severity_plus_uplifts_v1",
            "summary_policy": "bounded_union_hidden_uncertainty_v1",
            "parameters": {
                "hazard_round_digits": 6,
                "hazard_hidden_uplift_strength": 0.2,
                "hazard_structural_risk_strength": 0.3,
                "hazard_occupancy_strength": 0.35,
                "hazard_support_uplift_strength": 0.15,
                "hazard_uncertainty_boost": 0.12,
                "hazard_blocking_threshold": 0.8,
                "severity_weights": {
                    "low": 0.08,
                    "medium": 0.18,
                    "high": 0.35,
                    "critical": 0.55,
                },
            },
            "thresholds": {
                "tier_floors": {
                    "low": 0.0,
                    "guarded": 0.2,
                    "elevated": 0.4,
                    "high": 0.6,
                    "critical": 0.8,
                }
            },
        },
        "provenance": {
            "algorithm": "hazard_map_v1",
            "deterministic": True,
            "inputs": [
                "risk_heatmap.json",
                "telemetry_matrix.json",
                "occupancy_snapshot.json",
                "capture_estimate.json",
            ],
            "model_version": "hazard_rev1",
        },
    }


def test_merge_decision_blocks_on_hazard_blocking_signal() -> None:
    cfg = normalize_config({})
    artifact = run_stage(
        repo_path=Path("/tmp/repo"),
        base_ref="base",
        head_ref="head",
        run_id="run",
        config=cfg,
        hazard_map_artifact=_hazard_artifact(blocking_signals_present=True),
    )
    assert artifact["decision"]["result"] == "block"
    assert "HAZARD_BLOCKING_SIGNAL_PRESENT" in artifact["reason_codes"]


def test_merge_decision_cautions_on_elevated_hazard() -> None:
    cfg = normalize_config({})
    artifact = run_stage(
        repo_path=Path("/tmp/repo"),
        base_ref="base",
        head_ref="head",
        run_id="run",
        config=cfg,
        hazard_map_artifact=_hazard_artifact(
            hazard_score=0.45,
            hazard_tier="elevated",
            blocking_signals_present=False,
            uncertainty_flags=["null_heavy_occupancy"],
        ),
    )
    assert artifact["decision"]["result"] == "caution"
    assert artifact["summary"]["decision_label"] == "CAUTION"
    assert "HAZARD_TIER_ELEVATED" in artifact["reason_codes"]


def test_merge_decision_allows_low_clean_hazard() -> None:
    cfg = normalize_config({})
    artifact = run_stage(
        repo_path=Path("/tmp/repo"),
        base_ref="base",
        head_ref="head",
        run_id="run",
        config=cfg,
        hazard_map_artifact=_hazard_artifact(
            hazard_score=0.12,
            hazard_tier="low",
            blocking_signals_present=False,
            hidden_pressure=0.0,
            uncertainty_flags=[],
        ),
    )
    assert artifact["decision"]["result"] == "allow"
    assert artifact["reason_codes"] == []


def test_merge_decision_run_id_mismatch_fails_closed() -> None:
    cfg = normalize_config({})
    with pytest.raises(StageError, match="run_id mismatch"):
        run_stage(
            repo_path=Path("/tmp/repo"),
            base_ref="base",
            head_ref="head",
            run_id="other",
            config=cfg,
            hazard_map_artifact=_hazard_artifact(),
        )


def test_merge_decision_missing_summary_field_fails_closed() -> None:
    cfg = normalize_config({})
    hazard = _hazard_artifact()
    del hazard["summary"]["hazard_score"]  # type: ignore[index]
    with pytest.raises(StageError, match="summary missing required field"):
        run_stage(
            repo_path=Path("/tmp/repo"),
            base_ref="base",
            head_ref="head",
            run_id="run",
            config=cfg,
            hazard_map_artifact=hazard,
        )


def test_merge_decision_invalid_hazard_tier_fails_closed() -> None:
    cfg = normalize_config({})
    with pytest.raises(StageError, match="supported hazard tier"):
        run_stage(
            repo_path=Path("/tmp/repo"),
            base_ref="base",
            head_ref="head",
            run_id="run",
            config=cfg,
            hazard_map_artifact=_hazard_artifact(hazard_tier="severe"),
        )


def test_merge_decision_unsupported_model_version_fails_closed() -> None:
    cfg = normalize_config({})
    cfg["merge_decision_model_version"] = "merge_revX"
    with pytest.raises(StageError, match="unsupported merge decision model version"):
        run_stage(
            repo_path=Path("/tmp/repo"),
            base_ref="base",
            head_ref="head",
            run_id="run",
            config=cfg,
            hazard_map_artifact=_hazard_artifact(),
        )
