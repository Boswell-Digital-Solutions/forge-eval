from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest
from forge_contract_core.validators.families import validate_family_payload
from forge_contract_core.validators.role_matrix import check_producer_admitted

from forge_eval.centipede_runner import run_centipede_pipeline
from forge_eval.config import load_config
from forge_eval.errors import StageError, ValidationError


def _run(cmd: list[str], *, cwd: Path) -> None:
    subprocess.run(cmd, cwd=cwd, check=True, text=True, capture_output=True)


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _make_two_commit_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    _run(["git", "init"], cwd=repo)
    _run(["git", "config", "user.email", "forge-eval@example.invalid"], cwd=repo)
    _run(["git", "config", "user.name", "Forge Eval Test"], cwd=repo)

    _write(repo / "src" / "app.py", "def answer():\n    return 41\n")
    _write(repo / "docs" / "notes.md", "# Notes\n\nBase\n")
    _run(["git", "add", "."], cwd=repo)
    _run(["git", "commit", "-m", "base"], cwd=repo)

    _write(repo / "src" / "app.py", "def answer():\n    return 42\n")
    _write(repo / "docs" / "notes.md", "# Notes\n\nChanged\n")
    _run(["git", "add", "."], cwd=repo)
    _run(["git", "commit", "-m", "head"], cwd=repo)
    return repo


def _write_centipede_input(
    path: Path, *, repo: Path, target_refs: list[object]
) -> Path:
    payload = {
        "schema_version": "ForgeEvalCentipedeInput.v1",
        "repo_path": str(repo),
        "base_ref": "HEAD~1",
        "head_ref": "HEAD",
        "target_refs": target_refs,
        "metadata": {
            "test_case": path.stem,
            "repository_id": "forge-eval-test-repo",
            "source_projection_id": f"projection:{path.stem}",
            "source_fused_bundle_id": f"fused-bundle:{path.stem}",
        },
    }
    path.write_text(json.dumps(payload, sort_keys=True), encoding="utf-8")
    return path


def test_centipede_pipeline_writes_minimum_phase_03_artifacts(tmp_path: Path) -> None:
    repo = _make_two_commit_repo(tmp_path)
    input_path = _write_centipede_input(
        tmp_path / "centipede_input.json",
        repo=repo,
        target_refs=[
            {
                "target_id": "target-001",
                "file_path": "src/app.py",
                "source_kind": "unit_test",
            }
        ],
    )
    out = tmp_path / "artifacts"

    result = run_centipede_pipeline(
        input_path=input_path,
        out_dir=out,
        config=load_config(None),
    )

    assert result["artifacts_written"] == [
        "config.resolved.json",
        "risk_heatmap.json",
        "context_slices.json",
        "forge_eval_evidence_bundle.json",
        "forge_eval_evidence_bundle.contract.json",
    ]
    assert result["contract_validation"] == {
        "producer_repo_id": "forge-eval",
        "artifact_family": "forge_eval_evidence_bundle",
        "artifact_version": 1,
        "validation_state": "passed",
    }
    assert sorted(path.name for path in out.iterdir()) == [
        "config.resolved.json",
        "context_slices.json",
        "forge_eval_evidence_bundle.contract.json",
        "forge_eval_evidence_bundle.json",
        "risk_heatmap.json",
    ]

    risk = json.loads((out / "risk_heatmap.json").read_text(encoding="utf-8"))
    assert risk["summary"]["target_count"] == 1
    assert [target["file_path"] for target in risk["targets"]] == ["src/app.py"]

    bundle = json.loads(
        (out / "forge_eval_evidence_bundle.json").read_text(encoding="utf-8")
    )
    assert bundle["kind"] == "forge_eval_evidence_bundle"
    assert bundle["input_contract"]["schema_version"] == "ForgeEvalCentipedeInput.v1"
    assert bundle["input_contract"]["target_ref_count"] == 1
    assert {ref["artifact_path"] for ref in bundle["artifact_refs"]} == {
        "config.resolved.json",
        "risk_heatmap.json",
        "context_slices.json",
    }
    assert all(ref["hash_algorithm"] == "sha256" for ref in bundle["artifact_refs"])
    assert all(len(ref["artifact_hash"]) == 64 for ref in bundle["artifact_refs"])

    contract_payload = json.loads(
        (out / "forge_eval_evidence_bundle.contract.json").read_text(encoding="utf-8")
    )
    assert contract_payload["schema_version"] == "forge_eval.evidence_bundle.v1"
    assert contract_payload["forge_eval_run_id"] == result["run_id"]
    assert contract_payload["source_projection_id"] == "projection:centipede_input"
    assert contract_payload["source_fused_bundle_id"] == "fused-bundle:centipede_input"
    assert contract_payload["repository_id"] == "forge-eval-test-repo"
    assert contract_payload["base_ref"] == result["base_commit"]
    assert contract_payload["head_ref"] == result["head_commit"]
    assert contract_payload["deterministic"] is True
    assert contract_payload["validation_state"] == "passed"
    assert (
        "forge_contract_core.family_payload:passed"
        in contract_payload["validation_refs"]
    )
    assert (
        "forge_contract_core.role_matrix:passed" in contract_payload["validation_refs"]
    )
    assert {ref["artifact_kind"] for ref in contract_payload["artifact_refs"]} == {
        "config_resolved",
        "risk_heatmap",
        "context_slices",
        "forge_eval_evidence_bundle",
    }
    assert all("hash_algorithm" not in ref for ref in contract_payload["artifact_refs"])
    assert all(
        ref["artifact_hash"].startswith("sha256:")
        for ref in contract_payload["artifact_refs"]
    )

    check_producer_admitted("forge-eval", "forge_eval_evidence_bundle")
    validate_family_payload("forge_eval_evidence_bundle", 1, contract_payload)


def test_centipede_pipeline_fails_closed_when_target_ref_not_in_diff(
    tmp_path: Path,
) -> None:
    repo = _make_two_commit_repo(tmp_path)
    input_path = _write_centipede_input(
        tmp_path / "centipede_input.json",
        repo=repo,
        target_refs=["src/not_changed.py"],
    )

    with pytest.raises(StageError) as exc_info:
        run_centipede_pipeline(
            input_path=input_path,
            out_dir=tmp_path / "artifacts",
            config=load_config(None),
        )

    assert exc_info.value.stage == "centipede_adapter"
    assert exc_info.value.details["missing_target_refs"] == ["src/not_changed.py"]


def test_centipede_input_requires_target_refs(tmp_path: Path) -> None:
    repo = _make_two_commit_repo(tmp_path)
    input_path = _write_centipede_input(
        tmp_path / "centipede_input.json",
        repo=repo,
        target_refs=[],
    )

    with pytest.raises(ValidationError):
        run_centipede_pipeline(
            input_path=input_path,
            out_dir=tmp_path / "artifacts",
            config=load_config(None),
        )
