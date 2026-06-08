from __future__ import annotations

import copy
import hashlib
from pathlib import Path
from typing import Any

from forge_eval.adapters.centipede_input import (
    CENTIPEDE_INPUT_SCHEMA_VERSION,
    CentipedeInput,
    load_centipede_input,
)
from forge_eval.contracts.evaluation_spine import (
    build_forge_eval_evidence_bundle_payload,
    validate_forge_eval_evidence_bundle_payload,
)
from forge_eval.errors import StageError
from forge_eval.services.git_diff import resolve_commit
from forge_eval.stage_runner import (
    _compute_run_id,
    validate_artifacts_directory,
    write_json_file,
)
from forge_eval.stages.context_slices import run_stage as run_context_slices_stage
from forge_eval.stages.risk_heatmap import run_stage as run_risk_heatmap_stage
from forge_eval.validation.schema_loader import load_all_schemas
from forge_eval.validation.validate_artifact import validate_instance

CENTIPEDE_ENABLED_STAGES = ["risk_heatmap", "context_slices"]
CENTIPEDE_BUNDLE_KIND = "forge_eval_evidence_bundle"
CENTIPEDE_BUNDLE_SCHEMA_VERSION = "v1"
CENTIPEDE_CONTRACT_PAYLOAD_FILENAME = "forge_eval_evidence_bundle.contract.json"


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _filter_risk_artifact_to_target_refs(
    *,
    risk_artifact: dict[str, Any],
    input_contract: CentipedeInput,
) -> dict[str, Any]:
    requested_paths = set(input_contract.target_file_paths)
    targets = [
        target
        for target in risk_artifact.get("targets", [])
        if str(target.get("file_path", "")).replace("\\", "/") in requested_paths
    ]

    present_paths = {
        str(target.get("file_path", "")).replace("\\", "/") for target in targets
    }
    missing_paths = sorted(requested_paths - present_paths)
    if missing_paths:
        raise StageError(
            "centipede target refs were not present in the evaluated git diff",
            stage="centipede_adapter",
            details={
                "missing_target_refs": missing_paths,
                "base_ref": input_contract.base_ref,
                "head_ref": input_contract.head_ref,
            },
        )

    filtered = copy.deepcopy(risk_artifact)
    risk_values = [float(target["risk_score"]) for target in targets]
    filtered["targets"] = targets
    filtered["summary"] = {
        "target_count": len(targets),
        "min_risk_score": min(risk_values) if risk_values else 0.0,
        "max_risk_score": max(risk_values) if risk_values else 0.0,
    }
    return filtered


def _target_refs_payload(input_contract: CentipedeInput) -> list[dict[str, str]]:
    return [
        {
            "target_id": target.target_id,
            "file_path": target.file_path,
            "source_kind": target.source_kind,
        }
        for target in input_contract.target_refs
    ]


def _build_forge_eval_evidence_bundle(
    *,
    out_dir: Path,
    input_contract: CentipedeInput,
    run_id: str,
    base_commit: str,
    head_commit: str,
) -> dict[str, Any]:
    artifact_filenames = [
        "config.resolved.json",
        "risk_heatmap.json",
        "context_slices.json",
    ]
    artifact_refs = []
    for filename in artifact_filenames:
        path = out_dir / filename
        if not path.exists():
            raise StageError(
                "cannot build forge eval evidence bundle because an artifact is missing",
                stage="forge_eval_evidence_bundle",
                details={"missing_artifact": filename, "path": str(path)},
            )
        artifact_refs.append(
            {
                "artifact_kind": filename.removesuffix(".json").replace(
                    ".resolved", "_resolved"
                ),
                "artifact_path": filename,
                "artifact_hash": _sha256_file(path),
                "hash_algorithm": "sha256",
            }
        )

    return {
        "schema_version": CENTIPEDE_BUNDLE_SCHEMA_VERSION,
        "kind": CENTIPEDE_BUNDLE_KIND,
        "run_id": run_id,
        "repo_path": str(input_contract.repo_path.resolve()),
        "base_ref": input_contract.base_ref,
        "head_ref": input_contract.head_ref,
        "base_commit": base_commit,
        "head_commit": head_commit,
        "input_contract": {
            "schema_version": CENTIPEDE_INPUT_SCHEMA_VERSION,
            "target_ref_count": len(input_contract.target_refs),
            "target_refs": _target_refs_payload(input_contract),
            "metadata": input_contract.metadata,
        },
        "artifact_refs": artifact_refs,
        "provenance": {
            "adapter": "centipede_to_forge_eval_phase_03_contract_core_bridge",
            "deterministic": True,
            "fails_closed_on_missing_target_refs": True,
            "hash_algorithm": "sha256",
            "contract_family": "forge_eval_evidence_bundle",
            "contract_version": 1,
        },
    }


def run_centipede_pipeline(
    *,
    input_path: str | Path,
    out_dir: str | Path,
    config: dict[str, Any],
    schema_dir: str | Path | None = None,
) -> dict[str, Any]:
    input_contract = load_centipede_input(input_path)
    repo = input_contract.repo_path.resolve()
    out = Path(out_dir).resolve()

    if not repo.exists():
        raise StageError(
            "repository path does not exist",
            stage="centipede_adapter",
            details={"repo_path": str(repo)},
        )

    centipede_config = copy.deepcopy(config)
    centipede_config["enabled_stages"] = list(CENTIPEDE_ENABLED_STAGES)

    base_commit = resolve_commit(repo, input_contract.base_ref)
    head_commit = resolve_commit(repo, input_contract.head_ref)
    run_id = _compute_run_id(repo, base_commit, head_commit)

    schemas = load_all_schemas(schema_dir)

    resolved_config_artifact = {
        "schema_version": "v1",
        "kind": "config_resolved",
        "run_id": run_id,
        "repo_path": str(repo),
        "base_ref": input_contract.base_ref,
        "head_ref": input_contract.head_ref,
        "base_commit": base_commit,
        "head_commit": head_commit,
        "enabled_stages": list(CENTIPEDE_ENABLED_STAGES),
        "config": centipede_config,
    }
    write_json_file(out / "config.resolved.json", resolved_config_artifact)

    risk_artifact = run_risk_heatmap_stage(
        repo_path=repo,
        base_ref=input_contract.base_ref,
        head_ref=input_contract.head_ref,
        run_id=run_id,
        config=centipede_config,
    )
    risk_artifact = _filter_risk_artifact_to_target_refs(
        risk_artifact=risk_artifact,
        input_contract=input_contract,
    )
    validate_instance(
        risk_artifact, schemas["risk_heatmap"], artifact_kind="risk_heatmap"
    )
    write_json_file(out / "risk_heatmap.json", risk_artifact)

    context_artifact = run_context_slices_stage(
        repo_path=repo,
        base_ref=input_contract.base_ref,
        head_ref=input_contract.head_ref,
        run_id=run_id,
        config=centipede_config,
        target_file_subset=input_contract.target_file_paths,
    )
    validate_instance(
        context_artifact, schemas["context_slices"], artifact_kind="context_slices"
    )
    write_json_file(out / "context_slices.json", context_artifact)

    bundle_artifact = _build_forge_eval_evidence_bundle(
        out_dir=out,
        input_contract=input_contract,
        run_id=run_id,
        base_commit=base_commit,
        head_commit=head_commit,
    )
    validate_instance(
        bundle_artifact,
        schemas[CENTIPEDE_BUNDLE_KIND],
        artifact_kind=CENTIPEDE_BUNDLE_KIND,
    )
    local_bundle_path = out / "forge_eval_evidence_bundle.json"
    write_json_file(local_bundle_path, bundle_artifact)

    validation_result = validate_artifacts_directory(
        artifacts_dir=out, schema_dir=schema_dir
    )

    contract_payload = build_forge_eval_evidence_bundle_payload(
        local_bundle=bundle_artifact,
        input_contract=input_contract,
        repo=repo,
        base_commit=base_commit,
        head_commit=head_commit,
        local_bundle_hash=_sha256_file(local_bundle_path),
        validation_refs=["forge_eval.local_artifact_validation:passed"],
    )
    contract_validation_result = validate_forge_eval_evidence_bundle_payload(
        contract_payload
    )
    contract_payload["validation_refs"] = sorted(
        set(contract_payload.get("validation_refs", []))
        | {
            "forge_contract_core.role_matrix:passed",
            "forge_contract_core.family_payload:passed",
        }
    )
    contract_validation_result = validate_forge_eval_evidence_bundle_payload(
        contract_payload
    )
    write_json_file(out / CENTIPEDE_CONTRACT_PAYLOAD_FILENAME, contract_payload)

    return {
        "run_id": run_id,
        "base_commit": base_commit,
        "head_commit": head_commit,
        "artifacts_written": [
            "config.resolved.json",
            "risk_heatmap.json",
            "context_slices.json",
            "forge_eval_evidence_bundle.json",
            CENTIPEDE_CONTRACT_PAYLOAD_FILENAME,
        ],
        "validation": validation_result,
        "contract_validation": contract_validation_result,
    }
