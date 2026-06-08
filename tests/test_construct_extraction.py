from __future__ import annotations

import json
from pathlib import Path

import jsonschema

from forge_eval.config import normalize_config
from forge_eval.services.construct_extractor import (
    ROOT_CAUSE_HYPOTHESIS_ENUM,
    derive_root_cause_hypothesis,
    detect_framework,
    detect_language,
    extract_constructs,
)
from forge_eval.services.patch_scope_builder import build_patch_scope
from forge_eval.stages.localization_pack import run_stage

SCHEMA_DIR = Path(__file__).resolve().parent.parent / "src" / "forge_eval" / "schemas"


def _load_schema(name: str) -> dict:
    return json.loads((SCHEMA_DIR / name).read_text(encoding="utf-8"))


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


def _make_artifacts(file_paths: list[str]):
    slices = []
    findings = []
    telemetry_rows = []
    hazard_rows = []
    for i, fp in enumerate(file_paths):
        slices.append(
            {
                "slice_id": f"slice_{i}",
                "file_path": fp,
                "start_line": 1,
                "end_line": 20,
                "content": "# test",
                "context_radius": 12,
            }
        )
        dk = f"dfk_{i:064x}"
        findings.append(
            {
                "defect_key": dk,
                "file_path": fp,
                "line": 5,
                "category": "correctness",
                "severity": "medium",
                "reviewer_id": "r1",
                "message": "test",
                "confidence": 0.8,
            }
        )
        telemetry_rows.append(
            {
                "defect_key": dk,
                "file_path": fp,
                "line": 5,
                "category": "correctness",
                "severity": "medium",
                "reported_by": ["r1"],
                "support_count": 2,
                "observed_by": 2,
                "missed_by": 0,
                "null_by": 0,
                "k_eff_defect": 1,
            }
        )
        hazard_rows.append(
            {
                "defect_key": dk,
                "file_path": fp,
                "category": "correctness",
                "severity": "medium",
                "reported_by": ["r1"],
                "support_count": 2,
                "observed_by": 2,
                "missed_by": 0,
                "null_by": 0,
                "k_eff_defect": 1,
                "psi_post": 0.5,
                "local_risk_score": 0.8,
                "severity_weight": 0.5,
                "occupancy_uplift": 0.1,
                "structural_risk_uplift": 0.1,
                "support_uplift": 0.1,
                "hazard_contribution": 0.6,
                "hazard_flags": [],
            }
        )

    ctx = {
        "artifact_version": 1,
        "kind": "context_slices",
        "run_id": "r1",
        "slices": slices,
    }
    rf = {
        "artifact_version": 1,
        "kind": "review_findings",
        "run_id": "r1",
        "findings": findings,
    }
    tm = {
        "artifact_version": 1,
        "kind": "telemetry_matrix",
        "run_id": "r1",
        "rows": telemetry_rows,
    }
    hm = {
        "artifact_version": 1,
        "kind": "hazard_map",
        "run_id": "r1",
        "summary": {
            "hazard_score": 0.5,
            "hazard_tier": "elevated",
            "defect_count": len(file_paths),
            "observed_defects": len(file_paths),
            "selected_hidden": 0.3,
            "selected_total": 1.3,
            "mean_psi_post": 0.5,
            "max_risk_score": 0.8,
            "max_hazard_contribution": 0.6,
            "hidden_pressure": 0.2,
            "base_hazard_score": 0.4,
            "hidden_uplift": 0.05,
            "uncertainty_uplift": 0.05,
            "blocking_signals_present": False,
            "blocking_reason_flags": [],
            "uncertainty_flags": [],
        },
        "rows": hazard_rows,
    }
    rh = {"artifact_version": 1, "kind": "risk_heatmap", "run_id": "r1", "targets": []}
    return rh, ctx, rf, tm, hm


# ===== Test 1: Language detected from file extension =====


def test_language_detection():
    assert detect_language("src/main.py") == "python"
    assert detect_language("src/lib.rs") == "rust"
    assert detect_language("src/app.ts") == "typescript"
    assert detect_language("src/App.tsx") == "typescript"
    assert detect_language("src/Button.svelte") == "svelte"
    assert detect_language("src/data.json") is None


# ===== Test 2: Framework hint detection =====


def test_framework_detection():
    assert detect_framework("main.py", "from fastapi import APIRouter") == "fastapi"
    assert detect_framework("lib.rs", "use tauri::AppHandle") == "tauri"
    assert detect_framework("app.svelte", "export function load(") == "svelte_kit"
    assert detect_framework("main.py") is None
    assert detect_framework("main.py", "import os") is None


# ===== Test 3: Construct patterns match correctly =====


def test_construct_patterns():
    py_constructs = extract_constructs(
        "python", ["if x:", "await foo()", "try:", "return y"]
    )
    assert "if_guard" in py_constructs
    assert "async_call" in py_constructs
    assert "try_except" in py_constructs
    assert "return_boundary" in py_constructs

    rs_constructs = extract_constructs("rust", ["&mut val", "match x {", "foo.await"])
    assert "borrow_boundary" in rs_constructs
    assert "match_arm" in rs_constructs
    assert "async_task_boundary" in rs_constructs

    svelte_constructs = extract_constructs(
        "svelte", ["{#if cond}", "$state(0)", "$effect(() => {})"]
    )
    assert "if_guard" in svelte_constructs
    assert "reactive_state" in svelte_constructs
    assert "effect_boundary" in svelte_constructs


# ===== Test 4: Unknown language returns empty constructs =====


def test_unknown_language_empty_constructs():
    assert detect_language("data.csv") is None
    constructs = extract_constructs(None, ["some content"])
    assert constructs == []


# ===== Test 5: root_cause_hypothesis = ownership_violation for Rust borrow =====


def test_hypothesis_ownership_violation():
    h = derive_root_cause_hypothesis(
        language="rust",
        constructs=["borrow_boundary", "if_guard"],
    )
    assert h == "ownership_violation"


# ===== Test 6: root_cause_hypothesis = null when no constructs =====


def test_hypothesis_null_no_constructs():
    h = derive_root_cause_hypothesis(language="python", constructs=[])
    assert h is None


# ===== Test 7: root_cause_hypothesis always from locked enum =====


def test_hypothesis_always_valid_enum():
    valid_values = set(ROOT_CAUSE_HYPOTHESIS_ENUM) | {None}
    test_cases = [
        {
            "language": "python",
            "constructs": ["if_guard"],
            "support_count": 0,
            "hazard_contribution": 0.0,
        },
        {"language": "rust", "constructs": ["borrow_boundary"]},
        {"language": "svelte", "constructs": ["reactive_state"]},
        {"language": "python", "constructs": ["async_call"], "support_count": 2},
        {"language": "python", "constructs": ["serialization_boundary"]},
        {"language": "typescript", "constructs": ["if_guard"]},
        {"language": "python", "constructs": []},
    ]
    for tc in test_cases:
        h = derive_root_cause_hypothesis(**tc)
        assert h in valid_values, f"Got {h!r} for {tc}"


# ===== Test 8: Patch scope builds from targets =====


def test_patch_scope_builds():
    config = _config()
    targets = {
        "targets": [
            {"target_id": "t1", "file_path": "src/main.py", "allow_ranges": [[1, 20]]},
            {"target_id": "t2", "file_path": "src/utils.py", "allow_ranges": [[5, 15]]},
        ],
    }
    result = build_patch_scope(config=config, patch_targets_artifact=targets)
    assert len(result) == 2
    assert result[0]["file_path"] == "src/main.py"
    assert result[0]["target_id"] == "t1"


# ===== Test 9: Empty patch intersection (placeholder — full test in Slice 4) =====


def test_empty_patch_scope_no_targets():
    config = _config()
    result = build_patch_scope(config=config, patch_targets_artifact=None)
    assert result == []


# ===== Test 10: No patch targets → patch_scope_present = false =====


def test_no_targets_summary_false():
    config = _config()
    rh, ctx, rf, tm, hm = _make_artifacts(["src/main.py"])
    result = run_stage(
        run_id="r1",
        config=config,
        risk_heatmap_artifact=rh,
        context_slices_artifact=ctx,
        review_findings_artifact=rf,
        telemetry_matrix_artifact=tm,
        hazard_map_artifact=hm,
    )
    assert result["summary"]["patch_scope_present"] is False
    assert result["patch_scope"] == []


# ===== Test 11: Complete stage golden test =====


def test_complete_stage_golden():
    config = _config()
    rh, ctx, rf, tm, hm = _make_artifacts(["src/main.py", "src/utils.rs"])
    kwargs = dict(
        run_id="r1",
        config=config,
        risk_heatmap_artifact=rh,
        context_slices_artifact=ctx,
        review_findings_artifact=rf,
        telemetry_matrix_artifact=tm,
        hazard_map_artifact=hm,
    )
    result1 = run_stage(**kwargs)
    result2 = run_stage(**kwargs)

    j1 = json.dumps(result1, sort_keys=True, separators=(",", ":"))
    j2 = json.dumps(result2, sort_keys=True, separators=(",", ":"))
    assert j1 == j2, "Must be byte-identical"

    schema = _load_schema("localization_pack.schema.json")
    jsonschema.validate(instance=result1, schema=schema)

    for bc in result1["block_candidates"]:
        assert bc["detected_language"] in (
            "python",
            "rust",
            "typescript",
            "svelte",
            "other",
            None,
        )
        assert bc["root_cause_hypothesis"] in list(ROOT_CAUSE_HYPOTHESIS_ENUM) + [None]
