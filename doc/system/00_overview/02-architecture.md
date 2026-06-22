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
