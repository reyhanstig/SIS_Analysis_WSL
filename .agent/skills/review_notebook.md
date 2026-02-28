---
description: Review a Jupyter notebook for pipeline compatibility and code quality.
---

# Review Notebook Skill

This skill guides you through reviewing a Jupyter notebook to ensure it is ready for integration into the automated DVC pipeline.

## Checklist

1.  **Hardcoded Paths**:
    -   Scan for any absolute or relative file paths (e.g., `../data/`, `/mnt/c/Users/...`).
    -   Verify that ALL file I/O uses `scripts.paths.ProjectPaths`.

2.  **Imports & Dependencies**:
    -   Ensure `sys.path.append` logic handles project root correctly for local imports.
    -   Verify `ProjectPaths` is imported.
    -   Check for unused imports.

3.  **Parameters**:
    -   Identify "magic numbers" or configuration variables (e.g., thresholds, colors, year ranges).
    -   Ensure these are concentrated in a dedicated cell (ideally tagged `parameters`).

4.  **Execution Order**:
    -   The notebook must run sequentially from top to bottom.
    -   Check for cells that depend on manual variable edits or out-of-order execution.

5.  **Outputs**:
    -   Ensure outputs are saved to `ProjectPaths.PROCESSED_DATA_DIR` or `ProjectPaths.FIGURES_DIR`.
    -   Verify filenames are consistent with `dvc.yaml` expectations.

6.  **Code Quality**:
    -   Check for duplicated logic.
    -   Ensure variable names are descriptive.
    -   Verify comments explain *why*, not just *what*.

## Output Format

When invoking this skill, provide a report with the following structure:

### Review Report: [Notebook Name]

**Status**: [Ready / Needs Improvements]

**Issues Found**:
-   [Critical] Hardcoded path found in cell 5.
-   [Major] Parameter `threshold` is hardcoded in loop, should be extracted.
-   [Minor] Unused import `numpy`.

**Recommendations**:
1.  Replace path string with `ProjectPaths.RAW_DATA_DIR`.
2.  Create a `parameters` cell and move `threshold` there.
3.  Remove unused imports.
