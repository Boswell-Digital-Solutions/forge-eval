from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from forge_eval.config import normalize_config
from forge_eval.stage_runner import run_pipeline
from forge_eval.validation.schema_loader import load_schema
from forge_eval.validation.validate_artifact import load_json_file, validate_instance
from tests._evidence_test_helper import write_fake_evidence_binary

pytestmark = pytest.mark.integration


def _run(cmd: list[str], cwd: Path) -> str:
    proc = subprocess.run(
        cmd,
        cwd=str(cwd),
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    return proc.stdout.strip()


def _init_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    _run(["git", "init"], repo)
    _run(["git", "config", "user.email", "forge@example.com"], repo)
    _run(["git", "config", "user.name", "Forge Test"], repo)
    return repo


def _commit_all(repo: Path, message: str) -> None:
    _run(["git", "add", "-A"], repo)
    _run(["git", "commit", "-m", message], repo)


def test_pipeline_emits_review_telemetry_occupancy_capture_hazard_merge_decision_and_evidence_bundle_artifacts_and_is_deterministic(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo = _init_repo(tmp_path)
    fake = write_fake_evidence_binary(tmp_path / "forge-evidence")
    monkeypatch.setenv("FORGE_EVIDENCE_BIN", str(fake))
    (repo / "a.py").write_text("def add(a, b):\n    return a + b\n", encoding="utf-8")
    (repo / "README.md").write_text("# Example\n", encoding="utf-8")
    _commit_all(repo, "base")

    (repo / "a.py").write_text(
        "def add(a, b):\n    # TODO: verify overflow behavior\n    return a + b\n",
        encoding="utf-8",
    )
    _commit_all(repo, "head")

    cfg = normalize_config({})
    out1 = tmp_path / "out1"
    out2 = tmp_path / "out2"

    result1 = run_pipeline(
        repo_path=repo,
        base_ref="HEAD~1",
        head_ref="HEAD",
        out_dir=out1,
        config=cfg,
    )
    result2 = run_pipeline(
        repo_path=repo,
        base_ref="HEAD~1",
        head_ref="HEAD",
        out_dir=out2,
        config=cfg,
    )

    assert "review_findings.json" in result1["artifacts_written"]
    assert "review_findings.json" in result2["artifacts_written"]
    assert "telemetry_matrix.json" in result1["artifacts_written"]
    assert "telemetry_matrix.json" in result2["artifacts_written"]
    assert "occupancy_snapshot.json" in result1["artifacts_written"]
    assert "occupancy_snapshot.json" in result2["artifacts_written"]
    assert "capture_estimate.json" in result1["artifacts_written"]
    assert "capture_estimate.json" in result2["artifacts_written"]
    assert "hazard_map.json" in result1["artifacts_written"]
    assert "hazard_map.json" in result2["artifacts_written"]
    assert "merge_decision.json" in result1["artifacts_written"]
    assert "merge_decision.json" in result2["artifacts_written"]
    assert "evidence_bundle.json" in result1["artifacts_written"]
    assert "evidence_bundle.json" in result2["artifacts_written"]

    artifact1 = out1 / "review_findings.json"
    artifact2 = out2 / "review_findings.json"
    assert artifact1.read_bytes() == artifact2.read_bytes()

    telemetry1 = out1 / "telemetry_matrix.json"
    telemetry2 = out2 / "telemetry_matrix.json"
    assert telemetry1.read_bytes() == telemetry2.read_bytes()

    occupancy1 = out1 / "occupancy_snapshot.json"
    occupancy2 = out2 / "occupancy_snapshot.json"
    assert occupancy1.read_bytes() == occupancy2.read_bytes()

    capture1 = out1 / "capture_estimate.json"
    capture2 = out2 / "capture_estimate.json"
    assert capture1.read_bytes() == capture2.read_bytes()

    hazard1 = out1 / "hazard_map.json"
    hazard2 = out2 / "hazard_map.json"
    assert hazard1.read_bytes() == hazard2.read_bytes()

    merge1 = out1 / "merge_decision.json"
    merge2 = out2 / "merge_decision.json"
    assert merge1.read_bytes() == merge2.read_bytes()

    evidence1 = out1 / "evidence_bundle.json"
    evidence2 = out2 / "evidence_bundle.json"
    assert evidence1.read_bytes() == evidence2.read_bytes()

    schema = load_schema("review_findings")
    parsed = load_json_file(artifact1)
    validate_instance(parsed, schema, artifact_kind="review_findings")
    assert all(
        str(finding["defect_key"]).startswith("dfk_") for finding in parsed["findings"]
    )

    telemetry_schema = load_schema("telemetry_matrix")
    telemetry = load_json_file(telemetry1)
    validate_instance(telemetry, telemetry_schema, artifact_kind="telemetry_matrix")
    assert telemetry["summary"]["k_eff"] >= 0

    occupancy_schema = load_schema("occupancy_snapshot")
    occupancy = load_json_file(occupancy1)
    validate_instance(occupancy, occupancy_schema, artifact_kind="occupancy_snapshot")
    assert 0.0 <= occupancy["summary"]["mean_psi_post"] <= 1.0

    capture_schema = load_schema("capture_estimate")
    capture = load_json_file(capture1)
    validate_instance(capture, capture_schema, artifact_kind="capture_estimate")
    assert capture["estimators"]["selected_hidden"] >= 0.0

    hazard_schema = load_schema("hazard_map")
    hazard = load_json_file(hazard1)
    validate_instance(hazard, hazard_schema, artifact_kind="hazard_map")
    assert 0.0 <= hazard["summary"]["hazard_score"] <= 1.0

    merge_schema = load_schema("merge_decision")
    merge = load_json_file(merge1)
    validate_instance(merge, merge_schema, artifact_kind="merge_decision")
    assert merge["decision"]["result"] in {"allow", "caution", "block"}

    evidence_schema = load_schema("evidence_bundle")
    evidence = load_json_file(evidence1)
    validate_instance(evidence, evidence_schema, artifact_kind="evidence_bundle")
    assert evidence["decision"]["result"] == merge["decision"]["result"]
    assert evidence["summary"]["artifact_count"] == 9


def test_pipeline_coalesces_cross_reviewer_defects_when_reviewers_share_identity(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo = _init_repo(tmp_path)
    fake = write_fake_evidence_binary(tmp_path / "forge-evidence")
    monkeypatch.setenv("FORGE_EVIDENCE_BIN", str(fake))
    (repo / "README.md").write_text("# Example\n", encoding="utf-8")
    _commit_all(repo, "base")

    (repo / "README.md").write_text("# Example\n\nExtra docs note.\n", encoding="utf-8")
    _commit_all(repo, "head")

    cfg = normalize_config(
        {
            "reviewers": [
                {
                    "reviewer_id": "changed_lines.rule.v1",
                    "kind": "changed_lines",
                    "enabled": True,
                    "failure_mode": "fail_stage",
                    "scope_rules": {"include_extensions": [".md"]},
                    "finding_rules": {
                        "default_severity": "medium",
                        "default_category": "docs",
                        "confidence": 0.7,
                    },
                },
                {
                    "reviewer_id": "changed_lines.peer.v1",
                    "kind": "changed_lines",
                    "enabled": True,
                    "failure_mode": "fail_stage",
                    "scope_rules": {"include_extensions": [".md"]},
                    "finding_rules": {
                        "default_severity": "medium",
                        "default_category": "docs",
                        "confidence": 0.7,
                    },
                },
            ]
        }
    )
    out = tmp_path / "out"

    run_pipeline(
        repo_path=repo,
        base_ref="HEAD~1",
        head_ref="HEAD",
        out_dir=out,
        config=cfg,
    )

    review = load_json_file(out / "review_findings.json")
    telemetry = load_json_file(out / "telemetry_matrix.json")
    capture = load_json_file(out / "capture_estimate.json")

    defect_keys = sorted(str(item["defect_key"]) for item in review["findings"])
    assert len(defect_keys) == 2
    assert defect_keys[0] == defect_keys[1]

    defect = telemetry["defects"][0]
    assert defect["reported_by"] == ["changed_lines.peer.v1", "changed_lines.rule.v1"]
    assert defect["support_count"] == 2

    row = telemetry["matrix"][0]
    assert row["observations"]["changed_lines.peer.v1"] == 1
    assert row["observations"]["changed_lines.rule.v1"] == 1

    assert capture["counts"]["f1"] == 0
    assert capture["counts"]["f2"] == 1
    assert capture["counts"]["incidence_histogram"] == {"2": 1}
