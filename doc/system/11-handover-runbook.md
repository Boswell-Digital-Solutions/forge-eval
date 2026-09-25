# §11 - Handover and Runbook

## Build and Install

```bash
cd /home/charlie/Forge/ecosystem/forge-eval/repo

# Rust evidence binary
cd rust/forge-evidence
cargo build --offline

# Python package
cd ../../
pip install -e .
```

Offline dev install path when dependencies are already provisioned in the environment:

```bash
pip install --no-build-isolation -e .
```

Current verified lower bound from the live repo test surface:

- `jsonschema>=4.10.3`
- `PyYAML>=6.0.1`

Reason for the offline flag:

- plain `pip install -e .` uses an isolated build environment
- offline installs will fail unless build requirements are available from an index or wheel cache
- `--no-build-isolation` is the truthful local/offline path when build dependencies are already present

If the evidence binary is not on `PATH`:

```bash
export FORGE_EVIDENCE_BIN=/abs/path/to/rust/forge-evidence/target/debug/forge-evidence
```

Current evidence boundary:

- the Rust evidence binary is verified and callable
- Pack M invokes it in the main A-M stage path only for canonical JSON, artifact ID, and hashchain work

## Execute Pipeline

```bash
forge-eval run \
  --repo /abs/path/to/target/repo \
  --base <base-ref> \
  --head <head-ref> \
  --config /abs/path/to/config.yaml \
  --out /abs/path/to/artifacts
```

## Validate Artifacts

```bash
forge-eval validate --artifacts /abs/path/to/artifacts
```

## Deterministic Acceptance Checks

1. Run the same `forge-eval run` command twice on identical inputs.
2. Compare produced artifacts byte-for-byte.
3. Confirm reviewer execution statuses are explicit (`ok`/`failed`/`skipped`) in `review_findings.json`.
4. Confirm telemetry cells are explicit (`1`/`0`/`null`) in `telemetry_matrix.json`.
5. Confirm shared canonical defects can produce `reported_by` length > 1 and `support_count` > 1 in `telemetry_matrix.json`.
6. Confirm same-reviewer duplicates and metadata collisions fail closed in tests.
7. Confirm occupancy rows are bounded (`psi_post` in `[0,1]`) in `occupancy_snapshot.json`.
8. Confirm capture outputs include Chao1, ICE, and selected hidden estimate in `capture_estimate.json`.
9. Confirm hazard output includes bounded `hazard_score`, deterministic `hazard_tier`, and explicit uncertainty flags in `hazard_map.json`.
10. Confirm merge decision output includes advisory `allow | caution | block` result and deterministic `reason_codes` in `merge_decision.json`.
11. Confirm evidence bundle output includes the full A-L artifact inventory, stable `canonical_sha256` / `artifact_id` values, and a deterministic `final_chain_hash` in `evidence_bundle.json`.
12. Run Python and Rust tests before merge.

## Guardrails for Next Packs

1. Keep schema-first contracts; add new artifact kinds in `schemas/` before stage logic.
2. Preserve fail-closed defaults unless governance text explicitly allows deterministic reduction.
3. Keep evidence primitives centralized in Rust; do not duplicate them in Python.
4. Keep Pack G reviewer logic deterministic and isolated from Pack H+ telemetry/occupancy/hazard logic.
5. Preserve ghost-coverage guard: failed/skipped/inapplicable reviewer states must never be coerced to clean misses.
6. Preserve occupancy conservatism: weak/null-heavy coverage must not be treated as strong suppression.
7. Preserve capture conservatism: singleton-heavy sparse evidence must not collapse to low hidden-defect estimates.
8. Preserve hazard conservatism: hidden-defect pressure and uncertainty must not be converted into a clean-looking change set.
9. Preserve merge-decision narrowness: Pack L must consume hazard evidence conservatively and remain advisory.
10. Preserve Pack M narrowness: evidence bundle assembly must stay local, deterministic, and bounded to packaging/manifest work; no publish or release actions.
