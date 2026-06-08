from __future__ import annotations

from pathlib import Path
from typing import Any, Iterable

from forge_eval.services.slice_extractor import extract_context_slices


def run_stage(
    *,
    repo_path: str | Path,
    base_ref: str,
    head_ref: str,
    run_id: str,
    config: dict[str, Any],
    target_file_subset: Iterable[str] | None = None,
) -> dict[str, object]:
    repo = Path(repo_path)

    extracted = extract_context_slices(
        repo_path=repo,
        base_ref=base_ref,
        head_ref=head_ref,
        config=config,
        target_file_subset=target_file_subset,
    )

    return {
        "schema_version": "v1",
        "kind": "context_slices",
        "run_id": run_id,
        "repo_path": str(repo.resolve()),
        "base_ref": base_ref,
        "head_ref": head_ref,
        "config": {
            "context_radius_lines": int(config["context_radius_lines"]),
            "merge_gap_lines": int(config["merge_gap_lines"]),
            "max_slices_per_target": int(config["max_slices_per_target"]),
            "max_lines_per_slice": int(config["max_lines_per_slice"]),
            "max_total_lines": int(config["max_total_lines"]),
            "fail_on_slice_truncation": bool(config["fail_on_slice_truncation"]),
            "binary_file_policy": str(config["binary_file_policy"]),
        },
        "slices": extracted["slices"],
        "summary": extracted["summary"],
        "provenance": {
            "algorithm": "context_slice_extraction_v1",
            "head_version_content": True,
            "deterministic": True,
        },
    }
