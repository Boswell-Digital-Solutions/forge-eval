"""The run-path lineage emit is opt-in (default off) and non-blocking.

These assert the posture, not the wire: emission stays a no-op until the operator sets
FORGE_EVAL_LINEAGE_URL, and any emitter failure is swallowed so a raw run still completes.
Self-contained — no DataForge-Local, no git repo, no full pipeline.
"""
from __future__ import annotations

from forge_eval import centipede_runner
from forge_eval.centipede_runner import (
    FORGE_EVAL_LINEAGE_URL_ENV,
    _build_lineage_emitter,
    _emit_centipede_lineage,
)
from forge_eval.lineage import NullLineageEmitter


def test_emitter_defaults_to_noop_when_url_unset(monkeypatch):
    monkeypatch.delenv(FORGE_EVAL_LINEAGE_URL_ENV, raising=False)
    assert isinstance(_build_lineage_emitter(), NullLineageEmitter)


def test_emit_is_noop_and_returns_missing_when_off(monkeypatch, tmp_path):
    monkeypatch.delenv(FORGE_EVAL_LINEAGE_URL_ENV, raising=False)
    local_bundle = tmp_path / "forge_eval_evidence_bundle.json"
    local_bundle.write_text('{"kind":"forge_eval_evidence_bundle"}\n', encoding="utf-8")
    outcome = _emit_centipede_lineage(
        bundle_artifact={"run_id": "r"},
        contract_payload={"repository_id": "repo:demo"},
        local_bundle_path=local_bundle,
        run_id="r",
        base_commit="b",
        head_commit="h",
    )
    assert outcome == "lineage_missing"


def test_emit_is_non_blocking_on_emitter_failure(monkeypatch, tmp_path):
    """URL set but the emitter cannot be built (e.g. SDK absent) → swallowed, run continues."""
    monkeypatch.setenv(FORGE_EVAL_LINEAGE_URL_ENV, "http://127.0.0.1:9")

    def _boom(**_kwargs):
        raise RuntimeError("lineage SDK absent")

    monkeypatch.setattr(
        centipede_runner.ForgeEvalLineageEmitter, "from_env", staticmethod(_boom)
    )
    local_bundle = tmp_path / "forge_eval_evidence_bundle.json"
    local_bundle.write_text("{}\n", encoding="utf-8")
    outcome = _emit_centipede_lineage(
        bundle_artifact={},
        contract_payload={},
        local_bundle_path=local_bundle,
        run_id="r",
        base_commit="b",
        head_commit="h",
    )
    assert outcome == "lineage_missing"  # caught; no exception escaped
