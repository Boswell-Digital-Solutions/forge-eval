from __future__ import annotations

import json
from pathlib import Path

import pytest

from forge_eval.errors import StageError
from forge_eval.evidence_cli import EvidenceCliError
from forge_eval.stages.evidence_bundle import run_stage
from tests._evidence_test_helper import write_fake_evidence_binary

REQUIRED_FILES = {
    "config.resolved.json": {
        "schema_version": "v1",
        "kind": "config_resolved",
        "run_id": "run-1",
        "repo_path": "/tmp/repo",
        "base_ref": "base",
        "head_ref": "head",
        "base_commit": "aaa",
        "head_commit": "bbb",
        "enabled_stages": [
            "risk_heatmap",
            "context_slices",
            "review_findings",
            "telemetry_matrix",
            "occupancy_snapshot",
            "capture_estimate",
            "hazard_map",
            "merge_decision",
            "evidence_bundle",
        ],
        "config": {"evidence_bundle_model_version": "evidence_bundle_rev1"},
    },
    "risk_heatmap.json": {
        "schema_version": "v1",
        "kind": "risk_heatmap",
        "run_id": "run-1",
        "repo_path": "/tmp/repo",
        "base_ref": "base",
        "head_ref": "head",
    },
    "context_slices.json": {
        "schema_version": "v1",
        "kind": "context_slices",
        "run_id": "run-1",
        "repo_path": "/tmp/repo",
        "base_ref": "base",
        "head_ref": "head",
    },
    "review_findings.json": {
        "artifact_version": 1,
        "kind": "review_findings",
        "run": {
            "run_id": "run-1",
            "repo_path": "/tmp/repo",
            "base_ref": "base",
            "head_ref": "head",
            "base_commit": "aaa",
            "head_commit": "bbb",
        },
    },
    "telemetry_matrix.json": {
        "artifact_version": 1,
        "kind": "telemetry_matrix",
        "run": {
            "run_id": "run-1",
            "repo_path": "/tmp/repo",
            "base_ref": "base",
            "head_ref": "head",
            "base_commit": "aaa",
            "head_commit": "bbb",
        },
    },
    "occupancy_snapshot.json": {
        "artifact_version": 1,
        "kind": "occupancy_snapshot",
        "run": {
            "run_id": "run-1",
            "repo_path": "/tmp/repo",
            "base_ref": "base",
            "head_ref": "head",
            "base_commit": "aaa",
            "head_commit": "bbb",
        },
    },
    "capture_estimate.json": {
        "artifact_version": 1,
        "kind": "capture_estimate",
        "run": {
            "run_id": "run-1",
            "repo_path": "/tmp/repo",
            "base_ref": "base",
            "head_ref": "head",
            "base_commit": "aaa",
            "head_commit": "bbb",
        },
    },
    "hazard_map.json": {
        "artifact_version": 1,
        "kind": "hazard_map",
        "run": {
            "run_id": "run-1",
            "repo_path": "/tmp/repo",
            "base_ref": "base",
            "head_ref": "head",
            "base_commit": "aaa",
            "head_commit": "bbb",
        },
        "summary": {
            "hazard_score": 0.55,
            "hazard_tier": "elevated",
            "blocking_signals_present": True,
            "hidden_pressure": 1.0,
            "uncertainty_flags": ["WEAK_SUPPORT"],
        },
    },
    "merge_decision.json": {
        "artifact_version": 1,
        "kind": "merge_decision",
        "run": {
            "run_id": "run-1",
            "repo_path": "/tmp/repo",
            "base_ref": "base",
            "head_ref": "head",
            "base_commit": "aaa",
            "head_commit": "bbb",
            "hazard_artifact": "hazard_map.json",
        },
        "decision": {
            "result": "block",
            "advisory": True,
            "blocking_conditions_present": True,
            "caution_conditions_present": True,
        },
        "summary": {
            "decision_label": "BLOCK",
            "hazard_score": 0.55,
            "dominant_hazard_tier": "elevated",
            "blocking_signals_present": True,
            "blocking_reason_count": 1,
            "caution_reason_count": 1,
            "reason_code_count": 2,
            "uncertainty_flag_count": 1,
        },
        "reason_codes": ["HAZARD_BLOCKING_SIGNAL_PRESENT", "HAZARD_TIER_ELEVATED"],
    },
}


def _write_json(path: Path, payload: dict) -> None:
    path.write_text(
        json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
        + "\n",
        encoding="utf-8",
    )


def _materialize_artifacts(tmp_path: Path) -> Path:
    out = tmp_path / "artifacts"
    out.mkdir()
    for name, payload in REQUIRED_FILES.items():
        _write_json(out / name, payload)
    return out


def _stage_inputs() -> dict:
    return {
        "resolved_config_artifact": REQUIRED_FILES["config.resolved.json"],
        "risk_heatmap_artifact": REQUIRED_FILES["risk_heatmap.json"],
        "context_slices_artifact": REQUIRED_FILES["context_slices.json"],
        "review_findings_artifact": REQUIRED_FILES["review_findings.json"],
        "telemetry_matrix_artifact": REQUIRED_FILES["telemetry_matrix.json"],
        "occupancy_snapshot_artifact": REQUIRED_FILES["occupancy_snapshot.json"],
        "capture_estimate_artifact": REQUIRED_FILES["capture_estimate.json"],
        "hazard_map_artifact": REQUIRED_FILES["hazard_map.json"],
        "merge_decision_artifact": REQUIRED_FILES["merge_decision.json"],
    }


def test_evidence_bundle_stage_emits_deterministic_manifest(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    out = _materialize_artifacts(tmp_path)
    fake = write_fake_evidence_binary(tmp_path / "forge-evidence")
    monkeypatch.setenv("FORGE_EVIDENCE_BIN", str(fake))

    artifact = run_stage(
        repo_path="/tmp/repo",
        artifacts_dir=out,
        base_ref="base",
        head_ref="head",
        run_id="run-1",
        config={"evidence_bundle_model_version": "evidence_bundle_rev1"},
        **_stage_inputs(),
    )

    assert artifact["kind"] == "evidence_bundle"
    assert artifact["decision"]["result"] == "block"
    assert artifact["inputs"]["evidence_runtime"] == "forge_evidence_cli"
    assert artifact["model"]["name"] == "evidence_bundle_rev1"
    assert artifact["summary"]["artifact_count"] == 9
    assert (
        artifact["summary"]["final_chain_hash"]
        == artifact["manifest"]["final_chain_hash"]
    )
    assert [item["path"] for item in artifact["artifacts"]] == [
        "config.resolved.json",
        "risk_heatmap.json",
        "context_slices.json",
        "review_findings.json",
        "telemetry_matrix.json",
        "occupancy_snapshot.json",
        "capture_estimate.json",
        "hazard_map.json",
        "merge_decision.json",
    ]


def test_evidence_bundle_missing_upstream_file_fails_closed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    out = _materialize_artifacts(tmp_path)
    fake = write_fake_evidence_binary(tmp_path / "forge-evidence")
    monkeypatch.setenv("FORGE_EVIDENCE_BIN", str(fake))
    (out / "hazard_map.json").unlink()

    with pytest.raises(StageError, match="requires upstream artifact file"):
        run_stage(
            repo_path="/tmp/repo",
            artifacts_dir=out,
            base_ref="base",
            head_ref="head",
            run_id="run-1",
            config={"evidence_bundle_model_version": "evidence_bundle_rev1"},
            **_stage_inputs(),
        )


def test_evidence_bundle_run_id_mismatch_fails_closed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    out = _materialize_artifacts(tmp_path)
    fake = write_fake_evidence_binary(tmp_path / "forge-evidence")
    monkeypatch.setenv("FORGE_EVIDENCE_BIN", str(fake))
    merge = json.loads(json.dumps(REQUIRED_FILES["merge_decision.json"]))
    merge["run"]["run_id"] = "other"

    with pytest.raises(StageError, match="run_id mismatch"):
        run_stage(
            repo_path="/tmp/repo",
            artifacts_dir=out,
            base_ref="base",
            head_ref="head",
            run_id="run-1",
            config={"evidence_bundle_model_version": "evidence_bundle_rev1"},
            merge_decision_artifact=merge,
            **{
                k: v
                for k, v in _stage_inputs().items()
                if k != "merge_decision_artifact"
            },
        )


def test_evidence_bundle_unsupported_model_version_fails_closed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    out = _materialize_artifacts(tmp_path)
    fake = write_fake_evidence_binary(tmp_path / "forge-evidence")
    monkeypatch.setenv("FORGE_EVIDENCE_BIN", str(fake))

    with pytest.raises(StageError, match="unsupported evidence bundle model version"):
        run_stage(
            repo_path="/tmp/repo",
            artifacts_dir=out,
            base_ref="base",
            head_ref="head",
            run_id="run-1",
            config={"evidence_bundle_model_version": "evidence_bundle_revX"},
            **_stage_inputs(),
        )


def test_evidence_bundle_evidence_cli_failure_fails_closed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    out = _materialize_artifacts(tmp_path)
    fake = write_fake_evidence_binary(tmp_path / "forge-evidence")
    monkeypatch.setenv("FORGE_EVIDENCE_BIN", str(fake))
    monkeypatch.setenv("FORGE_FAKE_EVIDENCE_FAIL", "hashchain")

    with pytest.raises(EvidenceCliError, match="non-zero exit code"):
        run_stage(
            repo_path="/tmp/repo",
            artifacts_dir=out,
            base_ref="base",
            head_ref="head",
            run_id="run-1",
            config={"evidence_bundle_model_version": "evidence_bundle_rev1"},
            **_stage_inputs(),
        )
