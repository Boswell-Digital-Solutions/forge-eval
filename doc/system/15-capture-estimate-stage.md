# §15 - Pack J: Capture Estimate Stage

## Stage Contract

Input:

- `telemetry_matrix` artifact (required)
- `occupancy_snapshot` artifact (required)
- normalized capture-estimate config (required)

Output:

- `capture_estimate.json` (schema kind: `capture_estimate`)
- Downstream consumer: Pack K `hazard_map` stage

## Execution Model

1. Validate telemetry and occupancy artifacts and enforce `run_id` / commit alignment.
2. Cross-check defect sets and per-row observation counts across Pack H and Pack I.
3. Build deterministic incidence counts and frequency-of-frequencies histogram.
4. Compute bias-corrected Chao1 hidden estimate.
5. Compute Chao2 incidence-based hidden estimate.
6. Compute ICE hidden estimate with explicit low-information fallback.
7. Select conservative hidden burden with fixed `max_hidden` policy across all available estimators.
8. Emit schema-valid counts, estimator details, summary flags, and provenance.

## Estimators

### Chao1 (bias-corrected)

Frequency-based estimator using singleton (f1) and doubleton (f2) counts. Uses the bias-corrected formula: `hidden = f1 * (f1 - 1) / (2 * (f2 + 1))`. Guard applied when f2 = 0.

### Chao2 (incidence-based)

Incidence-based estimator appropriate for sample/reviewer data. Uses Q1 (defects seen by exactly 1 reviewer), Q2 (defects seen by exactly 2 reviewers), and m (number of usable reviewers) from the telemetry matrix.

Formula when Q2 > 0: `hidden = ((m - 1) / m) * (Q1^2 / (2 * Q2))`

When Q2 = 0 and Q1 > 0: conservative fallback `hidden = ((m - 1) / m) * (Q1 * (Q1 - 1) / 2)`, with `q2_zero_fallback` guard flag set.

When Q1 = 0: `hidden = 0.0` (no singleton pressure signal), with `q1_zero_no_signal` guard flag set.

When m < 2: Chao2 is marked unavailable (not enough sampling units for the estimator to be meaningful). The stage proceeds with Chao1 and ICE only.

Chao2 was added because Pack J already works with incidence/sample-style data (reviewer observations per defect), which is exactly what Chao2 expects. Q1 maps to f1, Q2 maps to f2, and m is derived from the telemetry summary's `k_usable` count.

### ICE (Incidence-based Coverage Estimator)

Rare/frequent split estimator using the incidence histogram. Computes sample coverage and coefficient of variation (gamma squared). Falls back to Chao1 hidden estimate when coverage collapses or rare-incidence support is too weak.

### Why Chao1 is retained

Chao1 is retained alongside Chao2 as a conservative comparator. Chao1 uses a simpler formula that is always computable (no minimum reviewer threshold), making it a reliable baseline even when Chao2 is unavailable.

## Selection Policy

One fixed deterministic rule governs which hidden estimate is used downstream:

- **Policy:** `max_hidden` (always)
- **Rule:** `selected_hidden = max(chao1_hidden, chao2_hidden, ice_hidden)` among available estimators only
- **Selected source:** recorded as `selected_source` in `estimators`, and as `selected_method` in `summary`
- **Unavailable estimators:** recorded explicitly in `unavailable_estimators` (never silently dropped)

No discretionary selection. No case-by-case heuristics.

## Estimator Execution Evidence

The `capture_estimate.json` artifact records full execution evidence for all three estimators:

- `estimators.chao1`: observed, hidden, total, formula_variant, guard_applied, inputs (f1, f2)
- `estimators.chao2`: enabled, available, hidden_estimate, total_estimate, guard_flags, inputs_used (q1, q2, m), reason_unavailable
- `estimators.ice`: observed, hidden, total, rare_threshold, sample_coverage, formula_variant, guard_applied, inputs
- `estimators.selection_policy`: the fixed selection rule ("max_hidden")
- `estimators.selected_source`: which estimator produced the governing hidden estimate
- `estimators.unavailable_estimators`: list of estimators that could not be computed

## Core Semantics

- only positive usable observations contribute to incidence counts.
- `null` is not converted into sampling effort.
- singleton-heavy rows increase hidden-defect concern.
- sparse-data guardrails stay visible in the artifact.

## Model Rules (v1)

- inclusion policy: `include_all`
- Chao1 variant: `bias_corrected`
- Chao2 sampling units: `k_usable` from telemetry summary
- ICE rare threshold: config-locked `ice_rare_threshold` (default `10`)
- selection policy: `max_hidden`

When ICE coverage collapses or rare-incidence support is too weak, Pack J uses an explicit fallback path instead of dividing by zero or silently returning zero hidden defects. When Chao2 cannot run (m < 2), it is marked unavailable and selection proceeds with the remaining estimators.

## Fail-Closed Behavior

- telemetry/occupancy defect-set mismatch -> stage failure.
- cross-artifact count mismatch (`observed_by`, `missed_by`, `null_by`, `k_eff_defect`) -> stage failure.
- included row with zero positive incidence -> stage failure.
- unsupported inclusion or selection policy -> stage failure.
- invalid histogram keys/counts or negative estimator outputs -> stage failure.
- invalid telemetry `k_usable` -> stage failure.
- schema validation failure -> run failure.

## Determinism Notes

- defect rows are counted in canonical `defect_key` order.
- histogram keys are emitted as sorted decimal strings.
- estimator rounding is fixed by `capture_round_digits`.
- selected hidden estimate is explicit and conservative.
- all three estimator outputs are deterministic given identical inputs.
