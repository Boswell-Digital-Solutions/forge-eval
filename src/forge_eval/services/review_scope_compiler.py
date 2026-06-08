from __future__ import annotations

from typing import Any

from forge_eval.errors import StageError


def compile_review_scope(
    *,
    block_candidates: list[dict[str, Any]],
    config: dict[str, Any],
) -> list[dict[str, Any]]:
    max_scope_lines = config.get("localization_max_review_scope_lines", 500)
    max_per_file = config.get("localization_max_scope_lines_per_file", 150)

    if not block_candidates:
        raise StageError(
            "localization_pack: no block candidates to compile review scope",
            stage="localization_pack",
        )

    by_file: dict[str, list[tuple[int, int]]] = {}
    for bc in block_candidates:
        fp = bc["file_path"]
        start = bc["start_line"]
        end = bc["end_line"]
        if fp not in by_file:
            by_file[fp] = []
        by_file[fp].append((start, end))

    scope: list[dict[str, Any]] = []
    total_lines = 0

    for fp in sorted(by_file.keys()):
        ranges = sorted(by_file[fp])
        merged = _merge_ranges(ranges)
        merged = _clamp_ranges(merged, max_per_file)

        for start, end in merged:
            line_count = end - start + 1
            if total_lines + line_count > max_scope_lines:
                remaining = max_scope_lines - total_lines
                if remaining > 0:
                    scope.append(
                        {
                            "file_path": fp,
                            "start_line": start,
                            "end_line": start + remaining - 1,
                        }
                    )
                    total_lines += remaining
                break
            scope.append(
                {
                    "file_path": fp,
                    "start_line": start,
                    "end_line": end,
                }
            )
            total_lines += line_count

        if total_lines >= max_scope_lines:
            break

    if not scope:
        raise StageError(
            "localization_pack: review scope is empty after compilation",
            stage="localization_pack",
        )

    return scope


def _merge_ranges(ranges: list[tuple[int, int]]) -> list[tuple[int, int]]:
    if not ranges:
        return []
    sorted_ranges = sorted(ranges)
    merged: list[tuple[int, int]] = [sorted_ranges[0]]
    for start, end in sorted_ranges[1:]:
        prev_start, prev_end = merged[-1]
        if start <= prev_end + 1:
            merged[-1] = (prev_start, max(prev_end, end))
        else:
            merged.append((start, end))
    return merged


def _clamp_ranges(
    ranges: list[tuple[int, int]],
    max_lines: int,
) -> list[tuple[int, int]]:
    result: list[tuple[int, int]] = []
    total = 0
    for start, end in ranges:
        line_count = end - start + 1
        if total + line_count > max_lines:
            remaining = max_lines - total
            if remaining > 0:
                result.append((start, start + remaining - 1))
                total += remaining
            break
        result.append((start, end))
        total += line_count
    return result
