from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from forge_eval.errors import StageError
from forge_eval.services.git_diff import (
    file_content_at_ref,
    list_changed_files,
    numstat_for_file,
    path_has_allowed_extension,
    path_is_excluded,
    unified_diff_for_file,
)
from forge_eval.services.range_ops import (
    LineRange,
    clamp_range,
    merge_ranges,
    overlap_with_ranges,
    range_line_count,
    split_ranges,
)

_HUNK_RE = re.compile(r"^@@\s+-\d+(?:,\d+)?\s+\+(\d+)(?:,(\d+))?\s+@@")


@dataclass(frozen=True)
class ChangedHunk:
    start_line: int
    end_line: int
    changed_line_count: int


def parse_unified_diff_hunks(diff_text: str) -> list[ChangedHunk]:
    hunks: list[ChangedHunk] = []
    for raw_line in diff_text.splitlines():
        if not raw_line.startswith("@@"):
            continue

        match = _HUNK_RE.match(raw_line)
        if not match:
            raise StageError(
                "failed to parse unified diff hunk",
                stage="context_slices",
                details={"line": raw_line},
            )

        start_line = int(match.group(1))
        count = int(match.group(2) or "1")

        if count == 0:
            # Deletion-only hunk in head context maps to insertion point line.
            hunks.append(
                ChangedHunk(
                    start_line=start_line, end_line=start_line, changed_line_count=0
                )
            )
            continue

        end_line = start_line + count - 1
        hunks.append(
            ChangedHunk(
                start_line=start_line, end_line=end_line, changed_line_count=count
            )
        )

    return hunks


def _render_slice_content(lines: list[str], rng: LineRange) -> str:
    start, end = rng
    # line numbers are 1-based and inclusive
    chunk = lines[start - 1 : end]
    return "\n".join(chunk)


def _build_slice(
    *,
    file_path: str,
    rng: LineRange,
    file_lines: list[str],
    changed_ranges: list[LineRange],
    base_ref: str,
    head_ref: str,
) -> dict[str, object]:
    changed_line_count = overlap_with_ranges(rng, changed_ranges)
    total_line_count = range_line_count(rng)
    start_line, end_line = rng

    return {
        "slice_id": f"{file_path}:{start_line}:{end_line}",
        "file_path": file_path,
        "start_line": start_line,
        "end_line": end_line,
        "changed_line_count": changed_line_count,
        "total_line_count": total_line_count,
        "content": _render_slice_content(file_lines, rng),
        "origin": {
            "source": "git_diff_head_version",
            "base_ref": base_ref,
            "head_ref": head_ref,
            "changed_ranges": [[start, end] for start, end in changed_ranges],
        },
    }


def _extract_file_slices(
    *,
    repo_path: Path,
    file_path: str,
    base_ref: str,
    head_ref: str,
    config: dict[str, object],
) -> list[dict[str, object]]:
    added, deleted, is_binary = numstat_for_file(
        repo_path, base_ref, head_ref, file_path
    )
    if is_binary:
        policy = str(config["binary_file_policy"])
        if policy == "ignore":
            return []
        raise StageError(
            "binary file changed and policy is fail",
            stage="context_slices",
            details={"file_path": file_path},
        )

    content = file_content_at_ref(repo_path, head_ref, file_path)
    file_lines = content.splitlines()
    line_count = len(file_lines)
    if line_count == 0:
        return []

    diff_text = unified_diff_for_file(
        repo_path,
        base_ref,
        head_ref,
        file_path,
        unified_lines=0,
    )
    hunks = parse_unified_diff_hunks(diff_text)
    if not hunks:
        return []

    radius = int(config["context_radius_lines"])
    merge_gap_lines = int(config["merge_gap_lines"])
    max_lines_per_slice = int(config["max_lines_per_slice"])
    max_slices_per_target = int(config["max_slices_per_target"])
    fail_on_slice_truncation = bool(config["fail_on_slice_truncation"])

    changed_ranges: list[LineRange] = [(h.start_line, h.end_line) for h in hunks]

    expanded_ranges: list[LineRange] = []
    for start, end in changed_ranges:
        expanded = (start - radius, end + radius)
        expanded_ranges.append(clamp_range(expanded, min_line=1, max_line=line_count))

    merged = merge_ranges(expanded_ranges, merge_gap_lines=merge_gap_lines)
    split = split_ranges(merged, max_lines=max_lines_per_slice)

    if len(split) > max_slices_per_target:
        if fail_on_slice_truncation:
            raise StageError(
                "max_slices_per_target exceeded",
                stage="context_slices",
                details={
                    "file_path": file_path,
                    "max_slices_per_target": max_slices_per_target,
                    "actual_slices": len(split),
                },
            )
        split = split[:max_slices_per_target]

    split.sort(key=lambda rng: (rng[0], rng[1]))

    return [
        _build_slice(
            file_path=file_path,
            rng=rng,
            file_lines=file_lines,
            changed_ranges=changed_ranges,
            base_ref=base_ref,
            head_ref=head_ref,
        )
        for rng in split
    ]


def extract_context_slices(
    *,
    repo_path: str | Path,
    base_ref: str,
    head_ref: str,
    config: dict[str, object],
    target_file_subset: Iterable[str] | None = None,
) -> dict[str, object]:
    repo = Path(repo_path)
    include_extensions = list(config["include_file_extensions"])
    exclude_paths = list(config["exclude_paths"])
    max_total_lines = int(config["max_total_lines"])

    target_set = None
    if target_file_subset is not None:
        target_set = {path.replace("\\", "/") for path in target_file_subset}

    changed_files = list_changed_files(repo, base_ref, head_ref)

    slices: list[dict[str, object]] = []
    included_targets: list[str] = []

    for changed in changed_files:
        if changed.status == "D":
            continue

        candidate_path = changed.path.replace("\\", "/")
        if target_set is not None and candidate_path not in target_set:
            continue
        if path_is_excluded(candidate_path, exclude_paths):
            continue
        if not path_has_allowed_extension(candidate_path, include_extensions):
            continue

        file_slices = _extract_file_slices(
            repo_path=repo,
            file_path=candidate_path,
            base_ref=base_ref,
            head_ref=head_ref,
            config=config,
        )
        if file_slices:
            included_targets.append(candidate_path)
        slices.extend(file_slices)

    slices.sort(
        key=lambda s: (str(s["file_path"]), int(s["start_line"]), int(s["end_line"]))
    )

    running_total = 0
    for slc in slices:
        running_total += int(slc["total_line_count"])
        if running_total > max_total_lines:
            raise StageError(
                "max_total_lines exceeded",
                stage="context_slices",
                details={
                    "max_total_lines": max_total_lines,
                    "actual_total_lines": running_total,
                },
            )

    return {
        "slices": slices,
        "summary": {
            "target_count": len(sorted(set(included_targets))),
            "slice_count": len(slices),
            "total_line_count": running_total,
        },
    }
