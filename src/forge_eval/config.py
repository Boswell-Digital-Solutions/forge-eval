from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

import yaml

from forge_eval.errors import ConfigError

KNOWN_STAGES = (
    "risk_heatmap",
    "context_slices",
    "review_findings",
    "telemetry_matrix",
    "occupancy_snapshot",
    "capture_estimate",
    "hazard_map",
    "merge_decision",
    "evidence_bundle",
    "localization_pack",
)
KNOWN_REVIEWER_KINDS = (
    "changed_lines",
    "documentation_consistency",
    "structural_risk",
)
KNOWN_REVIEWER_FAILURE_MODES = ("fail_stage", "record_failed")
KNOWN_REVIEWER_FAILURE_POLICIES = ("fail_stage", "record_and_continue")
KNOWN_TELEMETRY_APPLICABILITY_MODES = ("reviewer_kind_scope_v1",)
KNOWN_TELEMETRY_KEFF_MODES = ("global_min_per_defect",)
KNOWN_OCCUPANCY_MODEL_VERSIONS = ("occupancy_rev1",)
KNOWN_CAPTURE_INCLUSION_POLICIES = ("include_all",)
KNOWN_CAPTURE_SELECTION_POLICIES = ("max_hidden",)
KNOWN_HAZARD_MODEL_VERSIONS = ("hazard_rev1",)
KNOWN_MERGE_DECISION_MODEL_VERSIONS = ("merge_rev1",)
KNOWN_EVIDENCE_BUNDLE_MODEL_VERSIONS = ("evidence_bundle_rev1",)
KNOWN_LOCALIZATION_MODEL_VERSIONS = ("localization_pack_rev1",)
KNOWN_SEVERITIES = ("low", "medium", "high", "critical")
KNOWN_CATEGORIES = (
    "correctness",
    "consistency",
    "docs",
    "policy",
    "risk",
    "schema",
    "unknown",
)

DEFAULT_CONFIG: dict[str, Any] = {
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
    "risk_weights": {
        "w_churn": 0.45,
        "w_centrality": 0.35,
        "w_change_magnitude": 0.20,
    },
    "path_weights": {},
    "context_radius_lines": 12,
    "merge_gap_lines": 2,
    "max_slices_per_target": 8,
    "max_lines_per_slice": 120,
    "max_total_lines": 1200,
    "fail_on_slice_truncation": True,
    "include_file_extensions": [
        ".py",
        ".rs",
        ".ts",
        ".tsx",
        ".js",
        ".jsx",
        ".json",
        ".md",
    ],
    "exclude_paths": ["dist/", "build/", ".venv/", "node_modules/"],
    "binary_file_policy": "fail",
    "reviewer_failure_policy": "fail_stage",
    "telemetry_applicability_mode": "reviewer_kind_scope_v1",
    "telemetry_k_eff_mode": "global_min_per_defect",
    "occupancy_model_version": "occupancy_rev1",
    "occupancy_prior_base": 0.45,
    "occupancy_support_uplift": 0.20,
    "occupancy_detection_assumption": 0.70,
    "occupancy_miss_penalty_strength": 0.35,
    "occupancy_null_uncertainty_boost": 0.30,
    "occupancy_round_digits": 6,
    "capture_inclusion_policy": "include_all",
    "capture_selection_policy": "max_hidden",
    "ice_rare_threshold": 10,
    "capture_round_digits": 6,
    "hazard_model_version": "hazard_rev1",
    "hazard_round_digits": 6,
    "hazard_hidden_uplift_strength": 0.20,
    "hazard_structural_risk_strength": 0.30,
    "hazard_occupancy_strength": 0.35,
    "hazard_support_uplift_strength": 0.15,
    "hazard_uncertainty_boost": 0.12,
    "hazard_blocking_threshold": 0.80,
    "merge_decision_model_version": "merge_rev1",
    "merge_decision_caution_threshold": 0.20,
    "merge_decision_block_threshold": 0.60,
    "merge_decision_block_on_hazard_blocking_signals": True,
    "evidence_bundle_model_version": "evidence_bundle_rev1",
    "localization_model_version": "localization_pack_rev1",
    "localization_max_file_candidates": 10,
    "localization_max_block_candidates": 20,
    "localization_max_review_scope_lines": 500,
    "localization_max_scope_lines_per_file": 150,
    "localization_round_digits": 6,
    "localization_ranking_weights": {
        "support_count": 0.35,
        "defect_density": 0.25,
        "hazard_contribution": 0.25,
        "churn": 0.15,
    },
    "reviewers": [
        {
            "reviewer_id": "changed_lines.rule.v1",
            "kind": "changed_lines",
            "enabled": True,
            "failure_mode": "fail_stage",
            "scope_rules": {
                "include_extensions": [
                    ".md",
                    ".py",
                    ".json",
                    ".rs",
                    ".js",
                    ".ts",
                    ".tsx",
                    ".jsx",
                ]
            },
            "finding_rules": {
                "default_severity": "medium",
                "default_category": "consistency",
                "confidence": 0.7,
            },
        },
        {
            "reviewer_id": "documentation_consistency.v1",
            "kind": "documentation_consistency",
            "enabled": True,
            "failure_mode": "fail_stage",
            "scope_rules": {"include_extensions": [".md"]},
            "finding_rules": {
                "default_severity": "low",
                "default_category": "docs",
                "confidence": 0.65,
                "require_code_and_docs": True,
            },
        },
        {
            "reviewer_id": "structural_risk.v1",
            "kind": "structural_risk",
            "enabled": True,
            "failure_mode": "fail_stage",
            "scope_rules": {"min_risk_score": 0.8},
            "finding_rules": {
                "default_severity": "medium",
                "default_category": "risk",
                "confidence": 0.75,
                "risk_threshold": 0.8,
            },
        },
    ],
}


def _parse_config_file(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise ConfigError("config file does not exist", details={"path": str(path)})
    raw = path.read_text(encoding="utf-8")

    suffix = path.suffix.lower()
    if suffix == ".json":
        try:
            obj = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ConfigError(
                "invalid JSON config", details={"path": str(path), "error": str(exc)}
            ) from exc
    elif suffix in {".yaml", ".yml"}:
        try:
            obj = yaml.safe_load(raw)
        except yaml.YAMLError as exc:
            raise ConfigError(
                "invalid YAML config", details={"path": str(path), "error": str(exc)}
            ) from exc
    else:
        raise ConfigError(
            "unsupported config format; expected .json/.yaml/.yml",
            details={"path": str(path), "suffix": suffix},
        )

    if obj is None:
        return {}
    if not isinstance(obj, dict):
        raise ConfigError("config root must be an object", details={"path": str(path)})
    return obj


def _ensure_number(name: str, value: Any, *, min_value: float | None = None) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ConfigError(
            "config value must be numeric", details={"key": name, "value": value}
        )
    out = float(value)
    if min_value is not None and out < min_value:
        raise ConfigError(
            "config value below allowed minimum",
            details={"key": name, "value": out, "min": min_value},
        )
    return out


def _normalize_extensions(values: Any) -> list[str]:
    if not isinstance(values, list) or not all(isinstance(v, str) for v in values):
        raise ConfigError("include_file_extensions must be a list of strings")
    normalized = []
    for ext in values:
        ext = ext.strip()
        if not ext:
            raise ConfigError("empty extension entry is not allowed")
        if not ext.startswith("."):
            ext = f".{ext}"
        normalized.append(ext.lower())
    return sorted(set(normalized))


def _normalize_exclude_paths(values: Any) -> list[str]:
    if not isinstance(values, list) or not all(isinstance(v, str) for v in values):
        raise ConfigError("exclude_paths must be a list of strings")
    normalized = []
    for path in values:
        p = path.replace("\\", "/").strip()
        if not p:
            raise ConfigError("exclude_paths entries cannot be empty")
        if not p.endswith("/"):
            p = f"{p}/"
        normalized.append(p)
    return sorted(set(normalized))


def _normalize_path_weights(values: Any) -> dict[str, float]:
    if not isinstance(values, dict):
        raise ConfigError("path_weights must be an object")
    out: dict[str, float] = {}
    for key in sorted(values.keys()):
        val = values[key]
        if not isinstance(key, str) or not key:
            raise ConfigError("path_weights keys must be non-empty strings")
        weight = _ensure_number(f"path_weights.{key}", val, min_value=0.0)
        out[key.replace("\\", "/")] = weight
    return out


def _normalize_risk_weights(values: Any) -> dict[str, float]:
    if not isinstance(values, dict):
        raise ConfigError("risk_weights must be an object")

    expected = {"w_churn", "w_centrality", "w_change_magnitude"}
    unknown = set(values.keys()) - expected
    if unknown:
        raise ConfigError(
            "unknown risk_weights keys", details={"keys": sorted(unknown)}
        )

    merged = copy.deepcopy(DEFAULT_CONFIG["risk_weights"])
    for key, value in values.items():
        merged[key] = _ensure_number(f"risk_weights.{key}", value, min_value=0.0)

    total = merged["w_churn"] + merged["w_centrality"] + merged["w_change_magnitude"]
    if total <= 0.0:
        raise ConfigError(
            "risk weight sum must be > 0", details={"risk_weights": merged}
        )

    # Normalize to deterministic unit sum for stable scoring.
    return {k: merged[k] / total for k in sorted(merged.keys())}


def _normalize_scope_rules(values: Any) -> dict[str, Any]:
    if not isinstance(values, dict):
        raise ConfigError("reviewer scope_rules must be an object")
    out: dict[str, Any] = {}

    allowed = {"exclude_paths", "include_extensions", "min_risk_score"}
    unknown = set(values.keys()) - allowed
    if unknown:
        raise ConfigError(
            "unknown reviewer scope_rules keys", details={"keys": sorted(unknown)}
        )

    if "include_extensions" in values:
        out["include_extensions"] = _normalize_extensions(values["include_extensions"])
    else:
        out["include_extensions"] = []

    if "exclude_paths" in values:
        out["exclude_paths"] = _normalize_exclude_paths(values["exclude_paths"])
    else:
        out["exclude_paths"] = []

    if "min_risk_score" in values:
        score = _ensure_number(
            "scope_rules.min_risk_score", values["min_risk_score"], min_value=0.0
        )
        if score > 1.0:
            raise ConfigError(
                "scope_rules.min_risk_score must be <= 1.0",
                details={"value": score},
            )
        out["min_risk_score"] = score
    else:
        out["min_risk_score"] = 0.0

    return out


def _normalize_finding_rules(values: Any) -> dict[str, Any]:
    if not isinstance(values, dict):
        raise ConfigError("reviewer finding_rules must be an object")
    out: dict[str, Any] = {}

    allowed = {
        "confidence",
        "default_category",
        "default_severity",
        "require_code_and_docs",
        "risk_threshold",
    }
    unknown = set(values.keys()) - allowed
    if unknown:
        raise ConfigError(
            "unknown reviewer finding_rules keys", details={"keys": sorted(unknown)}
        )

    severity = values.get("default_severity", "medium")
    if severity not in KNOWN_SEVERITIES:
        raise ConfigError(
            "invalid reviewer default severity", details={"severity": severity}
        )
    out["default_severity"] = severity

    category = values.get("default_category", "unknown")
    if category not in KNOWN_CATEGORIES:
        raise ConfigError(
            "invalid reviewer default category", details={"category": category}
        )
    out["default_category"] = category

    confidence = values.get("confidence", 0.7)
    out["confidence"] = _ensure_number(
        "finding_rules.confidence", confidence, min_value=0.0
    )
    if out["confidence"] > 1.0:
        raise ConfigError(
            "finding_rules.confidence must be <= 1.0",
            details={"confidence": out["confidence"]},
        )

    risk_threshold = values.get("risk_threshold", 0.8)
    out["risk_threshold"] = _ensure_number(
        "finding_rules.risk_threshold", risk_threshold, min_value=0.0
    )
    if out["risk_threshold"] > 1.0:
        raise ConfigError(
            "finding_rules.risk_threshold must be <= 1.0",
            details={"risk_threshold": out["risk_threshold"]},
        )

    require_code_and_docs = values.get("require_code_and_docs", False)
    if not isinstance(require_code_and_docs, bool):
        raise ConfigError("finding_rules.require_code_and_docs must be boolean")
    out["require_code_and_docs"] = require_code_and_docs

    return out


def _normalize_reviewers(values: Any) -> list[dict[str, Any]]:
    if not isinstance(values, list):
        raise ConfigError("reviewers must be a list")

    normalized: list[dict[str, Any]] = []
    seen_ids: set[str] = set()

    for reviewer in values:
        if not isinstance(reviewer, dict):
            raise ConfigError("each reviewer must be an object")

        allowed_keys = {
            "reviewer_id",
            "kind",
            "enabled",
            "failure_mode",
            "scope_rules",
            "finding_rules",
        }
        unknown = set(reviewer.keys()) - allowed_keys
        if unknown:
            raise ConfigError(
                "unknown reviewer keys", details={"keys": sorted(unknown)}
            )

        reviewer_id = reviewer.get("reviewer_id")
        if not isinstance(reviewer_id, str) or not reviewer_id.strip():
            raise ConfigError("reviewer_id must be a non-empty string")
        reviewer_id = reviewer_id.strip()
        if reviewer_id in seen_ids:
            raise ConfigError(
                "duplicate reviewer_id in config", details={"reviewer_id": reviewer_id}
            )
        seen_ids.add(reviewer_id)

        kind = reviewer.get("kind")
        if kind not in KNOWN_REVIEWER_KINDS:
            raise ConfigError(
                "unsupported reviewer kind",
                details={"reviewer_id": reviewer_id, "kind": kind},
            )

        enabled = reviewer.get("enabled")
        if not isinstance(enabled, bool):
            raise ConfigError(
                "reviewer enabled must be boolean", details={"reviewer_id": reviewer_id}
            )

        failure_mode = reviewer.get("failure_mode")
        if failure_mode not in KNOWN_REVIEWER_FAILURE_MODES:
            raise ConfigError(
                "invalid reviewer failure_mode",
                details={"reviewer_id": reviewer_id, "failure_mode": failure_mode},
            )

        scope_rules = _normalize_scope_rules(reviewer.get("scope_rules", {}))
        finding_rules = _normalize_finding_rules(reviewer.get("finding_rules", {}))

        normalized.append(
            {
                "reviewer_id": reviewer_id,
                "kind": kind,
                "enabled": enabled,
                "failure_mode": failure_mode,
                "scope_rules": scope_rules,
                "finding_rules": finding_rules,
            }
        )

    if not normalized:
        raise ConfigError("at least one reviewer must be configured")

    normalized.sort(key=lambda item: str(item["reviewer_id"]))
    return normalized


def _normalize_localization_ranking_weights(values: Any) -> dict[str, float]:
    if not isinstance(values, dict):
        raise ConfigError("localization_ranking_weights must be an object")

    expected = {"support_count", "defect_density", "hazard_contribution", "churn"}
    unknown = set(values.keys()) - expected
    if unknown:
        raise ConfigError(
            "unknown localization_ranking_weights keys",
            details={"keys": sorted(unknown)},
        )

    merged = copy.deepcopy(DEFAULT_CONFIG["localization_ranking_weights"])
    for key, value in values.items():
        merged[key] = _ensure_number(
            f"localization_ranking_weights.{key}", value, min_value=0.0
        )

    total = sum(merged.values())
    if total <= 0.0:
        raise ConfigError(
            "localization ranking weight sum must be > 0", details={"weights": merged}
        )

    return {k: merged[k] / total for k in sorted(merged.keys())}


def normalize_config(raw: dict[str, Any] | None) -> dict[str, Any]:
    cfg: dict[str, Any] = copy.deepcopy(DEFAULT_CONFIG)
    raw = raw or {}

    unknown = set(raw.keys()) - set(DEFAULT_CONFIG.keys())
    if unknown:
        raise ConfigError("unknown config keys", details={"keys": sorted(unknown)})

    if "enabled_stages" in raw:
        value = raw["enabled_stages"]
        if not isinstance(value, list) or not all(isinstance(v, str) for v in value):
            raise ConfigError("enabled_stages must be a list of strings")
        requested = set(value)
        invalid = requested - set(KNOWN_STAGES)
        if invalid:
            raise ConfigError(
                "enabled_stages contains unknown stage",
                details={"stages": sorted(invalid)},
            )
        cfg["enabled_stages"] = [stage for stage in KNOWN_STAGES if stage in requested]
        if not cfg["enabled_stages"]:
            raise ConfigError("at least one stage must be enabled")

    if "risk_weights" in raw:
        cfg["risk_weights"] = _normalize_risk_weights(raw["risk_weights"])

    if "path_weights" in raw:
        cfg["path_weights"] = _normalize_path_weights(raw["path_weights"])

    int_constraints = {
        "context_radius_lines": 0,
        "merge_gap_lines": 0,
        "max_slices_per_target": 1,
        "max_lines_per_slice": 1,
        "max_total_lines": 1,
    }
    for key, min_value in int_constraints.items():
        if key not in raw:
            continue
        value = raw[key]
        if isinstance(value, bool) or not isinstance(value, int):
            raise ConfigError(
                "config value must be integer", details={"key": key, "value": value}
            )
        if value < min_value:
            raise ConfigError(
                "config value below minimum",
                details={"key": key, "value": value, "min": min_value},
            )
        cfg[key] = value

    if "fail_on_slice_truncation" in raw:
        value = raw["fail_on_slice_truncation"]
        if not isinstance(value, bool):
            raise ConfigError("fail_on_slice_truncation must be boolean")
        cfg["fail_on_slice_truncation"] = value

    if "include_file_extensions" in raw:
        cfg["include_file_extensions"] = _normalize_extensions(
            raw["include_file_extensions"]
        )

    if "exclude_paths" in raw:
        cfg["exclude_paths"] = _normalize_exclude_paths(raw["exclude_paths"])

    if "binary_file_policy" in raw:
        value = raw["binary_file_policy"]
        if value not in {"fail", "ignore"}:
            raise ConfigError("binary_file_policy must be 'fail' or 'ignore'")
        cfg["binary_file_policy"] = value

    if "reviewer_failure_policy" in raw:
        value = raw["reviewer_failure_policy"]
        if value not in KNOWN_REVIEWER_FAILURE_POLICIES:
            raise ConfigError(
                "reviewer_failure_policy must be 'fail_stage' or 'record_and_continue'"
            )
        cfg["reviewer_failure_policy"] = value

    if "telemetry_applicability_mode" in raw:
        value = raw["telemetry_applicability_mode"]
        if value not in KNOWN_TELEMETRY_APPLICABILITY_MODES:
            raise ConfigError(
                "telemetry_applicability_mode must be 'reviewer_kind_scope_v1'"
            )
        cfg["telemetry_applicability_mode"] = value

    if "telemetry_k_eff_mode" in raw:
        value = raw["telemetry_k_eff_mode"]
        if value not in KNOWN_TELEMETRY_KEFF_MODES:
            raise ConfigError("telemetry_k_eff_mode must be 'global_min_per_defect'")
        cfg["telemetry_k_eff_mode"] = value

    if "occupancy_model_version" in raw:
        value = raw["occupancy_model_version"]
        if value not in KNOWN_OCCUPANCY_MODEL_VERSIONS:
            raise ConfigError("occupancy_model_version must be 'occupancy_rev1'")
        cfg["occupancy_model_version"] = value

    occupancy_float_keys = (
        "occupancy_prior_base",
        "occupancy_support_uplift",
        "occupancy_detection_assumption",
        "occupancy_miss_penalty_strength",
        "occupancy_null_uncertainty_boost",
    )
    for key in occupancy_float_keys:
        if key not in raw:
            continue
        value = _ensure_number(key, raw[key], min_value=0.0)
        if value > 1.0:
            raise ConfigError(
                "occupancy config value must be <= 1.0",
                details={"key": key, "value": value},
            )
        cfg[key] = value

    if "occupancy_round_digits" in raw:
        value = raw["occupancy_round_digits"]
        if isinstance(value, bool) or not isinstance(value, int):
            raise ConfigError("occupancy_round_digits must be an integer")
        if value < 0 or value > 12:
            raise ConfigError(
                "occupancy_round_digits must be in [0, 12]", details={"value": value}
            )
        cfg["occupancy_round_digits"] = value

    if "capture_inclusion_policy" in raw:
        value = raw["capture_inclusion_policy"]
        if value not in KNOWN_CAPTURE_INCLUSION_POLICIES:
            raise ConfigError("capture_inclusion_policy must be 'include_all'")
        cfg["capture_inclusion_policy"] = value

    if "capture_selection_policy" in raw:
        value = raw["capture_selection_policy"]
        if value not in KNOWN_CAPTURE_SELECTION_POLICIES:
            raise ConfigError("capture_selection_policy must be 'max_hidden'")
        cfg["capture_selection_policy"] = value

    if "ice_rare_threshold" in raw:
        value = raw["ice_rare_threshold"]
        if isinstance(value, bool) or not isinstance(value, int):
            raise ConfigError("ice_rare_threshold must be an integer")
        if value < 1:
            raise ConfigError(
                "ice_rare_threshold must be >= 1", details={"value": value}
            )
        cfg["ice_rare_threshold"] = value

    if "capture_round_digits" in raw:
        value = raw["capture_round_digits"]
        if isinstance(value, bool) or not isinstance(value, int):
            raise ConfigError("capture_round_digits must be an integer")
        if value < 0 or value > 12:
            raise ConfigError(
                "capture_round_digits must be in [0, 12]", details={"value": value}
            )
        cfg["capture_round_digits"] = value

    if "hazard_model_version" in raw:
        value = raw["hazard_model_version"]
        if value not in KNOWN_HAZARD_MODEL_VERSIONS:
            raise ConfigError("hazard_model_version must be 'hazard_rev1'")
        cfg["hazard_model_version"] = value

    hazard_float_keys = (
        "hazard_hidden_uplift_strength",
        "hazard_structural_risk_strength",
        "hazard_occupancy_strength",
        "hazard_support_uplift_strength",
        "hazard_uncertainty_boost",
        "hazard_blocking_threshold",
    )
    for key in hazard_float_keys:
        if key not in raw:
            continue
        value = _ensure_number(key, raw[key], min_value=0.0)
        if value > 1.0:
            raise ConfigError(
                "hazard config value must be <= 1.0",
                details={"key": key, "value": value},
            )
        cfg[key] = value

    if "hazard_round_digits" in raw:
        value = raw["hazard_round_digits"]
        if isinstance(value, bool) or not isinstance(value, int):
            raise ConfigError("hazard_round_digits must be an integer")
        if value < 0 or value > 12:
            raise ConfigError(
                "hazard_round_digits must be in [0, 12]", details={"value": value}
            )
        cfg["hazard_round_digits"] = value

    if "merge_decision_model_version" in raw:
        value = raw["merge_decision_model_version"]
        if value not in KNOWN_MERGE_DECISION_MODEL_VERSIONS:
            raise ConfigError("merge_decision_model_version must be 'merge_rev1'")
        cfg["merge_decision_model_version"] = value

    merge_decision_float_keys = (
        "merge_decision_caution_threshold",
        "merge_decision_block_threshold",
    )
    for key in merge_decision_float_keys:
        if key not in raw:
            continue
        value = _ensure_number(key, raw[key], min_value=0.0)
        if value > 1.0:
            raise ConfigError(
                "merge decision config value must be <= 1.0",
                details={"key": key, "value": value},
            )
        cfg[key] = value

    if cfg["merge_decision_caution_threshold"] > cfg["merge_decision_block_threshold"]:
        raise ConfigError(
            "merge_decision_caution_threshold must be <= merge_decision_block_threshold",
            details={
                "merge_decision_caution_threshold": cfg[
                    "merge_decision_caution_threshold"
                ],
                "merge_decision_block_threshold": cfg["merge_decision_block_threshold"],
            },
        )

    if "merge_decision_block_on_hazard_blocking_signals" in raw:
        value = raw["merge_decision_block_on_hazard_blocking_signals"]
        if not isinstance(value, bool):
            raise ConfigError(
                "merge_decision_block_on_hazard_blocking_signals must be a boolean"
            )
        cfg["merge_decision_block_on_hazard_blocking_signals"] = value

    if "evidence_bundle_model_version" in raw:
        value = raw["evidence_bundle_model_version"]
        if value not in KNOWN_EVIDENCE_BUNDLE_MODEL_VERSIONS:
            raise ConfigError(
                "evidence_bundle_model_version must be 'evidence_bundle_rev1'"
            )
        cfg["evidence_bundle_model_version"] = value

    if "localization_model_version" in raw:
        value = raw["localization_model_version"]
        if value not in KNOWN_LOCALIZATION_MODEL_VERSIONS:
            raise ConfigError(
                "localization_model_version must be 'localization_pack_rev1'"
            )
        cfg["localization_model_version"] = value

    localization_int_keys = {
        "localization_max_file_candidates": 1,
        "localization_max_block_candidates": 1,
        "localization_max_review_scope_lines": 1,
        "localization_max_scope_lines_per_file": 1,
    }
    for key, min_val in localization_int_keys.items():
        if key not in raw:
            continue
        value = raw[key]
        if isinstance(value, bool) or not isinstance(value, int):
            raise ConfigError(
                "config value must be integer", details={"key": key, "value": value}
            )
        if value < min_val:
            raise ConfigError(
                "config value below minimum",
                details={"key": key, "value": value, "min": min_val},
            )
        cfg[key] = value

    if "localization_round_digits" in raw:
        value = raw["localization_round_digits"]
        if isinstance(value, bool) or not isinstance(value, int):
            raise ConfigError("localization_round_digits must be an integer")
        if value < 0 or value > 12:
            raise ConfigError(
                "localization_round_digits must be in [0, 12]", details={"value": value}
            )
        cfg["localization_round_digits"] = value

    if "localization_ranking_weights" in raw:
        cfg["localization_ranking_weights"] = _normalize_localization_ranking_weights(
            raw["localization_ranking_weights"]
        )

    if "reviewers" in raw:
        cfg["reviewers"] = _normalize_reviewers(raw["reviewers"])

    cfg["include_file_extensions"] = _normalize_extensions(
        cfg["include_file_extensions"]
    )
    cfg["exclude_paths"] = _normalize_exclude_paths(cfg["exclude_paths"])
    cfg["reviewers"] = _normalize_reviewers(cfg["reviewers"])

    enabled_stage_set = set(cfg["enabled_stages"])
    if (
        "review_findings" in enabled_stage_set
        and "context_slices" not in enabled_stage_set
    ):
        raise ConfigError(
            "review_findings stage requires context_slices stage to be enabled"
        )
    if (
        "telemetry_matrix" in enabled_stage_set
        and "review_findings" not in enabled_stage_set
    ):
        raise ConfigError(
            "telemetry_matrix stage requires review_findings stage to be enabled"
        )
    if (
        "occupancy_snapshot" in enabled_stage_set
        and "telemetry_matrix" not in enabled_stage_set
    ):
        raise ConfigError(
            "occupancy_snapshot stage requires telemetry_matrix stage to be enabled"
        )
    if (
        "capture_estimate" in enabled_stage_set
        and "occupancy_snapshot" not in enabled_stage_set
    ):
        raise ConfigError(
            "capture_estimate stage requires occupancy_snapshot stage to be enabled"
        )
    if (
        "hazard_map" in enabled_stage_set
        and "capture_estimate" not in enabled_stage_set
    ):
        raise ConfigError(
            "hazard_map stage requires capture_estimate stage to be enabled"
        )
    if "merge_decision" in enabled_stage_set and "hazard_map" not in enabled_stage_set:
        raise ConfigError(
            "merge_decision stage requires hazard_map stage to be enabled"
        )
    if (
        "evidence_bundle" in enabled_stage_set
        and "merge_decision" not in enabled_stage_set
    ):
        raise ConfigError(
            "evidence_bundle stage requires merge_decision stage to be enabled"
        )
    if (
        "localization_pack" in enabled_stage_set
        and "evidence_bundle" not in enabled_stage_set
    ):
        raise ConfigError(
            "localization_pack stage requires evidence_bundle stage to be enabled"
        )

    return cfg


def load_config(config_path: str | Path | None) -> dict[str, Any]:
    if config_path is None:
        return normalize_config({})
    path = Path(config_path)
    parsed = _parse_config_file(path)
    return normalize_config(parsed)
