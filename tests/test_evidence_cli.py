from __future__ import annotations

from pathlib import Path

import pytest

from forge_eval.errors import EvidenceCliError
from forge_eval.evidence_cli import EvidenceCli


def _write_executable(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")
    path.chmod(0o755)


def test_evidence_wrapper_success(tmp_path: Path) -> None:
    fake = tmp_path / "forge-evidence"
    _write_executable(
        fake,
        """#!/usr/bin/env bash
set -euo pipefail
cmd="$1"
shift
case "$cmd" in
  canonicalize)
    cat "$1"
    ;;
  sha256)
    echo "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
    ;;
  artifact-id)
    echo "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"
    ;;
  hashchain)
    echo '{"schema_version":"v1","kind":"hashchain","artifact_hashes":[],"chain_hashes":["1"],"final_chain_hash":"1"}'
    ;;
  *)
    echo "unsupported" >&2
    exit 1
    ;;
esac
""",
    )

    sample = tmp_path / "sample.json"
    sample.write_text('{"b":2,"a":1}', encoding="utf-8")

    cli = EvidenceCli(binary=str(fake))
    assert cli.canonicalize_json(sample) == b'{"b":2,"a":1}'
    assert cli.sha256_file(sample) == "a" * 64
    assert cli.artifact_id(sample, "risk_heatmap") == "b" * 64
    assert cli.hashchain(sample)["kind"] == "hashchain"


def test_evidence_wrapper_failure_is_structured(tmp_path: Path) -> None:
    fake = tmp_path / "forge-evidence"
    _write_executable(
        fake,
        """#!/usr/bin/env bash
set -euo pipefail
echo "boom" >&2
exit 7
""",
    )

    sample = tmp_path / "sample.json"
    sample.write_text("{}", encoding="utf-8")

    cli = EvidenceCli(binary=str(fake))
    with pytest.raises(EvidenceCliError) as exc:
        cli.sha256_file(sample)

    err = exc.value
    assert err.code == "evidence_cli_error"
    assert err.details["returncode"] == 7
    assert "boom" in err.details["stderr"]


@pytest.mark.integration
def test_evidence_wrapper_with_real_binary_if_available(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[1]
    binary = (
        repo_root / "rust" / "forge-evidence" / "target" / "debug" / "forge-evidence"
    )
    if not binary.exists():
        pytest.skip("real forge-evidence binary not built")

    source = tmp_path / "artifact.json"
    source.write_text('{"z":1,"a":2}', encoding="utf-8")

    cli = EvidenceCli(binary=str(binary))
    one = cli.canonicalize_json(source)
    two = cli.canonicalize_json(source)
    assert one == two

    sha = cli.sha256_file(source)
    assert len(sha) == 64
    artifact_id = cli.artifact_id(source, "risk_heatmap")
    assert len(artifact_id) == 64
