from __future__ import annotations

from forge_eval.reviewers.base import RawFinding, ReviewerSpec, SliceRecord


class DocumentationConsistencyReviewer:
    kind = "documentation_consistency"

    def review(
        self,
        *,
        slices: list[SliceRecord],
        context: dict[str, object],
        spec: ReviewerSpec,
    ) -> list[RawFinding]:
        require_code_and_docs = bool(
            spec.finding_rules.get("require_code_and_docs", False)
        )
        if not require_code_and_docs:
            return []

        has_docs_changes = bool(context.get("has_docs_changes", False))
        has_code_changes = bool(context.get("has_code_changes", False))

        ordered_slices = sorted(
            slices,
            key=lambda s: (
                str(s["file_path"]),
                int(s["start_line"]),
                int(s["end_line"]),
            ),
        )
        docs_slices = [
            slc
            for slc in ordered_slices
            if str(slc["file_path"]).lower().endswith(".md")
        ]
        code_slices = [
            slc
            for slc in ordered_slices
            if not str(slc["file_path"]).lower().endswith(".md")
        ]

        findings: list[RawFinding] = []
        if has_docs_changes and not has_code_changes and docs_slices:
            for slc in docs_slices:
                findings.append(
                    _build_finding(
                        spec=spec,
                        slc=slc,
                        title="Documentation updated without code changes",
                        description="Documentation slices changed, but no code slices were changed in this run.",
                    )
                )

        if has_code_changes and not has_docs_changes and code_slices:
            first_code = code_slices[0]
            findings.append(
                _build_finding(
                    spec=spec,
                    slc=first_code,
                    title="Code updated without documentation changes",
                    description="Code slices changed, but no documentation slices were changed in this run.",
                )
            )

        return findings


def _build_finding(
    *, spec: ReviewerSpec, slc: SliceRecord, title: str, description: str
) -> RawFinding:
    return {
        "reviewer_id": spec.reviewer_id,
        "file_path": str(slc["file_path"]),
        "slice_id": str(slc["slice_id"]),
        "title": title,
        "description": description,
        "severity": str(spec.finding_rules.get("default_severity", "low")),
        "confidence": float(spec.finding_rules.get("confidence", 0.65)),
        "category": str(spec.finding_rules.get("default_category", "docs")),
        "line_start": int(slc["start_line"]),
        "line_end": int(slc["end_line"]),
        "evidence": {
            "anchors": [str(slc["slice_id"])],
            "signals": [spec.kind],
        },
    }
