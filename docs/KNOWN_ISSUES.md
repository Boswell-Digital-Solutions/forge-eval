# forge-eval Known Issues

Dated findings with evidence, root cause, and an explicit open or closed scope. Recording a finding is not authorization to repair it.

## 2026-11-09 — doc/system §01 stops at Pack M, and §11 names a checkout path that does not exist

**Status: OPEN.** Recorded 2026-11-09. Recorded by forge BDS-FGITR-v0.1 (governance truth audit). Verified by source reading on `main` `be8431f`.

**What is wrong.**

1. `doc/system/01-overview-philosophy.md:7` says forge-eval implements Packs A-M. The list at lines 9-21 ends at Pack M.
2. `doc/system/01-overview-philosophy.md:27` gives the implemented path. The path ends at `evidence_bundle`.
3. The code has one more stage. `src/forge_eval/config.py:12-23` `KNOWN_STAGES` ends at `localization_pack` (line 22). `src/forge_eval/stages/localization_pack.py` implements it. `doc/system/19-localization-pack-stage.md` documents it as Pack N.
4. `doc/system/11-handover-runbook.md:6` says `cd /home/charlie/Forge/ecosystem/forge-eval/repo`. That directory does not exist on the operator machine. `doc/system/01-overview-philosophy.md:3` says the repository is in `ecosystem/local-systems`. The forge ecosystem map (`docs/ecosystem/ecosystem_map.json:509`) gives `canonical_path` `ecosystem/local-systems/forge-eval/repo`.

**Impact.** Low. A reader of §01 does not learn that Pack N exists. A reader who follows §11 starts in a directory that does not exist.

**Root cause.** Not established.

**Fix.** None applied.

**Closure.** Open. Closed when §01 names Pack N and the full stage path, §11 names the canonical checkout path, and `bash doc/system/BUILD.sh` passes.

## 2026-11-09 — doc/system chapters 30 and 40 are unreplaced bootstrap scaffolds

**Status: OPEN.** Recorded 2026-11-09. Recorded by forge BDS-FGITR-v0.1 (governance truth audit). Verified by source reading on `main` `be8431f`.

**What is wrong.**

1. `doc/system/30-governance.md:3` says "Document version: 1.0 (bootstrap scaffold)". Lines 7-10 say the chapter is a registry-generated bootstrap scaffold and ask for real authored content. The chapter has no other content.
2. `doc/system/40-change-control.md:3` and lines 7-10 hold the same scaffold text. The chapter has no other content.
3. `doc/system/_index.md` assembles both chapters into `doc/FEVSYSTEM.md` as §19 and §20.

**Impact.** Low. The canonical reference states no ownership, review, or change-control rules for forge-eval.

**Root cause.** Not established.

**Fix.** None applied.

**Closure.** Open. Closed when both chapters hold authored content and `bash doc/system/BUILD.sh` passes.

## 2026-10-02 — The Python CI job is red on main: ruff lint and ruff format fail

**Status: OPEN — not repaired by the CI-scope change.**

**Evidence.** The workflow `CI`, job `Python (lint + tests)`, fails at step `Ruff lint` on `main` (push run 36096866701, 2026-09-25) and on the pull request that added the Documentation CI (run 37050030544, 2026-10-02). On a clean `origin/main` checkout, `ruff check .` reports 4 errors, all fixable with `--fix`: `src/forge_eval/centipede_runner.py:1`, `tests/lineage/test_forge_eval_emitter.py:9`, `tests/lineage/test_stage_runner_lineage_optin.py:9` and `:11` (F401 unused import and import order). `ruff format --check .` reports 8 files that would be reformatted.

**Impact.** The step order is lint, format, pytest. The lint step fails first, so CI does not show whether the format step or the pytest step would pass. The `Rust (fmt + clippy + test)` job passes.

**Root cause.** Not established. The files were changed without a ruff run, or the ruff version moved. The workflow installs `ruff` through `.[dev]` without a pin, which can change the result over time.

**Not verified.** A local pytest run was not a valid proof: tests under `tests/lineage/` find a sibling `forge_lineage` checkout by walking up from the test file, and a local layout differs from CI.

**Closure.** Open. Closed when `ruff check .` and `ruff format --check .` pass on `main` and the `Python (lint + tests)` job is green.
