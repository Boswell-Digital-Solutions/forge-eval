from __future__ import annotations

import json
from pathlib import Path

import pytest

from forge_eval.config import normalize_config
from forge_eval.errors import StageError
from forge_eval.services.localization_ranker import rank_candidates
from forge_eval.services.review_scope_compiler import compile_review_scope
from forge_eval.stages.localization_pack import run_stage

SCHEMA_DIR = Path(__file__).resolve().parent.parent / "src" / "forge_eval" / "schemas"


def _config(**overrides) -> dict:
    raw = {
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
    raw.update(overrides)
    return normalize_config(raw)


def _make_context_slices(file_slices: dict[str, list[tuple[int, int]]]) -> dict:
    slices = []
    idx = 0
    for fp, ranges in sorted(file_slices.items()):
        for start, end in ranges:
            slices.append(
                {
                    "slice_id": f"slice_{idx}",
                    "file_path": fp,
                    "start_line": start,
                    "end_line": end,
                    "content": "# test",
                    "context_radius": 12,
                }
            )
            idx += 1
    return {
        "artifact_version": 1,
        "kind": "context_slices",
        "run_id": "run1",
        "slices": slices,
    }


def _make_review_findings(findings_data: list[dict]) -> dict:
    findings = []
    for fd in findings_data:
        findings.append(
            {
                "defect_key": fd.get("defect_key", f"dfk_{'0' * 64}"),
                "file_path": fd["file_path"],
                "line": fd.get("line", 5),
                "category": fd.get("category", "correctness"),
                "severity": fd.get("severity", "medium"),
                "reviewer_id": fd.get("reviewer_id", "r1"),
                "message": "test",
                "confidence": 0.8,
            }
        )
    return {
        "artifact_version": 1,
        "kind": "review_findings",
        "run_id": "run1",
        "findings": findings,
    }


def _make_telemetry_matrix(rows_data: list[dict]) -> dict:
    rows = []
    for rd in rows_data:
        rows.append(
            {
                "defect_key": rd.get("defect_key", f"dfk_{'0' * 64}"),
                "file_path": rd["file_path"],
                "line": rd.get("line", 5),
                "category": "correctness",
                "severity": "medium",
                "reported_by": ["r1"],
                "support_count": rd.get("support_count", 1),
                "observed_by": 1,
                "missed_by": 0,
                "null_by": 0,
                "k_eff_defect": 1,
            }
        )
    return {
        "artifact_version": 1,
        "kind": "telemetry_matrix",
        "run_id": "run1",
        "rows": rows,
    }


def _make_hazard_map(rows_data: list[dict], hazard_tier: str = "elevated") -> dict:
    rows = []
    for rd in rows_data:
        rows.append(
            {
                "defect_key": rd.get("defect_key", f"dfk_{'0' * 64}"),
                "file_path": rd["file_path"],
                "category": "correctness",
                "severity": "medium",
                "reported_by": ["r1"],
                "support_count": 1,
                "observed_by": 1,
                "missed_by": 0,
                "null_by": 0,
                "k_eff_defect": 1,
                "psi_post": 0.5,
                "local_risk_score": 0.8,
                "severity_weight": 0.5,
                "occupancy_uplift": 0.1,
                "structural_risk_uplift": 0.1,
                "support_uplift": 0.1,
                "hazard_contribution": rd.get("hazard_contribution", 0.5),
                "hazard_flags": [],
            }
        )
    return {
        "artifact_version": 1,
        "kind": "hazard_map",
        "run_id": "run1",
        "summary": {
            "hazard_score": 0.5,
            "hazard_tier": hazard_tier,
            "defect_count": len(rows),
            "observed_defects": len(rows),
            "selected_hidden": 0.3,
            "selected_total": 1.3,
            "mean_psi_post": 0.5,
            "max_risk_score": 0.8,
            "max_hazard_contribution": 0.7,
            "hidden_pressure": 0.2,
            "base_hazard_score": 0.4,
            "hidden_uplift": 0.05,
            "uncertainty_uplift": 0.05,
            "blocking_signals_present": False,
            "blocking_reason_flags": [],
            "uncertainty_flags": [],
        },
        "rows": rows,
    }


# ===== Test 1: File ranking deterministic order =====


def test_file_ranking_deterministic():
    config = _config()
    ctx = _make_context_slices(
        {
            "src/a.py": [(1, 10), (11, 20)],
            "src/b.py": [(1, 10)],
        }
    )
    findings = _make_review_findings(
        [
            {"file_path": "src/a.py", "defect_key": f"dfk_{'a' * 64}", "line": 5},
            {"file_path": "src/a.py", "defect_key": f"dfk_{'b' * 64}", "line": 15},
            {"file_path": "src/b.py", "defect_key": f"dfk_{'c' * 64}", "line": 5},
        ]
    )
    telemetry = _make_telemetry_matrix(
        [
            {"file_path": "src/a.py", "support_count": 3},
            {"file_path": "src/b.py", "support_count": 1},
        ]
    )
    hazard = _make_hazard_map(
        [
            {"file_path": "src/a.py", "hazard_contribution": 0.8},
            {"file_path": "src/b.py", "hazard_contribution": 0.3},
        ]
    )

    fc, bc = rank_candidates(
        config=config,
        context_slices_artifact=ctx,
        review_findings_artifact=findings,
        telemetry_matrix_artifact=telemetry,
        hazard_map_artifact=hazard,
    )
    assert fc[0]["file_path"] == "src/a.py"
    assert fc[0]["score"] >= fc[1]["score"]


# ===== Test 2: Block ranking deterministic order =====


def test_block_ranking_deterministic():
    config = _config()
    ctx = _make_context_slices(
        {
            "src/main.py": [(1, 10), (20, 30)],
        }
    )
    findings = _make_review_findings(
        [
            {"file_path": "src/main.py", "defect_key": f"dfk_{'a' * 64}", "line": 5},
            {"file_path": "src/main.py", "defect_key": f"dfk_{'b' * 64}", "line": 5},
        ]
    )
    telemetry = _make_telemetry_matrix(
        [
            {"file_path": "src/main.py", "support_count": 3, "line": 5},
        ]
    )
    hazard = _make_hazard_map(
        [
            {"file_path": "src/main.py", "hazard_contribution": 0.7},
        ]
    )

    fc, bc = rank_candidates(
        config=config,
        context_slices_artifact=ctx,
        review_findings_artifact=findings,
        telemetry_matrix_artifact=telemetry,
        hazard_map_artifact=hazard,
    )
    assert len(bc) == 2
    assert bc[0]["score"] >= bc[1]["score"]


# ===== Test 3: Tie-breaking stable =====


def test_tiebreaking_stable():
    config = _config()
    ctx = _make_context_slices(
        {
            "src/b.py": [(1, 10)],
            "src/a.py": [(1, 10)],
        }
    )
    findings = _make_review_findings([])
    telemetry = _make_telemetry_matrix([])
    hazard = _make_hazard_map([])

    fc, bc = rank_candidates(
        config=config,
        context_slices_artifact=ctx,
        review_findings_artifact=findings,
        telemetry_matrix_artifact=telemetry,
        hazard_map_artifact=hazard,
    )
    assert fc[0]["file_path"] == "src/a.py"
    assert fc[1]["file_path"] == "src/b.py"


# ===== Test 4: Truncation to max candidates =====


def test_truncation_to_max_candidates():
    config = _config(
        localization_max_file_candidates=2, localization_max_block_candidates=3
    )
    file_slices = {f"src/f{i}.py": [(1, 10)] for i in range(5)}
    ctx = _make_context_slices(file_slices)
    findings = _make_review_findings([])
    telemetry = _make_telemetry_matrix([])
    hazard = _make_hazard_map([])

    fc, bc = rank_candidates(
        config=config,
        context_slices_artifact=ctx,
        review_findings_artifact=findings,
        telemetry_matrix_artifact=telemetry,
        hazard_map_artifact=hazard,
    )
    assert len(fc) == 2
    assert len(bc) <= 3


# ===== Test 5: summary_confidence = min of block confidences =====


def test_summary_confidence_is_min():
    config = _config()
    ctx = _make_context_slices(
        {
            "src/a.py": [(1, 10)],
            "src/b.py": [(1, 10)],
        }
    )
    findings = _make_review_findings(
        [
            {"file_path": "src/a.py", "defect_key": f"dfk_{'a' * 64}", "line": 5},
        ]
    )
    telemetry = _make_telemetry_matrix(
        [
            {"file_path": "src/a.py", "support_count": 5},
        ]
    )
    hazard = _make_hazard_map(
        [
            {"file_path": "src/a.py", "hazard_contribution": 0.8},
        ]
    )

    result = run_stage(
        run_id="run1",
        config=config,
        risk_heatmap_artifact={
            "artifact_version": 1,
            "kind": "risk_heatmap",
            "run_id": "run1",
            "targets": [],
        },
        context_slices_artifact=ctx,
        review_findings_artifact=findings,
        telemetry_matrix_artifact=telemetry,
        hazard_map_artifact=hazard,
    )
    block_confidences = [b["confidence"] for b in result["block_candidates"]]
    assert result["summary"]["summary_confidence"] == round(min(block_confidences), 6)


# ===== Test 6: Review scope merges overlapping ranges =====


def test_review_scope_merges_overlapping():
    blocks = [
        {"file_path": "src/main.py", "start_line": 1, "end_line": 10},
        {"file_path": "src/main.py", "start_line": 8, "end_line": 20},
        {"file_path": "src/main.py", "start_line": 25, "end_line": 30},
    ]
    config = _config()
    scope = compile_review_scope(block_candidates=blocks, config=config)
    file_scopes = [s for s in scope if s["file_path"] == "src/main.py"]
    assert file_scopes[0]["start_line"] == 1
    assert file_scopes[0]["end_line"] == 20
    assert file_scopes[1]["start_line"] == 25
    assert file_scopes[1]["end_line"] == 30


# ===== Test 7: Review scope clamps to max_review_scope_lines =====


def test_review_scope_clamps_to_max():
    blocks = [
        {"file_path": "src/main.py", "start_line": 1, "end_line": 100},
    ]
    config = _config(localization_max_review_scope_lines=50)
    scope = compile_review_scope(block_candidates=blocks, config=config)
    total = sum(s["end_line"] - s["start_line"] + 1 for s in scope)
    assert total <= 50


# ===== Test 8: Review scope fails closed on empty candidates =====


def test_review_scope_fails_on_empty():
    config = _config()
    with pytest.raises(StageError, match="no block candidates"):
        compile_review_scope(block_candidates=[], config=config)


# ===== Test 9: Patch target intersection constrains scope (placeholder for Slice 3) =====


def test_patch_scope_passthrough():
    from forge_eval.services.patch_scope_builder import build_patch_scope

    config = _config()
    result = build_patch_scope(config=config)
    assert result == []


# ===== Test 10: No patch targets -> empty scope =====


def test_no_patch_targets_empty_scope():
    from forge_eval.services.patch_scope_builder import build_patch_scope

    config = _config()
    result = build_patch_scope(config=config, patch_targets_artifact=None)
    assert result == []
    assert not result  # patch_scope_present = false


# ===== Test 11: Golden artifact determinism =====


def test_golden_artifact_determinism():
    config = _config()
    ctx = _make_context_slices(
        {
            "src/a.py": [(1, 10), (20, 30)],
            "src/b.py": [(1, 15)],
        }
    )
    findings = _make_review_findings(
        [
            {"file_path": "src/a.py", "defect_key": f"dfk_{'a' * 64}", "line": 5},
            {"file_path": "src/b.py", "defect_key": f"dfk_{'b' * 64}", "line": 10},
        ]
    )
    telemetry = _make_telemetry_matrix(
        [
            {"file_path": "src/a.py", "support_count": 2},
            {"file_path": "src/b.py", "support_count": 1},
        ]
    )
    hazard = _make_hazard_map(
        [
            {"file_path": "src/a.py", "hazard_contribution": 0.6},
            {"file_path": "src/b.py", "hazard_contribution": 0.3},
        ]
    )
    risk = {
        "artifact_version": 1,
        "kind": "risk_heatmap",
        "run_id": "run1",
        "targets": [],
    }

    kwargs = dict(
        run_id="run1",
        config=config,
        risk_heatmap_artifact=risk,
        context_slices_artifact=ctx,
        review_findings_artifact=findings,
        telemetry_matrix_artifact=telemetry,
        hazard_map_artifact=hazard,
    )

    result1 = run_stage(**kwargs)
    result2 = run_stage(**kwargs)
    json1 = json.dumps(result1, sort_keys=True, separators=(",", ":"))
    json2 = json.dumps(result2, sort_keys=True, separators=(",", ":"))
    assert json1 == json2, "Artifacts must be byte-identical on repeated runs"
