from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from forge_eval.config import normalize_config
from forge_eval.stage_runner import stable_json_dumps
from forge_eval.stages.risk_heatmap import run_stage
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


def _init_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    _run(["git", "init"], repo)
    _run(["git", "config", "user.email", "forge@example.com"], repo)
    _run(["git", "config", "user.name", "Forge Test"], repo)
    return repo


def _commit_all(repo: Path, message: str) -> None:
    _run(["git", "add", "-A"], repo)
    _run(["git", "commit", "-m", message], repo)


def test_risk_heatmap_repo_integration_is_deterministic(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path)

    (repo / "a.py").write_text(
        "\n".join([f"line{i:02d}" for i in range(1, 11)]) + "\n", encoding="utf-8"
    )
    (repo / "b.py").write_text("import a\n\nvalue = 1\n", encoding="utf-8")
    _commit_all(repo, "base")

    (repo / "a.py").write_text(
        "\n".join([f"line{i:02d}" if i != 5 else "line05_mod" for i in range(1, 11)])
        + "\n",
        encoding="utf-8",
    )
    (repo / "b.py").write_text("import a\nimport json\n\nvalue = 2\n", encoding="utf-8")
    _commit_all(repo, "head")

    cfg = normalize_config({})

    first = run_stage(
        repo_path=repo,
        base_ref="HEAD~1",
        head_ref="HEAD",
        run_id="run-risk",
        config=cfg,
    )
    second = run_stage(
        repo_path=repo,
        base_ref="HEAD~1",
        head_ref="HEAD",
        run_id="run-risk",
        config=cfg,
    )

    assert stable_json_dumps(first) == stable_json_dumps(second)
    assert [target["file_path"] for target in first["targets"]] == sorted(
        target["file_path"] for target in first["targets"]
    )

    schema = load_schema("risk_heatmap")
    validate_instance(first, schema, artifact_kind="risk_heatmap")
