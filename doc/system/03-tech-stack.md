# §3 - Tech Stack

## Python

- Python `>=3.12`
- `jsonschema` (Draft 2020-12 validation)
- `PyYAML` (config loading)
- stdlib for subprocess, JSON, path, hashing, regex, argparse

## Rust (`forge-evidence`)

- stable Rust toolchain
- `serde`, `serde_json`
- `sha2`, `hex`
- `clap`
- `anyhow`

## Git Interface

Git is invoked through subprocess with explicit commands:

- `git rev-parse`
- `git diff --name-status --find-renames`
- `git diff --numstat`
- `git diff --no-color --unified=0`
- `git show <ref:path>`
- `git ls-files`

## Build and Test Tooling

- `cargo build --offline`, `cargo test --offline`
- `pytest` for Python unit/integration coverage
