from __future__ import annotations

from pathlib import Path
from typing import Any

from forge_eval.errors import StageError
from forge_eval.services.capture_counts import build_capture_counts
from forge_eval.services.capture_selection import select_hidden_estimate
from forge_eval.services.capture_summary import build_capture_summary
from forge_eval.services.chao1 import estimate_chao1
from forge_eval.services.chao2 import estimate_chao2
from forge_eval.services.ice import estimate_ice


def run_stage(
    *,
    repo_path: str | Path,
    base_ref: str,
    head_ref: str,
    run_id: str,
    config: dict[str, Any],
    telemetry_matrix_artifact: dict[str, Any],
    occupancy_snapshot_artifact: dict[str, Any],
) -> dict[str, Any]:
    _validate_telemetry_artifact(telemetry_matrix_artifact)
    _validate_occupancy_artifact(occupancy_snapshot_artifact)

    telemetry_run = telemetry_matrix_artifact["run"]
    occupancy_run = occupancy_snapshot_artifact["run"]
    _validate_run_alignment(
        run_id=run_id, telemetry_run=telemetry_run, occupancy_run=occupancy_run
    )

    round_digits = _required_round_digits(config)
    counts_result = build_capture_counts(
        telemetry_matrix_artifact=telemetry_matrix_artifact,
        occupancy_snapshot_artifact=occupancy_snapshot_artifact,
        config=config,
    )
    counts = counts_result["counts"]
    included_rows = counts_result["included_rows"]

    observed = int(counts["included_rows"])
    telemetry_summary = telemetry_matrix_artifact["summary"]
    k_usable = telemetry_summary.get("k_usable")
    if isinstance(k_usable, bool) or not isinstance(k_usable, int) or k_usable < 0:
        raise StageError(
            "telemetry summary has invalid k_usable",
            stage="capture_estimate",
            details={"k_usable": k_usable},
        )

    chao1 = estimate_chao1(
        observed=observed,
        f1=int(counts["f1"]),
        f2=int(counts["f2"]),
        round_digits=round_digits,
    )
    chao2 = estimate_chao2(
        observed=observed,
        q1=int(counts["f1"]),
        q2=int(counts["f2"]),
        m=int(k_usable),
        round_digits=round_digits,
    )
    ice = estimate_ice(
        observed=observed,
        incidence_histogram=dict(counts["incidence_histogram"]),
        rare_threshold=int(counts["ice"]["rare_threshold"]),
        fallback_hidden=float(chao1["hidden"]),
        round_digits=round_digits,
    )
    selection = select_hidden_estimate(
        observed=observed,
        chao1=chao1,
        chao2=chao2,
        ice=ice,
        selection_policy=str(config["capture_selection_policy"]),
        round_digits=round_digits,
    )
    summary = build_capture_summary(
        counts=counts,
        selection=selection,
        chao1=chao1,
        chao2=chao2,
        ice=ice,
        included_rows=included_rows,
        round_digits=round_digits,
    )

    repo = Path(repo_path)
    run_payload = {
        "run_id": run_id,
        "repo_path": str(repo.resolve()),
        "base_ref": base_ref,
        "head_ref": head_ref,
        "base_commit": str(telemetry_run["base_commit"]),
        "head_commit": str(telemetry_run["head_commit"]),
        "telemetry_artifact": "telemetry_matrix.json",
        "occupancy_artifact": "occupancy_snapshot.json",
    }

    return {
        "artifact_version": 1,
        "kind": "capture_estimate",
        "run": run_payload,
        "inputs": {
            "mode": "deterministic_conservative",
            "occupancy_inclusion_policy": str(config["capture_inclusion_policy"]),
            "chao1_variant": "bias_corrected",
            "ice_rare_threshold": int(config["ice_rare_threshold"]),
            "selection_policy": str(config["capture_selection_policy"]),
            "sparse_guard_policy": "enabled",
            "round_digits": round_digits,
        },
        "counts": counts,
        "estimators": {
            "chao1": chao1,
            "chao2": chao2,
            "ice": ice,
            **selection,
        },
        "summary": summary,
        "provenance": {
            "algorithm": "capture_estimate_v1",
            "deterministic": True,
            "inputs": ["telemetry_matrix.json", "occupancy_snapshot.json"],
            "inclusion_policy": str(config["capture_inclusion_policy"]),
            "selection_policy": str(config["capture_selection_policy"]),
        },
    }


def _validate_telemetry_artifact(artifact: dict[str, Any]) -> None:
    if artifact.get("kind") != "telemetry_matrix":
        raise StageError(
            "capture_estimate requires telemetry_matrix artifact",
            stage="capture_estimate",
            details={"kind": artifact.get("kind")},
        )
    run = artifact.get("run")
    if not isinstance(run, dict):
        raise StageError(
            "telemetry_matrix artifact missing run object",
            stage="capture_estimate",
        )
    for field in ("run_id", "base_commit", "head_commit"):
        if not isinstance(run.get(field), str) or not str(run[field]):
            raise StageError(
                "telemetry_matrix artifact run object missing required fields",
                stage="capture_estimate",
                details={"field": field, "value": run.get(field)},
            )


def _validate_occupancy_artifact(artifact: dict[str, Any]) -> None:
    if artifact.get("kind") != "occupancy_snapshot":
        raise StageError(
            "capture_estimate requires occupancy_snapshot artifact",
            stage="capture_estimate",
            details={"kind": artifact.get("kind")},
        )
    run = artifact.get("run")
    if not isinstance(run, dict):
        raise StageError(
            "occupancy_snapshot artifact missing run object",
            stage="capture_estimate",
        )
    for field in ("run_id", "base_commit", "head_commit"):
        if not isinstance(run.get(field), str) or not str(run[field]):
            raise StageError(
                "occupancy_snapshot artifact run object missing required fields",
                stage="capture_estimate",
                details={"field": field, "value": run.get(field)},
            )


def _validate_run_alignment(
    *,
    run_id: str,
    telemetry_run: dict[str, Any],
    occupancy_run: dict[str, Any],
) -> None:
    if str(telemetry_run["run_id"]) != str(run_id) or str(
        occupancy_run["run_id"]
    ) != str(run_id):
        raise StageError(
            "run_id mismatch across pipeline, telemetry, and occupancy artifacts",
            stage="capture_estimate",
            details={
                "pipeline_run_id": run_id,
                "telemetry_run_id": telemetry_run["run_id"],
                "occupancy_run_id": occupancy_run["run_id"],
            },
        )
    for field in ("base_commit", "head_commit"):
        if str(telemetry_run[field]) != str(occupancy_run[field]):
            raise StageError(
                "telemetry and occupancy artifacts disagree on run commits",
                stage="capture_estimate",
                details={
                    "field": field,
                    "telemetry_value": telemetry_run[field],
                    "occupancy_value": occupancy_run[field],
                },
            )


def _required_round_digits(config: dict[str, Any]) -> int:
    value = config.get("capture_round_digits")
    if isinstance(value, bool) or not isinstance(value, int) or value < 0 or value > 12:
        raise StageError(
            "capture_round_digits must be an integer in [0, 12]",
            stage="capture_estimate",
            details={"value": value},
        )
    return value
