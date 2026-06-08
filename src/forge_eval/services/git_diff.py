from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path

from forge_eval.errors import GitError


@dataclass(frozen=True)
class ChangedFile:
    status: str
    path: str
    old_path: str | None = None


def _run_git(repo_path: str | Path, args: list[str], *, text: bool = True) -> str:
    repo = str(Path(repo_path))
    cmd = ["git", "-C", repo, *args]
    proc = subprocess.run(
        cmd,
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=text,
    )
    if proc.returncode != 0:
        raise GitError(
            "git command failed",
            details={
                "cmd": cmd,
                "returncode": proc.returncode,
                "stderr": proc.stderr.strip() if isinstance(proc.stderr, str) else "",
            },
        )
    if not isinstance(proc.stdout, str):
        raise GitError("unexpected non-text git output", details={"cmd": cmd})
    return proc.stdout


def resolve_commit(repo_path: str | Path, ref: str) -> str:
    out = _run_git(repo_path, ["rev-parse", ref]).strip()
    if not out:
        raise GitError("failed to resolve git ref", details={"ref": ref})
    return out


def list_changed_files(
    repo_path: str | Path, base_ref: str, head_ref: str
) -> list[ChangedFile]:
    output = _run_git(
        repo_path,
        ["diff", "--name-status", "--find-renames", base_ref, head_ref],
    )

    results: list[ChangedFile] = []
    for raw_line in output.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        parts = line.split("\t")
        status = parts[0]
        if status.startswith("R"):
            if len(parts) != 3:
                raise GitError(
                    "ambiguous rename status line", details={"line": raw_line}
                )
            results.append(ChangedFile(status="R", old_path=parts[1], path=parts[2]))
            continue

        if len(parts) != 2:
            raise GitError("ambiguous name-status line", details={"line": raw_line})
        normalized_status = status[0]
        results.append(ChangedFile(status=normalized_status, path=parts[1]))

    results.sort(key=lambda item: (item.path, item.status, item.old_path or ""))
    return results


def numstat_for_file(
    repo_path: str | Path, base_ref: str, head_ref: str, file_path: str
) -> tuple[int, int, bool]:
    output = _run_git(
        repo_path, ["diff", "--numstat", base_ref, head_ref, "--", file_path]
    )
    lines = [line for line in output.splitlines() if line.strip()]
    if not lines:
        return (0, 0, False)
    first = lines[0]
    parts = first.split("\t")
    if len(parts) < 3:
        raise GitError(
            "ambiguous numstat line", details={"line": first, "file_path": file_path}
        )
    add_s, del_s = parts[0], parts[1]
    if add_s == "-" or del_s == "-":
        return (0, 0, True)
    try:
        return (int(add_s), int(del_s), False)
    except ValueError as exc:
        raise GitError(
            "invalid numstat values", details={"line": first, "file_path": file_path}
        ) from exc


def unified_diff_for_file(
    repo_path: str | Path,
    base_ref: str,
    head_ref: str,
    file_path: str,
    *,
    unified_lines: int,
) -> str:
    return _run_git(
        repo_path,
        [
            "diff",
            "--no-color",
            f"--unified={unified_lines}",
            "--find-renames",
            base_ref,
            head_ref,
            "--",
            file_path,
        ],
    )


def file_content_at_ref(repo_path: str | Path, ref: str, file_path: str) -> str:
    spec = f"{ref}:{file_path}"
    return _run_git(repo_path, ["show", spec])


def list_tracked_files(repo_path: str | Path) -> list[str]:
    output = _run_git(repo_path, ["ls-files"])
    files = [line.strip() for line in output.splitlines() if line.strip()]
    files.sort()
    return files


def path_is_excluded(path: str, exclude_prefixes: list[str]) -> bool:
    normalized = path.replace("\\", "/")
    return any(normalized.startswith(prefix) for prefix in exclude_prefixes)


def path_has_allowed_extension(path: str, include_extensions: list[str]) -> bool:
    lower = path.lower()
    return any(lower.endswith(ext) for ext in include_extensions)
