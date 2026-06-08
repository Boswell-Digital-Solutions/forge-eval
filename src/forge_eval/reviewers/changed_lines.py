from __future__ import annotations

from typing import Any

from forge_eval.reviewers.base import RawFinding, ReviewerSpec, SliceRecord


class ChangedLinesRuleReviewer:
    kind = "changed_lines"

    def review(
        self,
        *,
        slices: list[SliceRecord],
        context: dict[str, Any],
        spec: ReviewerSpec,
    ) -> list[RawFinding]:
        findings: list[RawFinding] = []
        has_schema_like_change = bool(context.get("has_schema_like_change", False))
        has_docs_changes = bool(context.get("has_docs_changes", False))
        has_code_changes = bool(context.get("has_code_changes", False))

        for slc in sorted(
            slices,
            key=lambda s: (
                str(s["file_path"]),
                int(s["start_line"]),
                int(s["end_line"]),
            ),
        ):
            file_path = str(slc["file_path"])
            content = str(slc.get("content", ""))
            lowered_content = content.lower()
            lowered_path = file_path.lower()

            if (
                ("schema" in lowered_path or lowered_path.endswith(".schema.json"))
                and "validator" not in lowered_content
                and "compat" not in lowered_content
            ):
                findings.append(
                    _build_raw(
                        spec=spec,
                        slc=slc,
                        title="Schema change lacks validator or compatibility marker",
                        description=(
                            "Slice includes schema-like changes without nearby validator/compatibility signal."
                        ),
                        category="schema",
                    )
                )

            if "policy" in lowered_path and not has_schema_like_change:
                findings.append(
                    _build_raw(
                        spec=spec,
                        slc=slc,
                        title="Policy change has no schema counterpart in diff",
                        description="Policy-related change detected without schema-like change in the same diff set.",
                        category="policy",
                    )
                )

            if lowered_path.endswith(".md") and not has_code_changes:
                findings.append(
                    _build_raw(
                        spec=spec,
                        slc=slc,
                        title="Documentation-only change has no code counterpart",
                        description="Documentation changed while no code file changes were detected in scoped slices.",
                        category="docs",
                    )
                )

            if (
                not lowered_path.endswith(".md")
                and has_docs_changes
                and "todo" in lowered_content
            ):
                findings.append(
                    _build_raw(
                        spec=spec,
                        slc=slc,
                        title="Code slice contains TODO while docs changed in same diff",
                        description="TODO marker was found in code while documentation also changed in this diff.",
                        category="consistency",
                    )
                )

        return findings


def _build_raw(
    *,
    spec: ReviewerSpec,
    slc: dict[str, Any],
    title: str,
    description: str,
    category: str,
) -> RawFinding:
    return {
        "reviewer_id": spec.reviewer_id,
        "file_path": str(slc["file_path"]),
        "slice_id": str(slc["slice_id"]),
        "title": title,
        "description": description,
        "severity": str(spec.finding_rules.get("default_severity", "medium")),
        "confidence": float(spec.finding_rules.get("confidence", 0.7)),
        "category": category,
        "line_start": int(slc["start_line"]),
        "line_end": int(slc["end_line"]),
        "evidence": {
            "anchors": [str(slc["slice_id"])],
            "signals": [spec.kind],
        },
    }
