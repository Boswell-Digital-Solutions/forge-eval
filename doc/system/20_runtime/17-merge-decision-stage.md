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
