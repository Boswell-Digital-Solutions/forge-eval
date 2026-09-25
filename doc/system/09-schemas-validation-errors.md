# §9 - Schemas, Validation, and Error Model

## Schema Set (Pack D + Pack G/H/I/J/K/L/M Extensions)

Implemented schema files:

- `risk_heatmap.schema.json`
- `context_slices.schema.json`
- `review_findings.schema.json`
- `telemetry_matrix.schema.json`
- `occupancy_snapshot.schema.json`
- `capture_estimate.schema.json`
- `calibration_report.schema.json`
- `hazard_map.schema.json`
- `merge_decision.schema.json`
- `evidence_bundle.schema.json`

All schemas are Draft 2020-12 and strict at root (`additionalProperties: false`).

`review_findings.schema.json` enforces Pack G layout:

- `artifact_version`, `kind`, `run`
- reviewer execution summaries with status enum: `ok | failed | skipped`
- normalized findings with strict severity/category enums
- required deterministic `defect_key` format (`dfk_<sha256hex>`)
- summary counters and provenance inputs/failure policy fields

`telemetry_matrix.schema.json` enforces Pack H layout:

- `artifact_version`, `kind`, `run`, `reviewers`, `defects`, `matrix`, `summary`, `provenance`
- tri-state matrix cells limited to `1 | 0 | null`
- reviewer status/health fields (`eligible`, `usable`, `failed`, `skipped`)
- deterministic `k_eff` and per-defect `k_eff_defect`
- locked provenance modes (`reviewer_kind_scope_v1`, `global_min_per_defect`)

`occupancy_snapshot.schema.json` enforces Pack I layout:

- `artifact_version`, `kind`, `run`, `rows`, `summary`, `model`, `provenance`
- bounded posterior values (`psi_post` in `[0,1]`)
- deterministic row counts (`observed_by`, `missed_by`, `null_by`, `k_eff_defect`)
- explicit model metadata (`prior_policy`, `null_policy`, `suppression_policy`, locked parameters)
- provenance locked to telemetry input and model version (`occupancy_rev1`)

`capture_estimate.schema.json` enforces Pack J layout:

- `artifact_version`, `kind`, `run`, `inputs`, `counts`, `estimators`, `summary`, `provenance`
- deterministic incidence counts (`f1`, `f2`, histogram, ICE rare/frequent split)
- structured Chao1 and ICE outputs with explicit guard flags
- conservative selected hidden estimate (`max_hidden`)
- provenance locked to telemetry + occupancy inputs

`hazard_map.schema.json` enforces Pack K layout:

- `artifact_version`, `kind`, `run`, `inputs`, `summary`, `rows`, `model`, `provenance`
- deterministic per-defect hazard rows joined to structural `risk_score`
- bounded row and summary outputs (`hazard_contribution`, `hazard_score` in `[0,1]`)
- locked hazard tiers (`low`, `guarded`, `elevated`, `high`, `critical`)
- explicit uncertainty and blocking reason flags
- provenance locked to risk + telemetry + occupancy + capture inputs and `hazard_rev1`

`merge_decision.schema.json` enforces Pack L layout:

- `artifact_version`, `kind`, `run`, `inputs`, `decision`, `summary`, `reason_codes`, `model`, `provenance`
- advisory decision result locked to `allow | caution | block`
- deterministic reason-code vocabulary for blocking and cautionary Pack K-derived conditions
- provenance locked to `hazard_map.json` and `merge_rev1`

`evidence_bundle.schema.json` enforces Pack M layout:

- `artifact_version`, `kind`, `run`, `inputs`, `artifacts`, `decision`, `manifest`, `summary`, `model`, `provenance`
- deterministic artifact inventory with `canonical_sha256`, `artifact_id`, and stable relative paths
- bounded manifest from the Rust hashchain primitive (`forge-evidence-chain-v1`)
- provenance locked to the fixed A-L artifact chain and `evidence_bundle_rev1`

## Validation Behavior

- Schema loader fails on unknown artifact kind or missing schema files.
- Artifact validator enumerates all violations and reports machine-readable paths.
- `validate` command enforces required artifact presence based on enabled stage list in `config.resolved.json`.

## Structured Error Classes

- `ForgeEvalError` (base)
- `ConfigError`
- `ValidationError`
- `StageError`
- `EvidenceCliError`
- `GitError`

Each error serializes to:

- `code`
- `message`
- `stage`
- `details`

CLI exits non-zero on any structured error.
