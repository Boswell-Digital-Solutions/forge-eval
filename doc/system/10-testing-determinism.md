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

## Which CI runs for which change

A change to documentation runs the Documentation CI and no code CI.
A change to any other file runs the code CI.
A change to both runs both.
No workflow runs on a schedule.

The code workflow `.github/workflows/ci.yml` (jobs `python` and `rust`) uses a workflow-level `paths` filter on `push` and on `pull_request`:

```yaml
paths:
  - '**'
  - '!docs/**'
  - '!doc/**'
  - '!**/*.md'
  - 'README.md'
```

The last matching pattern wins, so the re-include comes last.
A change to `.github/workflows/**` is code, so it runs the code CI.

The re-include is documentation that code reads:

- `README.md`: `pyproject.toml` sets `readme = "README.md"`. The `python` job runs `pip install -e ".[dev]"`, and the build reads the file.

No test reads `doc/`, `docs/` or another Markdown file of this repository.
Tests that write Markdown files do so in temporary repositories.
If a test or script starts to read another documentation path, add that path as a re-include.

The Documentation CI is `.github/workflows/documentation.yml`.
It runs on a change under `docs/`, under `doc/`, to any `*.md` file, or to its own workflow file.
It runs `bash doc/system/BUILD.sh` and then `git diff --exit-code -- doc`.
`doc/FEVSYSTEM.md` is committed, so the diff step fails when the assembled reference does not match its parts.

This repository has no secret scan workflow.
If a secret scan is added, it must run on every change and must not use a path filter.

Warning: do not add a required status check on a path-filtered workflow.
The check stays pending forever when the filter skips the workflow, and the merge stays blocked.
