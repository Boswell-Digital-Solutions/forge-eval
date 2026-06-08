from __future__ import annotations

from typing import Any

from forge_eval.errors import StageError
from forge_eval.reviewers.base import (
    RawFinding,
    ReviewerRunResult,
    ReviewerSpec,
    SliceRecord,
)
from forge_eval.reviewers.registry import get_reviewer


def execute_reviewer(
    *,
    spec: ReviewerSpec,
    slices: list[SliceRecord],
    context: dict[str, Any],
    stage_failure_policy: str,
) -> ReviewerRunResult:
    if not spec.enabled:
        return ReviewerRunResult(
            status="skipped",
            slices_seen=0,
            findings_emitted=0,
            error=None,
            raw_findings=[],
        )

    scoped = _scoped_slices(slices, spec.scope_rules)
    if not scoped:
        return ReviewerRunResult(
            status="skipped",
            slices_seen=0,
            findings_emitted=0,
            error=None,
            raw_findings=[],
        )

    reviewer = get_reviewer(spec.kind)
    try:
        raw_findings = reviewer.review(slices=scoped, context=context, spec=spec)
    except Exception as exc:  # pragma: no cover - exercised in stage tests
        message = f"{type(exc).__name__}: {exc}"
        if stage_failure_policy == "fail_stage" or spec.failure_mode == "fail_stage":
            raise StageError(
                "reviewer execution failed",
                stage="review_findings",
                details={"reviewer_id": spec.reviewer_id, "error": message},
            ) from exc
        return ReviewerRunResult(
            status="failed",
            slices_seen=len(scoped),
            findings_emitted=0,
            error=message,
            raw_findings=[],
        )

    if not isinstance(raw_findings, list):
        raise StageError(
            "reviewer returned non-list findings",
            stage="review_findings",
            details={"reviewer_id": spec.reviewer_id, "type": str(type(raw_findings))},
        )

    normalized_raw: list[RawFinding] = []
    for idx, finding in enumerate(raw_findings):
        if not isinstance(finding, dict):
            raise StageError(
                "reviewer finding is not an object",
                stage="review_findings",
                details={
                    "reviewer_id": spec.reviewer_id,
                    "index": idx,
                    "type": str(type(finding)),
                },
            )
        if "reviewer_id" not in finding:
            finding = dict(finding)
            finding["reviewer_id"] = spec.reviewer_id
        normalized_raw.append(finding)

    return ReviewerRunResult(
        status="ok",
        slices_seen=len(scoped),
        findings_emitted=len(normalized_raw),
        error=None,
        raw_findings=normalized_raw,
    )


def _scoped_slices(
    slices: list[SliceRecord], scope_rules: dict[str, Any]
) -> list[SliceRecord]:
    include_exts = [
        str(item).lower() for item in scope_rules.get("include_extensions", [])
    ]
    exclude_paths = [
        str(item).replace("\\", "/") for item in scope_rules.get("exclude_paths", [])
    ]

    out: list[SliceRecord] = []
    for slc in slices:
        path = str(slc["file_path"]).replace("\\", "/")
        if include_exts and not any(path.lower().endswith(ext) for ext in include_exts):
            continue
        if any(path.startswith(prefix) for prefix in exclude_paths):
            continue
        out.append(slc)
    return out
