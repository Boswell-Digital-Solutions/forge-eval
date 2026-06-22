# §8 - Pack F: Context Slices Stage

## Stage Contract

Input:

- repo path
- base ref
- head ref
- normalized config
- optional target subset (wired from risk stage targets)

Output:

- `context_slices.json` (schema kind: `context_slices`)

## Deterministic Extraction Procedure

For each changed target file (non-deleted, extension-allowed, non-excluded):

1. Parse unified diff hunks (`--unified=0`) into changed ranges in head-line coordinates.
2. Expand each range by `context_radius_lines`.
3. Clamp expanded ranges to `[1, file_line_count]`.
4. Merge overlap/adjacency using `merge_gap_lines` (left-to-right after sort).
5. Split oversized merged ranges by `max_lines_per_slice`.
6. Build stable slice objects (`slice_id = file_path:start:end`) from head file content.
7. Sort slices by `(file_path, start_line, end_line)`.
8. Enforce `max_total_lines` globally.

## Cap and Failure Policy

- If binary file is changed and `binary_file_policy=fail`, stage fails closed.
- If `max_slices_per_target` is exceeded and `fail_on_slice_truncation=true`, stage fails closed.
- If `max_total_lines` is exceeded, stage fails closed.
- No silent line dropping.

## v1 Decisions Locked in Code

- Head-version content is the extraction source.
- Deleted files are excluded.
- Rename handling follows post-rename path from git diff parsing.
- Provenance marks source as `git_diff_head_version`.
