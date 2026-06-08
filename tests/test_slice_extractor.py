from __future__ import annotations

import pytest

from forge_eval.errors import StageError
from forge_eval.services.slice_extractor import parse_unified_diff_hunks


def test_parse_single_hunk() -> None:
    diff = """diff --git a/a.py b/a.py
@@ -5,1 +5,3 @@
+line1
+line2
+line3
"""
    hunks = parse_unified_diff_hunks(diff)
    assert [(h.start_line, h.end_line, h.changed_line_count) for h in hunks] == [
        (5, 7, 3)
    ]


def test_parse_multi_hunk() -> None:
    diff = """diff --git a/a.py b/a.py
@@ -1,1 +1,1 @@
+x
@@ -10,2 +12,2 @@
+y
+z
"""
    hunks = parse_unified_diff_hunks(diff)
    assert [(h.start_line, h.end_line, h.changed_line_count) for h in hunks] == [
        (1, 1, 1),
        (12, 13, 2),
    ]


def test_parse_deletion_hunk_maps_to_insertion_point() -> None:
    diff = """diff --git a/a.py b/a.py
@@ -8,3 +8,0 @@
-old
"""
    hunks = parse_unified_diff_hunks(diff)
    assert [(h.start_line, h.end_line, h.changed_line_count) for h in hunks] == [
        (8, 8, 0)
    ]


def test_parse_invalid_hunk_fails_closed() -> None:
    diff = """diff --git a/a.py b/a.py
@@ not-a-valid-hunk @@
+line
"""
    with pytest.raises(StageError):
        parse_unified_diff_hunks(diff)
