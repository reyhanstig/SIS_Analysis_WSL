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

2. **Read the Notebook**
   - Use `view_file` to read the full contents of the notebook `.ipynb` file.
   - Parse the JSON structure mentally. The key structure is:
     ```json
     {
       "cells": [
         {
           "cell_type": "markdown" | "code",
           "source": ["line1\n", "line2\n", ...]
         },
         ...
       ]
     }
     ```
   - Identify each cell's `cell_type` and `source` content.

3. **Build the Python Script Content**
   - Iterate through the `cells` array **in order**. For each cell:
     
     **If `cell_type` is `"markdown"`:**
     - Convert each line in the `source` array into a Python comment line.
     - Prefix each line with `# `.
     - Handle multi-line markdown: each line of the source becomes its own `# ` comment line.
     - Preserve blank lines within markdown cells by outputting `#` (a comment with no text).
     - Add one blank line after the comment block for readability.
     
     **If `cell_type` is `"code"`:**
     - Write the `source` lines directly as Python code.
     - Strip any trailing `\n` from each source line (they are already line-terminated in the notebook JSON).
     - Add two blank lines after each code cell for PEP 8-style separation.
     
     **If `cell_type` is `"raw"` or any other type:**
     - Treat like markdown (convert to comments), but prefix with `# [raw] ` to distinguish.

4. **Determine the Output File Path**
   - Default: Replace the `.ipynb` extension with `.py` in the same directory.
     - Example: `notebooks/22_seasonal_variation.ipynb` → `notebooks/22_seasonal_variation.py`
   - If the user specifies a different output path, use that instead.
   - If a script output directory exists (e.g., `scripts/`), ask the user if they prefer to place the output there.

5. **Write the Python Script**
   - Use `write_to_file` to create the `.py` file with the assembled content.
   - Set `Overwrite` to `true` if the output file already exists and the user confirms.
   - Add a header comment at the top of the script:
     ```python
     # -*- coding: utf-8 -*-
     # Auto-generated from: <notebook_filename>.ipynb
     # Generated on: <current date/time>
     # This script was converted from a Jupyter Notebook.
     # Markdown cells have been converted to comments.
     ```

6. **Verify the Output**
   - Use `view_file` to quickly review the first ~50 lines of the generated `.py` file.
   - Confirm successful creation to the user.
   - Optionally, offer to run the script using the `/test_and_run_python` workflow to validate it executes correctly.

## Notes
- The conversion is a **structural** transformation only. It does not execute or validate the notebook code.
- Notebook outputs (execution results, images, etc.) are **not** included in the script.
- If the notebook uses IPython magic commands (e.g., `%matplotlib inline`), these will be included as-is. The user may need to adjust or remove them for plain Python execution.
- Cell metadata (execution counts, tags, etc.) is **not** preserved in the output script.
