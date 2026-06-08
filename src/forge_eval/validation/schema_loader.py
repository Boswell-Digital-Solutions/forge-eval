from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from forge_eval.errors import ValidationError

SCHEMA_BY_ARTIFACT = {
    "risk_heatmap": "risk_heatmap.schema.json",
    "context_slices": "context_slices.schema.json",
    "review_findings": "review_findings.schema.json",
    "telemetry_matrix": "telemetry_matrix.schema.json",
    "occupancy_snapshot": "occupancy_snapshot.schema.json",
    "capture_estimate": "capture_estimate.schema.json",
    "calibration_report": "calibration_report.schema.json",
    "hazard_map": "hazard_map.schema.json",
    "merge_decision": "merge_decision.schema.json",
    "evidence_bundle": "evidence_bundle.schema.json",
    "forge_eval_evidence_bundle": "forge_eval_evidence_bundle.schema.json",
    "localization_pack": "localization_pack.schema.json",
    "localization_summary": "localization_summary.schema.json",
}


def default_schema_dir() -> Path:
    return Path(__file__).resolve().parent.parent / "schemas"


def load_schema(
    artifact_kind: str, schema_dir: str | Path | None = None
) -> dict[str, Any]:
    if artifact_kind not in SCHEMA_BY_ARTIFACT:
        raise ValidationError(
            "unknown artifact kind for schema lookup",
            details={"artifact_kind": artifact_kind},
        )
    base = Path(schema_dir) if schema_dir is not None else default_schema_dir()
    schema_file = base / SCHEMA_BY_ARTIFACT[artifact_kind]
    if not schema_file.exists():
        raise ValidationError(
            "schema file is missing", details={"path": str(schema_file)}
        )
    try:
        return json.loads(schema_file.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValidationError(
            "schema file is invalid JSON",
            details={"path": str(schema_file), "error": str(exc)},
        ) from exc


def load_all_schemas(schema_dir: str | Path | None = None) -> dict[str, dict[str, Any]]:
    return {
        kind: load_schema(kind, schema_dir=schema_dir)
        for kind in sorted(SCHEMA_BY_ARTIFACT.keys())
    }
