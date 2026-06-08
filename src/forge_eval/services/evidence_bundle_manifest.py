from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from forge_eval.errors import StageError
from forge_eval.evidence_cli import EvidenceCli

_HASHCHAIN_SEED = "forge-evidence-chain-v1"


def required_bundle_artifacts() -> tuple[tuple[str, str], ...]:
    return (
        ("config_resolved", "config.resolved.json"),
        ("risk_heatmap", "risk_heatmap.json"),
        ("context_slices", "context_slices.json"),
        ("review_findings", "review_findings.json"),
        ("telemetry_matrix", "telemetry_matrix.json"),
        ("occupancy_snapshot", "occupancy_snapshot.json"),
        ("capture_estimate", "capture_estimate.json"),
        ("hazard_map", "hazard_map.json"),
        ("merge_decision", "merge_decision.json"),
    )


def build_evidence_manifest(
    *, artifacts_dir: str | Path, evidence_cli: EvidenceCli
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    out_dir = Path(artifacts_dir)
    specs = required_bundle_artifacts()
    entries: list[dict[str, Any]] = []
    manifest_inputs: list[dict[str, str]] = []

    for index, (kind, rel_path) in enumerate(specs):
        file_path = out_dir / rel_path
        if not file_path.exists() or not file_path.is_file():
            raise StageError(
                "evidence bundle requires upstream artifact file",
                stage="evidence_bundle",
                details={"artifact_kind": kind, "path": str(file_path)},
            )
        canonical = evidence_cli.canonicalize_json(rel_path, cwd=out_dir)
        canonical_sha256 = hashlib.sha256(canonical).hexdigest()
        artifact_id = evidence_cli.artifact_id(rel_path, kind, cwd=out_dir)
        entries.append(
            {
                "index": index,
                "kind": kind,
                "path": rel_path,
                "canonical_sha256": canonical_sha256,
                "artifact_id": artifact_id,
                "file_size_bytes": file_path.stat().st_size,
            }
        )
        manifest_inputs.append({"path": rel_path, "kind": kind})

    temp_manifest = out_dir / "_evidence_hashchain_inputs.json"
    temp_manifest.write_text(
        json.dumps(
            {"artifacts": manifest_inputs},
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
        )
        + "\n",
        encoding="utf-8",
    )
    try:
        hashchain = evidence_cli.hashchain(temp_manifest.name, cwd=out_dir)
    finally:
        temp_manifest.unlink(missing_ok=True)

    manifest = _normalize_and_validate_hashchain(hashchain=hashchain, entries=entries)
    return entries, manifest


def _normalize_and_validate_hashchain(
    *, hashchain: dict[str, Any], entries: list[dict[str, Any]]
) -> dict[str, Any]:
    if hashchain.get("kind") != "hashchain":
        raise StageError(
            "forge-evidence hashchain output kind mismatch",
            stage="evidence_bundle",
            details={"kind": hashchain.get("kind")},
        )
    artifact_hashes = hashchain.get("artifact_hashes")
    chain_hashes = hashchain.get("chain_hashes")
    final_chain_hash = hashchain.get("final_chain_hash")
    if (
        not isinstance(artifact_hashes, list)
        or not isinstance(chain_hashes, list)
        or not isinstance(final_chain_hash, str)
    ):
        raise StageError(
            "forge-evidence hashchain output missing required fields",
            stage="evidence_bundle",
            details={"hashchain": hashchain},
        )
    if len(artifact_hashes) != len(entries):
        raise StageError(
            "forge-evidence hashchain artifact count mismatch",
            stage="evidence_bundle",
            details={"expected": len(entries), "actual": len(artifact_hashes)},
        )
    if len(chain_hashes) != len(entries) + 1:
        raise StageError(
            "forge-evidence hashchain length mismatch",
            stage="evidence_bundle",
            details={"expected": len(entries) + 1, "actual": len(chain_hashes)},
        )

    normalized_order: list[str] = []
    for expected, actual in zip(entries, artifact_hashes, strict=True):
        if not isinstance(actual, dict):
            raise StageError(
                "forge-evidence artifact hash entry must be object",
                stage="evidence_bundle",
                details={"entry": actual},
            )
        actual_path = _normalize_hashchain_path(actual.get("path"))
        actual_kind = actual.get("kind")
        actual_sha = actual.get("artifact_sha256")
        actual_id = actual.get("artifact_id")
        if actual_path != expected["path"]:
            raise StageError(
                "forge-evidence hashchain path order mismatch",
                stage="evidence_bundle",
                details={"expected": expected["path"], "actual": actual_path},
            )
        if actual_kind != expected["kind"]:
            raise StageError(
                "forge-evidence hashchain kind mismatch",
                stage="evidence_bundle",
                details={"expected": expected["kind"], "actual": actual_kind},
            )
        if actual_sha != expected["canonical_sha256"]:
            raise StageError(
                "forge-evidence hashchain canonical sha mismatch",
                stage="evidence_bundle",
                details={
                    "path": expected["path"],
                    "expected": expected["canonical_sha256"],
                    "actual": actual_sha,
                },
            )
        if actual_id != expected["artifact_id"]:
            raise StageError(
                "forge-evidence hashchain artifact id mismatch",
                stage="evidence_bundle",
                details={
                    "path": expected["path"],
                    "expected": expected["artifact_id"],
                    "actual": actual_id,
                },
            )
        normalized_order.append(actual_path)

    normalized_chain_hashes = [
        _require_hex(item, field="chain_hashes") for item in chain_hashes
    ]
    normalized_final_chain_hash = _require_hex(
        final_chain_hash, field="final_chain_hash"
    )
    if normalized_chain_hashes[-1] != normalized_final_chain_hash:
        raise StageError(
            "forge-evidence final chain hash does not match terminal chain hash",
            stage="evidence_bundle",
            details={
                "final_chain_hash": normalized_final_chain_hash,
                "terminal_chain_hash": normalized_chain_hashes[-1],
            },
        )

    return {
        "hashchain_seed": _HASHCHAIN_SEED,
        "artifact_order": normalized_order,
        "chain_hashes": normalized_chain_hashes,
        "final_chain_hash": normalized_final_chain_hash,
    }


def _normalize_hashchain_path(value: Any) -> str:
    if not isinstance(value, str) or not value:
        raise StageError(
            "forge-evidence hashchain path must be non-empty string",
            stage="evidence_bundle",
            details={"path": value},
        )
    normalized = value.replace("\\", "/")
    while normalized.startswith("./"):
        normalized = normalized[2:]
    return normalized


def _require_hex(value: Any, *, field: str) -> str:
    if (
        not isinstance(value, str)
        or len(value) != 64
        or any(ch not in "0123456789abcdef" for ch in value)
    ):
        raise StageError(
            "forge-evidence hash output must be lowercase 64-char hex",
            stage="evidence_bundle",
            details={"field": field, "value": value},
        )
    return value
