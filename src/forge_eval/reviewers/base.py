from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

RawFinding = dict[str, Any]
SliceRecord = dict[str, Any]


@dataclass(frozen=True)
class ReviewerSpec:
    reviewer_id: str
    kind: str
    enabled: bool
    failure_mode: str
    scope_rules: dict[str, Any]
    finding_rules: dict[str, Any]


@dataclass(frozen=True)
class ReviewerRunResult:
    status: str
    slices_seen: int
    findings_emitted: int
    error: str | None
    raw_findings: list[RawFinding]


class Reviewer(Protocol):
    kind: str

    def review(
        self,
        *,
        slices: list[SliceRecord],
        context: dict[str, Any],
        spec: ReviewerSpec,
    ) -> list[RawFinding]: ...


def reviewer_specs_from_config(reviewers: list[dict[str, Any]]) -> list[ReviewerSpec]:
    specs = [
        ReviewerSpec(
            reviewer_id=str(item["reviewer_id"]),
            kind=str(item["kind"]),
            enabled=bool(item["enabled"]),
            failure_mode=str(item["failure_mode"]),
            scope_rules=dict(item["scope_rules"]),
            finding_rules=dict(item["finding_rules"]),
        )
        for item in reviewers
    ]
    return sorted(specs, key=lambda spec: spec.reviewer_id)
