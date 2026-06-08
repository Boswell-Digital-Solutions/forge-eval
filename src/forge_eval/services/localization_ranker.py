from __future__ import annotations

from typing import Any

from forge_eval.errors import StageError


def _collect_file_paths(context_slices_artifact: dict[str, Any]) -> list[str]:
    paths: set[str] = set()
    for s in context_slices_artifact.get("slices", []):
        fp = s.get("file_path")
        if isinstance(fp, str) and fp:
            paths.add(fp)
    return sorted(paths)


def _count_slices_for_file(
    file_path: str, context_slices_artifact: dict[str, Any]
) -> int:
    return sum(
        1
        for s in context_slices_artifact.get("slices", [])
        if s.get("file_path") == file_path
    )


def _slices_for_file(
    file_path: str, context_slices_artifact: dict[str, Any]
) -> list[dict[str, Any]]:
    return [
        s
        for s in context_slices_artifact.get("slices", [])
        if s.get("file_path") == file_path
    ]


def _defect_keys_for_file(
    file_path: str, review_findings_artifact: dict[str, Any]
) -> list[str]:
    keys: list[str] = []
    for finding in review_findings_artifact.get("findings", []):
        if finding.get("file_path") == file_path:
            dk = finding.get("defect_key")
            if isinstance(dk, str) and dk:
                keys.append(dk)
    return sorted(set(keys))


def _support_count_for_file(
    file_path: str, telemetry_matrix_artifact: dict[str, Any]
) -> int:
    max_support = 0
    for row in telemetry_matrix_artifact.get("rows", []):
        if row.get("file_path") == file_path:
            sc = row.get("support_count", 0)
            if sc > max_support:
                max_support = sc
    return max_support


def _hazard_contribution_for_file(
    file_path: str, hazard_map_artifact: dict[str, Any]
) -> float:
    max_hc = 0.0
    for row in hazard_map_artifact.get("rows", []):
        if row.get("file_path") == file_path:
            hc = row.get("hazard_contribution", 0.0)
            if hc > max_hc:
                max_hc = hc
    return max_hc


def _reason_codes_for_file(
    file_path: str, review_findings_artifact: dict[str, Any]
) -> list[str]:
    codes: set[str] = set()
    for finding in review_findings_artifact.get("findings", []):
        if finding.get("file_path") == file_path:
            cat = finding.get("category")
            if cat:
                codes.add(f"finding:{cat}")
            sev = finding.get("severity")
            if sev:
                codes.add(f"severity:{sev}")
    return sorted(codes)


def _normalize(value: float, max_value: float) -> float:
    if max_value <= 0.0:
        return 0.0
    return min(value / max_value, 1.0)


def rank_candidates(
    *,
    config: dict[str, Any],
    context_slices_artifact: dict[str, Any],
    review_findings_artifact: dict[str, Any],
    telemetry_matrix_artifact: dict[str, Any],
    hazard_map_artifact: dict[str, Any],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    round_digits = config.get("localization_round_digits", 6)
    max_file_candidates = config.get("localization_max_file_candidates", 10)
    max_block_candidates = config.get("localization_max_block_candidates", 20)
    weights = config.get(
        "localization_ranking_weights",
        {
            "support_count": 0.35,
            "defect_density": 0.25,
            "hazard_contribution": 0.25,
            "churn": 0.15,
        },
    )

    file_paths = _collect_file_paths(context_slices_artifact)
    if not file_paths:
        raise StageError(
            "localization_pack: no files found in context_slices",
            stage="localization_pack",
        )

    raw_file_data: list[dict[str, Any]] = []
    for fp in file_paths:
        slice_count = _count_slices_for_file(fp, context_slices_artifact)
        support_count = _support_count_for_file(fp, telemetry_matrix_artifact)
        defect_keys = _defect_keys_for_file(fp, review_findings_artifact)
        defect_density = len(defect_keys) / max(slice_count, 1)
        hazard_contribution = _hazard_contribution_for_file(fp, hazard_map_artifact)
        reason_codes = _reason_codes_for_file(fp, review_findings_artifact)

        raw_file_data.append(
            {
                "file_path": fp,
                "slice_count": slice_count,
                "support_count": support_count,
                "defect_keys": defect_keys,
                "defect_density": defect_density,
                "hazard_contribution": hazard_contribution,
                "reason_codes": reason_codes,
            }
        )

    max_support = max((d["support_count"] for d in raw_file_data), default=1)
    max_density = max((d["defect_density"] for d in raw_file_data), default=1.0)
    max_churn = max((d["slice_count"] for d in raw_file_data), default=1)

    file_candidates: list[dict[str, Any]] = []
    for d in raw_file_data:
        raw_score = (
            weights.get("support_count", 0.35)
            * _normalize(d["support_count"], max_support)
            + weights.get("defect_density", 0.25)
            * _normalize(d["defect_density"], max_density)
            + weights.get("hazard_contribution", 0.25) * d["hazard_contribution"]
            + weights.get("churn", 0.15) * _normalize(d["slice_count"], max_churn)
        )
        score = round(max(0.0, min(raw_score, 1.0)), round_digits)
        ed = round(max(0.0, min(d["defect_density"], 1.0)), round_digits)
        confidence = round(
            max(
                0.0,
                min(
                    _normalize(d["support_count"], max(max_support, 1)) * 0.5
                    + ed * 0.5,
                    1.0,
                ),
            ),
            round_digits,
        )

        file_candidates.append(
            {
                "file_path": d["file_path"],
                "detected_language": None,
                "detected_framework": None,
                "score": score,
                "evidence_density": ed,
                "confidence": confidence,
                "reason_codes": d["reason_codes"],
                "defect_keys": d["defect_keys"],
            }
        )

    file_candidates.sort(key=lambda c: (-c["score"], c["file_path"]))
    file_candidates = file_candidates[:max_file_candidates]

    block_candidates = _rank_block_candidates(
        config=config,
        context_slices_artifact=context_slices_artifact,
        review_findings_artifact=review_findings_artifact,
        telemetry_matrix_artifact=telemetry_matrix_artifact,
        hazard_map_artifact=hazard_map_artifact,
        round_digits=round_digits,
        max_block_candidates=max_block_candidates,
        weights=weights,
    )

    return file_candidates, block_candidates


def _defect_keys_for_slice(
    slice_entry: dict[str, Any],
    review_findings_artifact: dict[str, Any],
) -> list[str]:
    file_path = slice_entry.get("file_path")
    start = slice_entry.get("start_line", 0)
    end = slice_entry.get("end_line", 0)
    keys: list[str] = []
    for finding in review_findings_artifact.get("findings", []):
        if finding.get("file_path") != file_path:
            continue
        f_line = finding.get("line", 0)
        if start <= f_line <= end:
            dk = finding.get("defect_key")
            if isinstance(dk, str) and dk:
                keys.append(dk)
    return sorted(set(keys))


def _support_for_slice(
    slice_entry: dict[str, Any],
    telemetry_matrix_artifact: dict[str, Any],
) -> int:
    file_path = slice_entry.get("file_path")
    start = slice_entry.get("start_line", 0)
    end = slice_entry.get("end_line", 0)
    max_sc = 0
    for row in telemetry_matrix_artifact.get("rows", []):
        if row.get("file_path") != file_path:
            continue
        r_line = row.get("line", start)
        if start <= r_line <= end:
            sc = row.get("support_count", 0)
            if sc > max_sc:
                max_sc = sc
    return max_sc


def _hazard_for_slice(
    slice_entry: dict[str, Any],
    hazard_map_artifact: dict[str, Any],
) -> float:
    file_path = slice_entry.get("file_path")
    # Hazard rows are keyed by (file_path, defect_key) and carry no line number,
    # so hazard contribution is taken as the max over the whole file rather than a
    # line-range overlap (unlike _support_for_slice, whose telemetry rows have a line).
    max_hc = 0.0
    for row in hazard_map_artifact.get("rows", []):
        if row.get("file_path") != file_path:
            continue
        hc = row.get("hazard_contribution", 0.0)
        if hc > max_hc:
            max_hc = hc
    return max_hc


def _rank_block_candidates(
    *,
    config: dict[str, Any],
    context_slices_artifact: dict[str, Any],
    review_findings_artifact: dict[str, Any],
    telemetry_matrix_artifact: dict[str, Any],
    hazard_map_artifact: dict[str, Any],
    round_digits: int,
    max_block_candidates: int,
    weights: dict[str, float],
) -> list[dict[str, Any]]:
    slices = context_slices_artifact.get("slices", [])
    if not slices:
        return []

    raw_blocks: list[dict[str, Any]] = []
    for s in slices:
        defect_keys = _defect_keys_for_slice(s, review_findings_artifact)
        support_count = _support_for_slice(s, telemetry_matrix_artifact)
        hazard_contribution = _hazard_for_slice(s, hazard_map_artifact)

        reason_codes: list[str] = []
        if defect_keys:
            reason_codes.append("has_defects")
        if support_count > 1:
            reason_codes.append("multi_reviewer_support")
        if hazard_contribution > 0.5:
            reason_codes.append("high_hazard")

        raw_blocks.append(
            {
                "slice_id": s.get("slice_id", ""),
                "file_path": s.get("file_path", ""),
                "start_line": s.get("start_line", 1),
                "end_line": s.get("end_line", 1),
                "defect_keys": defect_keys,
                "support_count": support_count,
                "hazard_contribution": hazard_contribution,
                "reason_codes": sorted(reason_codes),
            }
        )

    max_support = max((b["support_count"] for b in raw_blocks), default=1)
    max_defects = max((len(b["defect_keys"]) for b in raw_blocks), default=1)

    block_candidates: list[dict[str, Any]] = []
    for b in raw_blocks:
        defect_density_raw = len(b["defect_keys"]) / max(max_defects, 1)
        raw_score = (
            weights.get("support_count", 0.35)
            * _normalize(b["support_count"], max(max_support, 1))
            + weights.get("defect_density", 0.25) * defect_density_raw
            + weights.get("hazard_contribution", 0.25) * b["hazard_contribution"]
            + weights.get("churn", 0.15) * 0.5
        )
        score = round(max(0.0, min(raw_score, 1.0)), round_digits)
        ed = round(max(0.0, min(defect_density_raw, 1.0)), round_digits)
        confidence = round(
            max(
                0.0,
                min(
                    _normalize(b["support_count"], max(max_support, 1)) * 0.5
                    + ed * 0.5,
                    1.0,
                ),
            ),
            round_digits,
        )

        block_candidates.append(
            {
                "slice_id": b["slice_id"],
                "file_path": b["file_path"],
                "detected_language": None,
                "start_line": b["start_line"],
                "end_line": b["end_line"],
                "score": score,
                "evidence_density": ed,
                "confidence": confidence,
                "defect_keys": b["defect_keys"],
                "support_count": b["support_count"],
                "likely_constructs": [],
                "root_cause_hypothesis": None,
                "reason_codes": b["reason_codes"],
            }
        )

    block_candidates.sort(key=lambda c: (-c["score"], c["file_path"], c["slice_id"]))
    block_candidates = block_candidates[:max_block_candidates]

    return block_candidates
