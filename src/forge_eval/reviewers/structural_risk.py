from __future__ import annotations

from typing import Any

from forge_eval.reviewers.base import RawFinding, ReviewerSpec, SliceRecord


class StructuralRiskReviewer:
    kind = "structural_risk"

    def review(
        self,
        *,
        slices: list[SliceRecord],
        context: dict[str, Any],
        spec: ReviewerSpec,
    ) -> list[RawFinding]:
        risk_by_path = dict(context.get("risk_by_path", {}))
        threshold = max(
            float(spec.scope_rules.get("min_risk_score", 0.0)),
            float(spec.finding_rules.get("risk_threshold", 0.8)),
        )

        findings: list[RawFinding] = []
        emitted_paths: set[str] = set()

        ordered_slices = sorted(
            slices,
            key=lambda s: (
                str(s["file_path"]),
                int(s["start_line"]),
                int(s["end_line"]),
            ),
        )
        for slc in ordered_slices:
            file_path = str(slc["file_path"])
            if file_path in emitted_paths:
                continue
            risk_score = float(risk_by_path.get(file_path, 0.0))
            if risk_score < threshold:
                continue

            findings.append(
                {
                    "reviewer_id": spec.reviewer_id,
                    "file_path": file_path,
                    "slice_id": str(slc["slice_id"]),
                    "title": f"High structural risk score {risk_score:.4f}",
                    "description": (
                        "File crossed structural risk threshold during Pack E scoring."
                    ),
                    "severity": str(
                        spec.finding_rules.get("default_severity", "medium")
                    ),
                    "confidence": float(spec.finding_rules.get("confidence", 0.75)),
                    "category": str(spec.finding_rules.get("default_category", "risk")),
                    "line_start": int(slc["start_line"]),
                    "line_end": int(slc["end_line"]),
                    "evidence": {
                        "anchors": [str(slc["slice_id"])],
                        "signals": [
                            f"risk_score:{risk_score:.8f}",
                            f"threshold:{threshold:.8f}",
                        ],
                    },
                }
            )
            emitted_paths.add(file_path)

        return findings
