# §6 - Evidence Subsystem

## Rust Binary: `forge-evidence`

CLI commands:

```bash
forge-evidence canonicalize <input.json>
forge-evidence sha256 <input-file>
forge-evidence artifact-id <input.json> --kind <artifact-kind>
forge-evidence hashchain <directory-or-manifest>
```

## Deterministic Policies

- Canonical JSON:
  - sorted object keys
  - compact output (no pretty print)
  - UTF-8 bytes
  - arrays preserve order
  - non-finite floats rejected
- SHA-256 output as lowercase 64-char hex.
- Artifact ID: `sha256(kind + NUL + canonical_json_bytes)`.
- Hashchain seed: `sha256("forge-evidence-chain-v1")`, then chained left-to-right.

## Python Wrapper: `evidence_cli.py`

Wrapper behavior is fail-closed:

- explicit subprocess calls only
- non-zero exit -> `EvidenceCliError`
- parse and validate output shape (length, JSON object)
- no fallback to Python-native canonicalization/hashing

Environment override:

- `FORGE_EVIDENCE_BIN` can point to a non-PATH binary.

## Current Runtime Posture

- `forge-evidence` and `evidence_cli.py` are implemented, directly callable, and covered by Rust/Python tests.
- Pack M is the first runtime stage that invokes the evidence wrapper during `forge-eval run`.
- This is the active boundary in the current repo state:
  - Packs A-L remain Python-owned stage logic
  - Pack M invokes `forge-evidence` only for canonical JSON, artifact identity, and hashchain work
  - signing, publishing, and release execution remain out of scope
