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
   - For small notebooks (< 1MB), use `view_file` to read the contents and parse the JSON.
   - **CRITICAL for Large Notebooks (> 1MB):** If the notebook contains large embedded outputs (base64 images, long logs), manual parsing is error-prone. Use a programmatic approach instead:
     - Use `run_command` with a `python3 -c` script to parse the JSON and write the output directly. This ensures no cells are missed due to truncation.
     - Example robust parser:
       ```bash
       python3 -c "
       import json, sys
       from datetime import datetime
       nb = json.load(open('path/to/notebook.ipynb'))
       print('# -*- coding: utf-8 -*-')
       print(f'# Auto-generated from: {notebook_path}')
       # ... header logic ...
       for cell in nb['cells']:
           if cell['cell_type'] == 'markdown':
               print(''.join([f'# {l}' if l.strip() else '#' for l in cell['source']]) + '\n')
           elif cell['cell_type'] == 'code':
               print(''.join(cell['source']) + '\n\n')
       " > path/to/output.py
       ```

3. **Build the Python Script Content**
   - Whether building manually or via script, ensure the following logic:
     - **Markdown:** Prefix lines with `# `. Preserve blank lines as `#`. Add 1 blank line after the block.
     - **Code:** Write raw code. Add 2 blank lines after each code cell (PEP 8).
     - **Metadata:** Add a standard header with the source filename and conversion timestamp.

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
