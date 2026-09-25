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
