from __future__ import annotations

import json
from pathlib import Path

import pytest

from forge_eval.config import DEFAULT_CONFIG, load_config, normalize_config
from forge_eval.errors import ConfigError


def test_config_normalization_defaults() -> None:
    cfg = normalize_config({})
    assert cfg["enabled_stages"] == [
        "risk_heatmap",
        "context_slices",
        "review_findings",
        "telemetry_matrix",
        "occupancy_snapshot",
        "capture_estimate",
        "hazard_map",
        "merge_decision",
        "evidence_bundle",
    ]
    assert cfg["include_file_extensions"] == sorted(
        DEFAULT_CONFIG["include_file_extensions"]
    )
    assert cfg["exclude_paths"] == sorted(DEFAULT_CONFIG["exclude_paths"])
    assert abs(sum(cfg["risk_weights"].values()) - 1.0) < 1e-9
    assert cfg["reviewer_failure_policy"] == "fail_stage"
    assert cfg["telemetry_applicability_mode"] == "reviewer_kind_scope_v1"
    assert cfg["telemetry_k_eff_mode"] == "global_min_per_defect"
    assert cfg["occupancy_model_version"] == "occupancy_rev1"
    assert cfg["occupancy_detection_assumption"] == 0.70
    assert cfg["capture_inclusion_policy"] == "include_all"
    assert cfg["capture_selection_policy"] == "max_hidden"
    assert cfg["hazard_model_version"] == "hazard_rev1"
    assert cfg["merge_decision_model_version"] == "merge_rev1"
    assert cfg["evidence_bundle_model_version"] == "evidence_bundle_rev1"
    assert [reviewer["reviewer_id"] for reviewer in cfg["reviewers"]] == sorted(
        reviewer["reviewer_id"] for reviewer in cfg["reviewers"]
    )


def test_config_unknown_key_fails() -> None:
    with pytest.raises(ConfigError):
        normalize_config({"unknown_key": 123})


def test_load_config_json(tmp_path: Path) -> None:
    path = tmp_path / "config.json"
    path.write_text(
        json.dumps(
            {
                "enabled_stages": ["context_slices"],
                "risk_weights": {
                    "w_churn": 3.0,
                    "w_centrality": 1.0,
                    "w_change_magnitude": 0.0,
                },
            }
        ),
        encoding="utf-8",
    )
    cfg = load_config(path)
    assert cfg["enabled_stages"] == ["context_slices"]
    assert cfg["risk_weights"]["w_churn"] == 0.75


def test_load_config_yaml(tmp_path: Path) -> None:
    path = tmp_path / "config.yaml"
    path.write_text(
        "enabled_stages:\n  - risk_heatmap\ninclude_file_extensions:\n  - py\n  - .TS\n",
        encoding="utf-8",
    )
    cfg = load_config(path)
    assert cfg["enabled_stages"] == ["risk_heatmap"]
    assert cfg["include_file_extensions"] == [".py", ".ts"]


def test_duplicate_reviewer_id_fails() -> None:
    with pytest.raises(ConfigError):
        normalize_config(
            {
                "reviewers": [
                    {
                        "reviewer_id": "dup",
                        "kind": "changed_lines",
                        "enabled": True,
                        "failure_mode": "fail_stage",
                        "scope_rules": {},
                        "finding_rules": {},
                    },
                    {
                        "reviewer_id": "dup",
                        "kind": "structural_risk",
                        "enabled": True,
                        "failure_mode": "fail_stage",
                        "scope_rules": {},
                        "finding_rules": {},
                    },
                ]
            }
        )


def test_unsupported_reviewer_kind_fails() -> None:
    with pytest.raises(ConfigError):
        normalize_config(
            {
                "reviewers": [
                    {
                        "reviewer_id": "bad.kind",
                        "kind": "llm_magic",
                        "enabled": True,
                        "failure_mode": "fail_stage",
                        "scope_rules": {},
                        "finding_rules": {},
                    }
                ]
            }
        )


def test_review_findings_requires_context_slices() -> None:
    with pytest.raises(ConfigError):
        normalize_config({"enabled_stages": ["risk_heatmap", "review_findings"]})


def test_telemetry_matrix_requires_review_findings() -> None:
    with pytest.raises(ConfigError):
        normalize_config(
            {"enabled_stages": ["risk_heatmap", "context_slices", "telemetry_matrix"]}
        )


def test_occupancy_snapshot_requires_telemetry_matrix() -> None:
    with pytest.raises(ConfigError):
        normalize_config(
            {
                "enabled_stages": [
                    "risk_heatmap",
                    "context_slices",
                    "review_findings",
                    "occupancy_snapshot",
                ]
            }
        )


def test_occupancy_model_version_must_be_supported() -> None:
    with pytest.raises(ConfigError):
        normalize_config({"occupancy_model_version": "occupancy_revX"})


def test_capture_estimate_requires_occupancy_snapshot() -> None:
    with pytest.raises(ConfigError):
        normalize_config(
            {
                "enabled_stages": [
                    "risk_heatmap",
                    "context_slices",
                    "review_findings",
                    "telemetry_matrix",
                    "capture_estimate",
                ]
            }
        )


def test_capture_selection_policy_must_be_supported() -> None:
    with pytest.raises(ConfigError):
        normalize_config({"capture_selection_policy": "smallest_hidden"})


def test_hazard_map_requires_capture_estimate() -> None:
    with pytest.raises(ConfigError):
        normalize_config(
            {
                "enabled_stages": [
                    "risk_heatmap",
                    "context_slices",
                    "review_findings",
                    "telemetry_matrix",
                    "occupancy_snapshot",
                    "hazard_map",
                ]
            }
        )


def test_hazard_model_version_must_be_supported() -> None:
    with pytest.raises(ConfigError):
        normalize_config({"hazard_model_version": "hazard_revX"})


def test_merge_decision_requires_hazard_map() -> None:
    with pytest.raises(ConfigError):
        normalize_config(
            {
                "enabled_stages": [
                    "risk_heatmap",
                    "context_slices",
                    "review_findings",
                    "telemetry_matrix",
                    "occupancy_snapshot",
                    "capture_estimate",
                    "merge_decision",
                ]
            }
        )


def test_merge_decision_model_version_must_be_supported() -> None:
    with pytest.raises(ConfigError):
        normalize_config({"merge_decision_model_version": "merge_revX"})


def test_merge_decision_thresholds_must_be_ordered() -> None:
    with pytest.raises(ConfigError):
        normalize_config(
            {
                "merge_decision_caution_threshold": 0.7,
                "merge_decision_block_threshold": 0.6,
            }
        )


def test_evidence_bundle_requires_merge_decision() -> None:
    with pytest.raises(ConfigError):
        normalize_config(
            {
                "enabled_stages": [
                    "risk_heatmap",
                    "context_slices",
                    "review_findings",
                    "telemetry_matrix",
                    "occupancy_snapshot",
                    "capture_estimate",
                    "hazard_map",
                    "evidence_bundle",
                ]
            }
        )


def test_evidence_bundle_model_version_must_be_supported() -> None:
    with pytest.raises(ConfigError):
        normalize_config({"evidence_bundle_model_version": "evidence_bundle_revX"})
