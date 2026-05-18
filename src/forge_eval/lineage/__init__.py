"""ForgeLineage emission for Forge-Eval (Phase 06).

This module is intentionally non-blocking: every helper catches exceptions
from the lineage SDK / network and returns a stable status. Raw forge-eval
pipeline execution must continue even if lineage emission fails.

Governed downstream consequences (eval-cal-node Gate 3 promotion) call into
``forge_lineage_sdk.enforcement.enforce_edge_for_promotion`` and fail closed.
That enforcement is performed by the consumer (eval-cal-node), not here.
"""

from forge_eval.lineage.emitter import (
    ForgeEvalLineageEmitter,
    LineageEmissionStatus,
    NullLineageEmitter,
)

__all__ = [
    "ForgeEvalLineageEmitter",
    "LineageEmissionStatus",
    "NullLineageEmitter",
]
