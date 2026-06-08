from __future__ import annotations

from pathlib import Path

_FAKE_EVIDENCE_SOURCE = r"""#!/usr/bin/env python3
import hashlib
import json
import os
import sys
from pathlib import Path


def canonicalize_bytes(raw: bytes) -> bytes:
    value = json.loads(raw.decode("utf-8"))
    return (json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)).encode("utf-8")


def default_kind(path: str) -> str:
    return Path(path).stem


def artifact_id(kind: str, canonical: bytes) -> str:
    return hashlib.sha256(kind.encode("utf-8") + b"\0" + canonical).hexdigest()


def load_inputs(path: Path):
    if path.is_dir():
        out = []
        for child in sorted(path.rglob("*.json")):
            out.append({"path": child.as_posix(), "kind": default_kind(child.name)})
        if not out:
            raise SystemExit("directory contains no .json artifacts")
        return out

    data = json.loads(path.read_text(encoding="utf-8"))
    items = data["artifacts"] if isinstance(data, dict) else data
    out = []
    for item in items:
        if isinstance(item, str):
            out.append({"path": item, "kind": default_kind(item)})
        else:
            out.append({"path": item["path"], "kind": item.get("kind", default_kind(item["path"]))})
    if not out:
        raise SystemExit("manifest produced no inputs")
    return out


def main() -> int:
    cmd = sys.argv[1]
    if cmd == "canonicalize":
        path = Path(sys.argv[2])
        sys.stdout.buffer.write(canonicalize_bytes(path.read_bytes()))
        return 0
    if cmd == "sha256":
        path = Path(sys.argv[2])
        sys.stdout.write(hashlib.sha256(path.read_bytes()).hexdigest() + "\n")
        return 0
    if cmd == "artifact-id":
        path = Path(sys.argv[2])
        kind = sys.argv[4]
        canonical = canonicalize_bytes(path.read_bytes())
        sys.stdout.write(artifact_id(kind, canonical) + "\n")
        return 0
    if cmd == "hashchain":
        if os.environ.get("FORGE_FAKE_EVIDENCE_FAIL") == "hashchain":
            sys.stderr.write("forced hashchain failure\n")
            return 19
        path = Path(sys.argv[2])
        base = path.parent if path.parent.as_posix() not in ("", ".") else Path(".")
        inputs = load_inputs(path)
        artifact_hashes = []
        for idx, entry in enumerate(inputs):
            raw_path = entry["path"]
            full = base / raw_path
            canonical = canonicalize_bytes(full.read_bytes())
            sha = hashlib.sha256(canonical).hexdigest()
            aid = artifact_id(entry["kind"], canonical)
            if os.environ.get("FORGE_FAKE_EVIDENCE_CORRUPT") == "artifact_id" and idx == 0:
                aid = "0" * 64
            artifact_hashes.append({
                "index": idx,
                "path": raw_path,
                "kind": entry["kind"],
                "artifact_sha256": sha,
                "artifact_id": aid,
            })
        prev = hashlib.sha256(b"forge-evidence-chain-v1").hexdigest()
        chain_hashes = [prev]
        for entry in artifact_hashes:
            prev = hashlib.sha256(f"{prev}:{entry['artifact_sha256']}".encode("utf-8")).hexdigest()
            chain_hashes.append(prev)
        sys.stdout.write(json.dumps({
            "schema_version": "v1",
            "kind": "hashchain",
            "artifact_hashes": artifact_hashes,
            "chain_hashes": chain_hashes,
            "final_chain_hash": prev,
        }, sort_keys=True, separators=(",", ":")))
        return 0
    sys.stderr.write("unsupported command\n")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
"""


def write_fake_evidence_binary(path: Path) -> Path:
    path.write_text(_FAKE_EVIDENCE_SOURCE, encoding="utf-8")
    path.chmod(0o755)
    return path
