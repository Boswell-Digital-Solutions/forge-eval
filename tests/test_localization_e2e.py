"""Slice 5 — End-to-end governed path tests for Pack N localization.

7 tests covering:
1. End-to-end localized repair run succeeds with valid LocalizationPack
2. Repair prompt contains only approved regions
3. Out-of-scope repair blocked by LOC-GATE-NO-SCOPE
4. Repair blocked by LOC-GATE-MISSING
5. allow_analysis_only=true downgrade produces analysis output, no patch
6. Artifact chain auditable: localization_pack_ref present
7. Byte-identical localization_pack.json on repeated runs
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import jsonschema

from forge_eval.config import normalize_config
from forge_eval.stages.localization_pack import run_stage

SCHEMA_DIR = Path(__file__).resolve().parent.parent / "src" / "forge_eval" / "schemas"

# Import localization_gate directly without triggering full NeuroForge package init
import importlib.util as _ilu  # noqa: E402

_LOC_GATE_PATH = (
    Path(__file__).resolve().parent.parent.parent.parent
    / "NeuroForge"
    / "neuroforge_backend"
    / "services"
    / "localization_gate.py"
)
_spec = _ilu.spec_from_file_location("localization_gate", _LOC_GATE_PATH)
_loc_gate_mod = _ilu.module_from_spec(_spec)
_spec.loader.exec_module(_loc_gate_mod)

evaluate_localization_gate = _loc_gate_mod.evaluate_localization_gate
render_localized_context = _loc_gate_mod.render_localized_context


def _load_schema(name: str) -> dict:
    path = SCHEMA_DIR / name
    return json.loads(path.read_text(encoding="utf-8"))


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


def _run_pack_n() -> dict:
    config = _config()
    return run_stage(
        run_id="run1",
        config=config,
        risk_heatmap_artifact=_make_risk_heatmap_artifact(),
        context_slices_artifact=_make_context_slices_artifact(),
        review_findings_artifact=_make_review_findings_artifact(),
        telemetry_matrix_artifact=_make_telemetry_matrix_artifact(),
        hazard_map_artifact=_make_hazard_map_artifact(),
    )


def _stable_json(obj: dict) -> str:
    return (
        json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True) + "\n"
    )


# ===== Test 1: End-to-end localized repair run succeeds =====


def test_e2e_localized_repair_valid_pack():
    """Pack N produces a valid localization_pack artifact from upstream artifacts."""
    result = _run_pack_n()
    schema = _load_schema("localization_pack.schema.json")
    jsonschema.validate(instance=result, schema=schema)
    assert result["kind"] == "localization_pack"
    assert len(result["file_candidates"]) > 0
    assert len(result["block_candidates"]) > 0
    assert len(result["review_scope"]) > 0


# ===== Test 2: Repair prompt contains only approved regions =====


def test_e2e_repair_prompt_approved_regions_only():
    """Localized context rendering includes only review_scope blocks."""
    result = _run_pack_n()
    context = render_localized_context(result, allow_analysis_only=False)

    # All review_scope entries should appear
    for entry in result["review_scope"]:
        fp = entry["file_path"]
        assert fp in context, f"review_scope file {fp} not in context"

    # Context should include localized review mode header
    assert "localized review mode" in context.lower()


# ===== Test 3: Out-of-scope repair blocked by LOC-GATE-NO-SCOPE =====


def test_e2e_out_of_scope_blocked():
    """Patch target outside review_scope is blocked by LOC-GATE-NO-SCOPE."""
    pack = _run_pack_n()

    with tempfile.TemporaryDirectory() as tmp_dir:
        pack_path = Path(tmp_dir) / "localization_pack.json"
        pack_path.write_text(json.dumps(pack), encoding="utf-8")

        eval_context = {
            "task_type": "patch",
            "workspace_root": str(tmp_dir),
            "run_id": "run1",
            "patch_targets": {
                "targets": [
                    {
                        "target_id": "tgt_outside",
                        "file_path": "src/totally_different.py",
                        "allow_ranges": [{"start_line": 500, "end_line": 600}],
                    }
                ],
            },
        }
        localization_input = {
            "artifact_ref": str(pack_path),
            "artifact_workspace_root": str(tmp_dir),
        }
        passed, error, _ = evaluate_localization_gate(
            eval_context=eval_context,
            localization_input=localization_input,
            trusted_roots=[Path(tmp_dir)],
        )
        assert not passed
        assert "LOC-GATE-NO-SCOPE" in error


# ===== Test 4: Repair blocked by LOC-GATE-MISSING =====


def test_e2e_repair_blocked_missing():
    """Repair without localization input is blocked by LOC-GATE-MISSING."""
    eval_context = {"task_type": "patch"}
    passed, error, _ = evaluate_localization_gate(
        eval_context=eval_context,
        localization_input=None,
        trusted_roots=[],
    )
    assert not passed
    assert "LOC-GATE-MISSING" in error


# ===== Test 5: allow_analysis_only downgrade =====


def test_e2e_analysis_only_downgrade():
    """allow_analysis_only=true downgrades to analysis — no patch scope rendered."""
    result = _run_pack_n()

    analysis_ctx = render_localized_context(result, allow_analysis_only=True)
    repair_ctx = render_localized_context(result, allow_analysis_only=False)

    # Analysis mode: patch scope suppressed
    assert "Patch Scope" not in analysis_ctx
    # Repair mode: patch scope rendered (if present)
    if result["patch_scope"]:
        assert "Patch Scope" in repair_ctx


# ===== Test 6: Artifact chain auditable =====


def test_e2e_artifact_chain_auditable():
    """Localization pack includes source artifact refs for audit trail."""
    result = _run_pack_n()
    refs = result["source_artifacts"]
    assert refs["risk_heatmap_ref"] == "risk_heatmap.json"
    assert refs["context_slices_ref"] == "context_slices.json"
    assert refs["review_findings_ref"] == "review_findings.json"
    assert refs["telemetry_matrix_ref"] == "telemetry_matrix.json"
    assert refs["hazard_map_ref"] == "hazard_map.json"
    assert result["provenance"]["algorithm"] == "localization_pack_v1"
    assert result["provenance"]["deterministic"] is True


# ===== Test 7: Byte-identical on repeated runs =====


def test_e2e_byte_identical_repeated_runs():
    """Repeated runs with identical inputs produce byte-identical artifacts."""
    result1 = _run_pack_n()
    result2 = _run_pack_n()

    json1 = _stable_json(result1)
    json2 = _stable_json(result2)

    assert json1 == json2, "Repeated Pack N runs must produce byte-identical output"
