# forge-eval Known Issues

Dated findings with evidence, root cause, and an explicit open or closed scope. Recording a finding is not authorization to repair it.

## 2026-10-02 — The Python CI job is red on main: ruff lint and ruff format fail

**Status: OPEN — not repaired by the CI-scope change.**

**Evidence.** The workflow `CI`, job `Python (lint + tests)`, fails at step `Ruff lint` on `main` (push run 36096866701, 2026-09-25) and on the pull request that added the Documentation CI (run 37050030544, 2026-10-02). On a clean `origin/main` checkout, `ruff check .` reports 4 errors, all fixable with `--fix`: `src/forge_eval/centipede_runner.py:1`, `tests/lineage/test_forge_eval_emitter.py:9`, `tests/lineage/test_stage_runner_lineage_optin.py:9` and `:11` (F401 unused import and import order). `ruff format --check .` reports 8 files that would be reformatted.

**Impact.** The step order is lint, format, pytest. The lint step fails first, so CI does not show whether the format step or the pytest step would pass. The `Rust (fmt + clippy + test)` job passes.

**Root cause.** Not established. The files were changed without a ruff run, or the ruff version moved. The workflow installs `ruff` through `.[dev]` without a pin, which can change the result over time.

**Not verified.** A local pytest run was not a valid proof: tests under `tests/lineage/` find a sibling `forge_lineage` checkout by walking up from the test file, and a local layout differs from CI.

**Closure.** Open. Closed when `ruff check .` and `ruff format --check .` pass on `main` and the `Python (lint + tests)` job is green.
