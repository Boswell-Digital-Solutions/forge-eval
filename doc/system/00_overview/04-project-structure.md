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
