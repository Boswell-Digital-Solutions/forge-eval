"""The bundle lineage node records an artifact_ref to the contract JSON (open-Q1 fix).

Self-contained: a capturing fake client (no FastAPI harness), so this asserts MY change —
that `bundle_artifact_path` lands as the bundle node's `artifact_ref` — directly.
"""
from __future__ import annotations

from forge_lineage_sdk import LocalOutcome

from forge_eval.lineage.emitter import ForgeEvalLineageEmitter


class _Accepted:
    outcome = LocalOutcome.accepted
    receipt = None
    error = None


class _CapturingClient:
    def __init__(self) -> None:
        self.envelopes: list[dict] = []

    def emit_envelope(self, envelope: dict) -> _Accepted:
        self.envelopes.append(envelope)
        return _Accepted()


def _evidence_bundle(run_id: str = "fe-run") -> dict:
    return {
        "kind": "evidence_bundle",
        "bundle_id": f"bundle:{run_id}",
        "payload_hash": "a" * 64,
        "manifest": {"bundle_hash": "a" * 64, "artifacts": [{"kind": "risk_heatmap"}]},
        "summary": {"decision": "approve"},
    }


def _bundle_node(envelope: dict) -> dict:
    return next(n for n in envelope["nodes"] if n["node_type"] == "forge_eval_evidence_bundle")


def test_bundle_node_records_artifact_ref_when_path_given():
    client = _CapturingClient()
    status = ForgeEvalLineageEmitter(client).emit_run_and_bundle(
        forge_eval_run_id="fe-ar",
        repository_id="repo:demo",
        head_ref="h",
        base_ref="b",
        evidence_bundle=_evidence_bundle("fe-ar"),
        bundle_artifact_path="/runs/fe-ar/forge_eval_evidence_bundle.contract.json",
    )
    assert status.outcome == "lineage_available"
    ref = _bundle_node(client.envelopes[0])["artifact_ref"]
    assert ref["artifact_kind"] == "forge_eval_evidence_bundle"
    assert ref["artifact_path"].endswith("forge_eval_evidence_bundle.contract.json")
    assert ref["artifact_hash"]  # the bundle payload hash


def test_bundle_node_omits_artifact_ref_when_path_absent():
    client = _CapturingClient()
    ForgeEvalLineageEmitter(client).emit_run_and_bundle(
        forge_eval_run_id="fe-noar",
        repository_id="repo:demo",
        head_ref="h",
        base_ref="b",
        evidence_bundle=_evidence_bundle("fe-noar"),
    )
    assert "artifact_ref" not in _bundle_node(client.envelopes[0])


def test_explicit_artifact_hash_is_self_verifying_file_hash():
    """When the caller supplies the file's own hash, the ref records it (not the bundle
    identity hash) so a consumer can verify the file it reads at artifact_path."""
    client = _CapturingClient()
    file_hash = "f" * 64
    ForgeEvalLineageEmitter(client).emit_run_and_bundle(
        forge_eval_run_id="fe-fh",
        repository_id="repo:demo",
        head_ref="h",
        base_ref="b",
        evidence_bundle=_evidence_bundle("fe-fh"),  # bundle identity hash = "a" * 64
        bundle_artifact_path="/runs/fe-fh/forge_eval_evidence_bundle.contract.json",
        bundle_artifact_hash=file_hash,
    )
    ref = _bundle_node(client.envelopes[0])["artifact_ref"]
    assert ref["artifact_hash"] == file_hash
    assert ref["artifact_hash"] != "a" * 64  # not the bundle identity hash
