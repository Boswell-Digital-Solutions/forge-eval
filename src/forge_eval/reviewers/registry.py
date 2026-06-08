from __future__ import annotations

from forge_eval.errors import StageError
from forge_eval.reviewers.base import Reviewer
from forge_eval.reviewers.changed_lines import ChangedLinesRuleReviewer
from forge_eval.reviewers.documentation_consistency import (
    DocumentationConsistencyReviewer,
)
from forge_eval.reviewers.structural_risk import StructuralRiskReviewer

_REVIEWER_REGISTRY: dict[str, Reviewer] = {
    "changed_lines": ChangedLinesRuleReviewer(),
    "documentation_consistency": DocumentationConsistencyReviewer(),
    "structural_risk": StructuralRiskReviewer(),
}


def get_reviewer(kind: str) -> Reviewer:
    reviewer = _REVIEWER_REGISTRY.get(kind)
    if reviewer is None:
        raise StageError(
            "unsupported reviewer kind",
            stage="review_findings",
            details={"kind": kind},
        )
    return reviewer


def supported_reviewer_kinds() -> list[str]:
    return sorted(_REVIEWER_REGISTRY.keys())
