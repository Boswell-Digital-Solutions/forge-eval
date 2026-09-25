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
