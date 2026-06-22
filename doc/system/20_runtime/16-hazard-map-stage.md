# §16 - Pack K: Hazard Map Stage

## Stage Contract

Input:

- `risk_heatmap` artifact (required)
- `telemetry_matrix` artifact (required)
- `occupancy_snapshot` artifact (required)
- `capture_estimate` artifact (required)
- normalized hazard config block (required)

Output:

- `hazard_map.json` (schema kind: `hazard_map`)
- Downstream consumer: Pack L `merge_decision` stage

## Execution Model

1. Validate all upstream artifacts and enforce deterministic run alignment.
2. Join telemetry defects to occupancy rows by canonical `defect_key`.
3. Join each defect row to structural `risk_score` by `file_path`.
4. Compute deterministic per-defect hazard contribution from severity, residual occupancy, structural risk, and reviewer support.
5. Aggregate row contributions with a bounded union score.
6. Apply conservative hidden-defect uplift from Pack J and uncertainty uplift from sparse/null-heavy evidence.
7. Clamp final `hazard_score` to `[0,1]` and map to a deterministic tier.
8. Emit schema-valid summary, rows, model metadata, and provenance.

## Core Signals

Pack K combines four conservative signals:

- structural risk pressure from `risk_heatmap`
- observed defect burden from `telemetry_matrix`
- residual occupancy concern from `occupancy_snapshot`
- hidden-defect pressure from `capture_estimate`

## Model Rules (Rev 1)

- model version: `hazard_rev1`
- row policy: `severity_plus_uplifts_v1`
- summary policy: `bounded_union_hidden_uncertainty_v1`
- tier set: `low`, `guarded`, `elevated`, `high`, `critical`

Row contributions are deterministic and conservative:

- severity sets the base weight
- higher `psi_post` increases concern
- higher structural `risk_score` amplifies the same defect evidence
- cross-reviewer support can only increase concern; it never reduces it

Summary hazard remains bounded and interpretable:

- row contributions are merged with a bounded union score
- `selected_hidden` from Pack J applies hidden-defect uplift
- sparse/null-heavy evidence applies uncertainty uplift
- final `hazard_score` is clamped to `[0,1]`

## Fail-Closed Behavior

- missing upstream artifact -> stage failure
- run or commit mismatch across Pack H/I/J/K inputs -> stage failure
- defect-set mismatch between telemetry and occupancy -> stage failure
- missing structural risk mapping for a defect file -> stage failure
- unsupported `hazard_model_version` -> stage failure
- out-of-range hazard config params -> stage failure
- duplicate risk target or duplicate defect rows -> stage failure
- schema validation failure -> run failure

## Determinism Notes

- defect rows iterate in canonical `defect_key` order
- file-risk joins are exact on normalized `file_path`
- row flags and summary flags are emitted in deterministic order
- rounding is fixed by `hazard_round_digits`
- repeated identical inputs must produce byte-identical `hazard_map.json`
