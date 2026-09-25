# §14 - Pack I: Occupancy Snapshot Stage

## Stage Contract

Input:

- `telemetry_matrix` artifact (required)
- normalized occupancy model config (required)

Output:

- `occupancy_snapshot.json` (schema kind: `occupancy_snapshot`)
- Downstream consumer: Pack J `capture_estimate` stage

## Execution Model

1. Validate telemetry artifact shape and enforce `run_id` consistency.
2. Build canonical per-defect occupancy rows from telemetry defects + matrix.
3. Derive deterministic priors from support/severity using config-locked policy.
4. Compute deterministic posterior occupancy (`psi_post`) with:
   - positive retention from observed detections,
   - suppression only from usable misses,
   - uncertainty guard from `null` coverage.
5. Emit bounded, schema-valid rows sorted by `defect_key`.
6. Emit deterministic summary + model metadata for auditability.

## Core Semantics

- `null` is uncertainty, not a clean miss.
- suppression requires usable miss evidence (`0` cells).
- sparse usable coverage does not over-suppress occupancy.
- `psi_post` is always bounded in `[0,1]`.

## Model Rule (v1)

`occupancy_model_version=occupancy_rev1` with deterministic conservative rule:

- prior = `occupancy_prior_base + occupancy_support_uplift(if support_count>0) + severity_uplift`
- observed retention from `occupancy_detection_assumption`
- miss penalty from usable miss ratio and coverage ratio
- uncertainty guard from null ratio and low coverage
- bounded posterior: `clamp(..., 0.02, 0.995)`

All parameters are config-locked and emitted in `model.parameters`.

## Fail-Closed Behavior

- telemetry artifact kind mismatch -> stage failure.
- run mismatch or missing telemetry fields -> stage failure.
- duplicate or inconsistent defect/matrix keys -> stage failure.
- illegal matrix cell values (outside `1/0/null`) -> stage failure.
- impossible row counts or `k_eff_defect` mismatch -> stage failure.
- unsupported model version or out-of-range model params -> stage failure.
- schema validation failure -> run failure.

## Determinism Notes

- rows sorted by `defect_key`.
- fixed rounding policy via `occupancy_round_digits`.
- no clock-based fields in primary payload.
- model metadata is explicit and version-locked.
