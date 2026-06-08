from __future__ import annotations

from pathlib import Path
from typing import Any

from forge_eval.services.git_diff import (
    list_changed_files,
    list_tracked_files,
    numstat_for_file,
    path_has_allowed_extension,
    path_is_excluded,
)
from forge_eval.services.risk_analysis import build_risk_targets, compute_centrality_scores


def run_stage(
    *,
    repo_path: str | Path,
    base_ref: str,
    head_ref: str,
    run_id: str,
    config: dict[str, Any],
) -> dict[str, Any]:
    repo = Path(repo_path)

    include_extensions = list(config["include_file_extensions"])
    exclude_paths = list(config["exclude_paths"])

    changed_entries = list_changed_files(repo, base_ref, head_ref)
    changed_paths = sorted(
        {
            item.path.replace("\\", "/")
            for item in changed_entries
            if item.status != "D"
            and not path_is_excluded(item.path, exclude_paths)
            and path_has_allowed_extension(item.path, include_extensions)
        }
    )

    churn_by_path: dict[str, tuple[int, int]] = {}
    for path in changed_paths:
        added, deleted, _is_binary = numstat_for_file(repo, base_ref, head_ref, path)
        churn_by_path[path] = (added, deleted)

    tracked_files = list_tracked_files(repo)
    centrality_scores = compute_centrality_scores(
        repo_path=str(repo),
        head_ref=head_ref,
        tracked_files=tracked_files,
        include_extensions=include_extensions,
        exclude_paths=exclude_paths,
    )

    targets = build_risk_targets(
        changed_paths=changed_paths,
        churn_by_path=churn_by_path,
        centrality_scores=centrality_scores,
        risk_weights=dict(config["risk_weights"]),
        path_weights=dict(config["path_weights"]),
    )

    risk_values = [float(target["risk_score"]) for target in targets]

    return {
        "schema_version": "v1",
        "kind": "risk_heatmap",
        "run_id": run_id,
        "repo_path": str(repo.resolve()),
        "base_ref": base_ref,
        "head_ref": head_ref,
        "weights": dict(config["risk_weights"]),
        "targets": targets,
        "summary": {
            "target_count": len(targets),
            "min_risk_score": min(risk_values) if risk_values else 0.0,
            "max_risk_score": max(risk_values) if risk_values else 0.0,
        },
        "provenance": {
            "algorithm": "structural_risk_v1",
            "deterministic": True,
        },
    }
