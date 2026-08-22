"""Unit tests for `_stage_count()` — no DataForge-Local/FastAPI harness needed.

Covers the bug where every `forge-eval run-centipede` bundle (the only kind
self-healing actually consumes) reported `stage_count: 0` unconditionally,
because its artifact list lives under `artifact_refs`, not `artifacts` or
`manifest.artifacts`.
"""

from __future__ import annotations

from forge_eval.lineage.emitter import _stage_count


def test_counts_top_level_artifacts_list():
    assert _stage_count({"artifacts": [1, 2, 3]}) == 3


def test_counts_manifest_artifacts_list():
    assert _stage_count({"manifest": {"artifacts": [1, 2]}}) == 2


def test_counts_artifact_refs_for_centipede_bundles():
    assert _stage_count({"artifact_refs": [{"artifact_id": "a"}, {"artifact_id": "b"}]}) == 2


def test_real_centipede_bundle_reports_nonzero_stage_count():
    # Shape mirrors centipede_runner.py's actual bundle output: no
    # "artifacts"/"manifest" key at all, only "artifact_refs".
    bundle = {
        "schema_version": "forge_eval_evidence_bundle.v1",
        "kind": "forge_eval_evidence_bundle",
        "artifact_refs": [
            {"artifact_id": "config.resolved.json"},
            {"artifact_id": "risk_heatmap.json"},
            {"artifact_id": "context_slices.json"},
        ],
    }
    assert _stage_count(bundle) == 3


def test_empty_bundle_reports_zero():
    assert _stage_count({}) == 0


def test_non_list_artifacts_field_falls_through_to_zero():
    assert _stage_count({"artifacts": "not-a-list"}) == 0
