from __future__ import annotations

from typing import Any

from forge_eval.config import KNOWN_CATEGORIES, KNOWN_SEVERITIES
from forge_eval.errors import StageError
from forge_eval.reviewers.base import ReviewerSpec
from forge_eval.services.defect_identity import defect_key_for_finding, normalize_title


def normalize_findings(
    *,
    raw_findings: list[dict[str, Any]],
    reviewer_specs: list[ReviewerSpec],
) -> list[dict[str, Any]]:
    spec_by_id = {spec.reviewer_id: spec for spec in reviewer_specs}
    normalized: list[dict[str, Any]] = []

    for idx, raw in enumerate(raw_findings):
        if not isinstance(raw, dict):
            raise StageError(
                "raw finding is not an object",
                stage="review_findings",
                details={"index": idx, "type": str(type(raw))},
            )

        reviewer_id = _required_str(raw, "reviewer_id")
        spec = spec_by_id.get(reviewer_id)
        if spec is None:
            raise StageError(
                "raw finding references unknown reviewer_id",
                stage="review_findings",
                details={"reviewer_id": reviewer_id},
            )

        file_path = _required_str(raw, "file_path")
        slice_id = _required_str(raw, "slice_id")
        title = _required_str(raw, "title")
        description = _optional_str(raw, "description")

        severity = raw.get(
            "severity", spec.finding_rules.get("default_severity", "medium")
        )
        if severity not in KNOWN_SEVERITIES:
            raise StageError(
                "invalid finding severity",
                stage="review_findings",
                details={"severity": severity, "reviewer_id": reviewer_id},
            )

        category = raw.get(
            "category", spec.finding_rules.get("default_category", "unknown")
        )
        if category not in KNOWN_CATEGORIES:
            raise StageError(
                "invalid finding category",
                stage="review_findings",
                details={"category": category, "reviewer_id": reviewer_id},
            )

        confidence_raw = raw.get(
            "confidence", spec.finding_rules.get("confidence", 0.7)
        )
        confidence = _optional_probability(confidence_raw, key="confidence")

        line_start_raw = raw.get("line_start")
        line_end_raw = raw.get("line_end")
        line_start, line_end = _normalize_line_range(line_start_raw, line_end_raw)

        evidence = _normalize_evidence(raw.get("evidence"))

        finding = {
            "defect_key": defect_key_for_finding(
                reviewer_id=reviewer_id,
                file_path=file_path,
                category=category,
                title=title,
                line_start=line_start,
                line_end=line_end,
                slice_id=slice_id,
            ),
            "reviewer_id": reviewer_id,
            "file_path": file_path,
            "slice_id": slice_id,
            "title": title.strip(),
            "description": description,
            "severity": severity,
            "confidence": confidence,
            "category": category,
            "line_start": line_start,
            "line_end": line_end,
            "evidence": evidence,
        }
        normalized.append(finding)

    normalized.sort(
        key=lambda item: (
            str(item["reviewer_id"]),
            str(item["file_path"]),
            str(item["slice_id"]),
            str(item["category"]),
            normalize_title(str(item["title"])),
            0 if item["line_start"] is None else int(item["line_start"]),
            0 if item["line_end"] is None else int(item["line_end"]),
            str(item["defect_key"]),
        )
    )

    seen_pairs: set[tuple[str, str]] = set()
    for item in normalized:
        defect_key = str(item["defect_key"])
        reviewer_id = str(item["reviewer_id"])
        key = (defect_key, reviewer_id)
        if key in seen_pairs:
            raise StageError(
                "duplicate defect_key generated for same reviewer",
                stage="review_findings",
                details={"defect_key": defect_key, "reviewer_id": reviewer_id},
            )
        seen_pairs.add(key)

    return normalized


def _required_str(raw: dict[str, Any], key: str) -> str:
    value = raw.get(key)
    if not isinstance(value, str) or not value.strip():
        raise StageError(
            "missing or invalid finding field",
            stage="review_findings",
            details={"field": key, "value": value},
        )
    return value.strip()


def _optional_str(raw: dict[str, Any], key: str) -> str | None:
    value = raw.get(key)
    if value is None:
        return None
    if not isinstance(value, str):
        raise StageError(
            "invalid optional finding field",
            stage="review_findings",
            details={"field": key, "value": value},
        )
    trimmed = value.strip()
    return trimmed or None


def _optional_probability(value: Any, *, key: str) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise StageError(
            "probability field must be numeric or null",
            stage="review_findings",
            details={"field": key, "value": value},
        )
    out = float(value)
    if out < 0.0 or out > 1.0:
        raise StageError(
            "probability field out of range",
            stage="review_findings",
            details={"field": key, "value": out},
        )
    return out


def _normalize_line_range(
    line_start_raw: Any, line_end_raw: Any
) -> tuple[int | None, int | None]:
    if line_start_raw is None and line_end_raw is None:
        return (None, None)
    if line_start_raw is None or line_end_raw is None:
        raise StageError(
            "line_start and line_end must both be present or both be null",
            stage="review_findings",
            details={"line_start": line_start_raw, "line_end": line_end_raw},
        )
    if isinstance(line_start_raw, bool) or not isinstance(line_start_raw, int):
        raise StageError(
            "line_start must be integer",
            stage="review_findings",
            details={"line_start": line_start_raw},
        )
    if isinstance(line_end_raw, bool) or not isinstance(line_end_raw, int):
        raise StageError(
            "line_end must be integer",
            stage="review_findings",
            details={"line_end": line_end_raw},
        )
    if line_start_raw < 1 or line_end_raw < 1:
        raise StageError(
            "line range values must be >= 1",
            stage="review_findings",
            details={"line_start": line_start_raw, "line_end": line_end_raw},
        )
    if line_end_raw < line_start_raw:
        raise StageError(
            "line_end cannot be less than line_start",
            stage="review_findings",
            details={"line_start": line_start_raw, "line_end": line_end_raw},
        )
    return (line_start_raw, line_end_raw)


def _normalize_evidence(value: Any) -> dict[str, list[str]]:
    if value is None:
        return {"anchors": [], "signals": []}
    if not isinstance(value, dict):
        raise StageError(
            "finding evidence must be an object",
            stage="review_findings",
            details={"evidence": value},
        )
    unknown = set(value.keys()) - {"anchors", "signals"}
    if unknown:
        raise StageError(
            "finding evidence has unknown keys",
            stage="review_findings",
            details={"keys": sorted(unknown)},
        )

    anchors = _string_list(value.get("anchors", []), key="anchors")
    signals = _string_list(value.get("signals", []), key="signals")
    return {
        "anchors": sorted(set(anchors)),
        "signals": sorted(set(signals)),
    }


def _string_list(value: Any, *, key: str) -> list[str]:
    if not isinstance(value, list):
        raise StageError(
            "evidence list field must be array",
            stage="review_findings",
            details={"field": key, "value": value},
        )
    out: list[str] = []
    for idx, item in enumerate(value):
        if not isinstance(item, str):
            raise StageError(
                "evidence values must be strings",
                stage="review_findings",
                details={"field": key, "index": idx, "value": item},
            )
        text = item.strip()
        if text:
            out.append(text)
    return out
