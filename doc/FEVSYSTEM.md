# forge-eval - Compiled System Reference

**Designation:** FEV
**Document role:** Canonical compiled technical reference for the Forge Eval deterministic evaluation subsystem
**Source:** `doc/system/`
**Build command:** `bash doc/system/BUILD.sh`
**Document version:** 2.0 (2026-06-22) - canonical compliance migration
**Protocol:** BDS Documentation Protocol v2.0; BDS Repo Documentation System Canonical Compliance Standard

> **Generated artifact warning:** `doc/FEVSYSTEM.md` is assembled output. Edit
> the source modules under `doc/system/` and rebuild. Hand edits to the
> compiled artifact are overwritten by the next build.

Assembly contract:

- Command: `bash doc/system/BUILD.sh`
- Validation: `bash doc/system/validate_snapshots.sh` runs during assembly
- Primary output: `doc/FEVSYSTEM.md`

This `doc/system/` tree is the canonical source of truth for forge-eval. It
uses explicit **truth classes**: canonical facts define the repo role, authority
boundaries, runtime behavior, service contracts, and verification doctrine;
snapshot facts are dated, audit-derived counts and current implementation
inventory that may drift between audits.

| Part | File | Contents |
| --- | --- | --- |
| §1 | `00_overview/01-overview-philosophy.md` | §1 - Overview and Philosophy |
| §2 | `00_overview/02-architecture.md` | §2 - Architecture |
| §3 | `00_overview/04-project-structure.md` | §4 - Project Structure |
| §4 | `10_service-contract/05-cli-config-artifacts.md` | §5 - CLI, Config, and Artifacts |
| §5 | `20_runtime/06-evidence-subsystem.md` | §6 - Evidence Subsystem |
| §6 | `20_runtime/07-risk-heatmap-stage.md` | §7 - Pack E: Risk Heatmap Stage |
| §7 | `20_runtime/08-context-slices-stage.md` | §8 - Pack F: Context Slices Stage |
| §8 | `20_runtime/09-schemas-validation-errors.md` | §9 - Schemas, Validation, and Error Model |
| §9 | `20_runtime/12-reviewer-execution-stage.md` | §12 - Pack G: Reviewer Execution Stage |
| §10 | `20_runtime/13-telemetry-matrix-stage.md` | §13 - Pack H: Telemetry Matrix Stage |
| §11 | `20_runtime/14-occupancy-snapshot-stage.md` | §14 - Pack I: Occupancy Snapshot Stage |
| §12 | `20_runtime/15-capture-estimate-stage.md` | §15 - Pack J: Capture Estimate Stage |
| §13 | `20_runtime/16-hazard-map-stage.md` | §16 - Pack K: Hazard Map Stage |
| §14 | `20_runtime/17-merge-decision-stage.md` | §17 - Pack L: Merge Decision Stage |
| §15 | `20_runtime/18-evidence-bundle-stage.md` | §18 - Pack M: Evidence Bundle Stage |
| §16 | `20_runtime/19-localization-pack-stage.md` | 19 - Pack N: Localization Pack Stage |
| §17 | `30_dependencies/03-tech-stack.md` | §3 - Tech Stack |
| §18 | `40_governance/10-scope.md` | Scope |
| §19 | `40_governance/30-governance.md` | Governance |
| §20 | `40_governance/40-change-control.md` | Change Control |
| §21 | `50_operations/10-testing-determinism.md` | §10 - Testing and Determinism |
| §22 | `50_operations/11-handover-runbook.md` | §11 - Handover and Runbook |
| §23 | `99_appendices/20-structure.md` | Structure |
| §24 | `99_appendices/90-appendices.md` | Appendices |
| §25 | `99_appendices/91-bootstrap-overview.md` | Overview |
| §26 | `99_appendices/92-bootstrap-architecture.md` | Architecture |

## Quick Assembly

```bash
bash doc/system/BUILD.sh
```

---

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

---

# §2 - Architecture

## High-Level Components

1. CLI layer (`src/forge_eval/cli.py`)
2. Config normalization (`src/forge_eval/config.py`)
3. Stage orchestration (`src/forge_eval/stage_runner.py`)
4. Stage services (`src/forge_eval/stages/*`, `src/forge_eval/services/*`)
5. Schema loading/validation (`src/forge_eval/validation/*`)
6. Reviewer subsystem (`src/forge_eval/reviewers/*` + finding normalization/identity services)
7. Telemetry subsystem (`services/reviewer_health.py`, `services/applicability.py`, `services/telemetry_builder.py`, `services/k_eff.py`)
8. Occupancy subsystem (`services/occupancy_priors.py`, `services/occupancy_model.py`, `services/occupancy_rows.py`, `services/occupancy_summary.py`)
9. Hidden-defect subsystem (`services/capture_counts.py`, `services/chao1.py`, `services/ice.py`, `services/capture_selection.py`, `services/capture_summary.py`)
10. Hazard subsystem (`services/hazard_model.py`, `services/hazard_rows.py`, `services/hazard_summary.py`)
11. Merge-decision subsystem (`services/merge_decision_model.py`, `services/merge_decision_reasons.py`, `services/merge_decision_summary.py`)
12. Evidence-bundle subsystem (`services/evidence_bundle_model.py`, `services/evidence_bundle_manifest.py`, `services/evidence_bundle_summary.py`)
13. Evidence subsystem (Rust binary under `rust/forge-evidence`, Python wrapper in `evidence_cli.py`)
14. Lineage emission — DETECT hop (`src/forge_eval/lineage/*`)

### Lineage emission (DETECT hop)

Both run paths emit `forge_eval_run` + `forge_eval_evidence_bundle` lineage (with a `produced`
edge) to DataForge-Local after writing their bundle, so a real run is traceable downstream
(this is the DETECT hop of the self-healing loop). Posture is **default-off** (a no-op emitter
until the operator sets `FORGE_EVAL_LINEAGE_URL`) and **non-blocking** (any failure is logged and
swallowed; raw execution always completes). The shared posture + generic emit live in
`lineage/run_emit.py`; `run-centipede` (`centipede_runner.py`) and `run` (`stage_runner.py`) both
use it. The bundle node is identity-only; the file targets live in the bundle artifact, located via
the node's `artifact_ref`. The artifact is labelled by **kind**: `run-centipede` produces a
`forge_eval_evidence_bundle` (carries `input_contract.target_refs[]` — a self-healing consumer
resolves concrete fix targets from it), whereas `run` produces a full-evaluation `evidence_bundle`
(no per-file fix targets) — a self-healing consumer fails closed on it by design (a general
evaluation run is not a concrete fix list).

## Runtime Flow (`forge-eval run`)

1. Parse CLI args.
2. Load + normalize config (`JSON` or `YAML`).
3. Resolve base/head commits (`git rev-parse`).
4. Compute deterministic `run_id = sha256(repo_abs_path::base_commit::head_commit)[:16]`.
5. Write `config.resolved.json`.
6. Execute stages in fixed order:
   - `risk_heatmap`
   - `context_slices`
   - `review_findings`
   - `telemetry_matrix`
   - `occupancy_snapshot`
   - `capture_estimate`
   - `hazard_map`
   - `merge_decision`
   - `evidence_bundle`
7. Validate each stage artifact against strict schema.
8. Write schema-valid artifacts to output directory.

## Runtime Flow (`forge-eval validate`)

1. Load all known schemas.
2. Read `config.resolved.json` when present.
3. Derive required artifacts from enabled stages.
4. Fail if required artifacts are missing.
5. Validate any present known artifact kind.

## Python/Rust Boundary

- Python owns orchestration and stage logic.
- Rust owns deterministic evidence primitives.
- Cross-language integration is subprocess-based only.
- No Python fallback implementation for evidence primitives.
- Current A-M runtime boundary: Packs A-L remain Python-owned stage logic, and Pack M invokes `evidence_cli.py` only for canonical JSON, artifact ID, and hashchain assembly inside `evidence_bundle`.

---

# §4 - Project Structure

## Repository Tree (Core)

```text
repo/
  pyproject.toml
  README.md
  src/forge_eval/
    cli.py
    config.py
    stage_runner.py
    errors.py
    evidence_cli.py
    reviewers/
      base.py
      registry.py
      adapters.py
      changed_lines.py
      structural_risk.py
      documentation_consistency.py
    stages/
      risk_heatmap.py
      context_slices.py
      reviewer_execution.py
      telemetry_matrix.py
      occupancy_snapshot.py
      capture_estimate.py
      hazard_map.py
      merge_decision.py
      evidence_bundle.py
    services/
      git_diff.py
      risk_analysis.py
      range_ops.py
      slice_extractor.py
      finding_normalizer.py
      defect_identity.py
      reviewer_health.py
      applicability.py
      telemetry_builder.py
      k_eff.py
      occupancy_priors.py
      occupancy_model.py
      occupancy_rows.py
      occupancy_summary.py
      capture_counts.py
      chao1.py
      ice.py
      capture_selection.py
      capture_summary.py
      hazard_model.py
      hazard_rows.py
      hazard_summary.py
      merge_decision_model.py
      merge_decision_reasons.py
      merge_decision_summary.py
      evidence_bundle_model.py
      evidence_bundle_manifest.py
      evidence_bundle_summary.py
    schemas/
      *.schema.json
    validation/
      schema_loader.py
      validate_artifact.py
    lineage/
      emitter.py        # ForgeEvalLineageEmitter / NullLineageEmitter (run + bundle nodes, produced edge)
      run_emit.py       # shared opt-in/fail-soft run-path emit (centipede + stage_runner)
  tests/
    test_cli.py
    test_config.py
    test_evidence_cli.py
    test_risk_heatmap.py
    test_range_ops.py
    test_slice_extractor.py
    test_context_slices_stage.py
    test_reviewer_execution_stage.py
    test_telemetry_matrix_stage.py
    test_occupancy_snapshot_stage.py
    test_capture_estimate_stage.py
    test_hazard_map_stage.py
    test_merge_decision_stage.py
    test_evidence_bundle_stage.py
    test_finding_normalizer.py
    test_defect_identity.py
    test_schemas.py
    integration/
      test_risk_heatmap_repo.py
      test_context_slices_repo.py
      test_review_findings_repo.py
      golden/
        context_single_hunk.json
        context_distant_hunks.json
  rust/forge-evidence/
    src/
      main.rs
      canonical.rs
      hash.rs
      artifact_id.rs
      chain.rs
    tests/
      integration_cli.rs
```

## Responsibility Split

- `stages/`: stage entrypoints that produce artifact objects.
- `services/`: deterministic helpers (git access, scoring, range math, extraction, finding normalization, defect identity, reviewer health/applicability, telemetry matrix building, occupancy prior/posterior computation, hidden-defect counting/estimation, hazard scoring, advisory merge-decision reasoning, evidence-bundle manifest assembly).
- `reviewers/`: deterministic reviewer adapters and execution wrappers.
- `validation/`: schema lookup + JSON-schema enforcement.
- `schemas/`: locked contracts for implemented and future artifacts.
- `rust/forge-evidence/`: canonical evidence primitives.

---

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

---

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

---

# §7 - Pack E: Risk Heatmap Stage

## Stage Contract

Input:

- repo path
- base ref
- head ref
- normalized config

Output:

- `risk_heatmap.json` (schema kind: `risk_heatmap`)

## Feature Construction

Per changed, in-scope file:

1. Churn from `git diff --numstat` (`added + deleted`).
2. Change magnitude via `log1p(churn)`.
3. Lightweight connectivity centrality from import/use/require relations across tracked files.
4. Optional path weighting using longest matching configured prefix.

## Scoring

- Each raw feature vector is normalized to `[0,1]` deterministically.
- Raw risk:

`w_churn * churn_norm + w_centrality * centrality + w_change_magnitude * magnitude_norm`

- Path weight multiplier applied after weighted sum.
- Final `risk_score` is normalized to `[0,1]` across targets.
- Targets are sorted by `file_path`.

## Provenance

- `algorithm: structural_risk_v1`
- `deterministic: true`

---

# §8 - Pack F: Context Slices Stage

## Stage Contract

Input:

- repo path
- base ref
- head ref
- normalized config
- optional target subset (wired from risk stage targets)

Output:

- `context_slices.json` (schema kind: `context_slices`)

## Deterministic Extraction Procedure

For each changed target file (non-deleted, extension-allowed, non-excluded):

1. Parse unified diff hunks (`--unified=0`) into changed ranges in head-line coordinates.
2. Expand each range by `context_radius_lines`.
3. Clamp expanded ranges to `[1, file_line_count]`.
4. Merge overlap/adjacency using `merge_gap_lines` (left-to-right after sort).
5. Split oversized merged ranges by `max_lines_per_slice`.
6. Build stable slice objects (`slice_id = file_path:start:end`) from head file content.
7. Sort slices by `(file_path, start_line, end_line)`.
8. Enforce `max_total_lines` globally.

## Cap and Failure Policy

- If binary file is changed and `binary_file_policy=fail`, stage fails closed.
- If `max_slices_per_target` is exceeded and `fail_on_slice_truncation=true`, stage fails closed.
- If `max_total_lines` is exceeded, stage fails closed.
- No silent line dropping.

## v1 Decisions Locked in Code

- Head-version content is the extraction source.
- Deleted files are excluded.
- Rename handling follows post-rename path from git diff parsing.
- Provenance marks source as `git_diff_head_version`.

---

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

---

# §12 - Pack G: Reviewer Execution Stage

## Stage Contract

Input:

- `context_slices` artifact (required)
- `risk_heatmap` artifact (optional but used by `structural_risk` reviewer)
- normalized reviewer config

Output:

- `review_findings.json` (schema kind: `review_findings`)
- Downstream consumer: Pack H `telemetry_matrix` stage

## Execution Model

1. Load configured reviewers and sort by `reviewer_id`.
2. Apply deterministic scope filtering per reviewer.
3. Execute reviewer adapter with isolated input state.
4. Capture reviewer execution truth with explicit status:
   - `ok`
   - `failed`
   - `skipped`
5. Normalize raw findings into a strict contract.
6. Generate stable `defect_key` from canonical identity fields.
7. Sort findings deterministically and emit schema-valid artifact.

## Defect Identity

- `defect_key` is reviewer-independent canonical identity.
- Matching findings from different reviewers keep the same `defect_key`.
- Repeated `defect_key` values from the same reviewer still fail closed upstream.
- Pack H owns cross-reviewer coalescing and compatibility enforcement.

## Built-in Deterministic Reviewers

- `changed_lines`: deterministic rule checks over changed slices.
- `documentation_consistency`: code/docs pairing checks from slice set.
- `structural_risk`: threshold-based findings from Pack E risk scores.

## Fail-Closed Behavior

- Invalid reviewer config/kind -> stage failure.
- Malformed reviewer output/finding fields -> stage failure.
- Reviewer execution error:
  - `reviewer_failure_policy=fail_stage` -> fail stage.
  - `reviewer_failure_policy=record_and_continue` -> record reviewer `failed`.
- Artifact schema validation failure -> run failure.

## Determinism Notes

- Reviewer specs sorted by `reviewer_id`.
- Slices sorted by file/range before dispatch.
- Findings sorted by reviewer/file/slice/category/title/line anchor/`defect_key`.
- `defect_key` is deterministic hash (`dfk_<sha256hex>`) over reviewer-independent normalized identity fields.

---

# §13 - Pack H: Telemetry Matrix Stage

## Stage Contract

Input:

- `review_findings` artifact (required)
- normalized reviewer config (required)

Output:

- `telemetry_matrix.json` (schema kind: `telemetry_matrix`)
- Downstream consumer: Pack I `occupancy_snapshot` stage

## Execution Model

1. Validate `review_findings` shape and enforce `run_id` consistency.
2. Build canonical reviewer-health entries from reviewer execution truth.
3. Build canonical defect catalog from normalized findings, coalescing shared `defect_key` values across reviewers.
4. Compute reviewer-defect applicability deterministically.
5. Build tri-state observation matrix with strict cell values:
   - `1` = reviewer observed defect
   - `0` = reviewer was usable/applicable but did not report defect
   - `null` = reviewer failed, skipped, or was inapplicable
6. Compute per-defect `k_eff_defect` and conservative global `k_eff`.
7. Emit schema-valid `telemetry_matrix.json` with deterministic ordering.

## Reviewer Truth Preservation

- `status=failed` and `status=skipped` are never converted to clean misses.
- `usable` is derived conservatively (`status=ok` and `slices_seen > 0`).
- `eligible` and `usable` are explicit fields in each reviewer entry.

## Defect Coalescing Rule

- one `defect_key` represents one canonical defect identity.
- different reviewers may report that same canonical defect.
- telemetry merges distinct reviewers into `reported_by` and sets `support_count` to unique reviewer count.
- same-reviewer duplicate `defect_key` values still fail closed.
- incompatible repeated `defect_key` metadata (`file_path`, `category`, `severity`) still fails closed.

## Applicability Rule (v1)

`telemetry_applicability_mode=reviewer_kind_scope_v1`:

- extension/path scope checks from reviewer config are applied first
- `documentation_consistency` is limited to Markdown defects
- `structural_risk` excludes Markdown defects
- `changed_lines` applies broadly after scope checks

## `k_eff` Rule (v1)

`telemetry_k_eff_mode=global_min_per_defect`:

- per defect: `k_eff_defect = count(observation != null)`
- global: `k_eff = min(k_eff_defect over all matrix rows)`

This keeps Pack H conservative for downstream occupancy stages.

## Fail-Closed Behavior

- Invalid reviewer status or malformed reviewer entry -> stage failure.
- Duplicate reviewer IDs -> stage failure.
- Same-reviewer duplicate `defect_key` or incompatible repeated `defect_key` metadata -> stage failure.
- Findings that reference unknown reviewers -> stage failure.
- Unsupported applicability or `k_eff` modes -> stage failure.
- Illegal cell values (anything outside `1/0/null`) -> stage failure.
- Schema validation failure -> run failure.

## Determinism Notes

- Reviewer rows sorted by `reviewer_id`.
- Defects and matrix rows sorted by `defect_key`.
- Observation maps emitted in stable reviewer order.
- No clock-based fields in primary payload.

---

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

---

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

---

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

---

# §17 - Pack L: Merge Decision Stage

## Stage Contract

Input:

- `hazard_map` artifact (required)
- normalized merge-decision config block (required)

Output:

- `merge_decision.json` (schema kind: `merge_decision`)
- Downstream consumer: Pack M `evidence_bundle` stage

## Execution Model

1. Validate Pack K hazard artifact shape and enforce deterministic run alignment.
2. Load the locked merge-decision model (`merge_rev1`).
3. Evaluate Pack K summary fields with a deterministic rule table.
4. Emit advisory `allow | caution | block` decision plus stable machine-readable reason codes.
5. Validate the emitted artifact against the strict schema.

## Model Rules (Rev 1)

- model version: `merge_rev1`
- decision policy: `hazard_gate_v1`
- decision family: `allow`, `caution`, `block`

Blocking rules:

- configured hazard blocking signal present
- hazard tier `high` or `critical`
- hazard score at or above configured block threshold

Caution rules:

- hazard tier `guarded` or `elevated`
- hazard score at or above configured caution threshold
- Pack K uncertainty flags present
- elevated hidden pressure

Decision selection is deterministic:

- any blocking rule -> `block`
- else any caution rule -> `caution`
- else -> `allow`

## Reason Codes

Pack L emits stable machine-readable reason codes from a locked vocabulary:

- `HAZARD_BLOCKING_SIGNAL_PRESENT`
- `HAZARD_TIER_CRITICAL`
- `HAZARD_TIER_HIGH`
- `HAZARD_SCORE_AT_OR_ABOVE_BLOCK_THRESHOLD`
- `HAZARD_TIER_ELEVATED`
- `HAZARD_TIER_GUARDED`
- `HAZARD_SCORE_AT_OR_ABOVE_CAUTION_THRESHOLD`
- `HAZARD_UNCERTAINTY_PRESENT`
- `HAZARD_HIDDEN_PRESSURE_ELEVATED`

## Boundary

Pack L is advisory merge posture only.

It does not:

- perform git operations
- execute or recommend a merge command
- assemble evidence bundles
- invoke the Rust evidence CLI itself; bounded runtime evidence integration begins in Pack M
- mutate upstream artifacts

## Fail-Closed Behavior

- missing hazard artifact -> stage failure
- run or ref mismatch between pipeline and hazard artifact -> stage failure
- unsupported `merge_decision_model_version` -> stage failure
- out-of-range or misordered thresholds -> stage failure
- unsupported hazard tier or malformed Pack K summary fields -> stage failure
- schema validation failure -> run failure

## Determinism Notes

- decision rules are evaluated in fixed order
- reason codes are emitted in stable canonical order
- no clock fields appear in the artifact
- repeated identical inputs must produce byte-identical `merge_decision.json`

---

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

---

# 19 - Pack N: Localization Pack Stage

## Stage Contract

Input:

- `risk_heatmap` artifact (required)
- `context_slices` artifact (required)
- `review_findings` artifact (required)
- `telemetry_matrix` artifact (required)
- `hazard_map` artifact (required)
- `occupancy_snapshot` artifact (optional)
- normalized localization config block (required)

Output:

- `localization_pack.json` (schema kind: `localization_pack`)
- Downstream consumer: NeuroForge localized review/repair mode

## Execution Model

1. Validate all required upstream artifacts and enforce kind alignment.
2. Score file candidates using configurable ranking weights (support_count, defect_density, hazard_contribution, churn).
3. Score block candidates at slice granularity using the same weight vector.
4. Compute per-candidate confidence as a blend of support normalization and evidence density.
5. Enrich block candidates with deterministic construct extraction (language detection, framework hints, likely constructs, root cause hypothesis).
6. Compile review scope by grouping blocks by file, merging overlapping ranges, and clamping per-file and total line counts.
7. Build patch scope from upstream patch targets (passthrough, sorted deterministically).
8. Assemble summary with `summary_confidence = min(block confidences)`.
9. Emit schema-valid localization_pack artifact with model and provenance metadata.

## Core Signals

Pack N compiles evidence from four upstream artifacts:

- structural risk from `risk_heatmap`
- code context from `context_slices`
- defect evidence from `review_findings` and `telemetry_matrix`
- hazard assessment from `hazard_map`

## Model Rules (Rev 1)

- model version: `localization_pack_rev1`
- ranking policy: `heuristic_v1`
- scope merge policy: `deterministic_merge_v1`
- construct extraction policy: `ast_heuristic_v1`

### Ranking Weights (normalized to unit sum)

| Weight | Default |
|--------|---------|
| support_count | 0.35 |
| defect_density | 0.25 |
| hazard_contribution | 0.25 |
| churn | 0.15 |

### Config Keys

| Key | Default | Description |
|-----|---------|-------------|
| `localization_model_version` | `localization_pack_rev1` | Model version tag |
| `localization_max_file_candidates` | 10 | Max file candidates emitted |
| `localization_max_block_candidates` | 20 | Max block candidates emitted |
| `localization_max_review_scope_lines` | 500 | Total review scope line cap |
| `localization_max_scope_lines_per_file` | 150 | Per-file review scope line cap |
| `localization_round_digits` | 6 | Decimal rounding precision |
| `localization_ranking_weights` | see above | Weight vector (normalized) |

## Construct Extraction

Per-language keyword/pattern heuristics (no LLM inference in v1):

- **Python**: `if_guard`, `async_call`, `try_except`, `return_boundary`, `serialization_boundary`, `dependency_call`
- **Rust**: `if_guard`, `match_arm`, `borrow_boundary`, `async_task_boundary`, `trait_dispatch`, `error_propagation`
- **TypeScript**: `if_guard`, `async_call`, `null_check`, `type_assertion`, `promise_chain`
- **Svelte**: `if_guard`, `reactive_state`, `derived_state`, `effect_boundary`, `prop_mutation`, `async_ui_transition`

### Root Cause Hypothesis (locked v1 vocabulary)

`boundary_violation` | `null_path` | `async_race` | `missing_guard` | `serialization_boundary` | `ownership_violation` | `reactive_state_mutation` | `other` | `null`

## Review Scope Compilation

1. Group block candidates by file path.
2. Merge overlapping line ranges (union).
3. Clamp per-file to `max_scope_lines_per_file`.
4. Clamp total to `max_review_scope_lines`.
5. Fail closed if no valid scope remains.

## Artifact Schema

Both `localization_pack.schema.json` and `localization_summary.schema.json` enforce `additionalProperties: false` at all levels.

Key schema constraints:
- `detected_language`: `["python", "rust", "typescript", "svelte", "other", null]`
- `hazard_tier`: `["low", "guarded", "elevated", "high", "critical"]` (Pack K vocabulary)
- `root_cause_hypothesis`: bounded enum (9 values including `other` and `null`)
- `provenance.deterministic`: `const: true`

## NeuroForge Integration

### LOC-GATE Error Codes

| Code | Meaning | Recoverable |
|------|---------|-------------|
| `LOC-GATE-MISSING` | Repair requested, no localization artifact | No |
| `LOC-GATE-INVALID-REF` | Ref unresolvable under trusted roots | No |
| `LOC-GATE-SCHEMA-INVALID` | Pack fails schema validation | No |
| `LOC-GATE-RUN-MISMATCH` | run_id mismatch | No |
| `LOC-GATE-SCOPE-EMPTY` | review_scope is empty | No |
| `LOC-GATE-NO-SCOPE` | Patch target outside scope | No |

All LOC-GATE codes: `category=LOCALIZATION_CONTRACT`.

### Gate Execution Order (repair tasks)

1. LOC-GATE checks (1-6 above)
2. MAPO-TGT-GATE checks (unchanged)
3. MRPA apply

### Prompt Compiler

When localization input is valid:
- Prepends localized review contract text
- Renders only review_scope blocks as context
- Includes likely_constructs and root_cause_hypothesis per block
- Suppresses out-of-scope file/repo context
- `allow_analysis_only=true` suppresses patch_scope rendering

## Telemetry

Pack N stage logs:
- `localization_model_version`
- `file_candidate_count`, `block_candidate_count`
- `review_scope_line_count`, `patch_scope_present`
- `summary_confidence`, `hazard_tier`

NeuroForge LOC-GATE logs:
- `localization_artifact_ref`
- `localized_review_mode_enabled`
- `repair_blocked_reason` (on gate failure)
- `repair_downgraded` (on analysis-only)
- `approved_region_count`

## Fail-Closed Rules

- Required upstream artifact missing: stage failure
- Ranking cannot be performed deterministically: stage failure
- Review scope cannot be compiled: stage failure
- Line bounds invalid: stage failure
- Schema validation failure: stage failure
- Empty review scope: `LOC-GATE-SCOPE-EMPTY`

## Determinism Guarantee

Identical inputs produce byte-identical `localization_pack.json` artifacts. Enforced by:
- `sort_keys=True`, compact separators in JSON serialization
- Deterministic sort order (score descending, then alphabetical tie-breaking)
- No LLM inference in Pack N v1
- No clock/timestamp fields in canonical artifact

---

# §3 - Tech Stack

## Python

- Python `>=3.12`
- `jsonschema` (Draft 2020-12 validation)
- `PyYAML` (config loading)
- stdlib for subprocess, JSON, path, hashing, regex, argparse

## Rust (`forge-evidence`)

- stable Rust toolchain
- `serde`, `serde_json`
- `sha2`, `hex`
- `clap`
- `anyhow`

## Git Interface

Git is invoked through subprocess with explicit commands:

- `git rev-parse`
- `git diff --name-status --find-renames`
- `git diff --numstat`
- `git diff --no-color --unified=0`
- `git show <ref:path>`
- `git ls-files`

## Build and Test Tooling

- `cargo build --offline`, `cargo test --offline`
- `pytest` for Python unit/integration coverage

---

# Scope

**Document version:** 1.0 (bootstrap scaffold)

Scope and authority boundary of this documentation system.

> This chapter is a registry-generated bootstrap scaffold for a
> `documentation` class documentation system. Replace this placeholder with
> real authored content. Registry will not invent repo truth that is not
> already present in the repo.

---

# Governance

**Document version:** 1.0 (bootstrap scaffold)

Ownership, review, and change-authority boundaries.

> This chapter is a registry-generated bootstrap scaffold for a
> `documentation` class documentation system. Replace this placeholder with
> real authored content. Registry will not invent repo truth that is not
> already present in the repo.

---

# Change Control

**Document version:** 1.0 (bootstrap scaffold)

Change-control workflow, proposal lifecycle, and audit.

> This chapter is a registry-generated bootstrap scaffold for a
> `documentation` class documentation system. Replace this placeholder with
> real authored content. Registry will not invent repo truth that is not
> already present in the repo.

---

# §10 - Testing and Determinism

## Python Test Coverage (Packs A-M)

- CLI smoke + failure behavior
- config normalization and rejection cases
- schema loader + schema positive/negative validation
- risk stage logic/unit + integration on temporary git repos
- range operations and hunk parsing
- context-slice extraction unit + integration + cap-overflow behavior
- reviewer execution stage behavior (`ok`, `failed`, `skipped`)
- finding normalization and fail-closed malformed finding handling
- deterministic defect identity (`defect_key`) behavior
- telemetry matrix stage behavior (`1`/`0`/`null`, reviewer health, conservative `k_eff`, cross-reviewer defect coalescing)
- telemetry ghost-coverage guard behavior (`failed`/`skipped` reviewer => `null`)
- fail-closed telemetry checks for same-reviewer duplicates and incompatible canonical metadata collisions
- occupancy snapshot stage behavior (bounded `psi_post`, conservative null handling, stronger-coverage suppression)
- occupancy fail-closed behavior for illegal telemetry cells, count mismatches, and invalid model config
- capture estimate stage behavior (`f1`/`f2`, Chao1, ICE, conservative selection)
- capture fail-closed behavior for inconsistent defect sets, invalid selection policy, and mismatched cross-artifact counts
- hazard map stage behavior (row hazard calculation, tier mapping, conservative summary aggregation)
- hazard fail-closed behavior for missing risk mapping, run/commit mismatch, inconsistent defect sets, and invalid model version
- merge decision stage behavior (allow/caution/block routing, stable reason codes, hazard-only advisory boundary)
- merge decision fail-closed behavior for missing hazard input, run mismatch, invalid hazard tier, and unsupported model version
- evidence bundle stage behavior (artifact inventory ordering, bounded Rust evidence integration, stable manifest/hashchain assembly)
- evidence bundle fail-closed behavior for missing upstream files, run mismatch, unsupported model version, and runtime evidence-cli failure
- golden-file checks for context slices
- repeatability checks using byte-equality of serialized artifacts
- integration proof that pipeline emits deterministic `review_findings.json`, `telemetry_matrix.json`, `occupancy_snapshot.json`, `capture_estimate.json`, `hazard_map.json`, `merge_decision.json`, and `evidence_bundle.json`

## Rust Test Coverage (Pack B)

- canonicalization key-order invariance
- canonicalization idempotence
- SHA-256 known vector
- artifact-id stability
- hashchain stability

## Determinism Controls in Code

- explicit stage order constant
- sorted file/range/artifact iteration
- stable JSON serialization
- no runtime clock fields in primary stage artifacts
- fail-closed cap handling instead of opportunistic truncation
- explicit tri-state telemetry semantics (`1` observed, `0` eligible miss, `null` unavailable/inapplicable)
- reviewer-independent canonical defect identity with deterministic cross-reviewer coalescing
- explicit occupancy semantics (`null` contributes uncertainty, usable misses drive suppression)
- explicit hidden-defect semantics (singletons elevate caution, sparse guards stay visible)

---

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

---

# Structure

**Document version:** 1.0 (bootstrap scaffold)

Module/chapter layout and cross-reference rules.

> This chapter is a registry-generated bootstrap scaffold for a
> `documentation` class documentation system. Replace this placeholder with
> real authored content. Registry will not invent repo truth that is not
> already present in the repo.

---

# Appendices

**Document version:** 1.0 (bootstrap scaffold)

Appendices, glossary, and cross-references.

> This chapter is a registry-generated bootstrap scaffold for a
> `documentation` class documentation system. Replace this placeholder with
> real authored content. Registry will not invent repo truth that is not
> already present in the repo.

---

# Overview

**Document version:** 1.0 (bootstrap scaffold)

System identity, role, and boundary with the rest of the Forge ecosystem.

> This chapter is a registry-generated bootstrap scaffold for a
> `documentation` class documentation system. Replace this placeholder with
> real authored content. Registry will not invent repo truth that is not
> already present in the repo.

---

# Architecture

**Document version:** 1.0 (bootstrap scaffold)

High-level architecture, authority posture, and surface ownership.

> This chapter is a registry-generated bootstrap scaffold for a
> `documentation` class documentation system. Replace this placeholder with
> real authored content. Registry will not invent repo truth that is not
> already present in the repo.
