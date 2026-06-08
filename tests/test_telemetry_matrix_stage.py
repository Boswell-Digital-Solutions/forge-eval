from __future__ import annotations

from pathlib import Path

import pytest

from forge_eval.config import normalize_config
from forge_eval.errors import StageError
from forge_eval.stages.telemetry_matrix import run_stage


def _review_findings_artifact() -> dict[str, object]:
    return {
        "artifact_version": 1,
        "kind": "review_findings",
        "run": {
            "run_id": "run",
            "repo_path": "/tmp/repo",
            "base_ref": "base",
            "head_ref": "head",
            "base_commit": "basec",
            "head_commit": "headc",
            "slice_artifact": "context_slices.json",
            "risk_artifact": "risk_heatmap.json",
        },
        "reviewers": [
            {
                "reviewer_id": "changed_lines.rule.v1",
                "kind": "changed_lines",
                "status": "ok",
                "slices_seen": 2,
                "findings_emitted": 1,
                "error": None,
            },
            {
                "reviewer_id": "documentation_consistency.v1",
                "kind": "documentation_consistency",
                "status": "ok",
                "slices_seen": 1,
                "findings_emitted": 1,
                "error": None,
            },
            {
                "reviewer_id": "structural_risk.v1",
                "kind": "structural_risk",
                "status": "failed",
                "slices_seen": 1,
                "findings_emitted": 0,
                "error": "runtime timeout",
            },
        ],
        "findings": [
            {
                "defect_key": "dfk_" + ("a" * 64),
                "reviewer_id": "changed_lines.rule.v1",
                "file_path": "a.py",
                "slice_id": "a.py:1:5",
                "title": "Code finding",
                "description": None,
                "severity": "medium",
                "confidence": 0.7,
                "category": "consistency",
                "line_start": 1,
                "line_end": 5,
                "evidence": {"anchors": ["a.py:1:5"], "signals": ["changed_lines"]},
            },
            {
                "defect_key": "dfk_" + ("b" * 64),
                "reviewer_id": "documentation_consistency.v1",
                "file_path": "README.md",
                "slice_id": "README.md:1:8",
                "title": "Doc finding",
                "description": None,
                "severity": "low",
                "confidence": 0.65,
                "category": "docs",
                "line_start": 1,
                "line_end": 8,
                "evidence": {
                    "anchors": ["README.md:1:8"],
                    "signals": ["documentation_consistency"],
                },
            },
        ],
        "summary": {
            "reviewer_count": 3,
            "reviewer_ok_count": 2,
            "reviewer_failed_count": 1,
            "reviewer_skipped_count": 0,
            "finding_count": 2,
            "finding_count_by_severity": {
                "low": 1,
                "medium": 1,
                "high": 0,
                "critical": 0,
            },
        },
        "provenance": {
            "algorithm": "reviewer_execution_v1",
            "deterministic": True,
            "reviewer_failure_policy": "fail_stage",
            "inputs": ["context_slices.json", "risk_heatmap.json"],
        },
    }


def test_telemetry_matrix_stage_tri_state_and_k_eff() -> None:
    cfg = normalize_config({})
    out = run_stage(
        repo_path=Path("/tmp/repo"),
        base_ref="base",
        head_ref="head",
        run_id="run",
        config=cfg,
        review_findings_artifact=_review_findings_artifact(),
    )

    assert out["kind"] == "telemetry_matrix"
    assert out["artifact_version"] == 1
    assert out["summary"]["k_configured"] == 3
    assert out["summary"]["k_failed"] == 1
    assert out["summary"]["k_usable"] == 2
    assert out["summary"]["k_eff"] == 1

    rows = {row["defect_key"]: row for row in out["matrix"]}
    code_row = rows["dfk_" + ("a" * 64)]
    docs_row = rows["dfk_" + ("b" * 64)]

    assert code_row["observations"]["changed_lines.rule.v1"] == 1
    assert code_row["observations"]["documentation_consistency.v1"] is None
    assert code_row["observations"]["structural_risk.v1"] is None

    assert docs_row["observations"]["changed_lines.rule.v1"] == 0
    assert docs_row["observations"]["documentation_consistency.v1"] == 1
    assert docs_row["observations"]["structural_risk.v1"] is None


# Ghost-coverage guard proof: failed reviewer must produce null, never 0.
def test_telemetry_matrix_failed_reviewer_is_null_not_zero() -> None:
    cfg = normalize_config({})
    out = run_stage(
        repo_path=Path("/tmp/repo"),
        base_ref="base",
        head_ref="head",
        run_id="run",
        config=cfg,
        review_findings_artifact=_review_findings_artifact(),
    )
    code_row = next(
        row for row in out["matrix"] if row["defect_key"] == "dfk_" + ("a" * 64)
    )
    assert code_row["observations"]["structural_risk.v1"] is None


def test_telemetry_matrix_coalesces_cross_reviewer_defect_key() -> None:
    cfg = normalize_config({})
    artifact = _review_findings_artifact()
    artifact["reviewers"][2]["status"] = "ok"
    artifact["reviewers"][2]["error"] = None
    duplicate = dict(artifact["findings"][0])
    duplicate["reviewer_id"] = "structural_risk.v1"
    duplicate["severity"] = artifact["findings"][0]["severity"]
    duplicate["category"] = artifact["findings"][0]["category"]
    duplicate["file_path"] = artifact["findings"][0]["file_path"]
    artifact["findings"].append(duplicate)

    out = run_stage(
        repo_path=Path("/tmp/repo"),
        base_ref="base",
        head_ref="head",
        run_id="run",
        config=cfg,
        review_findings_artifact=artifact,
    )

    defect = next(
        item for item in out["defects"] if item["defect_key"] == "dfk_" + ("a" * 64)
    )
    assert defect["reported_by"] == ["changed_lines.rule.v1", "structural_risk.v1"]
    assert defect["support_count"] == 2

    row = next(
        item for item in out["matrix"] if item["defect_key"] == "dfk_" + ("a" * 64)
    )
    assert row["observations"]["changed_lines.rule.v1"] == 1
    assert row["observations"]["documentation_consistency.v1"] is None
    assert row["observations"]["structural_risk.v1"] == 1


def test_telemetry_matrix_same_reviewer_duplicate_defect_key_fails_closed() -> None:
    cfg = normalize_config({})
    artifact = _review_findings_artifact()
    artifact["findings"].append(dict(artifact["findings"][0]))

    with pytest.raises(StageError):
        run_stage(
            repo_path=Path("/tmp/repo"),
            base_ref="base",
            head_ref="head",
            run_id="run",
            config=cfg,
            review_findings_artifact=artifact,
        )


@pytest.mark.parametrize(
    "field,bad_value",
    [("file_path", "other.py"), ("category", "schema"), ("severity", "high")],
)
def test_telemetry_matrix_incompatible_cross_reviewer_duplicate_fails_closed(
    field: str, bad_value: str
) -> None:
    cfg = normalize_config({})
    artifact = _review_findings_artifact()
    artifact["reviewers"][2]["status"] = "ok"
    artifact["reviewers"][2]["error"] = None
    duplicate = dict(artifact["findings"][0])
    duplicate["reviewer_id"] = "structural_risk.v1"
    duplicate[field] = bad_value
    artifact["findings"].append(duplicate)

    with pytest.raises(StageError):
        run_stage(
            repo_path=Path("/tmp/repo"),
            base_ref="base",
            head_ref="head",
            run_id="run",
            config=cfg,
            review_findings_artifact=artifact,
        )


def test_telemetry_matrix_invalid_reviewer_status_fails_closed() -> None:
    cfg = normalize_config({})
    artifact = _review_findings_artifact()
    artifact["reviewers"][0]["status"] = "bad_status"

    with pytest.raises(StageError):
        run_stage(
            repo_path=Path("/tmp/repo"),
            base_ref="base",
            head_ref="head",
            run_id="run",
            config=cfg,
            review_findings_artifact=artifact,
        )


def test_telemetry_matrix_skipped_reviewer_is_not_usable() -> None:
    cfg = normalize_config({})
    artifact = _review_findings_artifact()
    artifact["reviewers"][2]["status"] = "skipped"
    artifact["reviewers"][2]["error"] = None

    out = run_stage(
        repo_path=Path("/tmp/repo"),
        base_ref="base",
        head_ref="head",
        run_id="run",
        config=cfg,
        review_findings_artifact=artifact,
    )

    reviewer = next(
        item for item in out["reviewers"] if item["reviewer_id"] == "structural_risk.v1"
    )
    assert reviewer["skipped"] is True
    assert reviewer["usable"] is False
