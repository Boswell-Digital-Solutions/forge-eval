from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from forge_eval.centipede_runner import run_centipede_pipeline
from forge_eval.config import load_config
from forge_eval.errors import ForgeEvalError
from forge_eval.stage_runner import (
    run_pipeline,
    stable_json_dumps,
    validate_artifacts_directory,
)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="forge-eval", description="Deterministic Forge eval loop"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    run_parser = subparsers.add_parser("run", help="run enabled stages")
    run_parser.add_argument("--repo", required=True, help="repository path")
    run_parser.add_argument("--base", required=True, help="base git ref")
    run_parser.add_argument("--head", required=True, help="head git ref")
    run_parser.add_argument(
        "--config", required=False, help="config path (.json/.yaml/.yml)"
    )
    run_parser.add_argument("--out", required=True, help="output artifacts directory")

    centipede_parser = subparsers.add_parser(
        "run-centipede",
        help="run the Phase 01 Centipede adapter boundary and emit forge_eval_evidence_bundle.json",
    )
    centipede_parser.add_argument(
        "--input",
        required=True,
        help="ForgeEvalCentipedeInput.v1 JSON input contract path",
    )
    centipede_parser.add_argument(
        "--config", required=False, help="config path (.json/.yaml/.yml)"
    )
    centipede_parser.add_argument(
        "--out", required=True, help="output artifacts directory"
    )

    validate_parser = subparsers.add_parser("validate", help="validate artifacts")
    validate_parser.add_argument(
        "--artifacts", required=True, help="artifacts directory"
    )

    return parser


def _print_json(data: dict[str, object]) -> None:
    sys.stdout.write(stable_json_dumps(data))


def _print_error(err: ForgeEvalError) -> None:
    payload = {
        "status": "error",
        "error": err.to_dict(),
    }
    sys.stderr.write(
        json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
        + "\n"
    )


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    try:
        if args.command == "run":
            config = load_config(args.config)
            result = run_pipeline(
                repo_path=Path(args.repo).resolve(),
                base_ref=args.base,
                head_ref=args.head,
                out_dir=Path(args.out).resolve(),
                config=config,
            )
            _print_json({"status": "ok", "result": result})
            return 0

        if args.command == "run-centipede":
            config = load_config(args.config)
            result = run_centipede_pipeline(
                input_path=Path(args.input).resolve(),
                out_dir=Path(args.out).resolve(),
                config=config,
            )
            _print_json({"status": "ok", "result": result})
            return 0

        if args.command == "validate":
            result = validate_artifacts_directory(
                artifacts_dir=Path(args.artifacts).resolve()
            )
            _print_json({"status": "ok", "result": result})
            return 0

        parser.error(f"unknown command: {args.command}")
        return 2

    except ForgeEvalError as err:
        _print_error(err)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
