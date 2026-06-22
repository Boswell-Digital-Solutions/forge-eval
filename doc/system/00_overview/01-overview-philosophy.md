# §1 - Overview and Philosophy

## Purpose

`forge-eval` is a deterministic, fail-closed evaluation foundation implementing Packs A-M:

- Pack A: Python scaffold, CLI, orchestration, error model.
- Pack B: Rust evidence binary (`forge-evidence`) for canonical JSON/hash/hashchain primitives.
- Pack C: Python subprocess wrapper around the Rust binary.
- Pack D: Strict JSON schema contracts for current and future artifacts.
- Pack E: Structural risk heatmap generation from git-derived features.
- Pack F: Context slice extraction from git diff hunks.
- Pack G: Deterministic reviewer execution, normalized findings, stable defect identity.
- Pack H: Deterministic telemetry matrix with reviewer-truth preservation and conservative `k_eff`.
- Pack I: Deterministic occupancy posterior estimation (`psi_post`) with conservative null handling.
- Pack J: Deterministic hidden-defect estimation (`capture_estimate`) with Chao1/ICE and conservative selection.
- Pack K: Deterministic hazard assessment (`hazard_map`) combining structural risk, observed burden, residual occupancy concern, and hidden-defect pressure.
- Pack L: Deterministic advisory merge decision (`merge_decision`) from Pack K hazard evidence.
- Pack M: Deterministic evidence bundle assembly (`evidence_bundle`) packaging the fixed A-L artifact chain.

## Current Pipeline Boundary

Implemented path:

`config -> risk_heatmap -> context_slices -> review_findings -> telemetry_matrix -> occupancy_snapshot -> capture_estimate -> hazard_map -> merge_decision -> evidence_bundle`

Planned downstream (not implemented here): publish/release or governance execution beyond evidence assembly.

## Governing Principles

1. Deterministic output for identical repo/config/base/head inputs.
2. Fail closed on ambiguity, unsupported state, and cap overflow.
3. Strict schema contracts with `additionalProperties: false` on primary objects.
4. No silent truncation; explicit policy-driven behavior only.
5. Stable artifact serialization on Python side (`sort_keys=True`, compact JSON).
6. Evidence-grade canonicalization delegated to Rust tooling.
