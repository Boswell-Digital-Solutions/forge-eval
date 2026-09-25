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
