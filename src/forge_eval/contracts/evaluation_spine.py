from __future__ import annotations

from pathlib import Path
from typing import Any

from forge_eval.adapters.centipede_input import CentipedeInput
from forge_eval.errors import ValidationError

FORGE_EVAL_EVIDENCE_BUNDLE_FAMILY = "forge_eval_evidence_bundle"
FORGE_EVAL_EVIDENCE_BUNDLE_VERSION = 1
FORGE_EVAL_EVIDENCE_BUNDLE_SCHEMA_VERSION = "forge_eval.evidence_bundle.v1"
FORGE_EVAL_PRODUCER_REPO_ID = "forge-eval"


def _metadata_string(metadata: dict[str, Any], *keys: str) -> str | None:
    for key in keys:
        value = metadata.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _to_canonical_sha256(value: str) -> str:
    normalized = value.strip().lower()
    if normalized.startswith("sha256:"):
        digest = normalized.removeprefix("sha256:")
    else:
        digest = normalized
    if len(digest) != 64 or any(char not in "0123456789abcdef" for char in digest):
        raise ValidationError(
            "artifact hash is not a valid sha256 digest",
            details={"artifact_hash": value},
        )
    return f"sha256:{digest}"


def _canonical_artifact_ref(ref: dict[str, Any]) -> dict[str, str]:
    artifact_kind = ref.get("artifact_kind")
    artifact_path = ref.get("artifact_path")
    artifact_hash = ref.get("artifact_hash")
    if not isinstance(artifact_kind, str) or not artifact_kind.strip():
        raise ValidationError("artifact ref is missing artifact_kind")
    if not isinstance(artifact_path, str) or not artifact_path.strip():
        raise ValidationError("artifact ref is missing artifact_path")
    if not isinstance(artifact_hash, str) or not artifact_hash.strip():
        raise ValidationError("artifact ref is missing artifact_hash")
    return {
        "artifact_kind": artifact_kind.strip(),
        "artifact_path": artifact_path.strip(),
        "artifact_hash": _to_canonical_sha256(artifact_hash),
    }


def build_forge_eval_evidence_bundle_payload(
    *,
    local_bundle: dict[str, Any],
    input_contract: CentipedeInput,
    repo: Path,
    base_commit: str,
    head_commit: str,
    local_bundle_hash: str,
    validation_refs: list[str] | None = None,
) -> dict[str, Any]:
    """Build the canonical contract-core payload for the forge-eval evidence bundle.

    The local forge-eval bundle remains an implementation artifact. This payload is
    the Evaluation Spine handoff shape admitted by forge-contract-core phase 02.
    """

    run_id = local_bundle.get("run_id")
    if not isinstance(run_id, str) or not run_id.strip():
        raise ValidationError("local forge-eval bundle is missing run_id")

    metadata = input_contract.metadata
    repository_id = (
        _metadata_string(metadata, "repository_id", "repo_id", "repository")
        or repo.name
    )
    source_projection_id = (
        _metadata_string(
            metadata,
            "source_projection_id",
            "centipede_projection_id",
            "projection_id",
        )
        or f"centipede-projection:{run_id}"
    )
    source_fused_bundle_id = (
        _metadata_string(
            metadata,
            "source_fused_bundle_id",
            "centipede_fused_bundle_id",
            "fused_bundle_id",
        )
        or f"centipede-fused-bundle:{run_id}"
    )

    artifact_refs = [
        _canonical_artifact_ref(ref) for ref in local_bundle.get("artifact_refs", [])
    ]
    artifact_refs.append(
        {
            "artifact_kind": "forge_eval_evidence_bundle",
            "artifact_path": "forge_eval_evidence_bundle.json",
            "artifact_hash": _to_canonical_sha256(local_bundle_hash),
        }
    )

    return {
        "schema_version": FORGE_EVAL_EVIDENCE_BUNDLE_SCHEMA_VERSION,
        "forge_eval_run_id": run_id,
        "source_projection_id": source_projection_id,
        "source_fused_bundle_id": source_fused_bundle_id,
        "repository_id": repository_id,
        "base_ref": base_commit,
        "head_ref": head_commit,
        "artifact_refs": artifact_refs,
        "deterministic": True,
        "validation_state": "passed",
        "validation_refs": list(validation_refs or []),
    }


def validate_forge_eval_evidence_bundle_payload(
    payload: dict[str, Any],
) -> dict[str, Any]:
    """Validate forge-eval's canonical payload through forge-contract-core.

    This bridge intentionally imports forge-contract-core lazily so forge-eval can
    collect and run non-Evaluation-Spine tests without importing the contract repo.
    Evaluation Spine runs fail closed if the canonical dependency is unavailable.
    """

    try:
        from forge_contract_core.validators.families import validate_family_payload
        from forge_contract_core.validators.role_matrix import check_producer_admitted
    except (
        Exception
    ) as exc:  # pragma: no cover - exercised only in missing dependency envs
        raise ValidationError(
            "forge-contract-core is required for Evaluation Spine contract validation",
            details={
                "required_package": "forge_contract_core",
                "artifact_family": FORGE_EVAL_EVIDENCE_BUNDLE_FAMILY,
                "artifact_version": FORGE_EVAL_EVIDENCE_BUNDLE_VERSION,
                "error": str(exc),
            },
        ) from exc

    try:
        check_producer_admitted(
            FORGE_EVAL_PRODUCER_REPO_ID, FORGE_EVAL_EVIDENCE_BUNDLE_FAMILY
        )
        validate_family_payload(
            FORGE_EVAL_EVIDENCE_BUNDLE_FAMILY,
            FORGE_EVAL_EVIDENCE_BUNDLE_VERSION,
            payload,
        )
    except Exception as exc:
        raise ValidationError(
            "forge-eval evidence bundle payload failed forge-contract-core validation",
            details={
                "producer_repo_id": FORGE_EVAL_PRODUCER_REPO_ID,
                "artifact_family": FORGE_EVAL_EVIDENCE_BUNDLE_FAMILY,
                "artifact_version": FORGE_EVAL_EVIDENCE_BUNDLE_VERSION,
                "error": str(exc),
            },
        ) from exc

    return {
        "producer_repo_id": FORGE_EVAL_PRODUCER_REPO_ID,
        "artifact_family": FORGE_EVAL_EVIDENCE_BUNDLE_FAMILY,
        "artifact_version": FORGE_EVAL_EVIDENCE_BUNDLE_VERSION,
        "validation_state": "passed",
    }
