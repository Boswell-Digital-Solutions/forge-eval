from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any

from forge_eval.errors import ValidationError

CENTIPEDE_INPUT_SCHEMA_VERSION = "ForgeEvalCentipedeInput.v1"


@dataclass(frozen=True)
class CentipedeTargetRef:
    target_id: str
    file_path: str
    source_kind: str


@dataclass(frozen=True)
class CentipedeInput:
    schema_version: str
    repo_path: Path
    base_ref: str
    head_ref: str
    target_refs: tuple[CentipedeTargetRef, ...]
    metadata: dict[str, Any]
    raw: dict[str, Any]

    @property
    def target_file_paths(self) -> list[str]:
        return sorted({target.file_path for target in self.target_refs})


_ALLOWED_TOP_LEVEL_KEYS = {
    "schema_version",
    "repo_path",
    "base_ref",
    "head_ref",
    "target_refs",
    "metadata",
}


def _load_json_object(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise ValidationError(
            "centipede input file does not exist", details={"path": str(path)}
        )
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValidationError(
            "centipede input file is invalid JSON",
            details={"path": str(path), "error": str(exc)},
        ) from exc
    if not isinstance(value, dict):
        raise ValidationError(
            "centipede input root must be an object", details={"path": str(path)}
        )
    return value


def _required_non_empty_string(obj: dict[str, Any], key: str) -> str:
    value = obj.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValidationError(
            "centipede input field must be a non-empty string", details={"field": key}
        )
    return value.strip()


def _normalize_repo_relative_path(value: Any, *, target_index: int) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValidationError(
            "centipede target file_path must be a non-empty string",
            details={"target_index": target_index},
        )

    normalized = value.replace("\\", "/").strip()
    path = PurePosixPath(normalized)
    if path.is_absolute():
        raise ValidationError(
            "centipede target file_path must be repository-relative",
            details={"target_index": target_index, "file_path": value},
        )
    if any(part in {"", ".", ".."} for part in path.parts):
        raise ValidationError(
            "centipede target file_path cannot contain empty/current/parent traversal segments",
            details={"target_index": target_index, "file_path": value},
        )
    return str(path)


def _parse_target_ref(value: Any, *, target_index: int) -> CentipedeTargetRef:
    if isinstance(value, str):
        file_path = _normalize_repo_relative_path(value, target_index=target_index)
        return CentipedeTargetRef(
            target_id=f"file:{file_path}",
            file_path=file_path,
            source_kind="string_file_path",
        )

    if not isinstance(value, dict):
        raise ValidationError(
            "centipede target_refs entries must be strings or objects",
            details={"target_index": target_index, "value_type": type(value).__name__},
        )

    file_path_value = None
    for key in ("file_path", "path", "target_path"):
        if key in value:
            file_path_value = value[key]
            break
    file_path = _normalize_repo_relative_path(
        file_path_value, target_index=target_index
    )

    raw_target_id = value.get("target_id", f"file:{file_path}")
    if not isinstance(raw_target_id, str) or not raw_target_id.strip():
        raise ValidationError(
            "centipede target target_id must be a non-empty string when provided",
            details={"target_index": target_index},
        )

    raw_source_kind = value.get("source_kind", value.get("kind", "object_target_ref"))
    if not isinstance(raw_source_kind, str) or not raw_source_kind.strip():
        raise ValidationError(
            "centipede target source_kind/kind must be a non-empty string when provided",
            details={"target_index": target_index},
        )

    return CentipedeTargetRef(
        target_id=raw_target_id.strip(),
        file_path=file_path,
        source_kind=raw_source_kind.strip(),
    )


def load_centipede_input(input_path: str | Path) -> CentipedeInput:
    path = Path(input_path)
    obj = _load_json_object(path)

    unknown = sorted(set(obj.keys()) - _ALLOWED_TOP_LEVEL_KEYS)
    if unknown:
        raise ValidationError(
            "centipede input has unknown top-level keys", details={"keys": unknown}
        )

    schema_version = _required_non_empty_string(obj, "schema_version")
    if schema_version != CENTIPEDE_INPUT_SCHEMA_VERSION:
        raise ValidationError(
            "unsupported centipede input schema_version",
            details={
                "expected": CENTIPEDE_INPUT_SCHEMA_VERSION,
                "actual": schema_version,
            },
        )

    repo_path = Path(_required_non_empty_string(obj, "repo_path")).expanduser()
    base_ref = _required_non_empty_string(obj, "base_ref")
    head_ref = _required_non_empty_string(obj, "head_ref")

    raw_targets = obj.get("target_refs")
    if not isinstance(raw_targets, list) or not raw_targets:
        raise ValidationError("centipede input target_refs must be a non-empty list")

    parsed_targets = tuple(
        _parse_target_ref(value, target_index=index)
        for index, value in enumerate(raw_targets)
    )

    seen_paths: set[str] = set()
    duplicate_paths: set[str] = set()
    for target in parsed_targets:
        if target.file_path in seen_paths:
            duplicate_paths.add(target.file_path)
        seen_paths.add(target.file_path)
    if duplicate_paths:
        raise ValidationError(
            "centipede input target_refs contain duplicate file paths",
            details={"file_paths": sorted(duplicate_paths)},
        )

    metadata = obj.get("metadata", {})
    if not isinstance(metadata, dict):
        raise ValidationError(
            "centipede input metadata must be an object when provided"
        )

    return CentipedeInput(
        schema_version=schema_version,
        repo_path=repo_path,
        base_ref=base_ref,
        head_ref=head_ref,
        target_refs=parsed_targets,
        metadata=metadata,
        raw=obj,
    )
