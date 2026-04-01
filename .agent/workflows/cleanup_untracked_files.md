---
description: Identify and cleanup untracked, unimportant residual files or scripts.
---

# Cleanup Untracked Files

This workflow helps identify untracked files in the repository that are likely residual artifacts (one-off tests, temporary scripts, outdated reports) and prepares them for deletion.

## Steps

1. **List Untracked Files**
   - Run `git status --porcelain=v1` to get a list of all untracked files/directories (prefixed with `??`).
   - If there are no untracked files, report: "Workspace is clean. No untracked files found." and stop.

2. **Categorize Files**
   - Scan the list of untracked files and categorize them based on the following rules:
     - **Residual (Safe to Delete)**:
       - `test_*.py` (unless explicitly requested as part of the test suite)
       - `tmp_*`, `temp_*`
       - Files in the root directory that aren't configuration files (e.g., ad-hoc scripts like `check_*.py`, `test_*.csv`)
       - `__pycache__` directories
       - Outdated reports (e.g., `reports/workspace_report_*.md`)
       - Logs or executables (e.g., `*.log`, `*.exe`)
     - **Potential Work-in-Progress (Keep/Review)**:
       - `.ipynb` files with sequence numbers (e.g., `35_*.ipynb`, `36_*.ipynb`)
       - Files in `notebooks/pipeline/`
       - Significant changes to `requirements.txt` or `environment.yml`
       - New scripts in `scripts/`

3. **Present Proposal to User**
   - Output a table or list showing:
     - **Files to Delete**: [File Path] - [Reason]
     - **Files to Keep/Review**: [File Path] - [Reason]
   - Ask the user: "Would you like me to delete the files in the 'Delete' category?"

4. **Execute Deletion**
   - **Only after explicit user approval**, run `rm` (on Linux) or `del` (on Windows) for each confirmed file.
   - For directories, use `rm -rf`.
   - Use `// turbo` for this step if the command is straightforward.

5. **Verify and Finalize**
   - Run `git status --short` again to verify the files are gone.
   - Report the final status to the user.
