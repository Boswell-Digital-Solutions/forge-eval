from __future__ import annotations

from typing import Any

from forge_eval.errors import StageError

_SUPPORTED_MODEL = "evidence_bundle_rev1"


def load_evidence_bundle_model(config: dict[str, Any]) -> dict[str, Any]:
    model_version = str(config.get("evidence_bundle_model_version", ""))
    if model_version != _SUPPORTED_MODEL:
        raise StageError(
            "unsupported evidence bundle model version",
            stage="evidence_bundle",
            details={"evidence_bundle_model_version": model_version},
        )

    return {
        "name": _SUPPORTED_MODEL,
        "mode": "deterministic_manifest_assembly",
        "evidence_runtime": "forge_evidence_cli",
        "parameters": {
            "hash_strategy": "canonical_json_sha256",
            "artifact_id_strategy": "kind_nul_canonical_json",
            "hashchain_strategy": "forge_evidence_chain_v1",
        },
    }
