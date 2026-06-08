from __future__ import annotations

import math
import re
from pathlib import PurePosixPath
from typing import Any, Iterable

from forge_eval.services.git_diff import (
    file_content_at_ref,
    path_has_allowed_extension,
    path_is_excluded,
)

PY_IMPORT_RE = re.compile(
    r"^\s*(?:from\s+([a-zA-Z_][\w\.]*)\s+import\s+|import\s+([a-zA-Z_][\w\.]*))"
)
TS_IMPORT_RE = re.compile(r"^\s*import\s+.+?from\s+['\"]([^'\"]+)['\"]")
TS_IMPORT_SIDE_EFFECT_RE = re.compile(r"^\s*import\s+['\"]([^'\"]+)['\"]")
JS_REQUIRE_RE = re.compile(r"require\(['\"]([^'\"]+)['\"]\)")
RS_USE_RE = re.compile(r"^\s*use\s+crate::([a-zA-Z0-9_:]+)")


def _normalize_path(path: str) -> str:
    return path.replace("\\", "/")


def _normalize_scores(values: dict[str, float]) -> dict[str, float]:
    if not values:
        return {}
    low = min(values.values())
    high = max(values.values())
    if math.isclose(low, high):
        if math.isclose(high, 0.0):
            return {key: 0.0 for key in values}
        return {key: 1.0 for key in values}
    return {key: (values[key] - low) / (high - low) for key in values}


def _longest_prefix_weight(path: str, weights: dict[str, float]) -> float:
    normalized = _normalize_path(path)
    best_prefix = ""
    best_value = 1.0
    for prefix in sorted(weights.keys()):
        normalized_prefix = _normalize_path(prefix)
        if normalized.startswith(normalized_prefix) and len(normalized_prefix) >= len(best_prefix):
            best_prefix = normalized_prefix
            best_value = float(weights[prefix])
    return best_value


def _python_module_names(path: str) -> list[str]:
    p = PurePosixPath(path)
    if p.suffix != ".py":
        return []
    parts = list(p.parts)
    if parts[-1] == "__init__.py":
        module = ".".join(parts[:-1])
        return [module] if module else []
    module = ".".join(parts)
    return [module[:-3]]


def _rust_module_name(path: str) -> str | None:
    p = PurePosixPath(path)
    if p.suffix != ".rs":
        return None
    if p.name == "mod.rs":
        return "::".join(p.parts[:-1])
    return "::".join(list(p.parts))[:-3]


def _resolve_relative_import(source: str, spec: str, candidates: set[str]) -> str | None:
    if not spec.startswith("./") and not spec.startswith("../"):
        return None

    source_dir = PurePosixPath(source).parent
    base = source_dir.joinpath(spec)
    checks = []
    if base.suffix:
        checks.append(base)
    else:
        for ext in [".ts", ".tsx", ".js", ".jsx", ".py", ".rs"]:
            checks.append(PurePosixPath(str(base) + ext))
        for ext in [".ts", ".tsx", ".js", ".jsx"]:
            checks.append(base / f"index{ext}")

    for cand in checks:
        normalized = _normalize_path(str(cand))
        if normalized in candidates:
            return normalized
    return None


def compute_centrality_scores(
    *,
    repo_path: str,
    head_ref: str,
    tracked_files: Iterable[str],
    include_extensions: list[str],
    exclude_paths: list[str],
) -> dict[str, float]:
    candidate_files = [
        _normalize_path(path)
        for path in tracked_files
        if path_has_allowed_extension(path, include_extensions) and not path_is_excluded(path, exclude_paths)
    ]
    candidate_files = sorted(set(candidate_files))
    candidate_set = set(candidate_files)

    py_module_to_path: dict[str, str] = {}
    rust_module_to_path: dict[str, str] = {}

    for path in candidate_files:
        for module in _python_module_names(path):
            py_module_to_path[module] = path
        rust_module = _rust_module_name(path)
        if rust_module:
            rust_module_to_path[rust_module] = path

    edges: set[tuple[str, str]] = set()
    for source in candidate_files:
        try:
            content = file_content_at_ref(repo_path, head_ref, source)
        except Exception:
            # Missing files at head are ignored here; stage logic handles changed targets separately.
            continue

        for line in content.splitlines():
            py_match = PY_IMPORT_RE.match(line)
            if py_match and source.endswith(".py"):
                module = py_match.group(1) or py_match.group(2)
                target = py_module_to_path.get(module)
                if target and target != source:
                    edges.add((source, target))
                continue

            if source.endswith((".ts", ".tsx", ".js", ".jsx")):
                ts_match = TS_IMPORT_RE.match(line) or TS_IMPORT_SIDE_EFFECT_RE.match(line)
                if ts_match:
                    target = _resolve_relative_import(source, ts_match.group(1), candidate_set)
                    if target and target != source:
                        edges.add((source, target))
                    continue
                for req in JS_REQUIRE_RE.findall(line):
                    target = _resolve_relative_import(source, req, candidate_set)
                    if target and target != source:
                        edges.add((source, target))

            if source.endswith(".rs"):
                rs_match = RS_USE_RE.match(line)
                if rs_match:
                    module = rs_match.group(1)
                    target = rust_module_to_path.get(module)
                    if target and target != source:
                        edges.add((source, target))

    out_degree = {path: 0.0 for path in candidate_files}
    in_degree = {path: 0.0 for path in candidate_files}
    for source, target in sorted(edges):
        out_degree[source] += 1.0
        in_degree[target] += 1.0

    centrality_raw = {path: out_degree[path] + in_degree[path] for path in candidate_files}
    return _normalize_scores(centrality_raw)


def build_risk_targets(
    *,
    changed_paths: list[str],
    churn_by_path: dict[str, tuple[int, int]],
    centrality_scores: dict[str, float],
    risk_weights: dict[str, float],
    path_weights: dict[str, float],
) -> list[dict[str, Any]]:
    changed_paths = sorted({_normalize_path(path) for path in changed_paths})

    churn_raw: dict[str, float] = {}
    magnitude_raw: dict[str, float] = {}
    for path in changed_paths:
        added, deleted = churn_by_path.get(path, (0, 0))
        churn_total = float(max(0, added) + max(0, deleted))
        churn_raw[path] = churn_total
        magnitude_raw[path] = math.log1p(churn_total)

    churn_norm = _normalize_scores(churn_raw)
    magnitude_norm = _normalize_scores(magnitude_raw)

    raw_scores: dict[str, float] = {}
    for path in changed_paths:
        w_path = _longest_prefix_weight(path, path_weights)
        raw = (
            risk_weights["w_churn"] * churn_norm.get(path, 0.0)
            + risk_weights["w_centrality"] * centrality_scores.get(path, 0.0)
            + risk_weights["w_change_magnitude"] * magnitude_norm.get(path, 0.0)
        )
        raw_scores[path] = raw * w_path

    norm_scores = _normalize_scores(raw_scores)

    targets: list[dict[str, object]] = []
    for path in changed_paths:
        added, deleted = churn_by_path.get(path, (0, 0))
        reasons = [
            {"metric": "churn", "value": round(churn_norm.get(path, 0.0), 8)},
            {"metric": "centrality", "value": round(centrality_scores.get(path, 0.0), 8)},
            {"metric": "change_magnitude", "value": round(magnitude_norm.get(path, 0.0), 8)},
            {"metric": "path_weight", "value": round(_longest_prefix_weight(path, path_weights), 8)},
        ]

        targets.append(
            {
                "target_id": path,
                "file_path": path,
                "churn": {
                    "added_lines": int(added),
                    "deleted_lines": int(deleted),
                    "normalized": round(churn_norm.get(path, 0.0), 8),
                },
                "centrality": round(centrality_scores.get(path, 0.0), 8),
                "change_magnitude": round(magnitude_norm.get(path, 0.0), 8),
                "risk_raw": round(raw_scores.get(path, 0.0), 8),
                "risk_score": round(norm_scores.get(path, 0.0), 8),
                "reasons": reasons,
            }
        )

    targets.sort(key=lambda t: str(t["file_path"]))
    return targets
