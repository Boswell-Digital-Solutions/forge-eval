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
