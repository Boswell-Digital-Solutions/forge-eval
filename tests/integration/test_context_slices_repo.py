from __future__ import annotations

import copy
import subprocess
from pathlib import Path

import pytest

from forge_eval.config import normalize_config
from forge_eval.errors import StageError
from forge_eval.stage_runner import stable_json_dumps
from forge_eval.stages.context_slices import run_stage
from forge_eval.validation.schema_loader import load_schema
from forge_eval.validation.validate_artifact import validate_instance

pytestmark = pytest.mark.integration


def _run(cmd: list[str], cwd: Path) -> str:
    proc = subprocess.run(
        cmd,
        cwd=str(cwd),
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    return proc.stdout.strip()


def _init_repo(tmp_path: Path, name: str = "repo") -> Path:
    repo = tmp_path / name
    repo.mkdir()
    _run(["git", "init"], repo)
    _run(["git", "config", "user.email", "forge@example.com"], repo)
    _run(["git", "config", "user.name", "Forge Test"], repo)
    return repo


def _commit_all(repo: Path, message: str) -> None:
    _run(["git", "add", "-A"], repo)
    _run(["git", "commit", "-m", message], repo)


def _write_lines(path: Path, lines: list[str]) -> None:
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _base_lines(count: int) -> list[str]:
    return [f"line{i:02d}" for i in range(1, count + 1)]


def _artifact_for(
    repo: Path,
    *,
    run_id: str = "run-context",
    config_overrides: dict[str, object] | None = None,
) -> dict[str, object]:
    config = normalize_config(config_overrides or {})
    return run_stage(
        repo_path=repo,
        base_ref="HEAD~1",
        head_ref="HEAD",
        run_id=run_id,
        config=config,
    )


def _normalize_for_golden(artifact: dict[str, object]) -> dict[str, object]:
    normalized = copy.deepcopy(artifact)
    normalized["repo_path"] = "<repo>"
    return normalized


def _assert_matches_golden(name: str, artifact: dict[str, object]) -> None:
    golden_dir = Path(__file__).resolve().parent / "golden"
    expected = (golden_dir / name).read_text(encoding="utf-8")
    actual = stable_json_dumps(_normalize_for_golden(artifact))
    assert actual == expected


def test_single_file_single_hunk_one_slice_and_golden(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path, "single")
    file_path = repo / "a.py"

    _write_lines(file_path, _base_lines(12))
    _commit_all(repo, "base")

    lines = _base_lines(12)
    lines[4] = "line05_mod"
    _write_lines(file_path, lines)
    _commit_all(repo, "head")

    artifact = _artifact_for(
        repo,
        run_id="run-golden",
        config_overrides={"context_radius_lines": 1, "merge_gap_lines": 1},
    )

    assert artifact["summary"]["slice_count"] == 1
    slc = artifact["slices"][0]
    assert slc["start_line"] == 4
    assert slc["end_line"] == 6
    assert slc["changed_line_count"] == 1

    _assert_matches_golden("context_single_hunk.json", artifact)


def test_single_file_two_nearby_hunks_merge_to_one_slice(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path, "nearby")
    file_path = repo / "a.py"

    _write_lines(file_path, _base_lines(15))
    _commit_all(repo, "base")

    lines = _base_lines(15)
    lines[4] = "line05_mod"
    lines[6] = "line07_mod"
    _write_lines(file_path, lines)
    _commit_all(repo, "head")

    artifact = _artifact_for(
        repo, config_overrides={"context_radius_lines": 1, "merge_gap_lines": 1}
    )
    assert artifact["summary"]["slice_count"] == 1
    slc = artifact["slices"][0]
    assert slc["start_line"] == 4
    assert slc["end_line"] == 8


def test_single_file_distant_hunks_two_slices_and_golden(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path, "distant")
    file_path = repo / "a.py"

    _write_lines(file_path, _base_lines(30))
    _commit_all(repo, "base")

    lines = _base_lines(30)
    lines[4] = "line05_mod"
    lines[24] = "line25_mod"
    _write_lines(file_path, lines)
    _commit_all(repo, "head")

    artifact = _artifact_for(
        repo,
        run_id="run-golden",
        config_overrides={"context_radius_lines": 1, "merge_gap_lines": 1},
    )

    assert artifact["summary"]["slice_count"] == 2
    assert [s["slice_id"] for s in artifact["slices"]] == ["a.py:4:6", "a.py:24:26"]

    _assert_matches_golden("context_distant_hunks.json", artifact)


def test_oversized_slice_splits_deterministically(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path, "split")
    file_path = repo / "a.py"

    _write_lines(file_path, _base_lines(40))
    _commit_all(repo, "base")

    lines = _base_lines(40)
    lines[19] = "line20_mod"
    _write_lines(file_path, lines)
    _commit_all(repo, "head")

    artifact = _artifact_for(
        repo,
        config_overrides={
            "context_radius_lines": 5,
            "max_lines_per_slice": 4,
            "merge_gap_lines": 1,
        },
    )

    assert [s["slice_id"] for s in artifact["slices"]] == [
        "a.py:15:18",
        "a.py:19:22",
        "a.py:23:25",
    ]


def test_max_total_lines_exceeded_fails_closed(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path, "cap")
    file_path = repo / "a.py"

    _write_lines(file_path, _base_lines(40))
    _commit_all(repo, "base")

    lines = _base_lines(40)
    lines[19] = "line20_mod"
    _write_lines(file_path, lines)
    _commit_all(repo, "head")

    with pytest.raises(StageError):
        _artifact_for(
            repo,
            config_overrides={
                "context_radius_lines": 5,
                "max_lines_per_slice": 10,
                "max_total_lines": 5,
            },
        )


def test_binary_file_change_policy_fail(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path, "binary")

    (repo / "a.py").write_text("print('a')\n", encoding="utf-8")
    (repo / "blob.bin").write_bytes(b"\x00\x01\x02\x03")
    _commit_all(repo, "base")

    (repo / "a.py").write_text("print('b')\n", encoding="utf-8")
    (repo / "blob.bin").write_bytes(b"\x04\x05\x06\x07")
    _commit_all(repo, "head")

    with pytest.raises(StageError):
        _artifact_for(
            repo,
            config_overrides={
                "include_file_extensions": [".py", ".bin"],
                "binary_file_policy": "fail",
            },
        )


def test_context_slices_schema_validation_and_repeatability(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path, "schema")
    file_path = repo / "a.py"

    _write_lines(file_path, _base_lines(12))
    _commit_all(repo, "base")

    lines = _base_lines(12)
    lines[4] = "line05_mod"
    _write_lines(file_path, lines)
    _commit_all(repo, "head")

    first = _artifact_for(
        repo, run_id="repeat", config_overrides={"context_radius_lines": 1}
    )
    second = _artifact_for(
        repo, run_id="repeat", config_overrides={"context_radius_lines": 1}
    )
    assert stable_json_dumps(first) == stable_json_dumps(second)

    schema = load_schema("context_slices")
    validate_instance(first, schema, artifact_kind="context_slices")
