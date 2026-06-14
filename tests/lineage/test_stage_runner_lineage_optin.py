"""The stage_runner (``forge-eval run``) lineage emit is opt-in + non-blocking.

Like the centipede path, the DETECT-hop emission stays a no-op until the operator sets
FORGE_EVAL_LINEAGE_URL, and any emitter failure is swallowed so a raw run still completes.
Also asserts the honest artifact label: a stage_runner full-evaluation bundle is tagged
``evidence_bundle`` (not ``forge_eval_evidence_bundle``), since it carries no fix targets.
Self-contained — no DataForge-Local, no git repo, no full pipeline.
"""
from __future__ import annotations

from pathlib import Path

from forge_eval.lineage import run_emit
from forge_eval.lineage.run_emit import (
    FORGE_EVAL_LINEAGE_URL_ENV,
    build_lineage_emitter,
    emit_run_bundle_lineage,
)
from forge_eval.lineage import NullLineageEmitter


class _RecordingEmitter:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    def emit_run_and_bundle(self, **kwargs):
        self.calls.append(kwargs)
        return type("S", (), {"outcome": "lineage_available"})()


def _bundle() -> dict:
    return {"kind": "evidence_bundle", "run_id": "r", "manifest": {"artifacts": [{"kind": "risk_heatmap"}]}}


def test_emitter_defaults_to_noop_when_url_unset(monkeypatch):
    monkeypatch.delenv(FORGE_EVAL_LINEAGE_URL_ENV, raising=False)
    assert isinstance(build_lineage_emitter(), NullLineageEmitter)


def test_emit_is_noop_and_returns_missing_when_off(monkeypatch, tmp_path):
    monkeypatch.delenv(FORGE_EVAL_LINEAGE_URL_ENV, raising=False)
    local_bundle = tmp_path / "evidence_bundle.json"
    local_bundle.write_text('{"kind":"evidence_bundle"}\n', encoding="utf-8")
    outcome = emit_run_bundle_lineage(
        evidence_bundle=_bundle(),
        repository_id="ForgeHQ",
        run_id="r",
        base_commit="b",
        head_commit="h",
        local_bundle_path=local_bundle,
        bundle_artifact_kind="evidence_bundle",
    )
    assert outcome == "lineage_missing"


def test_emit_is_non_blocking_on_emitter_failure(monkeypatch, tmp_path):
    """URL set but the emitter cannot be built (e.g. SDK absent) → swallowed, run continues."""
    monkeypatch.setenv(FORGE_EVAL_LINEAGE_URL_ENV, "http://127.0.0.1:9")

    def _boom(**_kwargs):
        raise RuntimeError("lineage SDK absent")

    monkeypatch.setattr(run_emit.ForgeEvalLineageEmitter, "from_env", staticmethod(_boom))
    local_bundle = tmp_path / "evidence_bundle.json"
    local_bundle.write_text("{}\n", encoding="utf-8")
    outcome = emit_run_bundle_lineage(
        evidence_bundle={},
        repository_id="ForgeHQ",
        run_id="r",
        base_commit="b",
        head_commit="h",
        local_bundle_path=local_bundle,
    )
    assert outcome == "lineage_missing"  # caught; no exception escaped


def test_emit_labels_a_stage_runner_bundle_as_evidence_bundle(tmp_path):
    """The stage_runner bundle is honestly labelled `evidence_bundle` (not the centipede
    fix-target kind), and the run's repo + commit flow to the emitter."""
    local_bundle = tmp_path / "evidence_bundle.json"
    local_bundle.write_text('{"kind":"evidence_bundle"}\n', encoding="utf-8")
    rec = _RecordingEmitter()
    outcome = emit_run_bundle_lineage(
        evidence_bundle=_bundle(),
        repository_id="ForgeHQ",
        run_id="run-9",
        base_commit="base-sha",
        head_commit="head-sha",
        local_bundle_path=local_bundle,
        bundle_artifact_kind="evidence_bundle",
        emitter=rec,
    )
    assert outcome == "lineage_available"
    (call,) = rec.calls
    assert call["bundle_artifact_kind"] == "evidence_bundle"
    assert call["repository_id"] == "ForgeHQ"
    assert call["forge_eval_run_id"] == "run-9"
    assert call["head_ref"] == "head-sha" and call["base_ref"] == "base-sha"
    assert str(call["bundle_artifact_path"]).endswith("evidence_bundle.json")
    assert call["bundle_artifact_hash"]  # self-verifying file hash
