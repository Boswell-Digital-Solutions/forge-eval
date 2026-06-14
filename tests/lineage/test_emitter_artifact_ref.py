"""The bundle lineage node records an artifact_ref to the contract JSON (open-Q1 fix).

Self-contained: a capturing fake client (no FastAPI harness), so this asserts MY change —
that `bundle_artifact_path` lands as the bundle node's `artifact_ref` — directly.
"""
from __future__ import annotations

from forge_lineage_sdk import LocalOutcome
from forge_lineage_sdk.validators import validate_node

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
    # Conforms to ArtifactRef.v1: family = kind, id = the locator path, payload_hash = file hash.
    assert ref["schema_version"] == "ArtifactRef.v1"
    assert ref["artifact_family"] == "forge_eval_evidence_bundle"
    assert ref["artifact_id"].endswith("forge_eval_evidence_bundle.contract.json")
    assert ref["payload_hash"]  # the bundle payload hash


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


def test_bundle_artifact_kind_defaults_to_forge_eval_evidence_bundle_and_is_overridable():
    """The artifact_kind label defaults to the centipede fix-target bundle, but the
    stage_runner path overrides it to `evidence_bundle` (a full-evaluation bundle)."""
    client = _CapturingClient()
    ForgeEvalLineageEmitter(client).emit_run_and_bundle(
        forge_eval_run_id="fe-sr",
        repository_id="repo:demo",
        head_ref="h",
        base_ref="b",
        evidence_bundle=_evidence_bundle("fe-sr"),
        bundle_artifact_path="/runs/fe-sr/evidence_bundle.json",
        bundle_artifact_kind="evidence_bundle",
    )
    ref = _bundle_node(client.envelopes[0])["artifact_ref"]
    assert ref["artifact_family"] == "evidence_bundle"
    assert ref["artifact_id"].endswith("evidence_bundle.json")


def test_explicit_artifact_hash_is_self_verifying_file_hash():
    """When the caller supplies the file's own hash, the ref's payload_hash records it
    (not the bundle identity hash) so a consumer can verify the file it reads."""
    client = _CapturingClient()
    file_hash = "f" * 64
    ForgeEvalLineageEmitter(client).emit_run_and_bundle(
        forge_eval_run_id="fe-fh",
        repository_id="repo:demo",
        head_ref="h",
        base_ref="b",
        evidence_bundle=_evidence_bundle("fe-fh"),
        bundle_artifact_path="/runs/fe-fh/forge_eval_evidence_bundle.contract.json",
        bundle_artifact_hash=file_hash,
    )
    ref = _bundle_node(client.envelopes[0])["artifact_ref"]
    assert ref["payload_hash"] == file_hash


def test_emitted_bundle_node_passes_real_sdk_schema_validation():
    """REGRESSION GUARD: the capturing client bypasses SDK validation — which is exactly
    why the non-conformant artifact_ref shipped undetected. Validate the emitted bundle
    node against the REAL LineageNode.v1 / ArtifactRef.v1 schema so it cannot regress."""
    client = _CapturingClient()
    ForgeEvalLineageEmitter(client).emit_run_and_bundle(
        forge_eval_run_id="fe-val",
        repository_id="repo:demo",
        head_ref="h",
        base_ref="b",
        evidence_bundle=_evidence_bundle("fe-val"),
        bundle_artifact_path="/runs/fe-val/forge_eval_evidence_bundle.json",
        bundle_artifact_hash="a" * 64,
    )
    envelope = client.envelopes[0]
    # Every node the emitter builds must be schema-valid (the artifact_ref'd bundle especially).
    for node in envelope["nodes"]:
        validate_node(node)  # raises SchemaValidationError if non-conformant
