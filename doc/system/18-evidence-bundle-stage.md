# §18 - Pack M: Evidence Bundle Stage

## Stage Contract

Input:

- fixed upstream artifact chain through `merge_decision.json`
- normalized evidence-bundle config block (`evidence_bundle_model_version`)
- bounded runtime `forge-evidence` access via `evidence_cli.py`

Output:

- `evidence_bundle.json` (schema kind: `evidence_bundle`)

## Execution Model

1. Validate the fixed A-L artifact chain is present and kind-consistent.
2. Validate deterministic run alignment using `config.resolved.json` and `merge_decision.json`.
3. Load the locked evidence-bundle model (`evidence_bundle_rev1`).
4. Invoke `forge-evidence` through `evidence_cli.py` for:
   - canonical JSON bytes
   - deterministic artifact IDs
   - bounded hashchain assembly
5. Cross-check the Rust hashchain output against the Python-side artifact inventory.
6. Emit a schema-valid `evidence_bundle.json` manifest artifact.

## Runtime Evidence Boundary

Pack M is the first runtime stage that invokes `forge-evidence`.

The active boundary is intentionally narrow:

- canonical JSON only
- artifact identity only
- hashchain only

Pack M does not add:

- signing
- publishing
- deployment
- release execution
- git operations

## Artifact Semantics

`evidence_bundle.json` packages the fixed A-L proof surface into:

- `run`: deterministic run provenance and merge-decision source pointer
- `inputs`: stable artifact list and bounded evidence runtime mode
- `artifacts`: ordered artifact inventory with `canonical_sha256`, `artifact_id`, and `file_size_bytes`
- `decision`: bounded reference to the final advisory merge posture
- `manifest`: deterministic hashchain seed, artifact order, chain hashes, and `final_chain_hash`
- `summary`: compact deterministic coverage/decision summary
- `model`: locked Pack M assembly model metadata
- `provenance`: deterministic algorithm metadata and explicit runtime evidence integration mode

## Model Rules (Rev 1)

- model version: `evidence_bundle_rev1`
- mode: `deterministic_manifest_assembly`
- evidence runtime: `forge_evidence_cli`
- hash strategy: canonical JSON SHA-256
- artifact ID strategy: `sha256(kind + NUL + canonical_json_bytes)`
- hashchain strategy: `forge-evidence-chain-v1`

Artifact order is fixed:

1. `config.resolved.json`
2. `risk_heatmap.json`
3. `context_slices.json`
4. `review_findings.json`
5. `telemetry_matrix.json`
6. `occupancy_snapshot.json`
7. `capture_estimate.json`
8. `hazard_map.json`
9. `merge_decision.json`

## Fail-Closed Behavior

- missing upstream artifact file -> stage failure
- kind mismatch in the fixed A-L artifact chain -> stage failure
- run/ref mismatch between pipeline and `config.resolved.json` or `merge_decision.json` -> stage failure
- unsupported `evidence_bundle_model_version` -> stage failure
- runtime `forge-evidence` execution failure -> `EvidenceCliError`
- malformed or inconsistent hashchain output -> stage failure
- schema validation failure -> run failure

## Determinism Notes

- artifact inventory order is fixed and explicit
- manifest paths are relative and stable across output directories
- Pack M does not hash or embed its own output file recursively
- repeated identical inputs must produce byte-identical `evidence_bundle.json`
