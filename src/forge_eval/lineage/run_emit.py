"""Shared run-path lineage emission helpers (opt-in, non-blocking).

Both forge-eval run paths emit ``forge_eval_run`` + ``forge_eval_evidence_bundle``
lineage after writing their bundle, so a real run is traceable in DataForge-Local.
This module is the single home for the *posture* (env-gated, fail-soft) and the
generic emit, so the centipede and stage_runner paths don't drift.

Posture (doctrine): emission is **default-off** — a no-op emitter until the operator
sets ``FORGE_EVAL_LINEAGE_URL`` — and **non-blocking** — any failure (SDK absent,
DataForge-Local unreachable, bad response) is logged and swallowed so raw execution
always completes.

NOTE: ``centipede_runner`` currently carries its own equivalent ``_build_lineage_emitter``
/ ``_sha256_file`` (it predates this module and its tests patch those names); it is left
untouched. New callers (stage_runner) use the helpers here; centipede can be consolidated
onto them later without behaviour change.
"""
from __future__ import annotations

import hashlib
import logging
import os
from pathlib import Path
from typing import Any

from forge_eval.lineage.emitter import ForgeEvalLineageEmitter, NullLineageEmitter

# Opt-in lineage emission. Off by default: turning emission on is an explicit env
# decision, never an implicit consequence of running forge-eval.
FORGE_EVAL_LINEAGE_URL_ENV = "FORGE_EVAL_LINEAGE_URL"
FORGE_EVAL_LINEAGE_TOKEN_ENV = "FORGE_EVAL_LINEAGE_TOKEN"

logger = logging.getLogger(__name__)


def build_lineage_emitter() -> Any:
    """A live emitter when ``FORGE_EVAL_LINEAGE_URL`` is set, else a no-op emitter."""
    base_url = os.environ.get(FORGE_EVAL_LINEAGE_URL_ENV, "").strip()
    if not base_url:
        return NullLineageEmitter()
    token = os.environ.get(FORGE_EVAL_LINEAGE_TOKEN_ENV, "").strip() or "local-forge-eval"
    return ForgeEvalLineageEmitter.from_env(base_url=base_url, writer_token=token)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def emit_run_bundle_lineage(
    *,
    evidence_bundle: dict[str, Any],
    repository_id: str,
    run_id: str,
    base_commit: str | None,
    head_commit: str,
    local_bundle_path: Path,
    bundle_artifact_kind: str = "forge_eval_evidence_bundle",
    emitter: Any | None = None,
) -> str:
    """Emit run + bundle lineage; record the bundle artifact ref on the bundle node.

    ``bundle_artifact_kind`` labels the artifact flavour so a downstream consumer can
    distinguish a centipede fix-target bundle (``forge_eval_evidence_bundle``, carries
    ``input_contract.target_refs``) from a stage_runner full-evaluation bundle
    (``evidence_bundle``, no per-file fix targets). The bundle node itself is
    identity-only regardless; the artifact_ref points at the local bundle JSON.

    Non-blocking: returns the lineage outcome string and never raises.
    """
    try:
        emitter = emitter or build_lineage_emitter()
        status = emitter.emit_run_and_bundle(
            forge_eval_run_id=run_id,
            repository_id=repository_id,
            head_ref=head_commit,
            base_ref=base_commit,
            evidence_bundle=evidence_bundle,
            bundle_artifact_path=str(local_bundle_path),
            bundle_artifact_hash=sha256_file(local_bundle_path),
            bundle_artifact_kind=bundle_artifact_kind,
        )
        return status.outcome
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "forge_eval lineage emission skipped; raw execution continues", exc_info=exc
        )
        return "lineage_missing"
