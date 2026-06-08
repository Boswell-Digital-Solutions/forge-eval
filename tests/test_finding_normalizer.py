from __future__ import annotations

import pytest

from forge_eval.errors import StageError
from forge_eval.reviewers.base import ReviewerSpec
from forge_eval.services.finding_normalizer import normalize_findings


def _spec() -> ReviewerSpec:
    return ReviewerSpec(
        reviewer_id="changed_lines.rule.v1",
        kind="changed_lines",
        enabled=True,
        failure_mode="fail_stage",
        scope_rules={},
        finding_rules={
            "default_severity": "medium",
            "default_category": "consistency",
            "confidence": 0.7,
        },
    )


def test_normalizer_applies_defaults_and_generates_defect_key() -> None:
    findings = normalize_findings(
        raw_findings=[
            {
                "reviewer_id": "changed_lines.rule.v1",
                "file_path": "a.py",
                "slice_id": "a.py:1:5",
                "title": "Missing validator marker",
            }
        ],
        reviewer_specs=[_spec()],
    )
    assert len(findings) == 1
    finding = findings[0]
    assert finding["severity"] == "medium"
    assert finding["category"] == "consistency"
    assert finding["confidence"] == 0.7
    assert finding["defect_key"].startswith("dfk_")
    assert finding["description"] is None
    assert finding["line_start"] is None
    assert finding["line_end"] is None


def test_normalizer_rejects_invalid_line_range() -> None:
    with pytest.raises(StageError):
        normalize_findings(
            raw_findings=[
                {
                    "reviewer_id": "changed_lines.rule.v1",
                    "file_path": "a.py",
                    "slice_id": "a.py:1:5",
                    "title": "Invalid line range",
                    "line_start": 10,
                    "line_end": 9,
                }
            ],
            reviewer_specs=[_spec()],
        )


def test_normalizer_rejects_duplicate_defect_key() -> None:
    with pytest.raises(StageError):
        normalize_findings(
            raw_findings=[
                {
                    "reviewer_id": "changed_lines.rule.v1",
                    "file_path": "a.py",
                    "slice_id": "a.py:1:5",
                    "title": "Duplicate",
                },
                {
                    "reviewer_id": "changed_lines.rule.v1",
                    "file_path": "a.py",
                    "slice_id": "a.py:1:5",
                    "title": "duplicate",
                },
            ],
            reviewer_specs=[_spec()],
        )


def test_normalizer_allows_duplicate_defect_key_across_reviewers() -> None:
    peer_spec = ReviewerSpec(
        reviewer_id="changed_lines.peer.v1",
        kind="changed_lines",
        enabled=True,
        failure_mode="fail_stage",
        scope_rules={},
        finding_rules={
            "default_severity": "medium",
            "default_category": "consistency",
            "confidence": 0.7,
        },
    )
    findings = normalize_findings(
        raw_findings=[
            {
                "reviewer_id": "changed_lines.rule.v1",
                "file_path": "a.py",
                "slice_id": "a.py:1:5",
                "title": "Duplicate",
            },
            {
                "reviewer_id": "changed_lines.peer.v1",
                "file_path": "a.py",
                "slice_id": "a.py:1:5",
                "title": "duplicate",
            },
        ],
        reviewer_specs=[_spec(), peer_spec],
    )
    assert len(findings) == 2
    assert findings[0]["defect_key"] == findings[1]["defect_key"]
