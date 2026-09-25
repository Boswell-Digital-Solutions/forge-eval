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
