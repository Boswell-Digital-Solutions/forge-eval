from __future__ import annotations

from typing import Any


def build_patch_scope(
    *,
    config: dict[str, Any],
    patch_targets_artifact: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    if patch_targets_artifact is None:
        return []

    targets = patch_targets_artifact.get("targets", [])
    patch_scope: list[dict[str, Any]] = []
    for target in targets:
        target_id = target.get("target_id", "")
        file_path = target.get("file_path", "")
        allow_ranges = target.get("allow_ranges", [])
        patch_scope.append(
            {
                "target_id": target_id,
                "file_path": file_path,
                "allow_ranges": allow_ranges,
            }
        )

    patch_scope.sort(key=lambda p: (p["file_path"], p["target_id"]))
    return patch_scope
