from __future__ import annotations

from typing import Any

from forge_eval.errors import StageError

MERGE_DECISION_MODEL_VERSION = "merge_rev1"


def load_merge_decision_model(config: dict[str, Any]) -> dict[str, Any]:
    model_version = str(config.get("merge_decision_model_version", ""))
    if model_version != MERGE_DECISION_MODEL_VERSION:
        raise StageError(
            "unsupported merge decision model version",
            stage="merge_decision",
            details={"merge_decision_model_version": model_version},
        )

    caution_threshold = _required_unit_float(config, "merge_decision_caution_threshold")
    block_threshold = _required_unit_float(config, "merge_decision_block_threshold")
    if caution_threshold > block_threshold:
        raise StageError(
            "merge decision caution threshold cannot exceed block threshold",
            stage="merge_decision",
            details={
                "merge_decision_caution_threshold": caution_threshold,
                "merge_decision_block_threshold": block_threshold,
            },
        )

    block_on_signals = config.get("merge_decision_block_on_hazard_blocking_signals")
    if not isinstance(block_on_signals, bool):
        raise StageError(
            "merge decision blocking-signal policy must be boolean",
            stage="merge_decision",
            details={
                "merge_decision_block_on_hazard_blocking_signals": block_on_signals
            },
        )

    return {
        "name": model_version,
        "mode": "deterministic_advisory",
        "decision_policy": "hazard_gate_v1",
        "parameters": {
            "merge_decision_caution_threshold": caution_threshold,
            "merge_decision_block_threshold": block_threshold,
            "merge_decision_block_on_hazard_blocking_signals": block_on_signals,
        },
    }


def _required_unit_float(config: dict[str, Any], key: str) -> float:
    value = config.get(key)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise StageError(
            "merge decision config value must be numeric",
            stage="merge_decision",
            details={"key": key, "value": value},
        )
    number = float(value)
    if number < 0.0 or number > 1.0:
        raise StageError(
            "merge decision config value must be in [0, 1]",
            stage="merge_decision",
            details={"key": key, "value": number},
        )
    return number
