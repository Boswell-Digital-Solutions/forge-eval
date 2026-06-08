from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from forge_eval.config import normalize_config
from forge_eval.errors import StageError, ValidationError
from forge_eval.services.capture_selection import select_hidden_estimate
from forge_eval.services.chao2 import estimate_chao2
from forge_eval.stages.capture_estimate import run_stage
from forge_eval.validation.schema_loader import load_all_schemas
from forge_eval.validation.validate_artifact import validate_instance


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


def _telemetry_artifact_singleton_heavy() -> dict[str, object]:
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
                "findings_emitted": 3,
                "slices_seen": 3,
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
                "findings_emitted": 0,
                "slices_seen": 3,
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
                "findings_emitted": 0,
                "slices_seen": 3,
                "error": None,
            },
        ],
        "defects": [
            {
                "defect_key": "dfk_" + ("1" * 64),
                "file_path": "one.py",
                "category": "correctness",
                "severity": "medium",
                "reported_by": ["r1"],
                "support_count": 1,
            },
            {
                "defect_key": "dfk_" + ("2" * 64),
                "file_path": "two.py",
                "category": "correctness",
                "severity": "medium",
                "reported_by": ["r1"],
                "support_count": 1,
            },
            {
                "defect_key": "dfk_" + ("3" * 64),
                "file_path": "three.py",
                "category": "risk",
                "severity": "high",
                "reported_by": ["r1"],
                "support_count": 1,
            },
        ],
        "matrix": [
            {
                "defect_key": "dfk_" + ("1" * 64),
                "observations": {"r1": 1, "r2": 0, "r3": None},
                "k_eff_defect": 2,
            },
            {
                "defect_key": "dfk_" + ("2" * 64),
                "observations": {"r1": 1, "r2": None, "r3": None},
                "k_eff_defect": 1,
            },
            {
                "defect_key": "dfk_" + ("3" * 64),
                "observations": {"r1": 1, "r2": 0, "r3": 0},
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
            "defect_count": 3,
            "matrix_rows": 3,
            "cells_observed": 3,
            "cells_missed": 3,
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


def _occupancy_artifact_singleton_heavy() -> dict[str, object]:
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
                "defect_key": "dfk_" + ("1" * 64),
                "psi_post": 0.71,
                "observed_by": 1,
                "missed_by": 1,
                "null_by": 1,
                "k_eff_defect": 2,
                "support_count": 1,
                "evidence_strength": "moderate",
                "inputs": {
                    "prior": 0.7,
                    "detection_assumption": 0.7,
                    "coverage_ratio": 0.666667,
                    "miss_penalty": 0.116667,
                    "uncertainty_guard": 0.033333,
                },
            },
            {
                "defect_key": "dfk_" + ("2" * 64),
                "psi_post": 0.69,
                "observed_by": 1,
                "missed_by": 0,
                "null_by": 2,
                "k_eff_defect": 1,
                "support_count": 1,
                "evidence_strength": "moderate",
                "inputs": {
                    "prior": 0.7,
                    "detection_assumption": 0.7,
                    "coverage_ratio": 0.333333,
                    "miss_penalty": 0.0,
                    "uncertainty_guard": 0.133333,
                },
            },
            {
                "defect_key": "dfk_" + ("3" * 64),
                "psi_post": 0.78,
                "observed_by": 1,
                "missed_by": 2,
                "null_by": 0,
                "k_eff_defect": 3,
                "support_count": 1,
                "evidence_strength": "moderate",
                "inputs": {
                    "prior": 0.75,
                    "detection_assumption": 0.7,
                    "coverage_ratio": 1.0,
                    "miss_penalty": 0.233333,
                    "uncertainty_guard": 0.0,
                },
            },
        ],
        "summary": {
            "defect_rows": 3,
            "rows_with_positive_observation": 3,
            "rows_with_nulls": 2,
            "mean_psi_post": 0.726667,
            "max_psi_post": 0.78,
            "min_psi_post": 0.69,
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


def test_capture_estimate_emits_estimators_counts_and_selection() -> None:
    cfg = normalize_config({})
    out = run_stage(
        repo_path=Path("/tmp/repo"),
        base_ref="base",
        head_ref="head",
        run_id="run",
        config=cfg,
        telemetry_matrix_artifact=_telemetry_artifact_repeat_supported(),
        occupancy_snapshot_artifact=_occupancy_artifact_repeat_supported(),
    )

    assert out["kind"] == "capture_estimate"
    assert out["counts"]["f1"] == 2
    assert out["counts"]["f2"] == 1
    assert out["counts"]["incidence_histogram"] == {"1": 2, "2": 1, "3": 1}
    assert out["estimators"]["chao1"]["hidden"] == 0.5
    assert out["estimators"]["ice"]["hidden"] > out["estimators"]["chao1"]["hidden"]
    assert out["estimators"]["selection_policy"] == "max_hidden"
    assert out["estimators"]["selected_method"] == "max_hidden"
    assert out["estimators"]["selected_source"] == "ice"
    assert out["estimators"]["selected_hidden"] == out["estimators"]["ice"]["hidden"]
    assert out["estimators"]["chao2"]["available"] is True
    assert out["estimators"]["chao2"]["hidden_estimate"] is not None
    assert out["estimators"]["unavailable_estimators"] == []
    assert out["summary"]["selected_hidden"] == out["estimators"]["selected_hidden"]
    assert out["summary"]["selection_policy"] == "max_hidden"
    assert out["summary"]["selected_method"] == "ice"
    assert out["summary"]["unavailable_estimators"] == []


def test_capture_estimate_singleton_heavy_inflates_hidden_more_than_repeat_supported() -> (
    None
):
    cfg = normalize_config({})
    repeat_supported = run_stage(
        repo_path=Path("/tmp/repo"),
        base_ref="base",
        head_ref="head",
        run_id="run",
        config=cfg,
        telemetry_matrix_artifact=_telemetry_artifact_repeat_supported(),
        occupancy_snapshot_artifact=_occupancy_artifact_repeat_supported(),
    )
    singleton_heavy = run_stage(
        repo_path=Path("/tmp/repo"),
        base_ref="base",
        head_ref="head",
        run_id="run",
        config=cfg,
        telemetry_matrix_artifact=_telemetry_artifact_singleton_heavy(),
        occupancy_snapshot_artifact=_occupancy_artifact_singleton_heavy(),
    )

    assert singleton_heavy["counts"]["f1"] == 3
    assert singleton_heavy["counts"]["f2"] == 0
    assert singleton_heavy["estimators"]["chao1"]["guard_applied"] is True
    assert singleton_heavy["estimators"]["ice"]["guard_applied"] is True
    assert (
        singleton_heavy["estimators"]["selected_hidden"]
        > repeat_supported["estimators"]["selected_hidden"]
    )
    assert singleton_heavy["summary"]["low_doubleton_support"] is True
    assert singleton_heavy["summary"]["sparse_data"] is True


def test_capture_estimate_inconsistent_defect_sets_fail_closed() -> None:
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
            telemetry_matrix_artifact=_telemetry_artifact_repeat_supported(),
            occupancy_snapshot_artifact=occupancy,
        )


def test_capture_estimate_invalid_selection_policy_fails_closed() -> None:
    cfg = normalize_config({})
    cfg["capture_selection_policy"] = "smallest_hidden"

    with pytest.raises(StageError):
        run_stage(
            repo_path=Path("/tmp/repo"),
            base_ref="base",
            head_ref="head",
            run_id="run",
            config=cfg,
            telemetry_matrix_artifact=_telemetry_artifact_repeat_supported(),
            occupancy_snapshot_artifact=_occupancy_artifact_repeat_supported(),
        )


def test_capture_estimate_mismatched_occupancy_counts_fail_closed() -> None:
    cfg = normalize_config({})
    occupancy = _occupancy_artifact_repeat_supported()
    occupancy["rows"][0]["observed_by"] = 2

    with pytest.raises(StageError):
        run_stage(
            repo_path=Path("/tmp/repo"),
            base_ref="base",
            head_ref="head",
            run_id="run",
            config=cfg,
            telemetry_matrix_artifact=_telemetry_artifact_repeat_supported(),
            occupancy_snapshot_artifact=occupancy,
        )


# ---------------------------------------------------------------------------
# Chao2 revision tests (10 required)
# ---------------------------------------------------------------------------


def _run_stage_default(
    telemetry: dict | None = None,
    occupancy: dict | None = None,
) -> dict:
    cfg = normalize_config({})
    return run_stage(
        repo_path=Path("/tmp/repo"),
        base_ref="base",
        head_ref="head",
        run_id="run",
        config=cfg,
        telemetry_matrix_artifact=telemetry or _telemetry_artifact_repeat_supported(),
        occupancy_snapshot_artifact=occupancy or _occupancy_artifact_repeat_supported(),
    )


def test_chao2_positive_calculation() -> None:
    """Test 1: Chao2 positive calculation — valid Q1, Q2, m produce correct hidden estimate."""
    # q1=2, q2=1, m=3 -> hidden = ((3-1)/3) * (2^2 / (2*1)) = (2/3)*2 = 1.333333
    result = estimate_chao2(observed=4, q1=2, q2=1, m=3, round_digits=6)
    assert result["available"] is True
    assert result["enabled"] is True
    assert result["hidden_estimate"] == 1.333333
    assert result["total_estimate"] == 5.333333
    assert result["guard_flags"]["q2_zero_fallback"] is False
    assert result["guard_flags"]["q1_zero_no_signal"] is False
    assert result["inputs_used"] == {"q1": 2, "q2": 1, "m": 3}
    assert result["reason_unavailable"] is None


def test_chao2_q2_zero_guard() -> None:
    """Test 2: Chao2 Q2=0 guard — uses fallback formula and sets guard flag."""
    # q1=3, q2=0, m=3 -> hidden = ((3-1)/3) * (3*(3-1)/2) = (2/3)*3 = 2.0
    result = estimate_chao2(observed=3, q1=3, q2=0, m=3, round_digits=6)
    assert result["available"] is True
    assert result["hidden_estimate"] == 2.0
    assert result["total_estimate"] == 5.0
    assert result["guard_flags"]["q2_zero_fallback"] is True
    assert result["guard_flags"]["q1_zero_no_signal"] is False


def test_chao2_unavailable_low_m() -> None:
    """Test 3: Chao2 unavailable — m < 2 marks unavailable with explicit reason."""
    result = estimate_chao2(observed=4, q1=2, q2=1, m=1, round_digits=6)
    assert result["available"] is False
    assert result["hidden_estimate"] is None
    assert result["total_estimate"] is None
    assert "m < 2" in result["reason_unavailable"]
    assert result["enabled"] is True


def test_selection_policy_chao2_wins() -> None:
    """Test 4: Selection policy — Chao2 wins when it has highest hidden estimate."""
    chao1 = {"hidden": 1.0, "total": 5.0, "observed": 4}
    chao2 = {"available": True, "hidden_estimate": 3.0, "total_estimate": 7.0}
    ice = {"hidden": 2.0, "total": 6.0, "observed": 4}
    sel = select_hidden_estimate(
        observed=4,
        chao1=chao1,
        chao2=chao2,
        ice=ice,
        selection_policy="max_hidden",
        round_digits=6,
    )
    assert sel["selected_source"] == "chao2"
    assert sel["selected_hidden"] == 3.0
    assert sel["selection_policy"] == "max_hidden"
    assert sel["selected_method"] == "max_hidden"
    assert sel["unavailable_estimators"] == []


def test_selection_policy_chao1_wins() -> None:
    """Test 5: Selection policy — Chao1 wins when it has highest hidden estimate."""
    chao1 = {"hidden": 5.0, "total": 9.0, "observed": 4}
    chao2 = {"available": True, "hidden_estimate": 2.0, "total_estimate": 6.0}
    ice = {"hidden": 3.0, "total": 7.0, "observed": 4}
    sel = select_hidden_estimate(
        observed=4,
        chao1=chao1,
        chao2=chao2,
        ice=ice,
        selection_policy="max_hidden",
        round_digits=6,
    )
    assert sel["selected_source"] == "chao1"
    assert sel["selected_hidden"] == 5.0


def test_selection_policy_ice_wins() -> None:
    """Test 6: Selection policy — ICE wins when it has highest hidden estimate."""
    out = _run_stage_default()
    # In repeat_supported: ICE hidden > Chao2 hidden > Chao1 hidden
    assert out["estimators"]["selected_source"] == "ice"
    assert out["estimators"]["selected_hidden"] == out["estimators"]["ice"]["hidden"]


def test_unavailable_estimator_recording() -> None:
    """Test 7: Unavailable estimator recording — Chao2 unavailable appears in list."""
    telemetry = _telemetry_artifact_repeat_supported()
    telemetry["summary"]["k_usable"] = 1  # m < 2 -> Chao2 unavailable
    telemetry["summary"]["k_eff"] = 1
    out = _run_stage_default(telemetry=telemetry)
    assert out["estimators"]["chao2"]["available"] is False
    assert out["estimators"]["chao2"]["reason_unavailable"] is not None
    assert "chao2" in out["estimators"]["unavailable_estimators"]
    assert "chao2" in out["summary"]["unavailable_estimators"]
    # Stage still succeeds — Chao1 and ICE are available
    assert out["estimators"]["selected_source"] in ("chao1", "ice", "tie")


def test_chao2_schema_validation_accepts_valid() -> None:
    """Test 8: Schema validation — revised capture_estimate.json validates against schema."""
    schemas = load_all_schemas()
    out = _run_stage_default()
    validate_instance(
        out, schemas["capture_estimate"], artifact_kind="capture_estimate"
    )


def test_chao2_schema_validation_rejects_malformed() -> None:
    """Test 9: Schema rejection — malformed Chao2 block fails schema validation."""
    schemas = load_all_schemas()
    out = _run_stage_default()
    broken = copy.deepcopy(out)
    del broken["estimators"]["chao2"]["guard_flags"]
    with pytest.raises(ValidationError):
        validate_instance(
            broken, schemas["capture_estimate"], artifact_kind="capture_estimate"
        )


def test_chao2_determinism() -> None:
    """Test 10: Determinism — identical inputs produce byte-identical output."""
    out1 = _run_stage_default()
    out2 = _run_stage_default()
    json1 = json.dumps(out1, sort_keys=True, separators=(",", ":"))
    json2 = json.dumps(out2, sort_keys=True, separators=(",", ":"))
    assert json1 == json2
