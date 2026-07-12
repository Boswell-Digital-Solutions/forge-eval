# bds · Forge Eval

> **System identity — bds family (Boswell Digital Solutions business system, local-systems tier).**
> The deterministic evaluation subsystem for the Forge **ecosystem backend**; part of `ecosystem/local-systems`.
> **Purpose:** business-side evaluation runtime — fail-closed, schema-validated behavioral/hazard evaluation, not public-app support.

Deterministic, schema-validated, fail-closed evaluation subsystem for the Forge ecosystem.

## Documentation Contract

- **Repo type:** Standalone CLI subsystem
- **Authority boundary:** Deterministic evaluation of sibling repositories and local artifact emission; not governance authority and not the durable truth store
- **Deep reference:** `doc/system/_index.md`, `doc/feSYSTEM.md`, `../../docs/canonical/ecosystem_canonical.md`
- **README role:** CLI entrypoint overview
- **Truth note:** Pack listings and emitted-artifact inventory in this README describe the current implementation snapshot unless explicitly marked as canonical invariants

Forge Eval is an **independent repository** within the local Forge ecosystem workspace. It evaluates other independent sibling repositories as target repos. It is not a child subsystem of DataForge, NeuroForge, or forge-smithy.

The core A–N evaluation pipeline is self-contained, requiring only `jsonschema` and `PyYAML` at runtime. A few **optional** subsystems integrate with sibling ecosystem repositories and are not required by the core `forge-eval run`/`validate` CLI: the centipede contract bridge (`forge_contract_core`, imported lazily and fail-closed) and lineage emission (`forge_lineage_sdk`). These are intentionally absent from `pyproject.toml` and are only needed when their respective entrypoints are used.

Current implemented packs:

* **Pack A**: Python scaffold + CLI + orchestration
* **Pack B**: Rust `forge-evidence` canonical JSON / hashing / hashchain
* **Pack C**: Python wrapper around Rust evidence binary
* **Pack D**: Strict JSON schemas
* **Pack E**: Structural risk heatmap stage
* **Pack F**: Context slice extraction stage
* **Pack G**: Deterministic reviewer execution + normalized findings + defect identity
* **Pack H**: Telemetry matrix + reviewer health + tri-state outcomes + `k_eff`
* **Pack I**: Occupancy snapshot + deterministic conservative `psi_post`
* **Pack J**: Hidden-defect capture estimate + Chao1/Chao2/ICE + conservative `max_hidden` selected hidden burden
* **Pack K**: Deterministic conservative hazard mapping (`hazard_map`) from structural risk + telemetry + occupancy + hidden-defect pressure
* **Pack L**: Deterministic advisory merge decision (`merge_decision`) from `hazard_map`
* **Pack M**: Deterministic evidence bundle assembly (`evidence_bundle`) from the fixed A-L artifact chain
* **Pack N**: Deterministic localization pack (`localization_pack`) — file/block candidate ranking plus review/patch scope derived from the A-K artifact chain; optional stage, not enabled by default

## Repo role

Forge Eval implements the deterministic eval pipeline foundation:

```text
risk -> context slices -> reviewer findings -> telemetry matrix -> occupancy snapshot -> capture estimate -> hazard map -> merge decision -> evidence bundle
```

Core invariants:

* deterministic outputs
* schema-locked artifacts
* fail-closed behavior
* fixed stage order
* byte-stable repeated runs on identical inputs

## Build Rust evidence binary

```bash
cd rust/forge-evidence
cargo build
```

`cargo build --offline` succeeds only when the crate dependencies are already in
the local cargo cache (or vendored). In a clean offline environment, run a
networked `cargo build` once to populate the cache first.

Binary path after build:

```text
rust/forge-evidence/target/debug/forge-evidence
```

Use `FORGE_EVIDENCE_BIN` to point the Python wrapper to the binary if it is not on `PATH`.
Pack M is the first runtime stage that invokes this binary.

## Install Python package

```bash
pip install -e .
```

Offline local dev note:

- `pyproject.toml` currently requires `jsonschema>=4.10.3` and `PyYAML>=6.0.1`.
- In a networked environment, plain `pip install -e .` is the normal path.
- In an offline environment where those dependencies are already present from system packages or a pre-provisioned venv, use:

```bash
pip install --no-build-isolation -e .
```

This avoids pip's isolated build environment trying to download build requirements.

## Run pipeline

```bash
forge-eval run --repo /path/to/target-repo --base <base> --head <head> --config config.yaml --out artifacts/
```

## Validate artifacts

```bash
forge-eval validate --artifacts artifacts/
```

## Current emitted artifacts

Depending on enabled stages, Forge Eval currently emits:

* `config.resolved.json`
* `risk_heatmap.json`
* `context_slices.json`
* `review_findings.json`
* `telemetry_matrix.json`
* `occupancy_snapshot.json`
* `capture_estimate.json`
* `hazard_map.json`
* `merge_decision.json`
* `evidence_bundle.json`
* `localization_pack.json` (only when the optional `localization_pack` stage is enabled)

## Current fixed stage order

```text
risk_heatmap -> context_slices -> review_findings -> telemetry_matrix -> occupancy_snapshot -> capture_estimate -> hazard_map -> merge_decision -> evidence_bundle
```

`localization_pack` is an additional optional stage, registered after
`evidence_bundle` in the canonical stage order but not enabled by default. Enable
it by adding `localization_pack` to `enabled_stages` in your config.

## Determinism notes

* JSON artifacts are written with sorted keys and compact separators.
* Stage order is fixed and deterministic.
* Context extraction uses head-version content with deterministic diff/range processing.
* Cap overflows fail closed with explicit error behavior.
* Reviewer failures are fail-closed by default (`reviewer_failure_policy=fail_stage`).
* `defect_key` is canonical across reviewers for matching identity fields.
* Cross-reviewer findings coalesce in telemetry; same-reviewer duplicates and metadata collisions fail closed.
* Telemetry uses strict tri-state semantics: `1`, `0`, or `null`.
* Failed, skipped, or inapplicable reviewers do not count as clean misses.
* Occupancy uses conservative posterior semantics: usable misses suppress, `null` adds uncertainty.
* Hidden-defect estimation uses deterministic Chao1/Chao2/ICE outputs with conservative `max_hidden` selection.

## Status

Forge Eval Packs A-N are implemented in the current repo state (Pack N localization is an optional, non-default stage).

The current A–M runtime path has been verified on a real local target repo:

- emitted artifact set: `config.resolved.json`, `risk_heatmap.json`, `context_slices.json`, `review_findings.json`, `telemetry_matrix.json`, `occupancy_snapshot.json`, `capture_estimate.json`, `hazard_map.json`, `merge_decision.json`, `evidence_bundle.json`
- `forge-eval validate` passed on the emitted artifacts
- repeated identical runs were byte-identical across all primary artifacts, including `evidence_bundle.json`
- fail-closed probes were confirmed for config, validation, reviewer-failure, and cross-artifact mismatch cases

Verification report:

- `reports/forge_eval_a_to_j_verification_report_rev1.md`
- `reports/forge_eval_pack_k_hazard_implementation_report_rev1.md`
- `reports/forge_eval_pack_l_merge_decision_implementation_report_rev1.md`
- `reports/forge_eval_pack_m_evidence_bundle_implementation_report_rev1.md`

## Important note on Rust evidence

The Rust evidence subsystem is implemented, callable, and tested. Pack M begins bounded runtime integration:

- Packs A-L remain Python-owned stage logic
- Pack M invokes `forge-evidence` only for canonical JSON, artifact ID, and hashchain work
- the runtime boundary remains local and deterministic
- signing, publishing, and release execution remain out of scope

## License

Proprietary — all rights reserved. See [`LICENSE`](LICENSE).
