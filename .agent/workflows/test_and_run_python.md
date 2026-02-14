---
description: Test and run Python scripts and Jupyter Notebook chunks in the geo_env virtual environment
---

# Test and Run Python Code

This workflow allows the agent to execute python code (scripts or notebook cells) using the user's specific `geo_env` conda environment.

## Prerequisites
- The `geo_env` python interpreter path must be configured.
- Code must run within the `SIS_Analysis` project context.

## Steps

1. **Resolve Python Interpreter**
   - Check if the file `.agent/python_env_path` exists using `find_by_name` or `list_dir`.
   - **If the file exists**:
     - Use `view_file` to read the path inside it. This is your `<PYTHON_PATH>`.
   - **If the file does NOT exist**:
     - You cannot proceed without the correct environment.
     - **Ask the user**: "I need to configure the `geo_env` python path to run scripts correctly. Please provide the absolute path to the `python.exe` in your `geo_env` (e.g., `C:\Users\reyha\anaconda3\envs\geo_env\python.exe` or `C:\Users\reyha\.conda\envs\geo_env\python.exe`)."
     - Stop and wait for the user's response.
     - **Once provided**:
       - Verify the path by running `run_command`: `"<PROVIDED_PATH>" --version`. (Expected: Python 3.11.14).
       - If valid, save this path to `.agent/python_env_path` using `write_to_file`.

2. **Prepare Code for Execution**
   - **If running an Existing Script**:
     - Identify the absolute path of the script: `<SCRIPT_PATH>`.
   - **If running a Notebook Chunk / New Snippet**:
     - You must create a standalone temporary script.
     - **Context & Dependencies**:
       - Does the code rely on imports? (e.g., `scripts.data_loader`) -> Add `sys.path` setup.
       - Does the code rely on variables? (e.g., `merged_gdf`, `dist_matrix_km`) -> You **MUST** add code to load these variables at the top of the script. Refer to `scripts/data_loader.py` or previous notebook cells for loading logic.
     - **Create the File**:
       - Path: `c:\Users\reyha\Documents\SIS_Analysis\.agent\tmp\test_runner.py`
       - **Header Content**:
         ```python
         import sys
         import os
         from pathlib import Path
         # Ensure project root is in sys.path
         project_root = Path(r"c:\Users\reyha\Documents\SIS_Analysis")
         if str(project_root) not in sys.path:
             sys.path.append(str(project_root))
         # Add imports here
         ```
       - **Body Content**: The loaded variables + the snippet to test.
       - Use `write_to_file` to create/overwrite this file.
     - Set `<SCRIPT_PATH>` to `c:\Users\reyha\Documents\SIS_Analysis\.agent\tmp\test_runner.py`.

3. **Execute the Code**
   - Construct the command line: `"<PYTHON_PATH>" "<SCRIPT_PATH>"`
   // turbo
   - Use `run_command` to execute it.
     - `Cwd`: `c:\Users\reyha\Documents\SIS_Analysis` (Project Root).

4. **Analyze Results**
   - Read the output.
   - If **Success**: Report results to the user.
   - If **Failure**:
     - Analyze the traceback.
     - If `ModuleNotFoundError`: Check `sys.path` appending in Step 2.
     - If `NameError`: You missed loading a dependency or variable in Step 2.
     - Fix the `test_runner.py` and retry if possible, or explain the error to the user.

5. **Cleanup**
   - If successful, you may delete `.agent/tmp/test_runner.py` using `run_command` (`del` or `rm`).
