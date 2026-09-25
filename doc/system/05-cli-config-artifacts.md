# §5 - CLI, Config, and Artifacts

## CLI Commands

```bash
forge-eval run --repo /path/to/repo --base <base> --head <head> --config config.yaml --out artifacts/
forge-eval validate --artifacts artifacts/
```

## Config Loading and Normalization

- Accepted formats: `.json`, `.yaml`, `.yml`
- Unknown keys are rejected.
- Stage list is validated against known stage set.
- Risk weights are normalized to a deterministic unit sum.
- File-extension and excluded-path lists are normalized and sorted.

Default stage order and enabled set:

1. `risk_heatmap`
2. `context_slices`
3. `review_findings`
4. `telemetry_matrix`
5. `occupancy_snapshot`
6. `capture_estimate`
7. `hazard_map`
8. `merge_decision`
9. `evidence_bundle`

Stage dependency constraints:

- `context_slices` requires `risk_heatmap`
- `review_findings` requires `context_slices`
- `telemetry_matrix` requires `review_findings`
- `occupancy_snapshot` requires `telemetry_matrix`
- `capture_estimate` requires `occupancy_snapshot`
- `hazard_map` requires `capture_estimate`
- `merge_decision` requires `hazard_map`
- `evidence_bundle` requires `merge_decision`

## Pack F/G/H/I/J/K/L Config Keys (Current)

- `context_radius_lines` (int, >=0)
- `merge_gap_lines` (int, >=0)
- `max_slices_per_target` (int, >=1)
- `max_lines_per_slice` (int, >=1)
- `max_total_lines` (int, >=1)
- `fail_on_slice_truncation` (bool)
- `include_file_extensions` (normalized unique list)
- `exclude_paths` (normalized unique list, trailing `/`)
- `binary_file_policy` (`fail` or `ignore`)
- `reviewer_failure_policy` (`fail_stage` or `record_and_continue`)
- `reviewers` (deterministically sorted reviewer config objects)
- `telemetry_applicability_mode` (`reviewer_kind_scope_v1`)
- `telemetry_k_eff_mode` (`global_min_per_defect`)
- `occupancy_model_version` (`occupancy_rev1`)
- `occupancy_prior_base` (float in `[0,1]`)
- `occupancy_support_uplift` (float in `[0,1]`)
- `occupancy_detection_assumption` (float in `[0,1]`)
- `occupancy_miss_penalty_strength` (float in `[0,1]`)
- `occupancy_null_uncertainty_boost` (float in `[0,1]`)
- `occupancy_round_digits` (int in `[0,12]`)
- `capture_inclusion_policy` (`include_all`)
- `capture_selection_policy` (`max_hidden`)
- `ice_rare_threshold` (int, >=1)
- `capture_round_digits` (int in `[0,12]`)
- `hazard_model_version` (`hazard_rev1`)
- `hazard_round_digits` (int in `[0,12]`)
- `hazard_hidden_uplift_strength` (float in `[0,1]`)
- `hazard_structural_risk_strength` (float in `[0,1]`)
- `hazard_occupancy_strength` (float in `[0,1]`)
- `hazard_support_uplift_strength` (float in `[0,1]`)
- `hazard_uncertainty_boost` (float in `[0,1]`)
- `hazard_blocking_threshold` (float in `[0,1]`)
- `merge_decision_model_version` (`merge_rev1`)
- `merge_decision_caution_threshold` (float in `[0,1]`)
- `merge_decision_block_threshold` (float in `[0,1]`)
- `merge_decision_block_on_hazard_blocking_signals` (bool)
- `evidence_bundle_model_version` (`evidence_bundle_rev1`)

## Artifacts Written by `run`

- `config.resolved.json`
- `risk_heatmap.json` (if enabled)
- `context_slices.json` (if enabled)
- `review_findings.json` (if enabled)
- `telemetry_matrix.json` (if enabled)
- `occupancy_snapshot.json` (if enabled)
- `capture_estimate.json` (if enabled)
- `hazard_map.json` (if enabled)
- `merge_decision.json` (if enabled)
- `evidence_bundle.json` (if enabled)

All Python-written artifacts use deterministic JSON encoding:

- sorted keys
- compact separators
- single trailing newline
