from __future__ import annotations

import json
from pathlib import Path

import pytest

from forge_eval import cli


def _valid_risk_heatmap_artifact() -> dict[str, object]:
    return {
        "schema_version": "v1",
        "kind": "risk_heatmap",
        "run_id": "run123",
        "repo_path": "/tmp/repo",
        "base_ref": "base",
        "head_ref": "head",
        "weights": {
            "w_churn": 0.4,
            "w_centrality": 0.4,
            "w_change_magnitude": 0.2,
        },
        "targets": [
            {
                "target_id": "a.py",
                "file_path": "a.py",
                "churn": {"added_lines": 1, "deleted_lines": 0, "normalized": 1.0},
                "centrality": 0.5,
                "change_magnitude": 0.5,
                "risk_raw": 0.5,
                "risk_score": 1.0,
                "reasons": [
                    {"metric": "churn", "value": 1.0},
                    {"metric": "centrality", "value": 0.5},
                    {"metric": "change_magnitude", "value": 0.5},
                    {"metric": "path_weight", "value": 1.0},
                ],
            }
        ],
        "summary": {"target_count": 1, "min_risk_score": 1.0, "max_risk_score": 1.0},
        "provenance": {"algorithm": "structural_risk_v1", "deterministic": True},
    }


def test_cli_help_smoke() -> None:
    with pytest.raises(SystemExit) as exc:
        cli.main(["--help"])
    assert exc.value.code == 0


def test_cli_run_with_stub_stage(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    called = {}

    def fake_run_pipeline(**kwargs: object) -> dict[str, object]:
        called.update(kwargs)
        return {
            "run_id": "abc",
            "base_commit": "base",
            "head_commit": "head",
            "artifacts_written": ["risk_heatmap.json"],
        }

    monkeypatch.setattr(cli, "run_pipeline", fake_run_pipeline)

    out_dir = tmp_path / "artifacts"
    rc = cli.main(
        [
            "run",
            "--repo",
            str(tmp_path),
            "--base",
            "main",
            "--head",
            "HEAD",
            "--out",
            str(out_dir),
        ]
    )
    assert rc == 0
    assert called["base_ref"] == "main"


def test_cli_validate_with_schema_valid_artifact(tmp_path: Path) -> None:
    artifacts = tmp_path / "artifacts"
    artifacts.mkdir()

    resolved = {
        "schema_version": "v1",
        "kind": "config_resolved",
        "run_id": "run123",
        "enabled_stages": ["risk_heatmap"],
    }
    (artifacts / "config.resolved.json").write_text(
        json.dumps(resolved), encoding="utf-8"
    )
    (artifacts / "risk_heatmap.json").write_text(
        json.dumps(_valid_risk_heatmap_artifact()), encoding="utf-8"
    )

    rc = cli.main(["validate", "--artifacts", str(artifacts)])
    assert rc == 0


def test_cli_validate_fails_on_invalid_artifact(tmp_path: Path) -> None:
    artifacts = tmp_path / "artifacts"
    artifacts.mkdir()

    resolved = {
        "schema_version": "v1",
        "kind": "config_resolved",
        "run_id": "run123",
        "enabled_stages": ["risk_heatmap"],
    }
    (artifacts / "config.resolved.json").write_text(
        json.dumps(resolved), encoding="utf-8"
    )

    broken = _valid_risk_heatmap_artifact()
    broken.pop("targets")
    (artifacts / "risk_heatmap.json").write_text(json.dumps(broken), encoding="utf-8")

    rc = cli.main(["validate", "--artifacts", str(artifacts)])
    assert rc == 1
