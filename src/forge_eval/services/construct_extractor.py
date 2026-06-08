from __future__ import annotations

import os
import re
from typing import Any

LANGUAGE_MAP: dict[str, str] = {
    ".py": "python",
    ".rs": "rust",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".svelte": "svelte",
}

FRAMEWORK_HINTS: dict[str, list[str]] = {
    "fastapi": ["from fastapi", "APIRouter", "@app."],
    "tauri": ["use tauri::", "#[tauri::command]"],
    "svelte_kit": ["load(", "PageLoad", "LayoutLoad"],
}

CONSTRUCT_PATTERNS: dict[str, dict[str, list[str]]] = {
    "python": {
        "if_guard": [r"\bif\b", r"\belif\b"],
        "async_call": [r"\bawait\b"],
        "try_except": [r"\btry\b", r"\bexcept\b"],
        "return_boundary": [r"\breturn\b"],
        "serialization_boundary": [r"\.model_dump\(", r"\.dict\(", r"json\."],
        "dependency_call": [r"Depends\("],
    },
    "rust": {
        "if_guard": [r"\bif\b", r"\bif let\b"],
        "match_arm": [r"\bmatch\b"],
        "borrow_boundary": [r"&mut\b", r"\.borrow\(", r"\.borrow_mut\("],
        "async_task_boundary": [r"\.await\b", r"tokio::spawn"],
        "trait_dispatch": [r"\.into\(\)", r"\.as_ref\(", r"dyn "],
        "error_propagation": [r"\?\s*;", r"unwrap\(\)", r"expect\("],
    },
    "typescript": {
        "if_guard": [r"\bif\b"],
        "async_call": [r"\bawait\b"],
        "null_check": [r"\?\.", r"!\."],
        "type_assertion": [r" as \w"],
        "promise_chain": [r"\.then\(", r"\.catch\("],
    },
    "svelte": {
        "if_guard": [r"\{#if\b"],
        "reactive_state": [r"\$state\("],
        "derived_state": [r"\$derived\("],
        "effect_boundary": [r"\$effect\("],
        "prop_mutation": [r"bind:"],
        "async_ui_transition": [r"\{#await\b"],
    },
}

ROOT_CAUSE_HYPOTHESIS_ENUM = (
    "boundary_violation",
    "null_path",
    "async_race",
    "missing_guard",
    "serialization_boundary",
    "ownership_violation",
    "reactive_state_mutation",
    "other",
)


def detect_language(file_path: str) -> str | None:
    ext = os.path.splitext(file_path)[1].lower()
    return LANGUAGE_MAP.get(ext)


def detect_framework(file_path: str, source_hint: str | None = None) -> str | None:
    if source_hint is None:
        return None
    for framework, hints in FRAMEWORK_HINTS.items():
        for hint in hints:
            if hint in source_hint:
                return framework
    return None


def extract_constructs(
    language: str | None, source_lines: list[str] | None = None
) -> list[str]:
    if language is None or language not in CONSTRUCT_PATTERNS:
        return []
    if source_lines is None:
        return []

    patterns = CONSTRUCT_PATTERNS[language]
    found: list[str] = []
    text = "\n".join(source_lines)
    for construct_name, regexes in sorted(patterns.items()):
        for regex in regexes:
            if re.search(regex, text):
                found.append(construct_name)
                break
    return sorted(set(found))


def derive_root_cause_hypothesis(
    *,
    language: str | None,
    constructs: list[str],
    support_count: int = 0,
    hazard_contribution: float = 0.0,
) -> str | None:
    if not constructs:
        return None

    if language == "rust" and any(
        c in constructs for c in ("borrow_boundary", "error_propagation")
    ):
        return "ownership_violation"
    if language == "svelte" and any(
        c in constructs for c in ("reactive_state", "prop_mutation")
    ):
        return "reactive_state_mutation"
    if "serialization_boundary" in constructs:
        return "serialization_boundary"
    if (
        any(c in constructs for c in ("async_call", "async_task_boundary"))
        and support_count > 1
    ):
        return "async_race"
    if any(c in constructs for c in ("null_check", "if_guard")):
        return "null_path"
    if "if_guard" not in constructs and hazard_contribution > 0.5:
        return "missing_guard"
    return "other"


def enrich_block_candidates(
    block_candidates: list[dict[str, Any]],
    *,
    config: dict[str, Any],
) -> list[dict[str, Any]]:
    for bc in block_candidates:
        fp = bc.get("file_path", "")
        lang = detect_language(fp)
        bc["detected_language"] = (
            lang if lang is not None else ("other" if fp else None)
        )

        bc["likely_constructs"] = []
        bc["root_cause_hypothesis"] = derive_root_cause_hypothesis(
            language=lang,
            constructs=bc["likely_constructs"],
            support_count=bc.get("support_count", 0),
            hazard_contribution=0.0,
        )

    return block_candidates
