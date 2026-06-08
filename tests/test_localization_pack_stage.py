from __future__ import annotations

import json
from pathlib import Path

import jsonschema
import pytest

from forge_eval.config import normalize_config
from forge_eval.errors import StageError
from forge_eval.stages.localization_pack import run_stage

SCHEMA_DIR = Path(__file__).resolve().parent.parent / "src" / "forge_eval" / "schemas"


def _load_schema(name: str) -> dict:
    path = SCHEMA_DIR / name
    return json.loads(path.read_text(encoding="utf-8"))


def _make_context_slices_artifact(file_paths: list[str] | None = None) -> dict:
    if file_paths is None:
        file_paths = ["src/main.py", "src/utils.py"]
    slices = []
    for i, fp in enumerate(file_paths):
        slices.append(
            {
                "slice_id": f"slice_{i}",
                "file_path": fp,
                "start_line": 1 + i * 10,
                "end_line": 10 + i * 10,
                "content": "# test content",
                "context_radius": 12,
            }
        )
    return {
        "artifact_version": 1,
        "kind": "context_slices",
        "run_id": "run1",
        "slices": slices,
    }


def _make_review_findings_artifact(file_paths: list[str] | None = None) -> dict:
    if file_paths is None:
        file_paths = ["src/main.py"]
    findings = []
    for i, fp in enumerate(file_paths):
        findings.append(
            {
                "defect_key": f"dfk_{i:064x}",
                "file_path": fp,
                "line": 5 + i * 10,
                "category": "correctness",
                "severity": "medium",
                "reviewer_id": "changed_lines.rule.v1",
                "message": "test finding",
                "confidence": 0.8,
            }
        )
    return {
        "artifact_version": 1,
        "kind": "review_findings",
        "run_id": "run1",
        "findings": findings,
    }


def _make_telemetry_matrix_artifact(file_paths: list[str] | None = None) -> dict:
    if file_paths is None:
        file_paths = ["src/main.py"]
    rows = []
    for i, fp in enumerate(file_paths):
        rows.append(
            {
                "defect_key": f"dfk_{i:064x}",
                "file_path": fp,
                "line": 5 + i * 10,
                "category": "correctness",
                "severity": "medium",
                "reported_by": ["changed_lines.rule.v1"],
                "support_count": 2,
                "observed_by": 2,
                "missed_by": 0,
                "null_by": 1,
                "k_eff_defect": 3,
            }
        )
    return {
        "artifact_version": 1,
        "kind": "telemetry_matrix",
        "run_id": "run1",
        "rows": rows,
    }


def _make_risk_heatmap_artifact(file_paths: list[str] | None = None) -> dict:
    if file_paths is None:
        file_paths = ["src/main.py"]
    targets = []
    for fp in file_paths:
        targets.append(
            {
                "file_path": fp,
                "risk_score": 0.8,
            }
        )
    return {
        "artifact_version": 1,
        "kind": "risk_heatmap",
        "run_id": "run1",
        "targets": targets,
    }


def _make_hazard_map_artifact(file_paths: list[str] | None = None) -> dict:
    if file_paths is None:
        file_paths = ["src/main.py"]
    rows = []
    for i, fp in enumerate(file_paths):
        rows.append(
            {
                "defect_key": f"dfk_{i:064x}",
                "file_path": fp,
                "category": "correctness",
                "severity": "medium",
                "reported_by": ["changed_lines.rule.v1"],
                "support_count": 2,
                "observed_by": 2,
                "missed_by": 0,
                "null_by": 1,
                "k_eff_defect": 3,
                "psi_post": 0.5,
                "local_risk_score": 0.8,
                "severity_weight": 0.5,
                "occupancy_uplift": 0.1,
                "structural_risk_uplift": 0.2,
                "support_uplift": 0.1,
                "hazard_contribution": 0.7,
                "hazard_flags": [],
            }
        )
    return {
        "artifact_version": 1,
        "kind": "hazard_map",
        "run_id": "run1",
        "summary": {
            "hazard_score": 0.6,
            "hazard_tier": "elevated",
            "defect_count": len(file_paths),
            "observed_defects": len(file_paths),
            "selected_hidden": 0.5,
            "selected_total": 1.5,
            "mean_psi_post": 0.5,
            "max_risk_score": 0.8,
            "max_hazard_contribution": 0.7,
            "hidden_pressure": 0.3,
            "base_hazard_score": 0.5,
            "hidden_uplift": 0.05,
            "uncertainty_uplift": 0.05,
            "blocking_signals_present": False,
            "blocking_reason_flags": [],
            "uncertainty_flags": [],
        },
        "rows": rows,
    }


def _config() -> dict:
    return normalize_config(
        {
            "enabled_stages": [
                "risk_heatmap",
                "context_slices",
                "review_findings",
                "telemetry_matrix",
                "occupancy_snapshot",
                "capture_estimate",
                "hazard_map",
                "merge_decision",
                "evidence_bundle",
                "localization_pack",
            ],
        }
    )


def _make_valid_pack() -> dict:
    return {
        "artifact_version": "localization_pack.v1",
        "kind": "localization_pack",
        "run_id": "run1",
        "source_artifacts": {
            "risk_heatmap_ref": "risk_heatmap.json",
            "context_slices_ref": "context_slices.json",
            "review_findings_ref": "review_findings.json",
            "telemetry_matrix_ref": "telemetry_matrix.json",
            "occupancy_snapshot_ref": None,
            "hazard_map_ref": "hazard_map.json",
            "patch_targets_ref": None,
            "concernspans_ref": None,
        },
        "file_candidates": [
            {
                "file_path": "src/main.py",
                "detected_language": "python",
                "detected_framework": "fastapi",
                "score": 0.8,
                "evidence_density": 0.7,
                "confidence": 0.6,
                "reason_codes": ["has_defects"],
                "defect_keys": ["dfk_abc"],
            }
        ],
        "function_candidates": [],
        "block_candidates": [
            {
                "slice_id": "slice_0",
                "file_path": "src/main.py",
                "detected_language": "python",
                "start_line": 1,
                "end_line": 10,
                "score": 0.75,
                "evidence_density": 0.6,
                "confidence": 0.55,
                "defect_keys": ["dfk_abc"],
                "support_count": 2,
                "likely_constructs": ["if_guard", "async_call"],
                "root_cause_hypothesis": "async_race",
                "reason_codes": ["has_defects", "multi_reviewer_support"],
            }
        ],
        "review_scope": [
            {
                "file_path": "src/main.py",
                "start_line": 1,
                "end_line": 10,
            }
        ],
        "patch_scope": [],
        "summary": {
            "summary_confidence": 0.55,
            "evidence_density_mean": 0.6,
            "hazard_tier": "elevated",
            "file_candidate_count": 1,
            "block_candidate_count": 1,
            "review_scope_line_count": 10,
            "patch_scope_present": False,
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


# ===== Test 1: Schema validates correctly shaped artifact =====


def test_localization_pack_schema_valid():
    schema = _load_schema("localization_pack.schema.json")
    pack = _make_valid_pack()
    jsonschema.validate(instance=pack, schema=schema)


# ===== Test 2: Missing required field fails schema validation =====


def test_localization_pack_schema_missing_required_field():
    schema = _load_schema("localization_pack.schema.json")
    pack = _make_valid_pack()
    del pack["run_id"]
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(instance=pack, schema=schema)


# ===== Test 3: additionalProperties violation fails =====


def test_localization_pack_schema_extra_field():
    schema = _load_schema("localization_pack.schema.json")
    pack = _make_valid_pack()
    pack["language"] = "python"
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(instance=pack, schema=schema)


# ===== Test 4: Unknown detected_language fails =====


def test_localization_pack_schema_invalid_language():
    schema = _load_schema("localization_pack.schema.json")
    pack = _make_valid_pack()
    pack["file_candidates"][0]["detected_language"] = "go"
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(instance=pack, schema=schema)


# ===== Test 5: Unknown root_cause_hypothesis fails =====


def test_localization_pack_schema_invalid_hypothesis():
    schema = _load_schema("localization_pack.schema.json")
    pack = _make_valid_pack()
    pack["block_candidates"][0]["root_cause_hypothesis"] = "magic_error"
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(instance=pack, schema=schema)


# ===== Test 6: hazard_tier "medium" fails (wrong vocabulary) =====


def test_localization_pack_schema_wrong_hazard_vocabulary():
    schema = _load_schema("localization_pack.schema.json")
    pack = _make_valid_pack()
    pack["summary"]["hazard_tier"] = "medium"
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(instance=pack, schema=schema)


# ===== Test 7: localization_summary schema validates correctly =====


def test_localization_summary_schema_valid():
    schema = _load_schema("localization_summary.schema.json")
    summary = {
        "artifact_version": "localization_summary.v1",
        "kind": "localization_summary",
        "run_id": "run1",
        "localization_pack_ref": "localization_pack.json",
        "summary_confidence": 0.55,
        "hazard_tier": "elevated",
        "file_candidate_count": 1,
        "block_candidate_count": 1,
        "review_scope_line_count": 10,
        "patch_scope_present": False,
        "top_files": ["src/main.py"],
        "top_reason_codes": ["has_defects"],
        "provenance": {
            "algorithm": "localization_pack_v1",
            "deterministic": True,
        },
    }
    jsonschema.validate(instance=summary, schema=schema)


# ===== Test 8: Stage scaffold runs and emits artifact =====


def test_stage_scaffold_runs():
    config = _config()
    result = run_stage(
        run_id="run1",
        config=config,
        risk_heatmap_artifact=_make_risk_heatmap_artifact(),
        context_slices_artifact=_make_context_slices_artifact(),
        review_findings_artifact=_make_review_findings_artifact(),
        telemetry_matrix_artifact=_make_telemetry_matrix_artifact(),
        hazard_map_artifact=_make_hazard_map_artifact(),
    )
    assert result["kind"] == "localization_pack"
    assert result["artifact_version"] == "localization_pack.v1"
    assert result["run_id"] == "run1"
    assert len(result["file_candidates"]) > 0
    assert result["provenance"]["deterministic"] is True


# ===== Test 9: Emitted artifact validates against schema =====


def test_stage_emitted_artifact_validates():
    config = _config()
    result = run_stage(
        run_id="run1",
        config=config,
        risk_heatmap_artifact=_make_risk_heatmap_artifact(),
        context_slices_artifact=_make_context_slices_artifact(),
        review_findings_artifact=_make_review_findings_artifact(),
        telemetry_matrix_artifact=_make_telemetry_matrix_artifact(),
        hazard_map_artifact=_make_hazard_map_artifact(),
    )
    schema = _load_schema("localization_pack.schema.json")
    jsonschema.validate(instance=result, schema=schema)


# ===== Test 10: Stage fails closed when required upstream missing =====


def test_stage_fails_on_missing_upstream():
    config = _config()
    with pytest.raises(
        StageError, match="localization_pack upstream artifact kind mismatch"
    ):
        run_stage(
            run_id="run1",
            config=config,
            risk_heatmap_artifact={"kind": "wrong"},
            context_slices_artifact=_make_context_slices_artifact(),
            review_findings_artifact=_make_review_findings_artifact(),
            telemetry_matrix_artifact=_make_telemetry_matrix_artifact(),
            hazard_map_artifact=_make_hazard_map_artifact(),
        )
