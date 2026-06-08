from __future__ import annotations

from pathlib import Path

import pytest

from forge_eval.config import normalize_config
from forge_eval.errors import StageError
from forge_eval.stages.reviewer_execution import run_stage


def _context_artifact_with_code_slice() -> dict[str, object]:
    return {
        "kind": "context_slices",
        "slices": [
            {
                "slice_id": "a.py:1:5",
                "file_path": "a.py",
                "start_line": 1,
                "end_line": 5,
                "changed_line_count": 1,
                "total_line_count": 5,
                "content": "print('hello')\n# TODO: refine\n",
                "origin": {
                    "source": "git_diff_head_version",
                    "base_ref": "base",
                    "head_ref": "head",
                    "changed_ranges": [[2, 2]],
                },
            }
        ],
    }


def _risk_artifact_high() -> dict[str, object]:
    return {
        "kind": "risk_heatmap",
        "targets": [
            {
                "file_path": "a.py",
                "risk_score": 0.95,
            }
        ],
    }


def test_reviewer_execution_stage_emits_findings_and_statuses() -> None:
    cfg = normalize_config({})
    out = run_stage(
        repo_path=Path("/tmp/repo"),
        base_ref="base",
        head_ref="head",
        run_id="run",
        config=cfg,
        context_slices_artifact=_context_artifact_with_code_slice(),
        risk_heatmap_artifact=_risk_artifact_high(),
        base_commit="basec",
        head_commit="headc",
    )

    assert out["kind"] == "review_findings"
    assert out["artifact_version"] == 1
    assert out["summary"]["reviewer_count"] == 3
    assert any(reviewer["status"] == "ok" for reviewer in out["reviewers"])
    assert any(reviewer["status"] == "skipped" for reviewer in out["reviewers"])
    assert all(finding["defect_key"].startswith("dfk_") for finding in out["findings"])


def test_reviewer_execution_record_and_continue_keeps_failed_status(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cfg = normalize_config(
        {
            "reviewer_failure_policy": "record_and_continue",
            "reviewers": [
                {
                    "reviewer_id": "changed_lines.rule.v1",
                    "kind": "changed_lines",
                    "enabled": True,
                    "failure_mode": "record_failed",
                    "scope_rules": {"include_extensions": [".py"]},
                    "finding_rules": {
                        "default_severity": "medium",
                        "default_category": "consistency",
                    },
                }
            ],
        }
    )

    class _BoomReviewer:
        kind = "changed_lines"

        def review(
            self, *, slices, context, spec
        ):  # pragma: no cover - exercised by test
            raise RuntimeError("boom")

    monkeypatch.setattr(
        "forge_eval.reviewers.adapters.get_reviewer", lambda kind: _BoomReviewer()
    )

    out = run_stage(
        repo_path=Path("/tmp/repo"),
        base_ref="base",
        head_ref="head",
        run_id="run",
        config=cfg,
        context_slices_artifact=_context_artifact_with_code_slice(),
        risk_heatmap_artifact=_risk_artifact_high(),
    )
    assert out["reviewers"][0]["status"] == "failed"
    assert out["summary"]["reviewer_failed_count"] == 1


def test_reviewer_execution_fail_stage_on_reviewer_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cfg = normalize_config(
        {
            "reviewer_failure_policy": "fail_stage",
            "reviewers": [
                {
                    "reviewer_id": "changed_lines.rule.v1",
                    "kind": "changed_lines",
                    "enabled": True,
                    "failure_mode": "record_failed",
                    "scope_rules": {"include_extensions": [".py"]},
                    "finding_rules": {
                        "default_severity": "medium",
                        "default_category": "consistency",
                    },
                }
            ],
        }
    )

    class _BoomReviewer:
        kind = "changed_lines"

        def review(
            self, *, slices, context, spec
        ):  # pragma: no cover - exercised by test
            raise RuntimeError("boom")

    monkeypatch.setattr(
        "forge_eval.reviewers.adapters.get_reviewer", lambda kind: _BoomReviewer()
    )

    with pytest.raises(StageError):
        run_stage(
            repo_path=Path("/tmp/repo"),
            base_ref="base",
            head_ref="head",
            run_id="run",
            config=cfg,
            context_slices_artifact=_context_artifact_with_code_slice(),
            risk_heatmap_artifact=_risk_artifact_high(),
        )
