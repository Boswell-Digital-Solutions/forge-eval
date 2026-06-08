"""Forge-Eval producer side of ForgeLineage Phase 06.

Emits a `forge_eval_run` node, a `forge_eval_evidence_bundle` node, and a
`produced` ImpactEdge between them. Emission failure is recorded but does
not raise: per the doctrine, lineage emission must be non-blocking for raw
execution.
"""

from __future__ import annotations

import hashlib
import json
import logging
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


# Resolve the SDK at import time. Tests inject the SDK path; production usage
# can rely on ``pip install -e contracts/forge_lineage/sdk`` later.
def _ensure_sdk_on_path() -> None:
    here = Path(__file__).resolve()
    candidates = [
        here.parents[6] / "contracts" / "forge_lineage" / "sdk",
        Path.home() / "Forge" / "ecosystem" / "contracts" / "forge_lineage" / "sdk",
    ]
    for c in candidates:
        if c.exists() and str(c) not in sys.path:
            sys.path.insert(0, str(c))
            return


_ensure_sdk_on_path()

# ``forge_lineage_sdk`` is an optional ecosystem dependency (installed via the
# ``lineage`` extra / a local editable checkout, not PyPI). Guard the import so
# this module — and the wider package — remains importable without it; emission
# fails closed with a clear error only when the SDK is actually exercised.
try:
    from forge_lineage_sdk import LineageClient, LocalOutcome  # noqa: E402
    from forge_lineage_sdk.builders import (  # noqa: E402
        build_edge,
        build_envelope,
        build_node,
    )

    _LINEAGE_SDK_IMPORT_ERROR: ImportError | None = None
except ImportError as exc:  # pragma: no cover - exercised only without the SDK
    LineageClient = LocalOutcome = None  # type: ignore[assignment,misc]
    build_edge = build_envelope = build_node = None  # type: ignore[assignment]
    _LINEAGE_SDK_IMPORT_ERROR = exc


def _require_sdk() -> None:
    """Fail closed with actionable guidance when the lineage SDK is absent."""
    if _LINEAGE_SDK_IMPORT_ERROR is not None:
        raise RuntimeError(
            "forge_lineage_sdk is not installed; install the 'lineage' extra "
            "(pip install -e '.[lineage]') or provide the ecosystem SDK checkout"
        ) from _LINEAGE_SDK_IMPORT_ERROR


@dataclass
class LineageEmissionStatus:
    """Stable record of what was emitted for a forge-eval run."""

    run_node_id: str | None = None
    bundle_node_id: str | None = None
    produced_edge_id: str | None = None
    outcome: str = "lineage_missing"  # one of the lineage_availability values
    error: str | None = None
    receipts: list[dict[str, Any]] | None = None


class ForgeEvalLineageEmitter:
    """Emits forge-eval lineage. Construct once per run; call ``emit_run_and_bundle``."""

    WRITER_IDENTITY = "forge-eval"
    SOURCE_SYSTEM = "forge-eval"
    SOURCE_COMPONENT = "forge-eval/stage_runner"

    def __init__(self, client: LineageClient) -> None:
        self._client = client

    @classmethod
    def from_env(
        cls,
        *,
        base_url: str = "http://127.0.0.1:8005",
        writer_token: str = "local-forge-eval",
    ) -> "ForgeEvalLineageEmitter":
        _require_sdk()
        client = LineageClient(
            base_url=base_url,
            writer_identity=cls.WRITER_IDENTITY,
            writer_token=writer_token,
        )
        return cls(client)

    def emit_run_and_bundle(
        self,
        *,
        forge_eval_run_id: str,
        repository_id: str,
        head_ref: str,
        base_ref: str | None,
        evidence_bundle: dict[str, Any],
        deterministic: bool = True,
        trace_id: str | None = None,
    ) -> LineageEmissionStatus:
        """Emit run + bundle nodes and the produced edge as a single envelope.

        Never raises: any error is captured in ``LineageEmissionStatus.error``
        and the returned ``outcome`` is ``lineage_missing`` or
        ``lineage_degraded``.
        """
        try:
            return self._emit(
                forge_eval_run_id=forge_eval_run_id,
                repository_id=repository_id,
                head_ref=head_ref,
                base_ref=base_ref,
                evidence_bundle=evidence_bundle,
                deterministic=deterministic,
                trace_id=trace_id,
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "forge_eval lineage emission raised; raw execution continues",
                exc_info=exc,
            )
            return LineageEmissionStatus(
                outcome="lineage_missing", error=f"{type(exc).__name__}: {exc}"
            )

    def _emit(
        self,
        *,
        forge_eval_run_id: str,
        repository_id: str,
        head_ref: str,
        base_ref: str | None,
        evidence_bundle: dict[str, Any],
        deterministic: bool,
        trace_id: str | None,
    ) -> LineageEmissionStatus:
        trace = trace_id or f"trace:forge-eval:{forge_eval_run_id}"

        run_payload: dict[str, Any] = {
            "schema_version": "forge_eval_run.v1",
            "forge_eval_run_id": forge_eval_run_id,
            "repository_id": repository_id,
            "head_ref": head_ref,
            "deterministic": bool(deterministic),
        }
        if base_ref:
            run_payload["base_ref"] = base_ref
        run_node = build_node(
            node_type="forge_eval_run",
            payload_schema_id="forge_eval_run",
            payload_schema_version="v1",
            payload=run_payload,
            source_system=self.SOURCE_SYSTEM,
            source_component=self.SOURCE_COMPONENT,
            trace_id=trace,
            writer_identity=self.WRITER_IDENTITY,
            stable_source_id=f"forge-eval:run:{forge_eval_run_id}",
        )

        bundle_id, bundle_hash = _bundle_identity(evidence_bundle)
        bundle_payload = {
            "schema_version": "forge_eval_evidence_bundle.v1",
            "forge_eval_run_id": forge_eval_run_id,
            "evidence_bundle_id": bundle_id,
            "payload_hash": bundle_hash,
            "stage_count": _stage_count(evidence_bundle),
        }
        bundle_node = build_node(
            node_type="forge_eval_evidence_bundle",
            payload_schema_id="forge_eval_evidence_bundle",
            payload_schema_version="v1",
            payload=bundle_payload,
            source_system=self.SOURCE_SYSTEM,
            source_component=self.SOURCE_COMPONENT,
            trace_id=trace,
            writer_identity=self.WRITER_IDENTITY,
            stable_source_id=f"forge-eval:bundle:{bundle_id}",
        )

        produced_edge = build_edge(
            source_node_id=run_node["node_id"],
            target_node_id=bundle_node["node_id"],
            edge_type="produced",
            causality_class="deterministic",
            effect_class="informational",
            trace_id=trace,
            writer_identity=self.WRITER_IDENTITY,
            created_by_system=self.SOURCE_SYSTEM,
            stable_source_id=f"{run_node['node_id']}->{bundle_node['node_id']}",
        )

        envelope = build_envelope(
            writer_identity=self.WRITER_IDENTITY,
            trace_id=trace,
            nodes=[run_node, bundle_node],
            edges=[produced_edge],
        )
        result = self._client.emit_envelope(envelope)

        if result.outcome in (LocalOutcome.accepted, LocalOutcome.accepted_duplicate):
            return LineageEmissionStatus(
                run_node_id=run_node["node_id"],
                bundle_node_id=bundle_node["node_id"],
                produced_edge_id=produced_edge["edge_id"],
                outcome="lineage_available",
                receipts=[result.receipt] if result.receipt else None,
            )

        return LineageEmissionStatus(
            run_node_id=run_node["node_id"],
            bundle_node_id=bundle_node["node_id"],
            produced_edge_id=produced_edge["edge_id"],
            outcome="lineage_degraded",
            error=(
                result.error.message
                if result.error
                else f"non-accept outcome: {result.outcome}"
            ),
        )


class NullLineageEmitter:
    """No-op emitter for environments where lineage is disabled (CI without
    the DataForge service running). Returns ``lineage_missing`` deterministically.
    """

    def emit_run_and_bundle(self, **_kwargs: Any) -> LineageEmissionStatus:
        return LineageEmissionStatus(
            outcome="lineage_missing", error="emitter_disabled"
        )


def _bundle_identity(evidence_bundle: dict[str, Any]) -> tuple[str, str]:
    """Derive a stable id and content hash from the evidence-bundle artifact."""
    canonical = json.dumps(
        evidence_bundle, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    digest = hashlib.sha256(canonical).hexdigest()
    bundle_id = (
        evidence_bundle.get("bundle_id")
        or evidence_bundle.get("manifest", {}).get("bundle_id")
        or f"bundle:{digest[:16]}"
    )
    payload_hash = (
        evidence_bundle.get("payload_hash")
        or evidence_bundle.get("manifest", {}).get("bundle_hash")
        or digest
    )
    return str(bundle_id), str(payload_hash)


def _stage_count(evidence_bundle: dict[str, Any]) -> int:
    artifacts = evidence_bundle.get("artifacts")
    if isinstance(artifacts, list):
        return len(artifacts)
    manifest = evidence_bundle.get("manifest")
    if isinstance(manifest, dict):
        items = manifest.get("artifacts")
        if isinstance(items, list):
            return len(items)
    return 0
