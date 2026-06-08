from __future__ import annotations

from typing import Any

from forge_eval.errors import StageError

_ALLOWED_APPLICABILITY_MODES = {"reviewer_kind_scope_v1"}


def reviewer_applicable_to_defect(
    *,
    reviewer: dict[str, Any],
    reviewer_config: dict[str, Any],
    defect: dict[str, Any],
    applicability_mode: str,
) -> bool:
    if applicability_mode not in _ALLOWED_APPLICABILITY_MODES:
        raise StageError(
            "unsupported telemetry applicability mode",
            stage="telemetry_matrix",
            details={"mode": applicability_mode},
        )

    file_path = str(defect.get("file_path", "")).replace("\\", "/")
    if not file_path:
        raise StageError(
            "defect missing file_path for applicability check",
            stage="telemetry_matrix",
            details={"defect_key": defect.get("defect_key")},
        )

    scope_rules = reviewer_config.get("scope_rules")
    if not isinstance(scope_rules, dict):
        raise StageError(
            "reviewer config missing scope_rules",
            stage="telemetry_matrix",
            details={"reviewer_id": reviewer.get("reviewer_id")},
        )

    include_extensions = [
        str(item).lower() for item in scope_rules.get("include_extensions", [])
    ]
    exclude_paths = [
        str(item).replace("\\", "/") for item in scope_rules.get("exclude_paths", [])
    ]

    lowered_path = file_path.lower()
    if include_extensions and not any(
        lowered_path.endswith(ext) for ext in include_extensions
    ):
        return False
    if any(file_path.startswith(prefix) for prefix in exclude_paths):
        return False

    kind = str(reviewer.get("kind", ""))
    if kind == "documentation_consistency":
        return lowered_path.endswith(".md")
    if kind == "structural_risk":
        return not lowered_path.endswith(".md")
    if kind == "changed_lines":
        return True

    raise StageError(
        "unsupported reviewer kind in applicability",
        stage="telemetry_matrix",
        details={"reviewer_id": reviewer.get("reviewer_id"), "kind": kind},
    )
