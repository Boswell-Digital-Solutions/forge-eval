from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from typing import Any

from forge_eval.errors import EvidenceCliError


class EvidenceCli:
    """Fail-closed subprocess wrapper for the Rust forge-evidence binary.

    Current A-J runtime posture: this wrapper is verified and callable, but
    `stage_runner.py` does not invoke it in the main stage pipeline yet.
    """

    def __init__(self, binary: str | None = None) -> None:
        self.binary = binary or os.environ.get("FORGE_EVIDENCE_BIN", "forge-evidence")

    def _run(self, args: list[str], *, cwd: str | Path | None = None) -> bytes:
        cmd = [self.binary, *args]
        try:
            proc = subprocess.run(
                cmd,
                check=False,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                cwd=str(cwd) if cwd is not None else None,
            )
        except OSError as exc:
            raise EvidenceCliError(
                f"failed to execute evidence binary: {self.binary}",
                details={
                    "cmd": cmd,
                    "cwd": None if cwd is None else str(cwd),
                    "os_error": str(exc),
                },
            ) from exc

        if proc.returncode != 0:
            raise EvidenceCliError(
                "evidence binary returned non-zero exit code",
                details={
                    "cmd": cmd,
                    "cwd": None if cwd is None else str(cwd),
                    "returncode": proc.returncode,
                    "stderr": proc.stderr.decode("utf-8", errors="replace").strip(),
                    "stdout": proc.stdout.decode("utf-8", errors="replace").strip(),
                },
            )

        return proc.stdout

    def canonicalize_json(
        self, input_path: str | Path, *, cwd: str | Path | None = None
    ) -> bytes:
        path = str(Path(input_path))
        return self._run(["canonicalize", path], cwd=cwd)

    def sha256_file(
        self, input_path: str | Path, *, cwd: str | Path | None = None
    ) -> str:
        path = str(Path(input_path))
        out = (
            self._run(["sha256", path], cwd=cwd)
            .decode("utf-8", errors="replace")
            .strip()
        )
        if len(out) != 64:
            raise EvidenceCliError(
                "invalid sha256 output length from evidence binary",
                details={"path": path, "output": out},
            )
        return out

    def artifact_id(
        self, input_path: str | Path, kind: str, *, cwd: str | Path | None = None
    ) -> str:
        path = str(Path(input_path))
        out = (
            self._run(["artifact-id", path, "--kind", kind], cwd=cwd)
            .decode("utf-8", errors="replace")
            .strip()
        )
        if len(out) != 64:
            raise EvidenceCliError(
                "invalid artifact-id output length from evidence binary",
                details={"path": path, "kind": kind, "output": out},
            )
        return out

    def hashchain(
        self, input_path: str | Path, *, cwd: str | Path | None = None
    ) -> dict[str, Any]:
        path = str(Path(input_path))
        raw = (
            self._run(["hashchain", path], cwd=cwd)
            .decode("utf-8", errors="replace")
            .strip()
        )
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise EvidenceCliError(
                "hashchain output from evidence binary is invalid JSON",
                details={"path": path, "output": raw},
            ) from exc
        if not isinstance(parsed, dict):
            raise EvidenceCliError(
                "hashchain output must be a JSON object",
                details={"path": path, "output": raw},
            )
        return parsed


_DEFAULT_EVIDENCE_CLI = EvidenceCli()


def canonicalize_json(input_path: str | Path) -> bytes:
    return _DEFAULT_EVIDENCE_CLI.canonicalize_json(input_path)


def sha256_file(input_path: str | Path) -> str:
    return _DEFAULT_EVIDENCE_CLI.sha256_file(input_path)


def artifact_id(input_path: str | Path, kind: str) -> str:
    return _DEFAULT_EVIDENCE_CLI.artifact_id(input_path, kind)


def hashchain(input_path: str | Path) -> dict[str, Any]:
    return _DEFAULT_EVIDENCE_CLI.hashchain(input_path)
