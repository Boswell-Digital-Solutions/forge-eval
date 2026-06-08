from __future__ import annotations

from typing import Any


class ForgeEvalError(Exception):
    """Structured base error for deterministic fail-closed behavior."""

    def __init__(
        self,
        *,
        code: str,
        message: str,
        stage: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.stage = stage
        self.details = details or {}

    def to_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "message": self.message,
            "stage": self.stage,
            "details": self.details,
        }


class ConfigError(ForgeEvalError):
    def __init__(self, message: str, *, details: dict[str, Any] | None = None) -> None:
        super().__init__(
            code="config_error", message=message, stage="config", details=details
        )


class ValidationError(ForgeEvalError):
    def __init__(
        self,
        message: str,
        *,
        stage: str | None = "validation",
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(
            code="validation_error", message=message, stage=stage, details=details
        )


class StageError(ForgeEvalError):
    def __init__(
        self,
        message: str,
        *,
        stage: str,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(
            code="stage_error", message=message, stage=stage, details=details
        )


class EvidenceCliError(ForgeEvalError):
    def __init__(self, message: str, *, details: dict[str, Any] | None = None) -> None:
        super().__init__(
            code="evidence_cli_error",
            message=message,
            stage="evidence_cli",
            details=details,
        )


class GitError(ForgeEvalError):
    def __init__(self, message: str, *, details: dict[str, Any] | None = None) -> None:
        super().__init__(
            code="git_error", message=message, stage="git", details=details
        )
