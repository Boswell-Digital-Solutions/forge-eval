from __future__ import annotations

from typing import Iterable

from forge_eval.errors import StageError

LineRange = tuple[int, int]


def range_line_count(rng: LineRange) -> int:
    return rng[1] - rng[0] + 1


def clamp_range(rng: LineRange, *, min_line: int, max_line: int) -> LineRange:
    start, end = rng
    if min_line < 1:
        raise StageError(
            "invalid clamp bounds",
            stage="context_slices",
            details={"min_line": min_line, "max_line": max_line},
        )
    if max_line < min_line:
        raise StageError(
            "invalid clamp bounds",
            stage="context_slices",
            details={"min_line": min_line, "max_line": max_line},
        )
    if start > end:
        raise StageError(
            "invalid range with start > end",
            stage="context_slices",
            details={"range": [start, end]},
        )

    clamped_start = max(min_line, start)
    clamped_end = min(max_line, end)
    if clamped_start > clamped_end:
        return (clamped_start, clamped_start)
    return (clamped_start, clamped_end)


def merge_ranges(
    ranges: Iterable[LineRange], *, merge_gap_lines: int
) -> list[LineRange]:
    if merge_gap_lines < 0:
        raise StageError(
            "merge_gap_lines cannot be negative",
            stage="context_slices",
            details={"merge_gap_lines": merge_gap_lines},
        )

    ordered = sorted(ranges, key=lambda r: (r[0], r[1]))
    if not ordered:
        return []

    merged: list[LineRange] = [ordered[0]]
    for next_start, next_end in ordered[1:]:
        cur_start, cur_end = merged[-1]
        if next_start <= (cur_end + 1 + merge_gap_lines):
            merged[-1] = (cur_start, max(cur_end, next_end))
        else:
            merged.append((next_start, next_end))
    return merged


def split_range(rng: LineRange, *, max_lines: int) -> list[LineRange]:
    if max_lines <= 0:
        raise StageError(
            "max_lines must be > 0",
            stage="context_slices",
            details={"max_lines": max_lines},
        )
    start, end = rng
    if start > end:
        raise StageError(
            "invalid range with start > end",
            stage="context_slices",
            details={"range": [start, end]},
        )

    length = range_line_count(rng)
    if length <= max_lines:
        return [rng]

    out: list[LineRange] = []
    cursor = start
    while cursor <= end:
        chunk_end = min(end, cursor + max_lines - 1)
        out.append((cursor, chunk_end))
        cursor = chunk_end + 1
    return out


def split_ranges(ranges: Iterable[LineRange], *, max_lines: int) -> list[LineRange]:
    out: list[LineRange] = []
    for rng in ranges:
        out.extend(split_range(rng, max_lines=max_lines))
    return out


def total_line_count(ranges: Iterable[LineRange]) -> int:
    total = 0
    for rng in ranges:
        total += range_line_count(rng)
    return total


def overlap_line_count(a: LineRange, b: LineRange) -> int:
    start = max(a[0], b[0])
    end = min(a[1], b[1])
    if end < start:
        return 0
    return end - start + 1


def overlap_with_ranges(target: LineRange, changed_ranges: Iterable[LineRange]) -> int:
    return sum(overlap_line_count(target, other) for other in changed_ranges)
