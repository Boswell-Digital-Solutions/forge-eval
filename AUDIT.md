# Repository Audit — forge-eval

**Date:** 2026-05-31
**Branch:** `claude/repo-audit-eg7AI`
**Scope:** Full repository — Python package `forge_eval`, Rust crate `forge-evidence`, schemas, tests, docs, packaging.
**Method:** Static review of source plus empirical runs of `ruff`, `cargo test`, `cargo clippy`, `cargo fmt`, and `pip install`.

## What this project is

`forge-eval` is a deterministic, schema-validated, fail-closed evaluation pipeline. A
Python package orchestrates a fixed sequence of stages
(`risk_heatmap → context_slices → review_findings → telemetry_matrix →
occupancy_snapshot → capture_estimate → hazard_map → merge_decision →
evidence_bundle`, plus a later `localization_pack`), and a small Rust crate
(`forge-evidence`) provides canonical JSON, SHA-256, artifact IDs, and a hashchain.

- ~97 Python files, ~15.6k LOC; 6 Rust files, ~640 LOC; 13 JSON schemas.
- Core invariants (per README): deterministic byte-stable outputs, sorted-key/compact
  JSON, fixed stage order, fail-closed on error.

## Summary

The codebase is well-structured and the core logic is generally careful about
determinism (sorted keys, explicit ordering, conservative posteriors). The issues
found are mostly **hygiene and tooling-gate** problems rather than logic defects, but
several would block a quality gate, and a couple of unused-variable findings point at
**latent/incomplete logic** worth a closer look.

| # | Severity | Area | Issue |
|---|----------|------|-------|
| 1 | High | Lint gate | `ruff check .` fails with **19 errors** (unused imports/vars) |
| 2 | Med  | Logic smell | Two F841 findings look like **dropped/incomplete logic**, not just style |
| 3 | Med  | Packaging | `requires-python = ">=3.12"`, but no lower-bound CI guarantee; install fails on 3.11 |
| 4 | Med  | Packaging | No declared **test/dev dependencies** (`pytest`, `jsonschema` used by tests) |
| 5 | Med  | Format gate | `ruff format --check` wants to reformat **76 files**; `cargo fmt --check` fails on 5 |
| 6 | Low  | Robustness | Broad `except Exception` in a "fail-closed" pipeline (a few sites) |
| 7 | Low  | Optional dep | `lineage/emitter.py` imports external `forge_lineage_sdk` not in `pyproject` |
| 8 | Med  | CI | **No `.github/` or any CI configuration exists** — nothing enforces the gates above |
| 9 | Med  | Tests | `pytest` **aborts with 19 collection errors** in a clean 3.11 checkout |
| 10 | Info | Tooling | No `[tool.ruff]` / `[tool.mypy]` config; lint/format rules are implicit |
| 11 | Low  | Efficiency | `slice_extractor.py:247` sorts a set only to take its length |

> **Independent deep review of the statistical/determinism core** (Chao1/Chao2/ICE
> estimators, capture/occupancy/hazard math, `git_diff`, `finding_normalizer`,
> `lineage/emitter`, schema validation) found **no correctness or determinism
> defects** — division-by-zero guards, NaN/inf checks, and stable sorting are all
> present and correct. The substantive logic is in good shape; the findings below are
> tooling, packaging, and hygiene.

---

## High

### 1. `ruff check .` fails — 19 errors

`ruff 0.15.8 check .` exits non-zero with 19 findings. If lint is (or becomes) a
gate, this is red. Breakdown:

**Source (`src/`):**
- `centipede_runner.py:19` — `stable_json_dumps` imported but unused (F401)
- `services/construct_extractor.py:74` — `lang` assigned but never used (F841)
- `services/evidence_bundle_manifest.py:6` — `typing.Iterable` unused (F401)
- `services/slice_extractor.py:10` — `git_diff.ChangedFile` unused (F401)
- `services/localization_ranker.py:214,215` — `start`, `end` unused (F841) — see #2
- `stages/localization_pack.py:128,133` — `top_reason_codes`, `top_files` unused (F841) — see #2

**Tests (`tests/`):** 11 further F401/E402 (unused `pytest`, `jsonschema`,
`json`, `sys`, `load_schema`, `StageError`, etc.), e.g.
`tests/test_construct_extraction.py`, `tests/test_localization_e2e.py`
(also an E402 module-import-not-at-top).

13 of the 19 are auto-fixable with `ruff check --fix`.

---

## Medium

### 2. Unused locals that look like dropped logic (not just style)

Two of the F841 findings are worth a human look because the *names* imply behavior
that isn't happening:

- **`services/localization_ranker.py:214-215`** extracts `start = slice_entry.get("start_line")`
  and `end = slice_entry.get("end_line")` and then **never uses them** while iterating
  `hazard_map_artifact.rows` to compute a max hazard contribution. This strongly
  suggests a *line-range overlap check was intended* (only count hazard rows that fall
  within `[start, end]`) but the comparison was dropped — so hazard contribution may be
  computed over the whole file rather than the slice.
- **`stages/localization_pack.py:128 & 133`** compute `top_reason_codes` (sorted
  reason-code ranking) and `top_files` (top-3 candidate files) and then **discard
  them**. These look like summary fields that were meant to be emitted into the
  `localization_pack` artifact but never wired into the output dict.

Neither breaks a schema or a test today, but both are behavioral gaps, not cosmetic.
Recommend confirming against the localization spec before deleting the variables.

### 3. `requires-python = ">=3.12"` with no enforced floor

`pyproject.toml` pins `requires-python = ">=3.12"`. On this environment (Python
**3.11.15**) `pip install -e .` fails outright:

```
ERROR: Package 'forge-eval' requires a different Python: 3.11.15 not in '>=3.12'
```

That's correct behavior, but combined with the absence of a verified CI matrix
(**unverified** — see note above) there's nothing guaranteeing contributors actually
run on 3.12. Either document/standardize the 3.12 toolchain or relax the floor if 3.11
is acceptable (the code uses `from __future__ import annotations` and `X | None`
syntax that works under 3.11 anyway).

### 4. No declared test/dev dependencies

`pyproject.toml` declares only runtime deps (`jsonschema`, `PyYAML`). The test suite
imports `pytest` and `jsonschema`, but there is no `[project.optional-dependencies]`
`dev`/`test` group and no `[dependency-groups]`. A fresh checkout can't run the tests
from packaging metadata alone. Add a `test`/`dev` extra (pytest, ruff, and pin
jsonschema for tests).

### 5. Formatting gates fail

- `ruff format --check .` → **76 files would be reformatted** (21 already formatted).
- `cargo fmt --check` (in `rust/forge-evidence`) → fails; 5 files differ
  (`canonical.rs`, `chain.rs`, `main.rs`, `tests/integration_cli.rs`).

The code isn't malformed — it just hasn't been run through the formatters, so any
"format" CI gate is currently red. `ruff format .` + `cargo fmt` resolve all of it.

> Note: `cargo test` **passes** (5 + 5 tests) and `cargo clippy --all-targets`
> is **clean** (exit 0). The Rust side is in good shape apart from formatting.

### 8. No CI configuration at all
There is **no `.github/` directory** (nor any other CI config) in the repo. Despite
the README and `reports/` describing extensive verification, nothing in version
control automatically runs `pytest`, `ruff`, `cargo test`, or `cargo clippy` on a
push/PR. Given findings #1 and #5 are currently red, adding even a minimal CI workflow
(lint + format + py tests + cargo test/clippy) would stop further drift.

### 9. `pytest` aborts during collection (19 errors)
In a clean checkout on this environment (Python 3.11.15, package not installed),
`PYTHONPATH=src pytest` does not run — it stops with **"Interrupted: 19 errors during
collection"** across most stage test modules. I could not capture the underlying
tracebacks this session, but the probable causes are exactly the packaging gaps in
#3/#4/#7: the `>=3.12` requirement, undeclared test deps, and/or the undeclared
`forge_lineage_sdk` import being pulled in at collection time. Net effect: the suite is
not runnable from packaging metadata + a stock interpreter, which compounds #8. Confirm
by running on Python 3.12 with the test deps installed and capture the real errors.

---

## Low / Info

### 6. Broad `except Exception` in a fail-closed system
A few sites swallow broad exceptions: `services/risk_analysis.py:124`
(`except Exception:`), `lineage/emitter.py:105` (`# noqa: BLE001`),
`contracts/evaluation_spine.py:127,145`, `reviewers/adapters.py:39`. For a system
whose stated invariant is "fail-closed," catch-all handlers deserve scrutiny — confirm
each re-raises a structured `ForgeEvalError` or is deliberately best-effort
(e.g. optional lineage emission), and narrow the exception types where possible.

### 7. Optional external dependency not declared
`lineage/emitter.py` imports `forge_lineage_sdk` (with `# noqa: E402`), which is not in
`pyproject.toml`. If lineage emission is optional, the import should be guarded and the
dependency declared as an extra; otherwise it's an undeclared hard dependency that will
ImportError outside the dev workspace.

### 10. No linter/formatter config in `pyproject.toml`
There's no `[tool.ruff]` (rule selection, line length, per-file-ignores for tests) or
`[tool.mypy]` section. Lint results therefore depend on ruff's defaults and whatever
version a contributor has. Pin tool config so the gate is reproducible — and consider
`per-file-ignores` so test files don't trip F401 on intentional imports.

### 11. Minor inefficiency
`services/slice_extractor.py:247` computes `len(sorted(set(included_targets)))` — the
`sorted()` is wasted work since only the count is used; `len(set(included_targets))` is
equivalent. (No behavioral effect; noted for completeness.)

---

## What's good
- **Determinism discipline:** canonical JSON writer sorts object keys
  (`rust/.../canonical.rs`), Python `stable_json_dumps` uses `sort_keys=True` +
  compact separators, directory walks are explicitly `sort()`ed, config normalization
  sorts/normalizes lists and reviewer ordering. Repeated-run byte-stability is
  plausible by construction.
- **Fail-closed structure:** `stage_runner` validates every stage's artifact `kind`
  against the expected kind *and* against its JSON schema before writing; missing
  prerequisite artifacts raise `StageError`.
- **Strong config validation:** `config.py` rejects unknown keys, enforces numeric
  ranges, normalizes weights to a unit sum, and validates stage-dependency ordering.
- **Rust crate:** clean clippy, passing tests, idempotent canonicalization with an
  explicit non-finite-float guard.
- **Statistical core verified clean:** an independent deep pass over Chao1/Chao2/ICE,
  capture/occupancy/hazard math, and `finding_normalizer` found correct bias-corrected
  formulas, complete division-by-zero / NaN / inf guards, consistent `round_digits`
  bounds, and stable (sorted) ordering everywhere output order matters.

## Recommended order
1. `ruff check --fix .` then hand-fix the remaining F841s — but for the four in
   `localization_ranker.py` / `localization_pack.py`, decide whether the *logic*
   should be completed rather than the variables deleted (#2).
2. `ruff format .` and `cargo fmt` (#5).
3. Add a `dev`/`test` dependency extra and `[tool.ruff]` config; reconcile the
   Python-version floor (#3, #4, #8).
4. Declare/guard `forge_lineage_sdk` and tighten broad excepts (#6, #7).
5. Get `pytest` green on 3.12, then add a CI workflow that runs lint + format + py
   tests + `cargo test`/`clippy` so the gates can't silently regress (#8, #9).

---

## Resolution log (2026-05-31)

Applied on branch `claude/repo-audit-eg7AI`:

- **#1 lint** — `ruff check .` now passes (0 errors). 13 unused imports auto-fixed; 4
  unused locals removed by hand (see #2).
- **#2 unused locals** — investigated, not droppable "logic": hazard rows carry no line
  field, so `_hazard_for_slice` correctly maxes over the whole file (removed the dead
  `start`/`end`, added a clarifying comment); the `localization_pack` summary schema is
  `additionalProperties: false`, so `top_reason_codes`/`top_files` could not be emitted
  (removed). `detect_framework`'s `lang` was genuinely unused (removed).
- **#5 format** — `ruff format .` (76 files) and `cargo fmt` (5 files) applied; both
  `--check` gates now pass.
- **#9 tests — corrected** — the "19 collection errors" was a Python-3.11/uninstalled
  artifact. On **Python 3.12 with the package installed, 166 tests pass, 0 fail.** Only
  **3** modules fail to collect, all from genuinely-absent sibling repos:
  `tests/lineage/test_forge_eval_emitter.py` (`fastapi`),
  `tests/test_centipede_integration.py` (`forge_contract_core`), and
  `tests/test_localization_e2e.py` (hardcoded `/home/NeuroForge/...` path). The 10
  integration "failures" seen earlier were an environment artifact (container-global
  commit-signing failing inside the tests' temp repos), not code defects.
- **#11 efficiency** — left as-is (cosmetic); `cargo test`/`clippy` remain clean.

Still open (not changed this pass): #3/#4 packaging (python floor, test/dev deps),
#6 broad excepts, #7 undeclared `forge_lineage_sdk`, #8 no CI, #10 no tool config.

## Resolution log (2026-06-01) — open findings

Applied on branch `claude/repo-audit-eg7AI`:

- **#3 python floor** — `requires-python = ">=3.12"` was already correct; the gap
  was enforcement, now closed by CI (#8) running the suite on 3.12.
- **#4 test/dev deps** — added `[project.optional-dependencies] dev` (`pytest`,
  `ruff`); CI installs `.[dev]`.
- **#6 broad except — partial** — `risk_analysis` now catches the specific
  `GitError` from `file_content_at_ref` (it was a genuinely over-broad catch). The
  other three sites are **intentional fail-closed/isolation boundaries** and were
  left broad pending an explicit decision: `evaluation_spine` (lazily imports
  `forge_contract_core`, must not couple to its exception hierarchy),
  `reviewers/adapters` (plugin-isolation, routes any reviewer failure through the
  `failure_mode` policy), and `lineage/emitter` (the "never raises / non-blocking"
  doctrine requires catching everything). Narrowing those would break documented
  guarantees.
- **#7 forge_lineage_sdk** — added a `lineage` optional-dependency group and
  guarded the SDK import in `lineage/emitter.py`, so the module (and the package)
  imports without the SDK and fails closed via `_require_sdk()` with actionable
  guidance only when emission is actually exercised. The lineage *integration*
  test still requires `fastapi` + the SDK and remains correctly skipped on a bare
  checkout.
- **#8 CI** — added `.github/workflows/ci.yml`: a Python job (install `.[dev]`,
  `ruff check`, `ruff format --check`, `pytest` minus the 3 sibling-repo
  integration tests) and a Rust job (`cargo fmt --check`, `clippy -D warnings`,
  `cargo test`).
- **#10 tool config** — added `[tool.ruff]` (pinned `target-version = "py312"`,
  `line-length = 88`, explicit `select = ["E","F","W","I"]`, `ignore = ["E501"]`
  since `ruff format` owns line length). Enabling import-sort (`I`) reordered
  imports in 26 files.

Still open: #6 sites 2–4 (the three intentional boundaries above — awaiting a
decision on whether to force-narrow), #11 (cosmetic, left as-is).
