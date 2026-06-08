from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

from forge_eval.errors import ValidationError


def _format_error_path(path_parts: list[Any]) -> str:
    if not path_parts:
        return "$"
    rendered = "$"
    for part in path_parts:
        if isinstance(part, int):
            rendered += f"[{part}]"
        else:
            rendered += f".{part}"
    return rendered


def validate_instance(
    instance: dict[str, Any], schema: dict[str, Any], *, artifact_kind: str
) -> None:
    validator = Draft202012Validator(schema)
    errors = sorted(
        validator.iter_errors(instance), key=lambda e: (list(e.path), e.message)
    )
    if errors:
        details = [
            {
                "path": _format_error_path(list(err.path)),
                "message": err.message,
            }
            for err in errors
        ]
        raise ValidationError(
            "artifact failed schema validation",
            details={"artifact_kind": artifact_kind, "errors": details},
        )


def load_json_file(path: str | Path) -> dict[str, Any]:
    file_path = Path(path)
    if not file_path.exists():
        raise ValidationError(
            "artifact file is missing", details={"path": str(file_path)}
        )
    try:
        obj = json.loads(file_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValidationError(
            "artifact file is invalid JSON",
            details={"path": str(file_path), "error": str(exc)},
        ) from exc
    if not isinstance(obj, dict):
        raise ValidationError(
            "artifact JSON root must be object",
            details={"path": str(file_path)},
        )
    return obj


def validate_file(
    path: str | Path, schema: dict[str, Any], *, artifact_kind: str
) -> dict[str, Any]:
    obj = load_json_file(path)
    validate_instance(obj, schema, artifact_kind=artifact_kind)
    return obj
