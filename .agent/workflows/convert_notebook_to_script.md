---
description: Convert a Jupyter Notebook (.ipynb) to a standalone Python script (.py), preserving cell order with markdown cells as comments.
---
# Convert Jupyter Notebook to Python Script

This workflow converts a selected `.ipynb` notebook file into a `.py` Python script. The overall order of the notebook is preserved: markdown cells become comment blocks, and code cells are written out in order.

## Prerequisites
- The target notebook must be a valid `.ipynb` file in JSON format.
- The output `.py` file will be placed in the same directory as the source notebook, unless the user specifies otherwise.

## Steps

1. **Identify the Target Notebook**
   - The user should provide the path to the `.ipynb` file to convert, or the agent should identify it from context (e.g., the active document).
   - Confirm the notebook path with the user if ambiguous.

2. **Read and Parse the Notebook**
   - Instead of manually parsing the complex JSON structure of `.ipynb` files, always use the dedicated utility script to extract the code safely and robustly. This avoids token limit issues and handles Jupyter cell types, metadata, and magic commands natively using `nbconvert`.
   - Use the `agent_notebook_utils.convert_notebook_to_script` function to read and convert the notebook in one step.
   - Example command to run via `run_command`:
     ```bash
     conda run -n sis_analysis python -c "from scripts.agent_notebook_utils import convert_notebook_to_script; convert_notebook_to_script('path/to/notebook.ipynb', 'path/to/output.py')"
     ```

3. **Build the Python Script Content**
   - The utility script handles formatting automatically, preserving markdown cells as comments and formatting code cells properly.

4. **Determine the Output File Path**
   - Default: Replace the `.ipynb` extension with `.py` in the same directory.
   - Check if a `scripts/` directory exists and offer it as an alternative if appropriate.

5. **Write and Verify the Script**
   - If using the programmatic approach, the file is written during the `run_command`.
   - If building manually, use `write_to_file`.
   - **Verification:** Always use `view_file` to check the first ~100 lines and the *last* few lines (e.g., via `tail`) to confirm the file is complete and not truncated.

## Notes
- **Large Files:** Embedded images/outputs in `.ipynb` files can make them extremely large (10MB+). Programmatic parsing is the only reliable way to handle these.
- **Magic Commands:** Preserve `%matplotlib inline` etc., but warn the user they might need adjustment for CLI execution.
- **Dependencies:** Ensure the script includes the project's root in `sys.path` if the notebook relies on local modules (e.g., `scripts.*`).
